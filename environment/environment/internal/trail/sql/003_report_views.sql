CREATE VIEW IF NOT EXISTS latest_complete_run AS
SELECT * FROM migration_run WHERE id = (SELECT id FROM authoritative_run);
