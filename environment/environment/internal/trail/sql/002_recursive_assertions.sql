CREATE VIEW IF NOT EXISTS authoritative_run AS
SELECT id FROM migration_run
WHERE status = 'COMPLETE'
ORDER BY completed_at DESC, id DESC
LIMIT 1;

CREATE VIEW IF NOT EXISTS coverage_gaps AS
SELECT ge.run_id, ge.edge_key
FROM graph_edge ge
JOIN authoritative_run ar ON ar.id = ge.run_id
LEFT JOIN policy_edge pe ON pe.run_id = ge.run_id AND pe.edge_key = ge.edge_key
WHERE ge.denied = 0 AND pe.edge_key IS NULL;
