#define _GNU_SOURCE
#include "astrotime.h"
#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static void seterr(char *err, size_t n, const char *msg) {
    if (err && n) snprintf(err, n, "%s", msg);
}

static int parse_standard_utc(const char *s, int64_t *posix) {
    struct tm tmv;
    memset(&tmv, 0, sizeof(tmv));
    char *end = strptime(s, "%Y-%m-%dT%H:%M:%SZ", &tmv);
    if (!end || *end != '\0') return -1;
    if (tmv.tm_sec < 0 || tmv.tm_sec > 59) return -1;
    time_t t = timegm(&tmv);
    if (t == (time_t)-1) return -1;
    struct tm back;
    if (!gmtime_r(&t, &back)) return -1;
    if (back.tm_year != tmv.tm_year || back.tm_mon != tmv.tm_mon || back.tm_mday != tmv.tm_mday ||
        back.tm_hour != tmv.tm_hour || back.tm_min != tmv.tm_min || back.tm_sec != tmv.tm_sec) return -1;
    *posix = (int64_t)t;
    return 0;
}

int astro_load_leaps(const char *path, leap_table *out, char *err, size_t errlen) {
    memset(out, 0, sizeof(*out));
    FILE *f = fopen(path, "r");
    if (!f) { seterr(err, errlen, "cannot open leap table"); return -1; }
    size_t cap = 8;
    leap_entry *items = calloc(cap, sizeof(*items));
    if (!items) { fclose(f); seterr(err, errlen, "out of memory"); return -1; }
    char line[256];
    int last_offset = -9999;
    int64_t last_posix = INT64_MIN;
    while (fgets(line, sizeof(line), f)) {
        char *p = line;
        while (isspace((unsigned char)*p)) p++;
        if (*p == '#' || *p == '\0') continue;
        char stamp[64], extra[8];
        int offset;
        int fields = sscanf(p, "%63s %d %7s", stamp, &offset, extra);
        if (fields != 2) { free(items); fclose(f); seterr(err, errlen, "invalid leap table row"); return -1; }
        int64_t posix;
        if (parse_standard_utc(stamp, &posix) != 0 || strstr(stamp, "T00:00:00Z") == NULL) {
            free(items); fclose(f); seterr(err, errlen, "leap effective instant must be UTC midnight"); return -1;
        }
        if (posix <= last_posix || (last_offset != -9999 && (offset < last_offset || offset > last_offset + 1))) {
            free(items); fclose(f); seterr(err, errlen, "leap table must be strictly ordered with unit offset changes"); return -1;
        }
        if (out->count == cap) {
            cap *= 2;
            leap_entry *grown = realloc(items, cap * sizeof(*items));
            if (!grown) { free(items); fclose(f); seterr(err, errlen, "out of memory"); return -1; }
            items = grown;
        }
        items[out->count].effective_posix = posix;
        items[out->count].offset = offset;
        out->count++;
        last_posix = posix;
        last_offset = offset;
    }
    fclose(f);
    if (out->count == 0) { free(items); seterr(err, errlen, "empty leap table"); return -1; }
    out->entries = items;
    return 0;
}

void astro_free_leaps(leap_table *table) {
    free(table->entries);
    table->entries = NULL;
    table->count = 0;
}
