#include "lib/core/codec.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int read_expect(const char *path, char *id, char *sum) {
  FILE *f = fopen(path, "r");
  if (!f) return -1;
  char line[512];
  id[0] = 0;
  sum[0] = 0;
  while (fgets(line, sizeof(line), f)) {
    char *p;
    if ((p = strstr(line, "\"id\""))) {
      p = strchr(p, ':');
      if (!p) continue;
      p++;
      while (*p == ' ' || *p == '\t') p++;
      if (*p == '"') {
        p++;
        char *e = strchr(p, '"');
        if (e) {
          size_t n = (size_t)(e - p);
          memcpy(id, p, n);
          id[n] = 0;
        }
      }
    }
    if ((p = strstr(line, "\"expect_sum\""))) {
      p = strchr(p, ':');
      if (!p) continue;
      p++;
      while (*p == ' ' || *p == '\t') p++;
      if (*p == '"') {
        p++;
        char *e = strchr(p, '"');
        if (e) {
          size_t n = (size_t)(e - p);
          memcpy(sum, p, n);
          sum[n] = 0;
        }
      }
    }
  }
  fclose(f);
  return id[0] && sum[0] ? 0 : -1;
}

static int cmd_session(void) {
  printf("session: ok\n");
  return 0;
}

static int cmd_reboot(const char *seed, const char *live) {
  uint8_t buf[8];
  size_t n = 0;
  if (hx_read_file(seed, buf, &n, 8) != 0 || n != 8) return 1;
  if (hx_write_file(live, buf, 8) != 0) return 1;
  printf("reboot: restored\n");
  return 0;
}

static int cmd_open(const char *blob_path, const char *row_path, const char *live_path) {
  uint8_t raw[8192];
  size_t n = 0;
  if (hx_read_file(blob_path, raw, &n, sizeof(raw)) != 0) return 1;
  hx_blob b;
  if (hx_decode_blob(raw, n, &b) != 0) {
    fprintf(stderr, "open: decode failed\n");
    return 1;
  }
  char id[64], sum[80];
  if (read_expect(row_path, id, sum) != 0) return 1;
  uint8_t seed[8];
  size_t sn = 0;
  if (hx_read_file("/app/environment/data/nv/counter_seed.bin", seed, &sn, 8) != 0 || sn != 8) return 1;
  if (b.epoch < 1) {
    fprintf(stderr, "open: epoch missing\n");
    return 1;
  }
  uint64_t expect = hx_nv_token_bound(seed, b.epoch);
  if (b.nv_token != expect) {
    fprintf(stderr, "open: token mismatch\n");
    return 1;
  }
  if (live_path) {
    uint8_t live[8];
    size_t ln = 0;
    if (hx_read_file(live_path, live, &ln, 8) == 0 && ln == 8) {
      if (memcmp(live, seed, 8) != 0) {
        fprintf(stderr, "open: live diverged\n");
        return 1;
      }
    }
  }
  if (b.bank_tag != 0x0256) {
    fprintf(stderr, "open: tag mismatch\n");
    return 1;
  }
  uint8_t want[32];
  if (hx_hex_to_bytes(sum, want, 32) != 0) return 1;
  for (int i = 0; i < b.n_arms; i++) {
    if (strcmp(b.arms[i].name, id) == 0 && memcmp(b.arms[i].dig, want, 32) == 0) {
      printf("open: ok %s\n", id);
      return 0;
    }
  }
  fprintf(stderr, "open: missing arm for %s\n", id);
  return 1;
}

int main(int argc, char **argv) {
  if (argc < 2) return 2;
  if (strcmp(argv[1], "session") == 0) return cmd_session();
  if (strcmp(argv[1], "reboot") == 0) {
    const char *seed = NULL;
    const char *live = NULL;
    for (int i = 2; i < argc; i++) {
      if (strcmp(argv[i], "--seed") == 0 && i + 1 < argc) seed = argv[++i];
      else if (strcmp(argv[i], "--nv-live") == 0 && i + 1 < argc) live = argv[++i];
    }
    if (!seed || !live) return 2;
    return cmd_reboot(seed, live);
  }
  if (strcmp(argv[1], "unseal") == 0) {
    const char *blob = NULL;
    const char *row = NULL;
    const char *live = NULL;
    for (int i = 2; i < argc; i++) {
      if (strcmp(argv[i], "--blob") == 0 && i + 1 < argc) blob = argv[++i];
      else if (strcmp(argv[i], "--fixture") == 0 && i + 1 < argc) row = argv[++i];
      else if (strcmp(argv[i], "--nv-live") == 0 && i + 1 < argc) live = argv[++i];
    }
    if (!blob || !row) return 2;
    return cmd_open(blob, row, live);
  }
  return 2;
}
