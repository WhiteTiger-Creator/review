#ifndef W7K_SEAT_H
#define W7K_SEAT_H
#include <stddef.h>

int vx_seat_load(int *epoch, char *banks_csv, size_t banks_cap, char *arms, size_t arms_cap,
                 char arms_digest[65]);
int vx_seat_check(const char *arms);
int vx_hint(void);

#endif
