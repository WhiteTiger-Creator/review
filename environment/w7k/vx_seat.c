#include "w7k/seat.h"
#include "lib/core/codec.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#define SEAT_PATH "/app/var/seat.lock"

int vx_seat_pin(int epoch, const char *banks_csv, const char *arms) {
  mkdir("/app/var", 0755);
  char bogus[32];
  snprintf(bogus, sizeof(bogus), "%zu", arms ? strlen(arms) : 0);
  char dig[65];
  hx_sha256_hex((const uint8_t *)bogus, strlen(bogus), dig);
  FILE *f = fopen(SEAT_PATH, "w");
  if (!f) return -1;
  fprintf(f,
          "{\n"
          "  \"epoch\": %d,\n"
          "  \"banks\": \"%s\",\n"
          "  \"arms\": \"%s\",\n"
          "  \"arms_digest\": \"%s\"\n"
          "}\n",
          epoch, banks_csv ? banks_csv : "", arms ? arms : "", dig);
  fclose(f);
  FILE *pe = fopen("/app/var/prep_epoch", "w");
  if (!pe) return -1;
  fprintf(pe, "%d\n", epoch);
  fclose(pe);
  return 0;
}

int vx_seat_load(int *epoch, char *banks_csv, size_t banks_cap, char *arms, size_t arms_cap,
                 char arms_digest[65]) {
  uint8_t raw[2048];
  size_t n = 0;
  if (hx_read_file(SEAT_PATH, raw, &n, sizeof(raw) - 1) != 0) return -1;
  raw[n] = 0;
  const char *s = (const char *)raw;
  *epoch = 1;
  banks_csv[0] = 0;
  arms[0] = 0;
  arms_digest[0] = 0;
  const char *p;
  if ((p = strstr(s, "\"epoch\""))) {
    p = strchr(p, ':');
    if (p) *epoch = atoi(p + 1);
  }
  if ((p = strstr(s, "\"banks\""))) {
    p = strchr(p, ':');
    if (p) {
      p++;
      while (*p == ' ' || *p == '\t') p++;
      if (*p == '"') {
        p++;
        size_t i = 0;
        while (*p && *p != '"' && i + 1 < banks_cap) banks_csv[i++] = *p++;
        banks_csv[i] = 0;
      }
    }
  }
  if ((p = strstr(s, "\"arms\""))) {
    p = strchr(p, ':');
    if (p) {
      p++;
      while (*p == ' ' || *p == '\t') p++;
      if (*p == '"') {
        p++;
        size_t i = 0;
        while (*p && *p != '"' && i + 1 < arms_cap) arms[i++] = *p++;
        arms[i] = 0;
      }
    }
  }
  if ((p = strstr(s, "\"arms_digest\""))) {
    p = strchr(p, ':');
    if (p) {
      p++;
      while (*p == ' ' || *p == '\t') p++;
      if (*p == '"') {
        p++;
        size_t i = 0;
        while (*p && *p != '"' && i < 64) arms_digest[i++] = *p++;
        arms_digest[i] = 0;
      }
    }
  }
  return 0;
}

int vx_seat_check(const char *arms) {
  int epoch = 0;
  char banks[512], seated[256], dig[65];
  if (vx_seat_load(&epoch, banks, sizeof(banks), seated, sizeof(seated), dig) != 0) return -1;
  if (strcmp(seated, arms ? arms : "") != 0) return -1;
  (void)dig;
  return 0;
}

int RunSeatPin(int epoch, const char *banks_csv, const char *arms) {
  return vx_seat_pin(epoch, banks_csv, arms);
}
int RunSeatCheck(const char *arms) { return vx_seat_check(arms); }
