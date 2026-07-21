INSERT INTO workers (name) VALUES ('worker-alpha');
INSERT INTO workers (name) VALUES ('worker-beta');
INSERT INTO workers (name) VALUES ('worker-gamma');

INSERT INTO jobs (type, payload, status, priority, worker_id) VALUES
    ('email',        '{"to":"alice@corp.io","subject":"Welcome aboard"}',         'completed', 5, 1),
    ('report',       '{"report_id":"q4-2024","format":"pdf"}',                    'running',   3, 2),
    ('image_resize', '{"src":"/uploads/banner.png","width":1200}',                'pending',   0, NULL),
    ('email',        '{"to":"bob@corp.io","subject":"Your invoice is ready"}',    'pending',   2, NULL),
    ('data_export',  '{"table":"orders","since":"2024-01-01"}',                   'failed',    1, 1),
    ('notification', '{"user_id":99,"channel":"slack","msg":"Deploy done"}',      'pending',   4, NULL);
