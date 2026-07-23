CREATE TABLE IF NOT EXISTS catalog_meta (
    key TEXT PRIMARY KEY,
    val TEXT NOT NULL
);
INSERT OR IGNORE INTO catalog_meta(key, val) VALUES ('rev', '1');
