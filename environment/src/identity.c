#include "termatrix/matrix.h"
#include "termatrix/detail/abi_codes.h"

#ifndef TERMATRIX_TARGET_NAME
#define TERMATRIX_TARGET_NAME "unknown-target"
#endif

#ifndef TERMATRIX_CACHE_UNIT
#define TERMATRIX_CACHE_UNIT "identity"
#endif

#if defined(TERMATRIX_ABI_MUSL)
#define TERMATRIX_ABI_TEXT "musl"
#define TERMATRIX_ABI_CODE_VALUE TERMATRIX_ABI_CODE_MUSL
#elif defined(TERMATRIX_ABI_GLIBC)
#define TERMATRIX_ABI_TEXT "glibc"
#define TERMATRIX_ABI_CODE_VALUE TERMATRIX_ABI_CODE_GLIBC
#else
#define TERMATRIX_ABI_TEXT "unknown"
#define TERMATRIX_ABI_CODE_VALUE 0u
#endif

const char termatrix_identity_unit_marker[] =
    "termatrix-object|abi=" TERMATRIX_ABI_TEXT "|target=" TERMATRIX_TARGET_NAME "|unit=" TERMATRIX_CACHE_UNIT;

const char *termatrix_compiled_abi(void) {
    return TERMATRIX_ABI_TEXT;
}

const char *termatrix_compiled_target(void) {
    return TERMATRIX_TARGET_NAME;
}

