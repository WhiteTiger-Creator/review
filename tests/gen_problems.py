"""Stage the committed graded suite for the Lyapunov-exponent cocycle task.

The graded problems and their high-precision reference exponents are generated
offline and committed under tests/graded. This staging step copies them into the
verifier working directory. The reference exponents are the finite-horizon
Lyapunov exponents of each ordered matrix product, computed in high precision and
independently anchored by the fact that the sum of the exponents equals
(1/k) * sum_i log|det M_i|.
"""

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GRADED = os.path.join(HERE, "graded")


def main():
    out_dir, ref_path = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(GRADED, "ref.json")) as fh:
        ref = json.load(fh)
    for name in ref["order"]:
        shutil.copyfile(os.path.join(GRADED, name), os.path.join(out_dir, name))
    shutil.copyfile(os.path.join(GRADED, "ref.json"), ref_path)
    print(f"wrote {len(ref['order'])} problems")


if __name__ == "__main__":
    main()
