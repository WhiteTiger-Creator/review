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
  uint64_t tok = 0;
  for (int i = 0; i < 8; i++) tok = (tok << 8) | seed[i];
  b.nv_token = tok;
  b.epoch = 0;

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
  if (vx_seat_load(&se, banks, sizeof(banks), arms, sizeof(arms), arms_dig) != 0) {
    arms_dig[0] = 0;
  }

  char phase_d[65];
  memset(phase_d, '0', 64);
  phase_d[64] = 0;
  (void)tx_durable_write(epoch, digest, bank_s, nvhex, arms_dig, seed);
  (void)tx_gen_snapshot(epoch, out, out_len, out_view, seed);

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
          "  \"sync_label\": \"partial\",\n"
          "  \"phase_digest\": \"%s\",\n"
          "  \"lineage_hex\": \"%s\"\n"
          "}\n",
          out_len, digest, nvhex, bank_s, epoch, arms_dig, phase_d, phase_d);
  fclose(f);
  return 0;
}

int RunBind(const uint8_t *packed, size_t n, const char *nv_path, const char *out_blob, const char *out_view) {
  return qx_bind(packed, n, nv_path, out_blob, out_view);
}
