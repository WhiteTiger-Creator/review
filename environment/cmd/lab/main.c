#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int lab_seat(int epoch, const char *banks_csv, const char *arms);
int lab_weave(const char *arms);
int lab_seal(const char *nv_path, const char *out_blob, const char *out_view);
int lab_synth(int epoch, const char *banks_csv, const char *arms, const char *nv_path,
              const char *out_blob, const char *out_view);
int lab_recover(void);
int lab_replay(const char *out_view);

static void usage(void) {
  fprintf(stderr,
          "usage:\n"
          "  lab seat --prep N --banks A,B --arms a,b\n"
          "  lab weave --arms a,b\n"
          "  lab seal --nv PATH --out-blob PATH --out-view PATH\n"
          "  lab synth --prep N --banks A,B --arms a,b --nv PATH --out-blob PATH --out-view PATH\n"
          "  lab recover\n"
          "  lab replay --out-view PATH\n");
}

int main(int argc, char **argv) {
  if (argc < 2) {
    usage();
    return 2;
  }
  if (strcmp(argv[1], "recover") == 0) return lab_recover() == 0 ? 0 : 1;
  if (strcmp(argv[1], "replay") == 0) {
    const char *ov = NULL;
    for (int i = 2; i < argc; i++) {
      if (strcmp(argv[i], "--out-view") == 0 && i + 1 < argc) ov = argv[++i];
    }
    if (!ov) {
      usage();
      return 2;
    }
    return lab_replay(ov) == 0 ? 0 : 1;
  }
  if (strcmp(argv[1], "seat") == 0) {
    int epoch = -1;
    const char *banks = NULL, *arms = NULL;
    for (int i = 2; i < argc; i++) {
      if (strcmp(argv[i], "--prep") == 0 && i + 1 < argc) epoch = atoi(argv[++i]);
      else if (strcmp(argv[i], "--banks") == 0 && i + 1 < argc) banks = argv[++i];
      else if (strcmp(argv[i], "--arms") == 0 && i + 1 < argc) arms = argv[++i];
    }
    if (epoch < 1 || !banks || !arms) {
      usage();
      return 2;
    }
    return lab_seat(epoch, banks, arms) == 0 ? 0 : 1;
  }
  if (strcmp(argv[1], "weave") == 0) {
    const char *arms = NULL;
    for (int i = 2; i < argc; i++) {
      if (strcmp(argv[i], "--arms") == 0 && i + 1 < argc) arms = argv[++i];
    }
    if (!arms) {
      usage();
      return 2;
    }
    return lab_weave(arms) == 0 ? 0 : 1;
  }
  if (strcmp(argv[1], "seal") == 0) {
    const char *nv = NULL, *ob = NULL, *ov = NULL;
    for (int i = 2; i < argc; i++) {
      if (strcmp(argv[i], "--nv") == 0 && i + 1 < argc) nv = argv[++i];
      else if (strcmp(argv[i], "--out-blob") == 0 && i + 1 < argc) ob = argv[++i];
      else if (strcmp(argv[i], "--out-view") == 0 && i + 1 < argc) ov = argv[++i];
    }
    if (!nv || !ob || !ov) {
      usage();
      return 2;
    }
    return lab_seal(nv, ob, ov) == 0 ? 0 : 1;
  }
  if (strcmp(argv[1], "synth") != 0) {
    usage();
    return 2;
  }
  int epoch = -1;
  const char *banks = NULL, *arms = NULL, *nv = NULL, *ob = NULL, *ov = NULL;
  for (int i = 2; i < argc; i++) {
    if (strcmp(argv[i], "--prep") == 0 && i + 1 < argc) epoch = atoi(argv[++i]);
    else if (strcmp(argv[i], "--banks") == 0 && i + 1 < argc) banks = argv[++i];
    else if (strcmp(argv[i], "--arms") == 0 && i + 1 < argc) arms = argv[++i];
    else if (strcmp(argv[i], "--nv") == 0 && i + 1 < argc) nv = argv[++i];
    else if (strcmp(argv[i], "--out-blob") == 0 && i + 1 < argc) ob = argv[++i];
    else if (strcmp(argv[i], "--out-view") == 0 && i + 1 < argc) ov = argv[++i];
  }
  if (epoch < 1 || !banks || !arms || !nv || !ob || !ov) {
    usage();
    return 2;
  }
  return lab_synth(epoch, banks, arms, nv, ob, ov) == 0 ? 0 : 1;
}
