"""Broken reconciler stub - rewrite required (see task instruction)."""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--postings", required=True)
    parser.add_argument("--accounts", required=True)
    parser.add_argument("--window", required=True)
    parser.add_argument("--snapshot", required=True)
    args = parser.parse_args()

    # Stub: always writes an empty snapshot and fails.
    with open(args.snapshot, "w", encoding="utf-8"):
        pass
    sys.exit(1)


if __name__ == "__main__":
    main()
