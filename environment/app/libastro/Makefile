CC ?= gcc
CFLAGS ?= -O2 -std=c11 -fPIC -Wall -Wextra -Werror
LDFLAGS ?= -shared
SRC = src/leaps.c src/utc.c src/interp.c
OBJ = $(SRC:.c=.o)
all: libastrotime.so
libastrotime.so: $(OBJ)
	$(CC) $(LDFLAGS) -Wl,-soname,libastrotime.so.1 -o $@ $(OBJ) -lm
%.o: %.c include/astrotime.h
	$(CC) $(CFLAGS) -Iinclude -c $< -o $@
clean:
	rm -f $(OBJ) libastrotime.so
.PHONY: all clean
