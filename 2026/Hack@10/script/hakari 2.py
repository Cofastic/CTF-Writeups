#!/usr/bin/env python3
import random
import re
import socket
import sys

HOST = "34.126.187.50"
PORT = 5501

OUTER_PROMPT = b"Guess the next number: "
INNER_PREDICT_PROMPT = b"Predict the next number or type -1 to exit: "
OPTION_PROMPT = b"[1] encrypt, [2] decrypt: "
PT_PROMPT = b"Input plaintext to encrypt in hex: "

# =========================
# Socket helpers
# =========================
class Remote:
    def __init__(self, host, port, timeout=3.0):
        self.s = socket.create_connection((host, port))
        self.s.settimeout(timeout)
        self.buf = b""

    def sendline(self, data):
        if isinstance(data, int):
            data = str(data)
        if isinstance(data, str):
            data = data.encode()
        self.s.sendall(data + b"\n")

    def recv_until_any(self, tokens, allow_eof=False):
        """
        Read until any token in `tokens` is seen.
        Returns (data, matched_token_or_None).
        If allow_eof=True, returns buffered data on EOF/timeout.
        """
        while True:
            for tok in tokens:
                idx = self.buf.find(tok)
                if idx != -1:
                    end = idx + len(tok)
                    out = self.buf[:end]
                    self.buf = self.buf[end:]
                    return out, tok

            try:
                chunk = self.s.recv(4096)
            except socket.timeout:
                if allow_eof and self.buf:
                    out = self.buf
                    self.buf = b""
                    return out, None
                continue

            if not chunk:
                if allow_eof:
                    out = self.buf
                    self.buf = b""
                    return out, None
                raise EOFError("connection closed")

            self.buf += chunk

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


# =========================
# MT seed recovery helpers
# Adapted from Stackered's published method
# =========================
def unshift_right(x, shift):
    res = x
    for _ in range(32):
        res = x ^ (res >> shift)
    return res & 0xFFFFFFFF

def unshift_left(x, shift, mask):
    res = x
    for _ in range(32):
        res = x ^ ((res << shift) & mask)
    return res & 0xFFFFFFFF

def untemper(v):
    v = unshift_right(v, 18)
    v = unshift_left(v, 15, 0xEFC60000)
    v = unshift_left(v, 7, 0x9D2C5680)
    v = unshift_right(v, 11)
    return v & 0xFFFFFFFF

def invert_step(si, si227):
    """
    Recover partial initial-state info from two current-state values.
    """
    x = si ^ si227
    mti1 = (x & 0x80000000) >> 31
    if mti1:
        x ^= 0x9908B0DF
    x <<= 1
    mti = x & 0x80000000
    mti1 += x & 0x7FFFFFFF
    return mti & 0xFFFFFFFF, mti1 & 0xFFFFFFFF

def init_genrand(seed):
    mt = [0] * 624
    mt[0] = seed & 0xFFFFFFFF
    for i in range(1, 624):
        mt[i] = ((0x6C078965 * (mt[i - 1] ^ (mt[i - 1] >> 30))) + i) & 0xFFFFFFFF
    return mt

def recover_kj_from_ji(ji, ji1, i):
    const = init_genrand(19650218)
    key = ji - (const[i] ^ ((ji1 ^ (ji1 >> 30)) * 1664525))
    return key & 0xFFFFFFFF

def recover_ji_from_ii(ii, ii1, i):
    ji = (ii + i) ^ ((ii1 ^ (ii1 >> 30)) * 1566083941)
    return ji & 0xFFFFFFFF

def recover_kj_from_ii(ii, ii1, ii2, i):
    ji = recover_ji_from_ii(ii, ii1, i)
    ji1 = recover_ji_from_ii(ii1, ii2, i - 1)
    return recover_kj_from_ji(ji, ji1, i)

def recover_seed_candidates(leaked_outputs):
    """
    Recover the 2 possible 8-byte bytes-v2 seeds from the first 234 leaked outputs.
    We use the selected indices corresponding to k = 18.
    """
    if len(leaked_outputs) < 234:
        raise ValueError("Need at least 234 leaked outputs")

    s = [untemper(x) for x in leaked_outputs]

    # Use S3,S4,S5,S6 and S230,S231,S232,S233
    i230_, i231 = invert_step(s[3], s[230])
    i231_, i232 = invert_step(s[4], s[231])
    i232_, i233 = invert_step(s[5], s[232])
    i233_, i234 = invert_step(s[6], s[233])

    i231 = (i231 + i231_) & 0xFFFFFFFF
    i232 = (i232 + i232_) & 0xFFFFFFFF
    i233 = (i233 + i233_) & 0xFFFFFFFF

    # Recover K[16] and K[17]
    seed_l = (recover_kj_from_ii(i233, i232, i231, 233) - 16) & 0xFFFFFFFF
    seed_h1 = (recover_kj_from_ii(i234, i233, i232, 234) - 17) & 0xFFFFFFFF
    seed_h2 = (recover_kj_from_ii((i234 + 0x80000000) & 0xFFFFFFFF, i233, i232, 234) - 17) & 0xFFFFFFFF

    cand1 = ((seed_h1 << 32) | seed_l).to_bytes(8, "big")
    cand2 = ((seed_h2 << 32) | seed_l).to_bytes(8, "big")
    return cand1, cand2

def pick_correct_seed(leaked_outputs):
    cand1, cand2 = recover_seed_candidates(leaked_outputs)

    good = []
    for cand in (cand1, cand2):
        r = random.Random()
        r.seed(cand)
        test = [r.getrandbits(32) for _ in range(len(leaked_outputs))]
        if test == leaked_outputs:
            good.append(cand)

    if len(good) != 1:
        raise RuntimeError(f"Could not uniquely validate seed candidates: {good!r}")

    return good[0]


# =========================
# GF(2) helpers for affine cipher recovery
# =========================
def bytes_to_int(b):
    return int.from_bytes(b, "big")

def int_to_bytes(x):
    return x.to_bytes(16, "big")

def solve_gf2_from_columns(columns, y, n=128):
    """
    Solve A x = y over GF(2), where columns[j] is the j-th column of A as an n-bit int.
    Returns x as an n-bit int.
    """
    rows = [0] * n
    rhs = [(y >> i) & 1 for i in range(n)]

    # Build rows from columns
    for j, col in enumerate(columns):
        for i in range(n):
            if (col >> i) & 1:
                rows[i] |= (1 << j)

    where = [-1] * n
    r = 0

    for c in range(n):
        pivot = None
        for i in range(r, n):
            if (rows[i] >> c) & 1:
                pivot = i
                break
        if pivot is None:
            continue

        rows[r], rows[pivot] = rows[pivot], rows[r]
        rhs[r], rhs[pivot] = rhs[pivot], rhs[r]
        where[c] = r

        for i in range(n):
            if i != r and ((rows[i] >> c) & 1):
                rows[i] ^= rows[r]
                rhs[i] ^= rhs[r]

        r += 1

    x = 0
    for c in range(n):
        if where[c] != -1 and rhs[where[c]]:
            x |= (1 << c)

    # Verify
    for i in range(n):
        lhs = ((rows[i] & x).bit_count() & 1)
        if lhs != rhs[i]:
            raise RuntimeError("GF(2) solve failed")

    return x


# =========================
# Challenge interaction helpers
# =========================
def parse_wrong_number(text):
    m = re.search(r"Wrong\. The number was (\d+)\.", text)
    return int(m.group(1)) if m else None

def parse_secret_enc(text):
    m = re.search(r"Encrypted Secret:\s*([0-9a-fA-F]{32})", text)
    return bytes.fromhex(m.group(1)) if m else None

def parse_enc_result(text):
    m = re.search(r"enc\(plaintext\)\s*=\s*([0-9a-fA-F]{32})", text)
    return bytes.fromhex(m.group(1)) if m else None

def parse_flag(text):
    m = re.search(r"(hack10\{[^}\n]+\})", text)
    return m.group(1) if m else None

def harvest_outputs(r, count=234):
    leaked = []

    banner, _ = r.recv_until_any([OUTER_PROMPT])
    print(banner.decode(errors="ignore"), end="")

    for i in range(count):
        r.sendline("0")
        data, _ = r.recv_until_any([OUTER_PROMPT], allow_eof=False)
        text = data.decode(errors="ignore")
        print(text, end="")

        val = parse_wrong_number(text)
        if val is None:
            raise RuntimeError(
                f"Failed to parse leaked output at harvest step {i}. "
                "Maybe you hit the 1/2^32 chance that 0 was correct."
            )
        leaked.append(val)

    return leaked

def reach_jackpot(r, rng):
    """
    Use 3 correct predictions to enter jackpot mode.
    Returns the transition text that contains Encrypted Secret and the first inner prompt.
    """
    transition_text = ""

    for _ in range(3):
        nxt = rng.getrandbits(32)
        r.sendline(str(nxt))
        data, tok = r.recv_until_any([OUTER_PROMPT, INNER_PREDICT_PROMPT], allow_eof=False)
        text = data.decode(errors="ignore")
        print(text, end="")
        transition_text += text

        if "Wrong. The number was" in text:
            raise RuntimeError("Prediction failed before jackpot; seed recovery was wrong")

        if tok == INNER_PREDICT_PROMPT:
            return transition_text

    raise RuntimeError("Did not enter jackpot after 3 correct guesses")

def oracle_encrypt(r, rng, plaintext):
    """
    One chosen-plaintext encryption query in jackpot mode.
    Consumes one RNG output for the prediction gate.
    Returns (ciphertext_bytes_or_None, full_text).
    """
    nxt = rng.getrandbits(32)
    r.sendline(str(nxt))

    data, _ = r.recv_until_any([OPTION_PROMPT], allow_eof=False)
    text1 = data.decode(errors="ignore")
    # Correct prediction is silent; server goes straight to option prompt

    r.sendline("1")
    data, _ = r.recv_until_any([PT_PROMPT], allow_eof=False)
    text2 = data.decode(errors="ignore")

    r.sendline(plaintext.hex())
    data, _ = r.recv_until_any([INNER_PREDICT_PROMPT], allow_eof=True)
    text3 = data.decode(errors="ignore")

    full = text1 + text2 + text3
    ct = parse_enc_result(full)
    return ct, full


def main():
    r = Remote(HOST, PORT)

    try:
        # 1) Leak 234 outputs
        leaked = harvest_outputs(r, 234)
        print(f"\n[+] Harvested {len(leaked)} outputs")

        # 2) Recover exact 8-byte bytes-v2 seed
        seed = pick_correct_seed(leaked)
        print(f"[+] Recovered seed: {seed.hex()}")

        rng = random.Random()
        rng.seed(seed)
        for _ in range(234):
            rng.getrandbits(32)

        # 3) Predict 3 correct values to unlock jackpot
        transition = reach_jackpot(r, rng)
        secret_enc = parse_secret_enc(transition)
        if secret_enc is None:
            raise RuntimeError("Failed to parse Encrypted Secret")

        print(f"[+] Encrypted Secret: {secret_enc.hex()}")

        # 4) Recover affine map E(x) = A*x XOR b using encryption oracle
        zero = b"\x00" * 16
        b0, text = oracle_encrypt(r, rng, zero)
        if b0 is None:
            raise RuntimeError("Failed to get enc(0)")
        print(f"[+] b = enc(0) = {b0.hex()}")

        b0_int = bytes_to_int(b0)
        columns = []

        for i in range(128):
            basis = 1 << i
            pt = int_to_bytes(basis)
            ct, _ = oracle_encrypt(r, rng, pt)
            if ct is None:
                raise RuntimeError(f"Failed to get encryption for basis bit {i}")
            columns.append(bytes_to_int(ct) ^ b0_int)

            if (i + 1) % 16 == 0:
                print(f"[+] Recovered {i+1}/128 affine columns")

        # 5) Solve for secret from secret_enc = A*secret XOR b
        target = bytes_to_int(secret_enc) ^ b0_int
        secret_int = solve_gf2_from_columns(columns, target, 128)
        secret = int_to_bytes(secret_int)
        print(f"[+] Recovered secret: {secret.hex()}")

        # 6) Submit recovered secret to option 1 to trigger flag
        final_ct, final_text = oracle_encrypt(r, rng, secret)
        print(final_text, end="")

        flag = parse_flag(final_text)
        if flag:
            print(f"[+] FLAG: {flag}")
            return

        print("[!] Secret submitted, but flag was not parsed.")
        print("[!] If the server output format differs slightly, paste the output here.")

    finally:
        r.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)