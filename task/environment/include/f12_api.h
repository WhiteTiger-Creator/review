#pragma once
#ifdef __cplusplus
extern "C" {
#endif
#include <stddef.h>
#include <stdint.h>
int64_t f12_slot_total(const char *target, const char *const *names, size_t count, int base,
                       int64_t record_bytes);
#ifdef __cplusplus
}
#endif
