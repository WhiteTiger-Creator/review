# Termatrix ABI interface capsule contract

`bash /app/environment/scripts/build_matrix.sh /app/output/abi-matrix` builds
the release matrix using only local files and CMake. `TERMATRIX_TARGETS` is an
optional whitespace-separated ordered list. Without it, the release driver builds
`glibc-x86_64` followed by `musl-x86_64`.

| target | ABI family | ABI C define | target C define | compiler profile |
| --- | --- | --- | --- | --- |
| `glibc-x86_64` | `glibc` | `TERMATRIX_ABI_GLIBC=1` | `TERMATRIX_TARGET_GLIBC_X86_64=1` | `gnu-glibc` |
| `musl-x86_64` | `musl` | `TERMATRIX_ABI_MUSL=1` | `TERMATRIX_TARGET_MUSL_X86_64=1` | `musl-gcc` |

The `=1` notation above describes the active C preprocessor definitions seen
by consumers. Descriptor and interface files store the bare macro names:
`TERMATRIX_ABI_GLIBC`, `TERMATRIX_TARGET_GLIBC_X86_64`,
`TERMATRIX_ABI_MUSL`, and `TERMATRIX_TARGET_MUSL_X86_64`. JSON provenance
fields that name compile definitions use those bare descriptor values without
`=1`; pkg-config and CMake consumer metadata may still activate the same macros
as compiler definitions equivalent to `-D<name>=1`.

The per-target `requested.descriptor_file`, `requested.toolchain_file`, and
`requested.interface_fragment_file` values are POSIX paths relative to
`/app/environment`:

| target | descriptor | toolchain | interface fragment |
| --- | --- | --- | --- |
| `glibc-x86_64` | `config/matrix/glibc-x86_64.env` | `cmake/toolchains/glibc-x86_64.cmake` | `config/interfaces/glibc-x86_64.cmake` |
| `musl-x86_64` | `config/matrix/musl-x86_64.env` | `cmake/toolchains/musl-x86_64.cmake` | `config/interfaces/musl-x86_64.cmake` |

Each invocation is a publish transaction. Unsupported target names fail
non-zero before publishing artifacts for that request. Before a failed request
exits, it must delete `/app/output/abi-matrix/build-cache-provenance.json` or
overwrite it with a non-success report, so an older success report is never left
behind. Failed requests leave already published target artifacts untouched.
For example, `TERMATRIX_TARGETS="glibc-x86_64 freebsd-x86_64"` must fail and
must not create `/app/output/abi-matrix/artifacts/freebsd-x86_64`.

## Output layout

For each requested target `<target>`, the build writes:

- `/app/output/abi-matrix/artifacts/<target>/include/termatrix/matrix.h`
- `/app/output/abi-matrix/artifacts/<target>/lib/libtermatrix.a`
- `/app/output/abi-matrix/artifacts/<target>/lib/pkgconfig/termatrix.pc`
- `/app/output/abi-matrix/artifacts/<target>/lib/cmake/Termatrix/TermatrixConfig.cmake`
- `/app/output/abi-matrix/artifacts/<target>/lib/cmake/Termatrix/TermatrixTargets.cmake`
- `/app/output/abi-matrix/artifacts/<target>/abi_identity.json`
- `/app/output/abi-matrix/artifacts/<target>/cache_provenance.json`
- `/app/output/abi-matrix/artifacts/<target>/interface_ledger.json`

For example, the musl CMake config path is
`/app/output/abi-matrix/artifacts/musl-x86_64/lib/cmake/Termatrix/TermatrixConfig.cmake`.
The glibc imported-target metadata path is
`/app/output/abi-matrix/artifacts/glibc-x86_64/lib/cmake/Termatrix/TermatrixTargets.cmake`.

The published artifacts directory represents only the current requested target
list. A later single-target run must not leave an old artifact directory for a
target that was not requested. Reordered runs preserve the requested order in
the top-level report and in the report map.

## Top-level provenance

`build-cache-provenance.json` is deterministic JSON:

```json
{
  "schema_version": 2,
  "generator": "termatrix-cmake-cache-matrix-v2",
  "transaction": {
    "status": "success",
    "requested": ["glibc-x86_64", "musl-x86_64"],
    "published": ["glibc-x86_64", "musl-x86_64"]
  },
  "targets": ["glibc-x86_64", "musl-x86_64"],
  "reports": {
    "glibc-x86_64": {
      "cache": "artifacts/glibc-x86_64/cache_provenance.json",
      "interface": "artifacts/glibc-x86_64/interface_ledger.json"
    },
    "musl-x86_64": {
      "cache": "artifacts/musl-x86_64/cache_provenance.json",
      "interface": "artifacts/musl-x86_64/interface_ledger.json"
    }
  }
}
```

`targets`, `transaction.requested`, `transaction.published`, and the insertion
order of `reports` match the requested target order.

Static or manual writes of the JSON files and package files are insufficient;
the normal build command must regenerate them from the current local inputs.

## Cache provenance

Each `cache_provenance.json` has `schema_version: 2` and generator
`termatrix-cmake-cache-matrix-v2`. The `requested` object records `target`,
`abi_family`, `toolchain_file`, `descriptor_file`, `interface_fragment_file`,
and `compiler_profile`.

The `artifact` object records the library path, `library_sha256`,
`header_sha256`, and `object_units` containing `identity` and `mix`.
`header_sha256` is the SHA-256 digest of the copied public header file
`include/termatrix/matrix.h`, not a digest of a directory listing or header
tree.

The `cache` object records the cache root, the literal `key_fields` key with
this key field list, and one unit record for each object unit under the literal
key `units`:

```json
[
  "unit_source_sha256",
  "public_header_sha256",
  "descriptor_sha256",
  "toolchain_sha256",
  "interface_fragment_sha256",
  "build_logic_sha256",
  "target",
  "abi_family",
  "compiler_profile",
  "unit_name"
]
```

Each unit record includes `unit`, `key`, `cache_path`, `hit`, `reason`,
`valid_for_request`, `object_sha256`, `actual_object_sha256`, `object_target`,
`object_abi_family`, `identity`, `unit_source_sha256`,
`public_header_sha256`, `descriptor_sha256`, `toolchain_sha256`,
`interface_fragment_sha256`, and `build_logic_sha256`.

`object_sha256` and `actual_object_sha256` must match after a successful run.
`valid_for_request` is true only when the cached object unit belongs to the
requested target, ABI family, unit, and cache key. `hit` is true only when a
valid cache object already existed before the current invocation. `hit` is false
for a miss, changed input, stale metadata, or repaired cache corruption.
Non-hit cache recovery uses stable `reason` strings: `missing-cache-entry` for
an absent cache slot, `stale-metadata` for metadata that does not belong to the
current request, and `corrupt-object` for a cached object whose bytes do not
match its recorded object digest. A valid reused object reports a cache-hit
reason and keeps `valid_for_request: true`.

## Interface ledger

Each `interface_ledger.json` has `schema_version: 2` and generator
`termatrix-cmake-cache-matrix-v2`. It records:

- `requested`: the same target, ABI family, descriptor, toolchain, interface
  fragment, and compiler profile used by the cache report.
- `interface`: `pkg_config`, `cmake_config`, `cmake_targets`,
  `imported_target`, `include_dir`, `library`, `compile_definitions`,
  `identity`, and `valid_for_request`.
- `digests`: SHA-256 values for `library`, `public_header`, `pkg_config`,
  `cmake_config`, `cmake_targets`, `descriptor`, `toolchain`,
  `interface_fragment`, and `build_logic`.
- `cache`: the sibling cache report path under the literal key `report` and
  the object-unit names under the literal key `units` (not `object_units`):

```json
{
  "report": "cache_provenance.json",
  "units": ["identity", "mix"]
}
```

The digest object uses the exact keys `library_sha256`,
`public_header_sha256`, `pkg_config_sha256`, `cmake_config_sha256`,
`cmake_targets_sha256`, `descriptor_sha256`, `toolchain_sha256`,
`interface_fragment_sha256`, and `build_logic_sha256`.

The interface identity string is exactly
`termatrix-interface|abi=<abi_family>|target=<target>`.

The generated pkg-config and CMake package files must be relocatable. A consumer
that sets `PKG_CONFIG_PATH` to the target's `lib/pkgconfig` directory must see
only that target's ABI and target defines. A consumer that copies the target
artifact directory elsewhere and sets `CMAKE_PREFIX_PATH` to the copied
directory must be able to use `find_package(Termatrix CONFIG REQUIRED)` and link
`Termatrix::termatrix`.
The generated CMake package metadata must also carry the active
`interface_fragment_sha256` value so a relocated package still identifies the
interface authority fragment it was generated from.

Consumer probes may call `pkg-config --cflags termatrix` and
`pkg-config --cflags --libs termatrix`. CMake build probes may configure with
`cmake -S <consumer> -B <build> -DCMAKE_PREFIX_PATH=<copied-prefix>` and build
with `cmake --build <build> --parallel 1`. Temporary consumer build directories
may use names beginning with `cmake-consumer-build-`.

## Cache and recovery rules

The shared object cache root is `/app/output/termatrix-cache` unless
`TERMATRIX_CACHE_ROOT` overrides it. Cache keys change when the relevant unit
source, public headers, target descriptor, toolchain file, interface fragment,
build wrapper, driver source, CMake logic, target, ABI family, compiler profile,
or unit name changes. Changing `src/mix.c` should not invalidate the `identity`
object unit when the `identity` inputs are unchanged.

The concrete path for that mix unit is `/app/environment/src/mix.c`.

Later valid invocations preserve valid unchanged cache entries as hits, rebuild
cache entries whose object or metadata is missing or corrupted, rebuild entries
invalidated by source/header/descriptor/toolchain/interface/build-logic changes,
regenerate tampered published artifacts through the normal CMake pipeline, clean
stale publish staging directories such as `.publish-tmp-*`, and keep repeated
cache-hit reports byte-stable for the same requested target list. Runs that
switch descriptors, ABI families, or target order keep configure state, package
metadata, object identities, cache metadata, and provenance isolated between
requested targets.

The library archive contains object identity strings of the form:

```text
termatrix-object|abi=<abi_family>|target=<target>|unit=<unit>
```

The generated `termatrix.pc` and `Termatrix::termatrix` imported target must
export the include directory plus exactly the ABI and target defines for the
target being consumed.
