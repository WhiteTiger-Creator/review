#ifndef CELL_A_H
#define CELL_A_H

#include <stddef.h>
#include <stdint.h>

#ifndef CELL_PAD
#define CELL_PAD 4
#endif

#ifndef TAG_MODE
#define TAG_MODE 1
#endif

typedef struct {
    uint32_t head;
    uint8_t body[8 + CELL_PAD];
} cell_a_t;

uint32_t cell_a_width(void);
uint32_t cell_a_align(void);
size_t cell_a_tag(uint8_t *buf, size_t n);

#endif
