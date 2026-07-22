# Dense SVD

This project builds a small C++ command-line tool, `svd_solve`, that reads a
dense complex matrix from a file and writes its singular value decomposition
to another file.

## Layout

- `include/svd_types.hpp` -- the `Matrix` alias, the `SvdResult` struct, and
  the function declaration (`compute_svd`) you implement.
- `include/matrix_utils.hpp` -- dense matmul/transpose and a small norm
  helper, fully implemented.
- `include/svd_io.hpp` -- the case-file reader and output-file writer,
  fully implemented.
- `src/main_stub.cpp` -- the `svd_solve` entry point. Complete and does not
  need to change; it wires the case-file reader to your `compute_svd` and
  the output writer.
- `src/cli_args.hpp` -- command-line argument parsing for `main_stub.cpp`.
- `src/smoke_test.cpp` -- a local sanity harness, independent of grading,
  that runs your implementation against a tiny 2x2 fixture and checks the
  reconstruction identity.
- `data/` -- every public case file, in the format described in
  `docs/storage_format.md`; see `docs/data_cases.md`.
- `CMakeLists.txt`, `build.sh` -- build configuration.

## Build

```
./build.sh
```

or directly:

```
cmake -S . -B build
cmake --build build
```

This produces `build/svd_solve` and `build/smoke_test`.

## Run

```
./build/svd_solve data/case_toy2x2.txt /tmp/case_toy2x2.out
```

reads the case file named by the first argument and writes the
decomposition to the path named by the second argument, in the format
documented in `docs/output_format.md`.

## What to do

`compute_svd`, declared in `include/svd_types.hpp`, is not defined anywhere
in this starter. Add an implementation under `src/` (any new `.cpp` file
there other than `main_stub.cpp` and `smoke_test.cpp` is picked up
automatically by `CMakeLists.txt`) so that it satisfies the contract
documented in `include/svd_types.hpp` and `docs/output_format.md`.

Do not link against or call any external linear-algebra library (LAPACK,
Eigen, GSL, Armadillo, BLAS, MKL, or similar) -- none is installed in this
image, and none may be vendored into the source tree. Compute everything
under `src/` and `include/`.

Read `docs/storage_format.md` and `docs/output_format.md` for the exact
file contracts.
