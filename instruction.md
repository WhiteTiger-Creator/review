Under /app/environment, read a dense complex m x n matrix A (m >= n) from a case file and compute its SVD: nonnegative real singular values descending, plus unitary U and V with A equal to U times the diagonal singular value matrix times the conjugate transpose of V.

Each file matching /app/environment/data/case_*.txt holds one case, per docs/storage_format.md: row and column counts, then that many rows of numbers, each entry as its real part then its imaginary part. Given the case file and an output path, write a file (format in docs/output_format.md) with status plus the singular values, U, and V in the same pairing. Report status=ERROR and exit nonzero only for malformed input; every well-formed input factors successfully.

Grading recomputes everything from your reported U, singular values, and V against A: how close U^H U and V^H V sit to identity, how closely U times Sigma times V^H reconstructs A, both scaled by A's magnitude, and, where disclosed, how closely each singular value agrees with its known value at a tolerance scaled to that value's own magnitude. A zero imaginary part is still a genuine complex entry.

Do not link LAPACK, Eigen, GSL, or BLAS; compute everything under src/ and include/.

README.md describes the layout and build. include/svd_types.hpp declares compute_svd, undefined in the starter; add .cpp files under src/, picked up by CMake. Build with build.sh; run ./build/svd_solve data/case_toy2x2.txt /tmp/out.txt.

