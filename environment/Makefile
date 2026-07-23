CC = gcc
CFLAGS = -O2 -Iinclude
LDLIBS = -ldmumps_seq -lmumps_common_seq -lpord_seq -lmpiseq_seq -llapack -lblas -lgfortran -lm

SRC = src/main.c src/mtxread.c src/vecgen.c src/query.c src/counter.c

mode_census: $(SRC)
	$(CC) $(CFLAGS) $(SRC) -o mode_census $(LDLIBS)

clean:
	rm -f mode_census
