#include "routes.h"
#include "db.h"
#include <microhttpd.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <cjson/cJSON.h>

#define MAX_BODY_SIZE 65536

static char api_key[256] = {0};
static int api_key_loaded = 0;

static void ensure_api_key(void) {
    if (api_key_loaded) return;
    api_key_loaded = 1;
    FILE *f = fopen("/app/config/api.key", "r");
    if (!f) return;
    size_t len = fread(api_key, 1, sizeof(api_key) - 1, f);
    fclose(f);
    while (len > 0 && (api_key[len - 1] == '\n' || api_key[len - 1] == '\r'))
        api_key[--len] = '\0';
}

static int check_auth(struct MHD_Connection *connection) {
    if (api_key[0] == '\0') return 1;
    const char *key = MHD_lookup_connection_value(
        connection, MHD_HEADER_KIND, "X-API-Key");
    if (!key) return 0;
    return strcmp(key, api_key) == 0;
}

static enum MHD_Result send_json(struct MHD_Connection *connection,
    const char *body, unsigned int status_code) {
    struct MHD_Response *response = MHD_create_response_from_buffer(
        strlen(body), (void *)body, MHD_RESPMEM_MUST_COPY);
    MHD_add_response_header(response, "Content-Type", "application/json");
    MHD_add_response_header(response, "Access-Control-Allow-Origin", "*");
    MHD_add_response_header(response, "Access-Control-Allow-Methods",
                            "GET, POST, PUT, DELETE, OPTIONS");
    MHD_add_response_header(response, "Access-Control-Allow-Headers",
                            "Content-Type, X-API-Key");
    enum MHD_Result ret = MHD_queue_response(connection, status_code, response);
    MHD_destroy_response(response);
    return ret;
}

static enum MHD_Result send_json_with_headers(struct MHD_Connection *connection,
    const char *body, unsigned int status_code, int total_count) {
    struct MHD_Response *response = MHD_create_response_from_buffer(
        strlen(body), (void *)body, MHD_RESPMEM_MUST_COPY);
    MHD_add_response_header(response, "Content-Type", "application/json");
    MHD_add_response_header(response, "Access-Control-Allow-Origin", "*");
    MHD_add_response_header(response, "Access-Control-Allow-Methods",
                            "GET, POST, PUT, DELETE, OPTIONS");
    MHD_add_response_header(response, "Access-Control-Allow-Headers",
                            "Content-Type, X-API-Key");
    if (total_count >= 0) {
        char count_str[32];
        snprintf(count_str, sizeof(count_str), "%d", total_count);
        MHD_add_response_header(response, "X-Total-Count", count_str);
    }
    enum MHD_Result ret = MHD_queue_response(connection, status_code, response);
    MHD_destroy_response(response);
    return ret;
}

static enum MHD_Result handle_get_notes(struct MHD_Connection *connection) {
    const char *limit_str = MHD_lookup_connection_value(
        connection, MHD_GET_ARGUMENT_KIND, "limit");
    const char *offset_str = MHD_lookup_connection_value(
        connection, MHD_GET_ARGUMENT_KIND, "offset");

    int limit = 50;
    int offset = 0;

    if (limit_str) {
        limit = atoi(limit_str);
        if (limit <= 0) limit = 50;
        if (limit > 100) limit = 100;
    }
    if (offset_str) {
        offset = atoi(offset_str);
        if (offset < 0) offset = 0;
    }

    int total = get_total_notes_count();
    char *json = get_notes_paginated_json(limit, offset);

    if (!json) return send_json_with_headers(connection, "[]", MHD_HTTP_OK, total);
    enum MHD_Result ret = send_json_with_headers(connection, json, MHD_HTTP_OK, total);
    free(json);
    return ret;
}

static enum MHD_Result handle_get_note(struct MHD_Connection *connection, int id) {
    char *json = get_note_json(id);
    if (!json) return send_json(connection, "{\"error\":\"not found\"}", MHD_HTTP_NOT_FOUND);
    enum MHD_Result ret = send_json(connection, json, MHD_HTTP_OK);
    free(json);
    return ret;
}

static enum MHD_Result handle_body_upload(
    const char *upload_data, size_t *upload_data_size,
    void **con_cls) {
    if (*con_cls == NULL) {
        struct connection_info *ci = calloc(1, sizeof(struct connection_info));
        *con_cls = ci;
        return MHD_YES;
    }

    if (*upload_data_size > 0) {
        struct connection_info *ci = *con_cls;
        ci->data = realloc(ci->data, ci->data_size + *upload_data_size + 1);
        memcpy(ci->data + ci->data_size, upload_data, *upload_data_size);
        ci->data_size += *upload_data_size;
        ci->data[ci->data_size] = '\0';
        *upload_data_size = 0;
        return MHD_YES;
    }

    return MHD_NO;
}

static enum MHD_Result handle_create_note(struct MHD_Connection *connection,
    const char *upload_data, size_t *upload_data_size,
    void **con_cls) {

    enum MHD_Result body_result = handle_body_upload(
        upload_data, upload_data_size, con_cls);
    if (body_result != MHD_NO) return body_result;

    struct connection_info *ci = *con_cls;
    if (!ci->data) {
        return send_json(connection, "{\"error\":\"bad request\"}", MHD_HTTP_BAD_REQUEST);
    }

    if (ci->data_size > MAX_BODY_SIZE) {
        return send_json(connection,
            "{\"error\":\"payload too large\"}", 413);
    }

    cJSON *json = cJSON_Parse(ci->data);
    if (!json) {
        return send_json(connection, "{\"error\":\"invalid json\"}", MHD_HTTP_BAD_REQUEST);
    }

    cJSON *title = cJSON_GetObjectItem(json, "title");
    cJSON *content = cJSON_GetObjectItem(json, "content");

    if (!cJSON_IsString(title) || strlen(title->valuestring) == 0) {
        cJSON_Delete(json);
        return send_json(connection, "{\"error\":\"title required\"}", MHD_HTTP_BAD_REQUEST);
    }

    const char *content_str = cJSON_IsString(content) ? content->valuestring : "";
    int id = create_note(title->valuestring, content_str);

    cJSON *resp = cJSON_CreateObject();
    cJSON_AddNumberToObject(resp, "id", id);
    cJSON_AddStringToObject(resp, "title", title->valuestring);
    cJSON_AddStringToObject(resp, "content", content_str);
    char *resp_str = cJSON_PrintUnformatted(resp);

    enum MHD_Result ret = send_json(connection, resp_str, MHD_HTTP_CREATED);

    free(resp_str);
    cJSON_Delete(json);
    cJSON_Delete(resp);
    return ret;
}

static enum MHD_Result handle_update_note(struct MHD_Connection *connection,
    int note_id, const char *upload_data, size_t *upload_data_size,
    void **con_cls) {

    enum MHD_Result body_result = handle_body_upload(
        upload_data, upload_data_size, con_cls);
    if (body_result != MHD_NO) return body_result;

    if (!note_exists(note_id)) {
        return send_json(connection, "{\"error\":\"not found\"}", MHD_HTTP_NOT_FOUND);
    }

    struct connection_info *ci = *con_cls;
    if (!ci->data) {
        return send_json(connection, "{\"error\":\"bad request\"}", MHD_HTTP_BAD_REQUEST);
    }

    if (ci->data_size > MAX_BODY_SIZE) {
        return send_json(connection,
            "{\"error\":\"payload too large\"}", 413);
    }

    cJSON *json = cJSON_Parse(ci->data);
    if (!json) {
        return send_json(connection, "{\"error\":\"invalid json\"}", MHD_HTTP_BAD_REQUEST);
    }

    cJSON *title = cJSON_GetObjectItem(json, "title");
    cJSON *content = cJSON_GetObjectItem(json, "content");

    if (!cJSON_IsString(title) || strlen(title->valuestring) == 0) {
        cJSON_Delete(json);
        return send_json(connection, "{\"error\":\"title required\"}", MHD_HTTP_BAD_REQUEST);
    }

    const char *content_str = cJSON_IsString(content) ? content->valuestring : "";
    update_note(note_id, title->valuestring, content_str);

    cJSON *resp = cJSON_CreateObject();
    cJSON_AddNumberToObject(resp, "id", note_id);
    cJSON_AddStringToObject(resp, "title", title->valuestring);
    cJSON_AddStringToObject(resp, "content", content_str);
    char *resp_str = cJSON_PrintUnformatted(resp);

    enum MHD_Result ret = send_json(connection, resp_str, MHD_HTTP_OK);

    free(resp_str);
    cJSON_Delete(json);
    cJSON_Delete(resp);
    return ret;
}

static enum MHD_Result handle_delete_note(struct MHD_Connection *connection,
    int id) {
    if (!note_exists(id)) {
        return send_json(connection, "{\"error\":\"not found\"}", MHD_HTTP_NOT_FOUND);
    }
    delete_note(id);
    return send_json(connection, "{\"status\":\"deleted\"}", MHD_HTTP_OK);
}

enum MHD_Result route_request(struct MHD_Connection *connection,
    const char *url, const char *method,
    const char *upload_data, size_t *upload_data_size,
    void **con_cls) {

    ensure_api_key();

    if (strcmp(method, "OPTIONS") == 0) {
        return send_json(connection, "", MHD_HTTP_OK);
    }

    int is_mutation = (strcmp(method, "POST") == 0 ||
                       strcmp(method, "PUT") == 0 ||
                       strcmp(method, "DELETE") == 0);
    if (is_mutation && !check_auth(connection)) {
        return send_json(connection, "{\"error\":\"unauthorized\"}",
                         MHD_HTTP_UNAUTHORIZED);
    }

    if (strcmp(url, "/api/notes") == 0) {
        if (strcmp(method, "GET") == 0) return handle_get_notes(connection);
        if (strcmp(method, "POST") == 0)
            return handle_create_note(connection, upload_data,
                                      upload_data_size, con_cls);
    }

    if (strncmp(url, "/api/notes/", 11) == 0) {
        int id = atoi(url + 11);
        if (id <= 0)
            return send_json(connection, "{\"error\":\"invalid id\"}",
                             MHD_HTTP_BAD_REQUEST);

        if (strcmp(method, "GET") == 0) return handle_get_note(connection, id);
        if (strcmp(method, "PUT") == 0)
            return handle_update_note(connection, id, upload_data,
                                      upload_data_size, con_cls);
        if (strcmp(method, "DELETE") == 0) return handle_delete_note(connection, id);
    }

    return send_json(connection, "{\"error\":\"not found\"}", MHD_HTTP_NOT_FOUND);
}
