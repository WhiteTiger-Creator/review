#ifndef TERMATRIX_MATRIX_H
#define TERMATRIX_MATRIX_H

#include <stdint.h>
#include "termatrix/detail/export.h"

TERMATRIX_BEGIN_C

const char *termatrix_compiled_abi(void);
const char *termatrix_compiled_target(void);
uint32_t termatrix_abi_code(void);
uint32_t termatrix_mix(uint32_t seed);

TERMATRIX_END_C

#endif
