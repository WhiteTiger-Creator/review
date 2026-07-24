#include "qr_composer.h"

#include <string.h>
#include <sys/stat.h>

int qrt_cmd_init_store(void) {
    qrt_ensure_dir(QRT_STATE_DIR);
    qrt_ensure_dir(QRT_OUTPUT_DIR);
    printf("initialized state and output directories\n");
    return 0;
}

static int file_exists(const char *path) {
    struct stat st;
    return stat(path, &st) == 0;
}

int qrt_cmd_status(void) {
    static const struct {
        const char *label;
        const char *path;
    } items[] = {
        {"payloads", QRT_PAYLOADS_TSV},   {"plans", QRT_PLANS_TSV},
        {"segments", QRT_SEGMENTS_TSV},   {"codewords", QRT_CODEWORDS_TSV},
        {"blocks", QRT_BLOCKS_TSV},       {"streams", QRT_STREAMS_TSV},
        {"tournament", QRT_TOURNAMENT_TSV}, {"manifest", QRT_MANIFEST_PATH},
    };
    for (size_t i = 0; i < sizeof(items) / sizeof(items[0]); i++)
        printf("%s: %s\n", items[i].label, file_exists(items[i].path) ? "present" : "missing");
    return 0;
}

static void usage(void) {
    fprintf(stderr,
            "usage: qr-composer <command>\n"
            "commands:\n"
            "  init-store           create state and output directories\n"
            "  ingest-shipbatches   load shipbatch payloads into staging\n"
            "  plan-symbols         segmentation DP and version fixpoint\n"
            "  assemble-codewords   encode bitstream and pad codewords\n"
            "  protect-blocks       split blocks and compute RS ECC\n"
            "  interleave-streams   round-robin interleave transmission stream\n"
            "  run-mask-tournament  score all eight masks and pick winner\n"
            "  emit-labels          render PGM labels and run manifest\n"
            "  status               show pipeline stage artifacts\n");
}

int main(int argc, char **argv) {
    if (argc != 2) {
        usage();
        return 2;
    }
    qrt_gf_init();
    const char *cmd = argv[1];
    if (strcmp(cmd, "init-store") == 0) return qrt_cmd_init_store();
    if (strcmp(cmd, "ingest-shipbatches") == 0) return qrt_cmd_ingest();
    if (strcmp(cmd, "plan-symbols") == 0) return qrt_cmd_plan();
    if (strcmp(cmd, "assemble-codewords") == 0) return qrt_cmd_assemble();
    if (strcmp(cmd, "protect-blocks") == 0) return qrt_cmd_protect();
    if (strcmp(cmd, "interleave-streams") == 0) return qrt_cmd_interleave();
    if (strcmp(cmd, "run-mask-tournament") == 0) return qrt_cmd_tournament();
    if (strcmp(cmd, "emit-labels") == 0) return qrt_cmd_emit();
    if (strcmp(cmd, "status") == 0) return qrt_cmd_status();
    usage();
    return 2;
}
