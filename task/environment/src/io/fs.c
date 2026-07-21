#include "io/fs.h"

bool fs_write_u32(FILE *f, uint32_t v) { return fwrite(&v, sizeof(v), 1, f) == 1; }
bool fs_read_u32(FILE *f, uint32_t *out) { return fread(out, sizeof(*out), 1, f) == 1; }

bool fs_write_u64(FILE *f, uint64_t v) { return fwrite(&v, sizeof(v), 1, f) == 1; }
bool fs_read_u64(FILE *f, uint64_t *out) { return fread(out, sizeof(*out), 1, f) == 1; }

