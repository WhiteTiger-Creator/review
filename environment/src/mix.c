#include "termatrix/matrix.h"
#include "termatrix/detail/abi_codes.h"

#ifndef TERMATRIX_TARGET_NAME
#define TERMATRIX_TARGET_NAME "unknown-target"
#endif

#ifndef TERMATRIX_CACHE_UNIT
#define TERMATRIX_CACHE_UNIT "mix"
#endif

#if defined(TERMATRIX_ABI_MUSL)
#define TERMATRIX_ABI_CODE_VALUE TERMATRIX_ABI_CODE_MUSL
#define TERMATRIX_ABI_TEXT "musl"
#elif defined(TERMATRIX_ABI_GLIBC)
#define TERMATRIX_ABI_CODE_VALUE TERMATRIX_ABI_CODE_GLIBC
#define TERMATRIX_ABI_TEXT "glibc"
#else
#define TERMATRIX_ABI_CODE_VALUE 0u
#define TERMATRIX_ABI_TEXT "unknown"
#endif

const char termatrix_mix_unit_marker[] =
    "termatrix-object|abi=" TERMATRIX_ABI_TEXT "|target=" TERMATRIX_TARGET_NAME "|unit=" TERMATRIX_CACHE_UNIT;

uint32_t termatrix_abi_code(void) {
    return TERMATRIX_ABI_CODE_VALUE;
}

uint32_t termatrix_mix(uint32_t seed) {
    return (seed * 2654435761u) ^ TERMATRIX_ABI_CODE_VALUE;
}
