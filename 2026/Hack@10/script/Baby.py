import hashlib
from functools import lru_cache

# Read the challenge output and convert it back to the original hex stream
with open("output", "rb") as f:
    enc_hex = f.read().hex()

# Fixed beginning from the flag format
prefix_pairs = ["ha", "ck", "10"]

# Inner content appears to be hex
hexchars = "0123456789abcdef"

# Build candidate pair list
# First pair after "hack10" should be "{x"
# Middle pairs are "xx"
# Final pair is "x}"
start_pairs = ["{" + c for c in hexchars]
mid_pairs = [a + b for a in hexchars for b in hexchars]
end_pairs = [c + "}" for c in hexchars]

# Cache SHA-512 digests
digest_cache = {}

def sha512_hex(s: str) -> str:
    if s not in digest_cache:
        digest_cache[s] = hashlib.sha512(s.encode()).hexdigest()
    return digest_cache[s]

def possible_matches(pos: int, pair: str):
    """
    From enc_hex[pos:], try every valid random prefix length and every valid
    digest slice position for this pair.
    Returns possible next positions.
    """
    d = sha512_hex(pair)
    results = []

    # random bytes length: 0..31 bytes -> 0..62 hex chars
    for gap in range(0, 63, 2):
        j = pos + gap
        if j + 75 > len(enc_hex):
            continue

        # b = 1..15
        for start in range(1, 16):
            # Need at least 75 hex chars from the digest slice
            if not enc_hex.startswith(d[start:start + 75], j):
                continue

            # a = 90..128, so slice is d[start:end]
            # try longer slices first
            for end in range(128, max(89, start + 74), -1):
                seg = d[start:end]
                if enc_hex.startswith(seg, j):
                    results.append((j + len(seg), gap, start, end))

    return results

@lru_cache(None)
def solve_hex_body(pos: int, state: str):
    """
    state:
      'start'  -> expect first pair inside braces, like "{a"
      'mid'    -> expect hex-hex pair like "8d"
      'end'    -> optionally allow final pair like "4}"
    """
    if pos == len(enc_hex):
        return []

    candidates = []

    if state == "start":
        pair_pool = start_pairs
    elif state == "mid":
        pair_pool = mid_pairs + end_pairs
    else:
        pair_pool = end_pairs

    for pair in pair_pool:
        for next_pos, gap, start, end in possible_matches(pos, pair):
            # If this pair closes the flag, next must consume everything
            if pair.endswith("}"):
                if next_pos == len(enc_hex):
                    return [(pair, gap, start, end)]
                continue

            rest = solve_hex_body(next_pos, "mid")
            if rest is not None:
                return [(pair, gap, start, end)] + rest

    return None

def solve():
    pos = 0
    recovered = []

    # Recover fixed prefix pairs
    for pair in prefix_pairs:
        matches = possible_matches(pos, pair)
        if not matches:
            raise RuntimeError(f"Could not place fixed pair {pair!r}")
        # choose the longest valid-looking one first
        next_pos, gap, start, end = matches[0]
        recovered.append((pair, gap, start, end))
        pos = next_pos

    # Recover the rest
    rest = solve_hex_body(pos, "start")
    if not rest:
        raise RuntimeError("Could not recover remaining flag content")

    recovered.extend(rest)

    flag = "".join(pair for pair, *_ in recovered)
    return flag, recovered

if __name__ == "__main__":
    flag, chunks = solve()
    print("[+] Recovered flag:")
    print(flag)

    print("\n[+] Chunk breakdown:")
    for i, (pair, gap, start, end) in enumerate(chunks, 1):
        print(f"{i:02d}. pair={pair!r}  random_hex_gap={gap}  digest_slice=[{start}:{end}]")