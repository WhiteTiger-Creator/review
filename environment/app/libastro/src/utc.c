#define _GNU_SOURCE
#include "astrotime.h"
#include <stdio.h>
#include <string.h>
#include <time.h>

static void seterr(char *err, size_t n, const char *msg) { if (err && n) snprintf(err, n, "%s", msg); }

static int parse_parts(const char *s, struct tm *tmv, int *is_leap) {
    int y,mo,d,h,mi,se; char tail;
    if (sscanf(s, "%4d-%2d-%2dT%2d:%2d:%2dZ%c", &y,&mo,&d,&h,&mi,&se,&tail) != 6) return -1;
    if (mo < 1 || mo > 12 || d < 1 || d > 31 || h < 0 || h > 23 || mi < 0 || mi > 59 || se < 0 || se > 60) return -1;
    memset(tmv, 0, sizeof(*tmv));
    tmv->tm_year = y - 1900; tmv->tm_mon = mo - 1; tmv->tm_mday = d; tmv->tm_hour = h; tmv->tm_min = mi;
    *is_leap = (se == 60);
    tmv->tm_sec = *is_leap ? 59 : se;
    return 0;
}

static int offset_for_posix(const leap_table *table, int64_t posix, int *offset) {
    int found = 0;
    for (size_t i=0;i<table->count;i++) {
        if (table->entries[i].effective_posix <= posix) { *offset = table->entries[i].offset; found = 1; }
        else break;
    }
    return found ? 0 : -1;
}

int astro_utc_to_tai(const leap_table *table, const char *utc, int64_t *tai, char *err, size_t errlen) {
    struct tm tmv; int is_leap;
    if (parse_parts(utc, &tmv, &is_leap) != 0) { seterr(err, errlen, "invalid UTC timestamp"); return -1; }
    time_t base = timegm(&tmv);
    struct tm back;
    if (base == (time_t)-1 || !gmtime_r(&base, &back) || back.tm_year != tmv.tm_year || back.tm_mon != tmv.tm_mon || back.tm_mday != tmv.tm_mday || back.tm_hour != tmv.tm_hour || back.tm_min != tmv.tm_min || back.tm_sec != tmv.tm_sec) {
        seterr(err, errlen, "invalid UTC calendar date"); return -1;
    }
    if (!is_leap) {
        int offset;
        if (offset_for_posix(table, (int64_t)base, &offset) != 0) { seterr(err, errlen, "timestamp predates leap table"); return -1; }
        *tai = (int64_t)base + offset;
        return 0;
    }
    if (tmv.tm_hour != 23 || tmv.tm_min != 59) { seterr(err, errlen, "leap second must be 23:59:60Z"); return -1; }
    int64_t next_midnight = (int64_t)base + 1;
    int old_offset;
    if (offset_for_posix(table, (int64_t)base, &old_offset) != 0) { seterr(err, errlen, "timestamp predates leap table"); return -1; }
    int valid = 0;
    for (size_t i=0;i<table->count;i++) {
        if (table->entries[i].effective_posix == next_midnight && table->entries[i].offset == old_offset + 1) { valid = 1; break; }
    }
    if (!valid) { seterr(err, errlen, "timestamp is not a declared leap second"); return -1; }
    *tai = next_midnight + old_offset;
    return 0;
}

int astro_tai_to_utc(const leap_table *table, int64_t tai, char *out, size_t outlen, char *err, size_t errlen) {
    for (size_t i=1;i<table->count;i++) {
        int64_t boundary = table->entries[i].effective_posix;
        int old_offset = table->entries[i-1].offset;
        if (table->entries[i].offset == old_offset + 1 && tai == boundary + old_offset) {
            time_t prev = (time_t)(boundary - 1);
            struct tm tmv;
            if (!gmtime_r(&prev, &tmv) || strftime(out, outlen, "%Y-%m-%dT%H:%M:", &tmv) == 0) { seterr(err, errlen, "UTC formatting failed"); return -1; }
            size_t used = strlen(out);
            if (used + 4 > outlen) { seterr(err, errlen, "UTC buffer too small"); return -1; }
            memcpy(out + used, "60Z", 4);
            return 0;
        }
    }
    int chosen = -1;
    for (size_t i=0;i<table->count;i++) {
        int64_t tai_start = table->entries[i].effective_posix + table->entries[i].offset;
        if (tai >= tai_start) chosen = (int)i; else break;
    }
    if (chosen < 0) { seterr(err, errlen, "TAI instant predates leap table"); return -1; }
    time_t posix = (time_t)(tai - table->entries[chosen].offset);
    struct tm tmv;
    if (!gmtime_r(&posix, &tmv) || strftime(out, outlen, "%Y-%m-%dT%H:%M:%SZ", &tmv) == 0) { seterr(err, errlen, "UTC formatting failed"); return -1; }
    return 0;
}
