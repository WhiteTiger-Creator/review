CREATE TABLE IF NOT EXISTS users (
	id            INTEGER PRIMARY KEY AUTOINCREMENT,
	username      TEXT UNIQUE NOT NULL,
	password_hash TEXT NOT NULL,
	role          TEXT NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS sessions (
	remember_token TEXT PRIMARY KEY,
	user_id        INTEGER NOT NULL REFERENCES users(id),
	role           TEXT NOT NULL
);
