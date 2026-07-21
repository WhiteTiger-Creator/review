#include "db.h"
#include <sqlite3.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static sqlite3 *db = NULL;
static pthread_mutex_t db_mutex = PTHREAD_MUTEX_INITIALIZER;

int init_db(const char *path) {
    if (sqlite3_open_v2(path, &db,
                        SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX,
                        NULL) != SQLITE_OK) {
        fprintf(stderr, "Cannot open database\n");
        return -1;
    }
    const char *sql = "CREATE TABLE IF NOT EXISTS notes ("
                      "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                      "title TEXT NOT NULL,"
                      "content TEXT DEFAULT ''"
                      ");";
    char *err = NULL;
    if (sqlite3_exec(db, sql, NULL, NULL, &err) != SQLITE_OK) {
        fprintf(stderr, "SQL error: %s\n", err);
        sqlite3_free(err);
        return -1;
    }
    return 0;
}

void close_db(void) {
    pthread_mutex_lock(&db_mutex);
    if (db)
        sqlite3_close(db);
    db = NULL;
    pthread_mutex_unlock(&db_mutex);
}

int create_note(const char *title, const char *content) {
    (void)title;
    (void)content;
    return 0;
}

char *get_all_notes_json(void) { return strdup("[]"); }

char *get_notes_paginated_json(int limit, int offset) {
    (void)limit;
    (void)offset;
    return strdup("[]");
}

int get_total_notes_count(void) { return 0; }

char *get_note_json(int id) {
    (void)id;
    return NULL;
}

int update_note(int id, const char *title, const char *content) {
    (void)id;
    (void)title;
    (void)content;
    return 0;
}

int delete_note(int id) {
    (void)id;
    return 0;
}

int note_exists(int id) {
    (void)id;
    return 0;
}
