CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -std=c11
ROOT := $(abspath .)
BIN := /app/bin

SRCS_LAB := cmd/lab/main.c cmd/lab/driver.c \
	r4x/hx_fold.c r4x/hx_scan.c \
	m8q/zx_pack.c m8q/zx_copy.c \
	p2w/qx_bind.c p2w/qx_stat.c \
	n3v/tx_phase.c n3v/tx_stat.c \
	w7k/vx_seat.c w7k/vx_hint.c \
	lib/core/codec.c

SRCS_TPM := tools/lab_tpm.c lib/core/codec.c

.PHONY: all clean
all: $(BIN)/lab $(BIN)/lab_tpm

$(BIN)/lab: $(SRCS_LAB)
	@mkdir -p $(BIN)
	$(CC) $(CFLAGS) -I$(ROOT) -o $@ $(SRCS_LAB)

$(BIN)/lab_tpm: $(SRCS_TPM)
	@mkdir -p $(BIN)
	$(CC) $(CFLAGS) -I$(ROOT) -o $@ $(SRCS_TPM)

clean:
	rm -f $(BIN)/lab $(BIN)/lab_tpm
