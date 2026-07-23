# Termatrix local build notes

Termatrix is a compact C ABI library consumed by C and C++ callers. Most local
developers only build the native glibc artifact while changing the public header:

```bash
export CC=gcc
cmake -S . -B build/native
cmake --build build/native
```

These notes are intentionally historical. Release jobs use the matrix descriptors
and CMake toolchain files under `config/matrix/` and `cmake/toolchains/`.
