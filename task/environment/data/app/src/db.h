#ifndef DB_H
#define DB_H

int init_db(const char *path);
void close_db(void);
int create_note(const char *title, const char *content);
char *get_all_notes_json(void);
char *get_notes_paginated_json(int limit, int offset);
int get_total_notes_count(void);
char *get_note_json(int id);
int update_note(int id, const char *title, const char *content);
int delete_note(int id);
int note_exists(int id);

#endif
