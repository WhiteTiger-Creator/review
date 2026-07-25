"""Scoped check for prohibited extended precision or external linear-algebra usage.

The contract forbids *using* those facilities, not naming them. Comments, string
literals, and ordinary identifiers must never trigger a rejection; only real usage
does: an extended-precision type in code, an include directive that pulls in a
forbidden library, or a link pragma. Genuine linking against such a library also
fails at build time, since the fixed compile line links only the math library.
"""

import re
import sys

with open(sys.argv[1]) as fh:
    src = fh.read()

# Drop comments and string/char literals so that naming a method or library in a
# comment, a printed message, or an identifier cannot cause a false positive.
src = re.sub(r"/\*.*?\*/", " ", src, flags=re.DOTALL)
src = re.sub(r"//[^\n]*", " ", src)
src = re.sub(r'"(\\.|[^"\\\n])*"', " ", src)
src = re.sub(r"'(\\.|[^'\\\n])*'", " ", src)

reasons = []

# Extended or arbitrary precision floating types used in the code itself.
for pat, label in (
    (r"\blong\s+double\b", "long double"),
    (r"\b__float128\b", "__float128"),
    (r"\b_Float128\b", "_Float128"),
    (r"\b__float80\b", "__float80"),
):
    if re.search(pat, src):
        reasons.append("extended-precision type " + label)

# Include directives that pull in a forbidden library.
FORBIDDEN_HEADERS = {
    "gmp.h",
    "gmpxx.h",
    "mpfr.h",
    "mpf2mpfr.h",
    "quadmath.h",
    "lapacke.h",
    "lapack.h",
    "clapack.h",
    "cblas.h",
    "f77blas.h",
}
for m in re.finditer(r'#\s*include\s*[<"]\s*([^">]+?)\s*[">]', src):
    target = m.group(1).strip()
    base = target.split("/")[-1].lower()
    top = target.split("/")[0].lower()
    if (
        base in FORBIDDEN_HEADERS
        or top in ("gsl", "eigen")
        or base.startswith(("gsl_", "lapack", "cblas", "mpfr", "gmp"))
    ):
        reasons.append("forbidden include " + target)

# A link pragma naming an external library.
if re.search(r"#\s*pragma\s+comment\s*\(\s*lib", src, re.IGNORECASE):
    reasons.append("link pragma")

if reasons:
    sys.stderr.write("forbidden usage detected: " + "; ".join(reasons) + "\n")
    sys.exit(1)
sys.exit(0)
