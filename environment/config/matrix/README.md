# Matrix descriptors

Each `.env` descriptor declares a release target, its ABI family, the CMake
toolchain file, the interface fragment, and the public preprocessor defines that
must be exported to pkg-config and CMake consumers. The descriptors are data
inputs to the release driver; they are not generated artifacts.
