-- decoy surface coverage export
CREATE VIEW surf_v5 AS
SELECT corpus_tag, COUNT(*) AS row_hits
FROM stage_rows GROUP BY corpus_tag;
