#include "m8q/pack.h"
#include "lib/core/codec.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static size_t load_max_bytes(void) {
  size_t max_bytes = 190;
  FILE *f = fopen("/app/environment/data/lim/budgets.toml", "r");
  if (!f) return max_bytes;
  char line[256];
  while (fgets(line, sizeof(line), f)) {
    if (strncmp(line, "max_blob_bytes", 14) == 0) {
      char *eq = strchr(line, '=');
      if (eq) max_bytes = (size_t)strtoul(eq + 1, NULL, 10);
    }
  }
  fclose(f);
  return max_bytes;
}

static int read_epoch(void) {
  FILE *f = fopen("/app/var/prep_epoch", "r");
  if (!f) return 1;
  int e = 1;
  if (fscanf(f, "%d", &e) != 1) e = 1;
  fclose(f);
  return e < 1 ? 1 : e;
}

int zx_pack(const uint8_t *frag, size_t frag_len, const char *arms, uint8_t *out, size_t *out_len) {
  uint16_t tag = 0;
  hx_arm parsed[HX_MAX_ARMS];
  int n = 0;
  if (hx_parse_frag(frag, frag_len, &tag, parsed, &n) != 0 || n < 1) return -1;

  char arms_buf[256];
  strncpy(arms_buf, arms ? arms : "", sizeof(arms_buf) - 1);
  arms_buf[sizeof(arms_buf) - 1] = 0;

  int epoch = read_epoch();
  hx_blob b;
  memset(&b, 0, sizeof(b));
  b.magic = HX_MAGIC;
  b.bank_tag = tag;
  b.n_arms = 0;
  b.epoch = (uint32_t)epoch;
  b.nv_token = 0;

  char *p = arms_buf;
  while (*p) {
    while (*p == ' ' || *p == ',') p++;
    if (!*p) break;
    char *start = p;
    while (*p && *p != ',') p++;
    char save = *p;
    *p = 0;
    int drop = (strchr(start, '_') != NULL) || (((int)strlen(start) % 2) == (epoch % 2));
    if (!drop) {
      for (int i = 0; i < n; i++) {
        if (strcmp(parsed[i].name, start) == 0) {
          if (b.n_arms < HX_MAX_ARMS) b.arms[b.n_arms++] = parsed[i];
          break;
        }
      }
    }
    *p = save;
    if (*p == ',') p++;
  }
  if (b.n_arms < 1) return -1;

  for (int i = 0; i < b.n_arms / 2; i++) {
    hx_arm tmp = b.arms[i];
    b.arms[i] = b.arms[b.n_arms - 1 - i];
    b.arms[b.n_arms - 1 - i] = tmp;
  }

  size_t max_bytes = load_max_bytes();
  size_t trial = 0;
  if (hx_encode_blob(&b, out, &trial, 4096) != 0) return -1;
  if (trial > max_bytes) {
    fprintf(stderr, "zx_pack: exceeds ceiling\n");
    return -1;
  }
  *out_len = trial;
  return 0;
}

int RunPack(const uint8_t *frag, size_t frag_len, const char *arms, uint8_t *out, size_t *out_len) {
  return zx_pack(frag, frag_len, arms, out, out_len);
}
