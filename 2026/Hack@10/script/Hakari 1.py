#!/usr/bin/env python3
import re
import socket
from math import prod

HOST = "34.126.187.50"
PORT = 5500
E = 17


# =========================
# MT19937 untemper helpers
# =========================
def unshift_right_xor(y, shift):
    x = y
    for _ in range(10):
        x = y ^ (x >> shift)
    return x & 0xFFFFFFFF


def unshift_left_xor_mask(y, shift, mask):
    x = y
    for _ in range(10):
        x = y ^ ((x << shift) & mask)
    return x & 0xFFFFFFFF


def untemper(y):
    y = unshift_right_xor(y, 18)
    y = unshift_left_xor_mask(y, 15, 0xEFC60000)
    y = unshift_left_xor_mask(y, 7, 0x9D2C5680)
    y = unshift_right_xor(y, 11)
    return y & 0xFFFFFFFF


class MTPredictor:
    def __init__(self, state):
        if len(state) != 624:
            raise ValueError("MT state must contain exactly 624 integers")
        self.mt = state[:]
        self.index = 624

    def twist(self):
        for i in range(624):
            y = (self.mt[i] & 0x80000000) | (self.mt[(i + 1) % 624] & 0x7FFFFFFF)
            self.mt[i] = self.mt[(i + 397) % 624] ^ (y >> 1)
            if y & 1:
                self.mt[i] ^= 0x9908B0DF
        self.index = 0

    def getrandbits32(self):
        if self.index >= 624:
            self.twist()

        y = self.mt[self.index]
        self.index += 1

        y ^= (y >> 11)
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        y ^= (y >> 18)
        return y & 0xFFFFFFFF


# =========================
# Math helpers
# =========================
def crt(items):
    """
    Chinese Remainder Theorem
    items = [(n1, c1), (n2, c2), ...]
    returns x such that x ≡ c_i (mod n_i)
    """
    N = prod(n for n, _ in items)
    x = 0
    for n, c in items:
        m = N // n
        inv = pow(m, -1, n)
        x = (x + c * m * inv) % N
    return x, N


def integer_nthroot_exact(value, n):
    """
    Returns (root, exact)
    Pure Python exact nth-root, no sympy needed.
    """
    if value < 0:
        raise ValueError("value must be non-negative")
    if value in (0, 1):
        return value, True

    low, high = 0, 1
    while high ** n <= value:
        high <<= 1

    while low + 1 < high:
        mid = (low + high) // 2
        p = mid ** n
        if p == value:
            return mid, True
        if p < value:
            low = mid
        else:
            high = mid

    return low, (low ** n == value)


def long_to_bytes(x):
    if x == 0:
        return b"\x00"
    return x.to_bytes((x.bit_length() + 7) // 8, "big")


def are_pairwise_coprime(moduli):
    for i in range(len(moduli)):
        for j in range(i + 1, len(moduli)):
            if gcd(moduli[i], moduli[j]) != 1:
                return False
    return True


def gcd(a, b):
    while b:
        a, b = b, a % b
    return a


# =========================
# Socket helpers
# =========================
class Remote:
    def __init__(self, host, port, timeout=5.0):
        self.s = socket.create_connection((host, port))
        self.s.settimeout(timeout)
        self.buf = b""

    def recv_until_any(self, tokens):
        """
        Read until any token in `tokens` appears in buffer.
        Returns bytes up to and including the first matched token.
        """
        while True:
            for token in tokens:
                idx = self.buf.find(token)
                if idx != -1:
                    end = idx + len(token)
                    out = self.buf[:end]
                    self.buf = self.buf[end:]
                    return out

            chunk = self.s.recv(4096)
            if not chunk:
                raise EOFError("connection closed")
            self.buf += chunk

    def sendline(self, data):
        if isinstance(data, int):
            data = str(data)
        self.s.sendall(data.encode() + b"\n")

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


# =========================
# Solver
# =========================
def main():
    round_end_tokens = [
        b"Guess the next number: ",
        b"Predict the next number or type 'exit': ",
        b"Connection closed.",
    ]

    r = Remote(HOST, PORT)

    try:
        # Read initial banner
        banner = r.recv_until_any([
            b"Guess the next number: ",
            b"Predict the next number or type 'exit': ",
        ])
        print(banner.decode(errors="ignore"), end="")

        outputs = []

        # Step 1: intentionally lose 624 times to recover MT state
        # Guessing 0 is practically always wrong.
        for i in range(624):
            r.sendline("0")
            text = r.recv_until_any(round_end_tokens).decode(errors="ignore")
            print(text, end="")

            m = re.search(r"Wrong\. The number was (\d+)\.", text)
            if not m:
                if "Correct. Current streak:" in text:
                    raise RuntimeError(
                        "Unlucky: guessed correctly while harvesting. "
                        "Reconnect and run again."
                    )
                raise RuntimeError(
                    "Failed to parse revealed MT output while harvesting."
                )

            outputs.append(int(m.group(1)))

        print(f"\n[+] Collected {len(outputs)} MT outputs")
        recovered_state = [untemper(x) for x in outputs]
        mt = MTPredictor(recovered_state)
        print("[+] MT19937 state recovered")

        # Step 2: predict future outputs and collect RSA samples
        samples = []

        while len(samples) < 17:
            nxt = mt.getrandbits32()
            r.sendline(nxt)

            text = r.recv_until_any(round_end_tokens).decode(errors="ignore")
            print(text, end="")

            # Parse any RSA sample present in this round
            m_n = re.search(r"\bn\s*=\s*(\d+)", text)
            m_e = re.search(r"\be\s*=\s*(\d+)", text)
            m_c = re.search(r"\bc\s*=\s*(\d+)", text)

            if m_n and m_c:
                n = int(m_n.group(1))
                c = int(m_c.group(1))

                if m_e:
                    parsed_e = int(m_e.group(1))
                    if parsed_e != E:
                        raise RuntimeError(f"Unexpected exponent: {parsed_e}")

                samples.append((n, c))
                print(f"[+] Collected RSA sample {len(samples)}/17")

        print("\n[+] Enough samples collected, launching Håstad broadcast attack")

        moduli = [n for n, _ in samples]
        if not are_pairwise_coprime(moduli):
            print("[!] Warning: some moduli are not pairwise coprime")
            print("[!] Trying attack anyway...")

        x, _ = crt(samples[:17])   # x should equal m^17 exactly
        m, exact = integer_nthroot_exact(x, E)

        if not exact:
            print("[!] Exact 17th root not found.")
            print("[!] Try collecting more than 17 samples and retry with a subset.")
            return

        flag_bytes = long_to_bytes(m)

        print("\n[+] Raw flag bytes:", flag_bytes)
        try:
            print("[+] FLAG:", flag_bytes.decode())
        except UnicodeDecodeError:
            print("[+] FLAG (utf-8 decode failed):", flag_bytes.decode(errors="ignore"))

    finally:
        r.close()


if __name__ == "__main__":
    main()