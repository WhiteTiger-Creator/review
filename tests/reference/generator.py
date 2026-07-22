import csv
import hashlib
import json
import math
import random
from pathlib import Path


MASK40 = (1 << 40) - 1
DEFAULT_CHUNK_COUNT = 9
DEFAULT_SHARE_COUNT = 5
DEFAULT_POISON_CHOICES = 2


def flag_from(seed, chunk_count):
    material = hashlib.sha512((seed + "-sequence").encode()).digest()
    chunks = [
        int.from_bytes(material[:5], "big"),
        int.from_bytes(material[5:10], "big"),
        int.from_bytes(material[10:15], "big"),
    ]
    multiplier = int.from_bytes(material[15:20], "big") | 1
    lag_multiplier = int.from_bytes(material[20:25], "big") | 1
    third_multiplier = int.from_bytes(material[25:30], "big") | 1
    increment = int.from_bytes(material[30:35], "big")
    while len(chunks) < chunk_count:
        chunks.append(
            (
                multiplier * chunks[-1]
                + lag_multiplier * chunks[-2]
                + third_multiplier * chunks[-3]
                + increment
            )
            & MASK40
        )
    body = "".join(f"{chunk:010x}" for chunk in chunks)
    return (
        "CICADA{" + body + "}",
        multiplier,
        lag_multiplier,
        third_multiplier,
        increment,
    )


def fragment_messages(flag, rng, share_count):
    body = flag[7:-1]
    chunks = [body[i : i + 10] for i in range(0, len(body), 10)]
    messages = []
    for index, chunk in enumerate(chunks):
        random_values = [rng.getrandbits(40) for _ in range(share_count - 1)]
        final_value = int(chunk, 16)
        for value in random_values:
            final_value ^= value
        values = (*random_values, final_value)
        for share, value in enumerate(values):
            messages.append(
                {
                    "index": index,
                    "share": share,
                    "text": f"frag{index}.{share}:{value:010x}",
                }
            )
    return messages


def poison_messages(rng, messages, chunk_count, share_count, poison_choices):
    true_values = {message["text"].split(":", 1)[1] for message in messages}
    poison_values = set()
    poisons = []
    for index in range(chunk_count):
        for share in range(share_count):
            for _ in range(poison_choices):
                value = f"{rng.getrandbits(40):010x}"
                while value in true_values or value in poison_values:
                    value = f"{rng.getrandbits(40):010x}"
                poison_values.add(value)
                poisons.append(
                    {
                        "index": index,
                        "share": share,
                        "text": f"frag{index}.{share}:{value}",
                    }
                )
    return poisons


def is_probable_prime(n):
    if n < 2:
        return False
    for p in [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]:
        if n % p == 0:
            return n == p
    d = n - 1
    s = 0
    while d % 2 == 0:
        s += 1
        d //= 2
    for a in [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]:
        if a >= n - 2:
            continue
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        ok = False
        for _ in range(s - 1):
            x = (x * x) % n
            if x == n - 1:
                ok = True
                break
        if not ok:
            return False
    return True


def next_prime(n, exponent=7):
    n |= 1
    while True:
        if (n - 1) % exponent != 0 and is_probable_prime(n):
            return n
        n += 2


def rand_affine(rng, n):
    a = rng.randrange(5, 220) | 1
    while math.gcd(a, n) != 1:
        a += 2
    b = rng.getrandbits(96) | 1
    return a, b


def make_record(a, b, source_m, n, exponent, source, source_index=None):
    transformed = (a * source_m + b) % n
    row = {
        "id": "",
        "a": a,
        "b": b,
        "ciphertext": pow(transformed, exponent, n),
        "source": source,
        "source_m": source_m,
    }
    if source_index is not None:
        row["source_index"] = source_index
    return row


def instance(
    seed,
    bit_size=352,
    exponent=31,
    chunk_count=DEFAULT_CHUNK_COUNT,
    share_count=DEFAULT_SHARE_COUNT,
    poison_choices=DEFAULT_POISON_CHOICES,
):
    rng = random.Random(seed)
    p = next_prime((1 << (bit_size - 1)) + rng.getrandbits(bit_size - 2), exponent)
    q = next_prime((1 << (bit_size - 1)) + rng.getrandbits(bit_size - 2), exponent)
    while q == p:
        q = next_prime((1 << (bit_size - 1)) + rng.getrandbits(bit_size - 2), exponent)
    n = p * q
    flag, multiplier, lag_multiplier, third_multiplier, increment = flag_from(
        "rsa-affine-" + seed, chunk_count
    )
    messages = fragment_messages(flag, rng, share_count)
    poisons = poison_messages(rng, messages, chunk_count, share_count, poison_choices)

    records = []
    for message in messages:
        source_m = int.from_bytes(message["text"].encode(), "big")
        for _ in range(2):
            a, b = rand_affine(rng, n)
            records.append(
                make_record(
                    a,
                    b,
                    source_m,
                    n,
                    exponent,
                    "fragment",
                    message["index"],
                )
            )
    for message in poisons:
        source_m = int.from_bytes(message["text"].encode(), "big")
        for _ in range(2):
            a, b = rand_affine(rng, n)
            records.append(
                make_record(
                    a,
                    b,
                    source_m,
                    n,
                    exponent,
                    "poison",
                    message["index"],
                )
            )
    for _ in range(20):
        a, b = rand_affine(rng, n)
        fake_m = rng.randrange(2, n - 1)
        records.append(make_record(a, b, fake_m, n, exponent, "decoy"))

    rng.shuffle(records)
    if records[0]["source_m"] == records[1]["source_m"]:
        swap_index = next(
            index
            for index in range(2, len(records))
            if records[index]["source_m"] != records[0]["source_m"]
        )
        records[1], records[swap_index] = records[swap_index], records[1]
    ordered = []
    for index, row in enumerate(records, start=1):
        row = dict(row)
        row["id"] = f"c{index:02d}"
        ordered.append(row)
    return {
        "n": n,
        "e": exponent,
        "p": p,
        "q": q,
        "flag": flag,
        "commitment": hashlib.sha256(flag.encode()).hexdigest(),
        "multiplier": multiplier,
        "lag_multiplier": lag_multiplier,
        "third_multiplier": third_multiplier,
        "increment": increment,
        "chunk_count": chunk_count,
        "share_count": share_count,
        "poison_choices": poison_choices,
        "messages": messages,
        "poison_messages": poisons,
        "records": ordered,
    }


def hex_record(row):
    out = {
        "id": row["id"],
        "a": hex(row["a"]),
        "b": hex(row["b"]),
        "ciphertext": hex(row["ciphertext"]),
        "source": row["source"],
        "source_m": hex(row["source_m"]),
    }
    if "source_index" in row:
        out["source_index"] = row["source_index"]
    return out


def write_challenge(root, inst):
    root.mkdir(parents=True, exist_ok=True)
    (root / "public.txt").write_text(
        f"n={hex(inst['n'])}\ne={inst['e']}\n", encoding="utf-8"
    )
    (root / "commitment.txt").write_text(inst["commitment"] + "\n", encoding="utf-8")
    with (root / "ciphertexts.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "a", "b", "ciphertext"],
            lineterminator="\n",
        )
        writer.writeheader()
        for row in inst["records"]:
            writer.writerow(
                {
                    "id": row["id"],
                    "a": row["a"],
                    "b": hex(row["b"]),
                    "ciphertext": hex(row["ciphertext"]),
                }
            )
    (root / "relation.txt").write_text(
        f"multiplier={hex(inst['multiplier'])}\n"
        f"lag_multiplier={hex(inst['lag_multiplier'])}\n"
        f"third_multiplier={hex(inst['third_multiplier'])}\n"
        f"increment={hex(inst['increment'])}\n"
        "modulus=0x10000000000\n"
        f"chunk_count={inst['chunk_count']}\n"
        f"share_count={inst['share_count']}\n"
        "share_bits=40\n",
        encoding="utf-8",
    )
    (root / "manifest.txt").write_text(
        "public=public.txt\nciphertexts=ciphertexts.csv\ncommitment=commitment.txt\nrelation=relation.txt\n",
        encoding="utf-8",
    )


def write_secret(path, inst):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "n": hex(inst["n"]),
        "e": hex(inst["e"]),
        "p": hex(inst["p"]),
        "q": hex(inst["q"]),
        "flag": inst["flag"],
        "commitment": inst["commitment"],
        "multiplier": hex(inst["multiplier"]),
        "lag_multiplier": hex(inst["lag_multiplier"]),
        "third_multiplier": hex(inst["third_multiplier"]),
        "increment": hex(inst["increment"]),
        "chunk_count": inst["chunk_count"],
        "share_count": inst["share_count"],
        "poison_choices": inst["poison_choices"],
        "messages": inst["messages"],
        "poison_messages": inst["poison_messages"],
        "records": [hex_record(row) for row in inst["records"]],
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main():
    visible = instance("visible-v6", chunk_count=9)
    sample = instance("sample-v6", chunk_count=9)
    write_challenge(Path("environment/challenge"), visible)
    write_challenge(Path("environment/samples"), sample)
    write_secret(Path("tests/reference/visible_secret.json"), visible)


if __name__ == "__main__":
    main()
