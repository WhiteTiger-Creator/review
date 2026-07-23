#ifndef MTXREAD_H
#define MTXREAD_H
#include "spectral.h"
int read_symmetric_mtx(const char *path, SymCoo *out);
void free_symcoo(SymCoo *m);
#endif
