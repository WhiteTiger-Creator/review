#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

WORK=/tmp/lyaptask
rm -rf "$WORK"
mkdir -p "$WORK/in"

python3 /tests/gen_problems.py "$WORK/in" "$WORK/ref.json" 90310 1>&2

python3 /tests/check_forbidden.py /app/lyap.c 1>&2
if [ $? -ne 0 ]; then
    echo "forbidden extended-precision or linear-algebra usage detected" 1>&2
    exit 0
fi

cc -O2 -std=c11 -o "$WORK/lyap" /app/lyap.c -lm 2>"$WORK/build.err"
if [ ! -x "$WORK/lyap" ]; then
    echo "build failed" 1>&2
    cat "$WORK/build.err" 1>&2
    exit 0
fi

"$WORK/lyap" "$WORK/in" "$WORK/out.txt" 1>&2

export LYAP_OUT="$WORK/out.txt"
export LYAP_REF="$WORK/ref.json"
export LYAP_IN="$WORK/in"
python3 -m pytest -rA /tests/test_outputs.py
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
