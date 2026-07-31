#ifndef CELL_B_H
#define CELL_B_H

#include <stddef.h>
#include <stdint.h>

#ifndef CELL_PAD
#define CELL_PAD 4
#endif

typedef struct {
    uint32_t head;
    uint8_t pad[CELL_PAD];
    uint32_t tail;
} cell_b_t;

uint32_t cell_b_width(void);
size_t cell_b_tag(uint8_t *buf, size_t n);

#endif
