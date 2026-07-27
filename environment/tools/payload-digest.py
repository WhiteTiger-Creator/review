#!/usr/bin/env python3
"""Hash a payload the way /app/docs/digest-spec.md describes.

    ./tools/payload-digest.py payload.txt
    printf 'protocol\\tslate/1\\n' | ./tools/payload-digest.py -

The file is read as bytes and hashed as it stands, so it doubles as a check on
whether a payload ends with the single trailing newline the spec asks for.
"""
import hashlib
import sys


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if sys.argv[1] == "-":
        data = sys.stdin.buffer.read()
    else:
        with open(sys.argv[1], "rb") as handle:
            data = handle.read()
    if not data.endswith(b"\n"):
        print("warning: payload does not end with a newline", file=sys.stderr)
    print(hashlib.sha256(data).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
