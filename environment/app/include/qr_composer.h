#ifndef QR_COMPOSER_H
#define QR_COMPOSER_H

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#define QRT_MAX_VERSION 12
#define QRT_MAX_PAYLOADS 128
#define QRT_MAX_TEXT 512
#define QRT_MAX_SEGMENTS 64
#define QRT_MAX_ID 64
#define QRT_MAX_CODEWORDS 512
#define QRT_MAX_BLOCKS 16
#define QRT_MAX_SIZE 80

#define QRT_STATE_DIR "/app/state"
#define QRT_OUTPUT_DIR "/app/output/labels"
#define QRT_CONFIG_PATH "/app/config/composer.toml"

#define QRT_PAYLOADS_TSV QRT_STATE_DIR "/payloads.tsv"
#define QRT_PLANS_TSV QRT_STATE_DIR "/plans.tsv"
#define QRT_SEGMENTS_TSV QRT_STATE_DIR "/segments.tsv"
#define QRT_CODEWORDS_TSV QRT_STATE_DIR "/codewords.tsv"
#define QRT_BLOCKS_TSV QRT_STATE_DIR "/blocks.tsv"
#define QRT_STREAMS_TSV QRT_STATE_DIR "/streams.tsv"
#define QRT_TOURNAMENT_TSV QRT_STATE_DIR "/tournament.tsv"
#define QRT_MANIFEST_PATH QRT_OUTPUT_DIR "/label-run-manifest.json"

enum { QRT_MODE_NUMERIC = 0, QRT_MODE_ALNUM = 1, QRT_MODE_BYTE = 2 };

typedef struct {
    char batch_id[QRT_MAX_ID];
    char payload_id[QRT_MAX_ID];
    char ecc_level; /* 'L','M','Q','H' */
    char text[QRT_MAX_TEXT];
    int text_len;
} qrt_payload;

typedef struct {
    int mode;
    int char_count;
    int bit_count;
} qrt_segment;

typedef struct {
    int version;
    int cci_class;
    int total_bits;
    int segment_count;
    qrt_segment segments[QRT_MAX_SEGMENTS];
} qrt_plan;

typedef struct {
    int ec_per_block;
    int g1_blocks;
    int g1_data;
    int g2_blocks;
    int g2_data;
} qrt_block_spec;

/* ---- tables (tables.c) ---- */
extern const qrt_block_spec qrt_ecc_blocks[QRT_MAX_VERSION + 1][4];
extern const int qrt_alignment_centers[QRT_MAX_VERSION + 1][4]; /* -1 terminated */
extern const int qrt_remainder_bits[QRT_MAX_VERSION + 1];
int qrt_ecc_index(char level);
int qrt_ecc_format_bits(char level);
int qrt_symbol_size(int version);
int qrt_data_capacity_bits(int version, char level);

/* ---- util.c ---- */
void qrt_die(const char *fmt, ...);
void qrt_ensure_dir(const char *path);
char *qrt_read_file(const char *path, size_t *out_len);
void qrt_write_file(const char *path, const char *data, size_t len);
void qrt_hex_encode(const uint8_t *data, int len, char *out);
int qrt_hex_decode(const char *hex, uint8_t *out, int max);
int qrt_split_tsv(char *line, char **fields, int max_fields);

/* ---- sha256.c ---- */
void qrt_sha256_hex(const uint8_t *data, size_t len, char out[65]);

/* ---- config.c ---- */
void qrt_config_inbox(char *out, size_t cap);
int qrt_config_module_scale(void);
int qrt_config_quiet_modules(void);

/* ---- payload staging ---- */
int qrt_load_payloads(qrt_payload *out, int max);

/* ---- plan stage ---- */
int qrt_cci_width(int mode, int cci_class);
int qrt_segment_data_bits(int mode, int count);
int qrt_plan_symbol(const qrt_payload *p, qrt_plan *out);
int qrt_load_plan(const char *batch_id, const char *payload_id, qrt_plan *out);

/* ---- gf256 / RS ---- */
void qrt_gf_init(void);
uint8_t qrt_gf_mul(uint8_t a, uint8_t b);
uint8_t qrt_gf_exp(int i);
void qrt_rs_generator(int degree, uint8_t *out /* degree+1, MSB first */);
void qrt_rs_remainder(const uint8_t *data, int len, int degree, uint8_t *out);

/* ---- matrix ---- */
typedef struct {
    int size;
    uint8_t grid[QRT_MAX_SIZE][QRT_MAX_SIZE];
    uint8_t func[QRT_MAX_SIZE][QRT_MAX_SIZE];
} qrt_matrix;

void qrt_build_function_grid(int version, qrt_matrix *m);
void qrt_place_data(qrt_matrix *m, const uint8_t *stream, int stream_len, int version);
int qrt_mask_condition(int mask, int r, int c);
int qrt_format_info_bits(char level, int mask);
int qrt_version_info_bits(int version);
void qrt_apply_mask_and_format(const qrt_matrix *base, qrt_matrix *out, int mask, char level);
void qrt_matrix_sha256(const qrt_matrix *m, char out[65]);

/* ---- penalties ---- */
int qrt_penalty_runs(const qrt_matrix *m);
int qrt_penalty_blocks(const qrt_matrix *m);
int qrt_penalty_finder(const qrt_matrix *m);
int qrt_penalty_balance(const qrt_matrix *m);

/* ---- subcommands ---- */
int qrt_cmd_init_store(void);
int qrt_cmd_ingest(void);
int qrt_cmd_plan(void);
int qrt_cmd_assemble(void);
int qrt_cmd_protect(void);
int qrt_cmd_interleave(void);
int qrt_cmd_tournament(void);
int qrt_cmd_emit(void);
int qrt_cmd_status(void);

#endif
