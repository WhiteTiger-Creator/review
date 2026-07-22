#ifndef N3V_PHASE_H
#define N3V_PHASE_H
#include <stddef.h>
#include <stdint.h>

int tx_phase_reset(void);
int tx_phase_digest(char out64[65]);
int tx_stat_hint(void);

#endif
