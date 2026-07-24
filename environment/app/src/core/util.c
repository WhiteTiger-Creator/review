#include "qr_composer.h"

#include <errno.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>

void qrt_die(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    fprintf(stderr, "qr-composer: ");
    vfprintf(stderr, fmt, ap);
    fprintf(stderr, "\n");
    va_end(ap);
    exit(1);
}

void qrt_ensure_dir(const char *path) {
    char buf[512];
    size_t len = strlen(path);
    if (len >= sizeof(buf)) qrt_die("path too long: %s", path);
    memcpy(buf, path, len + 1);
    for (size_t i = 1; i < len; i++) {
        if (buf[i] == '/') {
            buf[i] = '\0';
            if (mkdir(buf, 0755) != 0 && errno != EEXIST) qrt_die("mkdir %s: %s", buf, strerror(errno));
            buf[i] = '/';
        }
    }
    if (mkdir(buf, 0755) != 0 && errno != EEXIST) qrt_die("mkdir %s: %s", buf, strerror(errno));
}

char *qrt_read_file(const char *path, size_t *out_len) {
    FILE *fh = fopen(path, "rb");
    if (!fh) return NULL;
    fseek(fh, 0, SEEK_END);
    long size = ftell(fh);
    fseek(fh, 0, SEEK_SET);
    if (size < 0) {
        fclose(fh);
        return NULL;
    }
    char *buf = malloc((size_t)size + 1);
    if (!buf) qrt_die("out of memory reading %s", path);
    size_t got = fread(buf, 1, (size_t)size, fh);
    fclose(fh);
    buf[got] = '\0';
    if (out_len) *out_len = got;
    return buf;
}

void qrt_write_file(const char *path, const char *data, size_t len) {
    char tmp[600];
    snprintf(tmp, sizeof(tmp), "%s.tmp", path);
    FILE *fh = fopen(tmp, "wb");
    if (!fh) qrt_die("open %s: %s", tmp, strerror(errno));
    if (len && fwrite(data, 1, len, fh) != len) qrt_die("write %s failed", tmp);
    fclose(fh);
    if (rename(tmp, path) != 0) qrt_die("rename %s -> %s: %s", tmp, path, strerror(errno));
}

static const char HEX[] = "0123456789abcdef";

void qrt_hex_encode(const uint8_t *data, int len, char *out) {
    for (int i = 0; i < len; i++) {
        out[2 * i] = HEX[data[i] >> 4];
        out[2 * i + 1] = HEX[data[i] & 0xF];
    }
    out[2 * len] = '\0';
}

static int hex_val(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int qrt_hex_decode(const char *hex, uint8_t *out, int max) {
    int n = 0;
    while (hex[0] && hex[1]) {
        int hi = hex_val(hex[0]);
        int lo = hex_val(hex[1]);
        if (hi < 0 || lo < 0) break;
        if (n >= max) return -1;
        out[n++] = (uint8_t)((hi << 4) | lo);
        hex += 2;
    }
    return n;
}

int qrt_split_tsv(char *line, char **fields, int max_fields) {
    int n = 0;
    char *p = line;
    while (n < max_fields) {
        fields[n++] = p;
        char *tab = strchr(p, '\t');
        if (!tab) break;
        *tab = '\0';
        p = tab + 1;
    }
    char *nl = strchr(fields[n - 1], '\n');
    if (nl) *nl = '\0';
    return n;
}
