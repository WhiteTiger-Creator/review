#include "db.h"
#include <sqlite3.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <cjson/cJSON.h>

static sqlite3 *db = NULL;
static pthread_mutex_t db_mutex = PTHREAD_MUTEX_INITIALIZER;

static int busy_handler(void *data, int count) {
    (void)data;
    if (count > 100) return 0;
    usleep((count < 10 ? count : 10) * 1000);
    return 1;
}

int init_db(const char *path) {
    if (sqlite3_open_v2(path, &db,
            SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX,
            NULL) != SQLITE_OK) {
        fprintf(stderr, "Cannot open database: %s\n", sqlite3_errmsg(db));
        return -1;
    }

    sqlite3_busy_handler(db, busy_handler, NULL);
    sqlite3_exec(db, "PRAGMA journal_mode=WAL;", NULL, NULL, NULL);

    const char *sql = "CREATE TABLE IF NOT EXISTS notes ("
                      "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                      "title TEXT NOT NULL,"
                      "content TEXT DEFAULT '',"
                      "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                      ");";

    char *err_msg = NULL;
    if (sqlite3_exec(db, sql, NULL, NULL, &err_msg) != SQLITE_OK) {
        fprintf(stderr, "SQL error: %s\n", err_msg);
        sqlite3_free(err_msg);
        return -1;
    }
    return 0;
}

void close_db(void) {
    pthread_mutex_lock(&db_mutex);
    if (db) sqlite3_close(db);
    db = NULL;
    pthread_mutex_unlock(&db_mutex);
}

int create_note(const char *title, const char *content) {
    pthread_mutex_lock(&db_mutex);
    const char *sql = "INSERT INTO notes (title, content) VALUES (?, ?);";
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    sqlite3_bind_text(stmt, 1, title, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, content, -1, SQLITE_TRANSIENT);
    sqlite3_step(stmt);
    int id = (int)sqlite3_last_insert_rowid(db);
    sqlite3_finalize(stmt);
    pthread_mutex_unlock(&db_mutex);
    return id;
}

char *get_all_notes_json(void) {
    pthread_mutex_lock(&db_mutex);
    const char *sql = "SELECT id, title, content FROM notes ORDER BY id;";
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) {
        pthread_mutex_unlock(&db_mutex);
        return NULL;
    }

    cJSON *arr = cJSON_CreateArray();
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        cJSON *obj = cJSON_CreateObject();
        cJSON_AddNumberToObject(obj, "id", sqlite3_column_int(stmt, 0));
        cJSON_AddStringToObject(obj, "title",
            (const char *)sqlite3_column_text(stmt, 1));
        cJSON_AddStringToObject(obj, "content",
            (const char *)sqlite3_column_text(stmt, 2));
        cJSON_AddItemToArray(arr, obj);
    }
    sqlite3_finalize(stmt);
    pthread_mutex_unlock(&db_mutex);
    char *json = cJSON_PrintUnformatted(arr);
    cJSON_Delete(arr);
    return json;
}

char *get_notes_paginated_json(int limit, int offset) {
    pthread_mutex_lock(&db_mutex);
    const char *sql = "SELECT id, title, content FROM notes ORDER BY id LIMIT ? OFFSET ?;";
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) {
        pthread_mutex_unlock(&db_mutex);
        return NULL;
    }
    sqlite3_bind_int(stmt, 1, limit);
    sqlite3_bind_int(stmt, 2, offset);

    cJSON *arr = cJSON_CreateArray();
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        cJSON *obj = cJSON_CreateObject();
        cJSON_AddNumberToObject(obj, "id", sqlite3_column_int(stmt, 0));
        cJSON_AddStringToObject(obj, "title",
            (const char *)sqlite3_column_text(stmt, 1));
        cJSON_AddStringToObject(obj, "content",
            (const char *)sqlite3_column_text(stmt, 2));
        cJSON_AddItemToArray(arr, obj);
    }
    sqlite3_finalize(stmt);
    pthread_mutex_unlock(&db_mutex);
    char *json = cJSON_PrintUnformatted(arr);
    cJSON_Delete(arr);
    return json;
}

int get_total_notes_count(void) {
    pthread_mutex_lock(&db_mutex);
    const char *sql = "SELECT COUNT(*) FROM notes;";
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) {
        pthread_mutex_unlock(&db_mutex);
        return 0;
    }
    int count = 0;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        count = sqlite3_column_int(stmt, 0);
    }
    sqlite3_finalize(stmt);
    pthread_mutex_unlock(&db_mutex);
    return count;
}

char *get_note_json(int id) {
    pthread_mutex_lock(&db_mutex);
    const char *sql = "SELECT id, title, content FROM notes WHERE id = ?;";
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) {
        pthread_mutex_unlock(&db_mutex);
        return NULL;
    }
    sqlite3_bind_int(stmt, 1, id);

    if (sqlite3_step(stmt) != SQLITE_ROW) {
        sqlite3_finalize(stmt);
        pthread_mutex_unlock(&db_mutex);
        return NULL;
    }

    cJSON *obj = cJSON_CreateObject();
    cJSON_AddNumberToObject(obj, "id", sqlite3_column_int(stmt, 0));
    cJSON_AddStringToObject(obj, "title",
        (const char *)sqlite3_column_text(stmt, 1));
    cJSON_AddStringToObject(obj, "content",
        (const char *)sqlite3_column_text(stmt, 2));
    sqlite3_finalize(stmt);
    pthread_mutex_unlock(&db_mutex);
    char *json = cJSON_PrintUnformatted(obj);
    cJSON_Delete(obj);
    return json;
}

int update_note(int id, const char *title, const char *content) {
    pthread_mutex_lock(&db_mutex);
    const char *sql = "UPDATE notes SET title = ?, content = ? WHERE id = ?;";
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) {
        pthread_mutex_unlock(&db_mutex);
        return 0;
    }
    sqlite3_bind_text(stmt, 1, title, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, content, -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 3, id);
    sqlite3_step(stmt);
    int changed = sqlite3_changes(db);
    sqlite3_finalize(stmt);
    pthread_mutex_unlock(&db_mutex);
    return changed;
}

int delete_note(int id) {
    pthread_mutex_lock(&db_mutex);
    const char *sql = "DELETE FROM notes WHERE id = ?;";
    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    sqlite3_bind_int(stmt, 1, id);
    sqlite3_step(stmt);
    int changed = sqlite3_changes(db);
    sqlite3_finalize(stmt);
    pthread_mutex_unlock(&db_mutex);
    return changed;
}

int note_exists(int id) {
    pthread_mutex_lock(&db_mutex);
    const char *sql = "SELECT COUNT(*) FROM notes WHERE id = ?;";
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) {
        pthread_mutex_unlock(&db_mutex);
        return 0;
    }
    sqlite3_bind_int(stmt, 1, id);
    int exists = 0;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        exists = sqlite3_column_int(stmt, 0) > 0;
    }
    sqlite3_finalize(stmt);
    pthread_mutex_unlock(&db_mutex);
    return exists;
}
