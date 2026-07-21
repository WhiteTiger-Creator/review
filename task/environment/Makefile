CC ?= cc
CFLAGS ?= -O2 -g -std=c11 -Wall -Wextra -Wshadow -Wconversion -Iinclude
LDFLAGS ?=

BIN_DIR := /usr/local/bin
OUT := $(BIN_DIR)/arena

SRC := \
  src/main.c \
  src/cli.c \
  src/tb_err.c \
  src/report.c \
  src/runtime/runtime.c \
  src/runtime/profile.c \
  src/runtime/script.c \
  src/core/idgen.c \
  src/core/queue.c \
  src/core/map_u64.c \
  src/core/vec_u64.c \
  src/core/vec_ev.c \
  src/io/fs.c \
  src/io/journal.c \
  src/logic/ingest.c \
  src/logic/settle.c \
  src/logic/nudge.c \
  src/logic/merge.c \
  src/logic/link.c

$(OUT): $(SRC) include/*.h include/runtime/*.h include/core/*.h include/io/*.h include/logic/*.h
	mkdir -p $(BIN_DIR)
	$(CC) $(CFLAGS) -o $@ $(SRC) $(LDFLAGS)

.PHONY: all clean
all: $(OUT)

clean:
	rm -f $(OUT)
