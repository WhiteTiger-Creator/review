#!/usr/bin/env python3
import hashlib
import sys

if len(sys.argv) != 7:
    raise SystemExit("usage: hex16.py PKG DEP LO HI PRE_TOK LIFT(0|1)")

pkg, dep, lo, hi, pre_tok, lift_s = sys.argv[1:7]
lift_bit = 1 if lift_s in {"1", "true", "True"} else 0
payload = f"{pkg}|{dep}|{lo}|{hi}|{pre_tok}|{lift_bit}"
print(hashlib.sha256(payload.encode()).hexdigest()[:16])
