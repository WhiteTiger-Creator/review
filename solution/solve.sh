#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/verifier/bin:/app/bin:/usr/local/bin:${PATH:-}"

cat > "/app/environment/r4x/hx_fold.c" <<'EOF'
#include "r4x/types.h"
#include "lib/core/codec.h"
#include <string.h>

int hx_fold(const uint8_t *banks, size_t n, uint8_t *out, size_t *out_len) {
  if (n < 6 || banks[0] != 0x4D || banks[1] != 0x52) return -1;
  size_t o = 2;
  size_t alen = ((size_t)banks[o] << 8) | banks[o + 1];
  o += 2;
  if (o + alen > n) return -1;
  const uint8_t *a = banks + o;
  o += alen;
  if (o + 2 > n) return -1;
  size_t blen = ((size_t)banks[o] << 8) | banks[o + 1];
  o += 2;
  if (o + blen > n) return -1;
  const uint8_t *b = banks + o;

  const uint8_t *pick = NULL;
  size_t plen = 0;
  if (blen >= 4) {
    uint16_t tagb = ((uint16_t)b[0] << 8) | b[1];
    if (tagb == 0x0256) { pick = b; plen = blen; }
  }
  if (!pick && alen >= 4) {
    uint16_t taga = ((uint16_t)a[0] << 8) | a[1];
    if (taga == 0x0256) { pick = a; plen = alen; }
  }
  if (!pick) {
    pick = blen ? b : a;
    plen = blen ? blen : alen;
  }
  if (plen < 4) return -1;
  memcpy(out, pick, plen);
  *out_len = plen;
  return 0;
}

int RunFold(const uint8_t *banks, size_t n, uint8_t *out, size_t *out_len) {
  return hx_fold(banks, n, out, out_len);
}
EOF

cat > "/app/environment/m8q/zx_pack.c" <<'EOF'
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
    for (int i = 0; i < n; i++) {
      if (strcmp(parsed[i].name, start) == 0) {
        if (b.n_arms < HX_MAX_ARMS) b.arms[b.n_arms++] = parsed[i];
        break;
      }
    }
    *p = save;
    if (*p == ',') p++;
  }
  if (b.n_arms < 1) return -1;

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
EOF

cat > "/app/environment/p2w/qx_bind.c" <<'EOF'
#include "p2w/bind.h"
#include "lib/core/codec.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

int vx_seat_load(int *epoch, char *banks_csv, size_t banks_cap, char *arms, size_t arms_cap,
                 char arms_digest[65]);
int tx_durable_write(int epoch, const char *view_digest, const char *bank_tag,
                     const char *nv_hex, const char *arms_digest, const uint8_t *seed8);
int tx_gen_snapshot(int epoch, const uint8_t *blob, size_t blob_len, const char *view_path,
                    const uint8_t *seed8);
int tx_phase_mark(const char *stage, int epoch);
int tx_phase_digest(char out64[65]);

static int read_prep_epoch(void) {
  FILE *f = fopen("/app/var/prep_epoch", "r");
  if (!f) return 1;
  int e = 1;
  if (fscanf(f, "%d", &e) != 1) e = 1;
  fclose(f);
  return e < 1 ? 1 : e;
}

int qx_bind(const uint8_t *packed, size_t n, const char *nv_path, const char *out_blob, const char *out_view) {
  hx_blob b;
  if (hx_decode_blob(packed, n, &b) != 0) return -1;

  uint8_t seed[8];
  size_t sn = 0;
  if (hx_read_file(nv_path, seed, &sn, 8) != 0 || sn != 8) return -1;

  int epoch = read_prep_epoch();
  b.epoch = (uint32_t)epoch;
  b.nv_token = hx_nv_token_bound(seed, b.epoch);

  uint8_t out[8192];
  size_t out_len = 0;
  if (hx_encode_blob(&b, out, &out_len, sizeof(out)) != 0) return -1;
  if (hx_write_file(out_blob, out, out_len) != 0) return -1;

  mkdir("/app/var", 0755);
  if (hx_write_file("/app/var/nv_live.bin", seed, 8) != 0) return -1;

  char digest[65];
  hx_sha256_hex(out, out_len, digest);

  char bank_s[16];
  if (b.bank_tag == 0x0256) snprintf(bank_s, sizeof(bank_s), "sha256");
  else if (b.bank_tag == 0x00a1) snprintf(bank_s, sizeof(bank_s), "sha1");
  else snprintf(bank_s, sizeof(bank_s), "%04x", b.bank_tag);

  char nvhex[32];
  snprintf(nvhex, sizeof(nvhex), "%llx", (unsigned long long)b.nv_token);

  int se = 0;
  char banks[512], arms[256], arms_dig[65];
  if (vx_seat_load(&se, banks, sizeof(banks), arms, sizeof(arms), arms_dig) != 0) return -1;

  if (tx_phase_mark("bind", epoch) != 0) return -1;
  char phase_d[65];
  if (tx_phase_digest(phase_d) != 0) return -1;

  char lineage_src[768];
  snprintf(lineage_src, sizeof(lineage_src), "%s|%s|%s|%d|%s", bank_s, nvhex, digest, epoch, arms_dig);
  char lineage[65];
  hx_sha256_hex((const uint8_t *)lineage_src, strlen(lineage_src), lineage);

  if (tx_durable_write(epoch, digest, bank_s, nvhex, arms_dig, seed) != 0) return -1;

  FILE *f = fopen(out_view, "w");
  if (!f) return -1;
  fprintf(f, "{\n  \"arms\": [\n");
  for (int i = 0; i < b.n_arms; i++) {
    char sum[65];
    hx_bytes_to_hex(b.arms[i].dig, 32, sum);
    fprintf(f, "    {\"name\": \"%s\", \"sum\": \"%s\"}%s\n", b.arms[i].name, sum,
            (i + 1 < b.n_arms) ? "," : "");
  }
  fprintf(f,
          "  ],\n"
          "  \"byte_len\": %zu,\n"
          "  \"view_digest\": \"%s\",\n"
          "  \"nv_token\": \"%s\",\n"
          "  \"bank_tag\": \"%s\",\n"
          "  \"epoch\": %d,\n"
          "  \"arms_digest\": \"%s\",\n"
          "  \"sync_label\": \"settled\",\n"
          "  \"phase_digest\": \"%s\",\n"
          "  \"lineage_hex\": \"%s\"\n"
          "}\n",
          out_len, digest, nvhex, bank_s, epoch, arms_dig, phase_d, lineage);
  fclose(f);

  if (tx_gen_snapshot(epoch, out, out_len, out_view, seed) != 0) return -1;
  return 0;
}

int RunBind(const uint8_t *packed, size_t n, const char *nv_path, const char *out_blob, const char *out_view) {
  return qx_bind(packed, n, nv_path, out_blob, out_view);
}
EOF

cat > "/app/environment/w7k/vx_seat.c" <<'EOF'
#include "w7k/seat.h"
#include "lib/core/codec.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#define SEAT_PATH "/app/var/seat.lock"

int vx_seat_pin(int epoch, const char *banks_csv, const char *arms) {
  mkdir("/app/var", 0755);
  char dig[65];
  hx_sha256_hex((const uint8_t *)(arms ? arms : ""), arms ? strlen(arms) : 0, dig);
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
  char want[65];
  hx_sha256_hex((const uint8_t *)(arms ? arms : ""), arms ? strlen(arms) : 0, want);
  if (strcmp(dig, want) != 0) return -1;
  return 0;
}

int RunSeatPin(int epoch, const char *banks_csv, const char *arms) {
  return vx_seat_pin(epoch, banks_csv, arms);
}
int RunSeatCheck(const char *arms) { return vx_seat_check(arms); }
EOF

cat > "/app/environment/n3v/tx_phase.c" <<'EOF'
#include "n3v/phase.h"
#include "lib/core/codec.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#define PHASE_PATH "/app/var/phase.jsonl"
#define DURABLE_PATH "/app/var/durable.json"
#define LIVE_PATH "/app/var/nv_live.bin"
#define GENS_ROOT "/app/var/gens"

int tx_phase_reset(void) {
  mkdir("/app/var", 0755);
  FILE *f = fopen(PHASE_PATH, "w");
  if (!f) return -1;
  fclose(f);
  return 0;
}

int tx_phase_mark(const char *stage, int epoch) {
  FILE *f = fopen(PHASE_PATH, "a");
  if (!f) return -1;
  fprintf(f, "{\"stage\":\"%s\",\"epoch\":%d}\n", stage ? stage : "x", epoch);
  fclose(f);
  return 0;
}

int tx_phase_digest(char out64[65]) {
  uint8_t buf[8192];
  size_t n = 0;
  if (hx_read_file(PHASE_PATH, buf, &n, sizeof(buf)) != 0) {
    memset(out64, '0', 64);
    out64[64] = 0;
    return -1;
  }
  hx_sha256_hex(buf, n, out64);
  return 0;
}

int tx_durable_write(int epoch, const char *view_digest, const char *bank_tag,
                     const char *nv_hex, const char *arms_digest, const uint8_t *seed8) {
  mkdir("/app/var", 0755);
  char seed_hex[17];
  hx_bytes_to_hex(seed8, 8, seed_hex);
  FILE *f = fopen(DURABLE_PATH, "w");
  if (!f) return -1;
  fprintf(f,
          "{\n"
          "  \"epoch\": %d,\n"
          "  \"view_digest\": \"%s\",\n"
          "  \"bank_tag\": \"%s\",\n"
          "  \"nv_token\": \"%s\",\n"
          "  \"arms_digest\": \"%s\",\n"
          "  \"seed_hex\": \"%s\"\n"
          "}\n",
          epoch, view_digest, bank_tag, nv_hex, arms_digest, seed_hex);
  fclose(f);
  return 0;
}

int tx_gen_snapshot(int epoch, const uint8_t *blob, size_t blob_len, const char *view_path,
                    const uint8_t *seed8) {
  char dir[256];
  snprintf(dir, sizeof(dir), "%s/%d", GENS_ROOT, epoch);
  char cmd[512];
  snprintf(cmd, sizeof(cmd), "mkdir -p %s", dir);
  if (system(cmd) != 0) return -1;
  char path[512];
  snprintf(path, sizeof(path), "%s/blob.bin", dir);
  if (hx_write_file(path, blob, blob_len) != 0) return -1;
  snprintf(path, sizeof(path), "%s/seed.bin", dir);
  if (hx_write_file(path, seed8, 8) != 0) return -1;
  uint8_t view[8192];
  size_t vn = 0;
  if (hx_read_file(view_path, view, &vn, sizeof(view)) != 0) return -1;
  snprintf(path, sizeof(path), "%s/view.json", dir);
  if (hx_write_file(path, view, vn) != 0) return -1;
  uint8_t phase[8192];
  size_t pn = 0;
  if (hx_read_file(PHASE_PATH, phase, &pn, sizeof(phase)) == 0) {
    snprintf(path, sizeof(path), "%s/phase.jsonl", dir);
    if (hx_write_file(path, phase, pn) != 0) return -1;
  }
  return 0;
}

int tx_recover(void) {
  mkdir("/app/var", 0755);
  /* prefer generation snapshot for current prep epoch */
  int epoch = 1;
  FILE *pe = fopen("/app/var/prep_epoch", "r");
  if (pe) {
    if (fscanf(pe, "%d", &epoch) != 1) epoch = 1;
    fclose(pe);
  }
  char path[512];
  snprintf(path, sizeof(path), "%s/%d/seed.bin", GENS_ROOT, epoch);
  uint8_t seed[8];
  size_t n = 0;
  if (hx_read_file(path, seed, &n, 8) == 0 && n == 8) {
    return hx_write_file(LIVE_PATH, seed, 8);
  }
  /* fallback: durable seed_hex */
  uint8_t raw[4096];
  size_t rn = 0;
  if (hx_read_file(DURABLE_PATH, raw, &rn, sizeof(raw)) != 0 || rn < 8) return -1;
  raw[rn < sizeof(raw) ? rn : sizeof(raw) - 1] = 0;
  const char *p = strstr((const char *)raw, "\"seed_hex\"");
  if (!p) return -1;
  p = strchr(p, ':');
  if (!p) return -1;
  p++;
  while (*p == ' ' || *p == '\t') p++;
  if (*p != '"') return -1;
  p++;
  char hex[17];
  size_t hi = 0;
  while (*p && *p != '"' && hi < 16) hex[hi++] = *p++;
  hex[hi] = 0;
  if (hi != 16) return -1;
  if (hx_hex_to_bytes(hex, seed, 8) != 0) return -1;
  return hx_write_file(LIVE_PATH, seed, 8);
}

int tx_replay(const char *out_view) {
  int epoch = 1;
  FILE *pe = fopen("/app/var/prep_epoch", "r");
  if (pe) {
    if (fscanf(pe, "%d", &epoch) != 1) epoch = 1;
    fclose(pe);
  }
  char path[512];
  snprintf(path, sizeof(path), "%s/%d/view.json", GENS_ROOT, epoch);
  uint8_t view[8192];
  size_t vn = 0;
  if (hx_read_file(path, view, &vn, sizeof(view)) != 0) return -1;
  return hx_write_file(out_view, view, vn);
}

int RunPhaseMark(const char *stage, int epoch) { return tx_phase_mark(stage, epoch); }
int RunDurable(int epoch, const char *view_digest, const char *bank_tag, const char *nv_hex,
               const char *arms_digest, const uint8_t *seed8) {
  return tx_durable_write(epoch, view_digest, bank_tag, nv_hex, arms_digest, seed8);
}
int RunGenSnap(int epoch, const uint8_t *blob, size_t blob_len, const char *view_path,
               const uint8_t *seed8) {
  return tx_gen_snapshot(epoch, blob, blob_len, view_path, seed8);
}
int RunRecover(void) { return tx_recover(); }
int RunReplay(const char *out_view) { return tx_replay(out_view); }
EOF

bash /app/environment/tools/mk_all.sh
mkdir -p /app/output /app/var
# Smoke the rebuilt synth path so a silent link/path failure cannot ship.
/app/bin/lab synth \
  --prep 7 \
  --banks /app/environment/data/banks/sha1.json,/app/environment/data/banks/sha256.json \
  --arms alpha,bravo,charlie \
  --nv /app/environment/data/nv/counter_seed.bin \
  --out-blob /app/output/pol_blob.bin \
  --out-view /app/output/settle_view.json
