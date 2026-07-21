#include "db.h"
#include <sqlite3.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static sqlite3 *db = NULL;

int init_db(const char *path) {
    if (sqlite3_open_v2(path, &db,
            SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_NOMUTEX,
            NULL) != SQLITE_OK) {
        fprintf(stderr, "Cannot open database: %s\n", sqlite3_errmsg(db));
        return -1;
    }

    const char *sql = "CREATE TABLE IF NOT EXISTS notes ("
                      "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                      "title TEXT NOT NULL,"
                      "content TEXT DEFAULT ''"
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
    if (db)
        sqlite3_close(db);
    db = NULL;
}

int create_note(const char *title, const char *content) {
    (void)title;
    (void)content;
    return 0;
}

char *get_all_notes_json(void) {
    return strdup("[]");
}

char *get_notes_paginated_json(int limit, int offset) {
    (void)limit;
    (void)offset;
    return strdup("[]");
}

int get_total_notes_count(void) {
    return 0;
}

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
