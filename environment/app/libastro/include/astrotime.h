#ifndef ASTROTIME_H
#define ASTROTIME_H
#include <stddef.h>
#include <stdint.h>

typedef struct {
    int64_t effective_posix;
    int offset;
} leap_entry;

typedef struct {
    leap_entry *entries;
    size_t count;
} leap_table;

int astro_load_leaps(const char *path, leap_table *out, char *err, size_t errlen);
void astro_free_leaps(leap_table *table);
int astro_utc_to_tai(const leap_table *table, const char *utc, int64_t *tai, char *err, size_t errlen);
int astro_tai_to_utc(const leap_table *table, int64_t tai, char *out, size_t outlen, char *err, size_t errlen);
double astro_hermite(double y0, double m0, double y1, double m1, double t, double span);
double astro_phase_hermite(double deg0, double slope0, double deg1, double slope1, double t, double span);
double astro_wrap_degrees(double deg);
#endif
