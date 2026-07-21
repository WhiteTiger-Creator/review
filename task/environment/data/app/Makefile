CC = gcc
CFLAGS = -Wall -Wextra
LDFLAGS = -lmicrohttpd -lsqlite3

SOURCES = src/main.c src/routes.c
TARGET = notes_server

$(TARGET): $(SOURCES)
	$(CC) $(CFLAGS) -o $(TARGET) $(SOURCES) $(LDFLAGS)

clean:
	rm -f $(TARGET)
