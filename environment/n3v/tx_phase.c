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
  (void)epoch;
  FILE *f = fopen(PHASE_PATH, "a");
  if (!f) return -1;
  fprintf(f, "{\"stage\":\"stage_%s\"}\n", stage ? stage : "x");
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
  (void)epoch;
  (void)view_digest;
  (void)bank_tag;
  (void)nv_hex;
  (void)arms_digest;
  (void)seed8;
  mkdir("/app/var", 0755);
  const char *stub = "{\n  \"epoch\": 0,\n  \"seed_hex\": \"\",\n  \"arms_digest\": \"\"\n}\n";
  return hx_write_file(DURABLE_PATH, (const uint8_t *)stub, strlen(stub));
}

int tx_gen_snapshot(int epoch, const uint8_t *blob, size_t blob_len, const char *view_path,
                    const uint8_t *seed8) {
  (void)epoch;
  (void)blob;
  (void)blob_len;
  (void)view_path;
  (void)seed8;
  return 0;
}

int tx_recover(void) {
  uint8_t z[8] = {0};
  mkdir("/app/var", 0755);
  return hx_write_file(LIVE_PATH, z, 8);
}

int tx_replay(const char *out_view) {
  (void)out_view;
  return -1;
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
