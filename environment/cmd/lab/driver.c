#include "lib/core/codec.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

int RunFold(const uint8_t *banks, size_t n, uint8_t *out, size_t *out_len);
int RunPack(const uint8_t *frag, size_t frag_len, const char *arms, uint8_t *out, size_t *out_len);
int RunBind(const uint8_t *packed, size_t n, const char *nv_path, const char *out_blob, const char *out_view);
int RunSeatPin(int epoch, const char *banks_csv, const char *arms);
int RunSeatCheck(const char *arms);
int RunRecover(void);
int RunReplay(const char *out_view);
int tx_phase_reset(void);
int tx_phase_mark(const char *stage, int epoch);

static int load_budget(size_t *max_bytes) {
  FILE *f = fopen("/app/environment/data/lim/budgets.toml", "r");
  if (!f) return -1;
  char line[256];
  *max_bytes = 190;
  while (fgets(line, sizeof(line), f)) {
    if (strncmp(line, "max_blob_bytes", 14) == 0) {
      char *eq = strchr(line, '=');
      if (eq) *max_bytes = (size_t)strtoul(eq + 1, NULL, 10);
    }
  }
  fclose(f);
  return 0;
}

int lab_seat(int epoch, const char *banks_csv, const char *arms) {
  if (epoch < 1) return -1;
  if (tx_phase_reset() != 0) return -1;
  return RunSeatPin(epoch, banks_csv, arms);
}

int lab_weave(const char *arms) {
  if (RunSeatCheck(arms) != 0) {
    fprintf(stderr, "seat mismatch\n");
    return -1;
  }
  int epoch = 1;
  char banks_csv[512], seated[256], dig[65];
  /* load banks from seat via seat check path already validated arms string */
  {
    FILE *f = fopen("/app/var/prep_epoch", "r");
    if (f) {
      if (fscanf(f, "%d", &epoch) != 1) epoch = 1;
      fclose(f);
    }
  }
  uint8_t raw[2048];
  size_t rn = 0;
  if (hx_read_file("/app/var/seat.lock", raw, &rn, sizeof(raw) - 1) != 0) return -1;
  raw[rn] = 0;
  banks_csv[0] = 0;
  const char *p = strstr((char *)raw, "\"banks\"");
  if (!p) return -1;
  p = strchr(p, ':');
  if (!p) return -1;
  p++;
  while (*p == ' ' || *p == '\t') p++;
  if (*p != '"') return -1;
  p++;
  size_t i = 0;
  while (*p && *p != '"' && i + 1 < sizeof(banks_csv)) banks_csv[i++] = *p++;
  banks_csv[i] = 0;
  (void)seated;
  (void)dig;

  char b1[512], b2[512];
  const char *comma = strchr(banks_csv, ',');
  if (!comma) return -1;
  size_t n1 = (size_t)(comma - banks_csv);
  if (n1 >= sizeof(b1)) return -1;
  memcpy(b1, banks_csv, n1);
  b1[n1] = 0;
  strncpy(b2, comma + 1, sizeof(b2) - 1);
  b2[sizeof(b2) - 1] = 0;

  uint8_t bank_a[8192], bank_b[8192], merged[16384], frag[8192], packed[8192];
  size_t alen = 0, blen = 0, mlen = 0, flen = 0, plen = 0;
  if (hx_load_json_bank(b1, 0x00a1, bank_a, &alen, sizeof(bank_a)) != 0) return -1;
  if (hx_load_json_bank(b2, 0x0256, bank_b, &blen, sizeof(bank_b)) != 0) return -1;
  if (hx_merge_bank_bufs(bank_a, alen, bank_b, blen, merged, &mlen, sizeof(merged)) != 0) return -1;

  if (RunFold(merged, mlen, frag, &flen) != 0) return -1;
  if (tx_phase_mark("fold", epoch) != 0) return -1;
  if (RunPack(frag, flen, arms, packed, &plen) != 0) return -1;
  if (tx_phase_mark("pack", epoch) != 0) return -1;

  size_t max_bytes = 190;
  load_budget(&max_bytes);
  if (plen > max_bytes) {
    fprintf(stderr, "packed exceeds max_blob_bytes (%zu > %zu)\n", plen, max_bytes);
    return -1;
  }
  mkdir("/app/var", 0755);
  return hx_write_file("/app/var/weave.bin", packed, plen);
}

int lab_seal(const char *nv_path, const char *out_blob, const char *out_view) {
  uint8_t packed[8192];
  size_t plen = 0;
  if (hx_read_file("/app/var/weave.bin", packed, &plen, sizeof(packed)) != 0 || plen < 8) return -1;
  return RunBind(packed, plen, nv_path, out_blob, out_view);
}

int lab_synth(int epoch, const char *banks_csv, const char *arms, const char *nv_path,
              const char *out_blob, const char *out_view) {
  if (lab_seat(epoch, banks_csv, arms) != 0) return -1;
  if (lab_weave(arms) != 0) return -1;
  return lab_seal(nv_path, out_blob, out_view);
}

int lab_recover(void) { return RunRecover(); }
int lab_replay(const char *out_view) { return RunReplay(out_view); }
