INSERT INTO candidate_exception_reviews VALUES
('NV-EX-001',1,'pending','nimbus-gateway','evidence/compose/gateway-prod.json','MTLS_REMOTE_DEBUG','2025-06-30','sec-review-a','TR-A7', '',0,'prod'),
('NV-EX-001',4,'approved','nimbus-gateway','evidence/compose/gateway-prod.json','MTLS_REMOTE_DEBUG','2025-06-30','sec-review-a','TR-A7', '',0,'prod'),
('NV-EX-002',2,'approved','nimbus-worker','evidence/compose/worker-secret.json','SECRET_MOUNT_LEGACY','2025-03-31','sec-review-b','TR-B2', '/run/secrets/legacy_token',1,'prod'),
('NV-EX-002',5,'withdrawn','nimbus-worker','evidence/compose/worker-secret.json','SECRET_MOUNT_LEGACY','2025-03-31','sec-review-b','TR-B2', '/run/secrets/legacy_token',1,'prod'),
('NV-EX-003',4,'approved','nimbus-cron','evidence/compose/cron-bad-secret.json','SECRET_MOUNT_LEGACY','2025-09-30','sec-review-c','TR-B8', '/run/secrets/legacy_token',0,'prod'),
('NV-EX-004',3,'provisional','nimbus-changelog','evidence/compose/changelog-signer.json','SIGNED_RELEASE_PIPELINE','2025-12-31','release-office','TR-C1', '',0,'prod'),
('NV-EX-004',6,'approved','nimbus-changelog','evidence/compose/changelog-signer.json','SIGNED_RELEASE_PIPELINE','2025-12-31','release-office','TR-C1', '',0,'prod'),
('NV-EX-005',6,'approved','nimbus-preview','evidence/compose/preview-compose.json','MTLS_REMOTE_DEBUG','2024-10-01','sec-review-d','TR-A9', '',0,'stage'),
('NV-EX-006',6,'approved','nimbus-gateway','evidence/compose/gateway-prod.json','MTLS_REMOTE_DEBUG','2025-06-30','sec-review-a','TR-A7-duplicate', '',0,'prod');

INSERT INTO candidate_release_refs VALUES
('refs/heads/release/2.27','https://github.com/docker/compose.git','2024-12-20T17:10:00Z'),
('refs/heads/release/2.27.x','https://github.com/docker/compose.git','2024-12-20T17:10:00Z'),
('refs/heads/release/2.28','https://github.com/docker/compose.git','2024-12-20T17:10:00Z'),
('refs/heads/release/2.29','https://github.com/docker/compose.git','2024-12-20T17:10:00Z'),
('refs/heads/release/security-2.29','https://github.com/docker/compose.git','2024-12-20T17:10:00Z'),
('refs/heads/main','https://github.com/docker/compose.git','2024-12-20T17:10:00Z');

INSERT INTO candidate_changelog_tags VALUES
('v2.27.4','https://github.com/docker/compose.git',1,'CHANGELOG.md#2274','2024-12-20T17:11:00Z'),
('v2.27.4-rc.1','https://github.com/docker/compose.git',1,'CHANGELOG.md#2274-rc1','2024-12-20T17:11:00Z'),
('v2.28.0','https://github.com/docker/compose.git',0,'CHANGELOG.md#2280','2024-12-20T17:11:00Z'),
('v2.28.0+in-toto','https://github.com/docker/compose.git',1,'CHANGELOG.md#2280','2024-12-20T17:11:00Z'),
('v2.29.1','https://github.com/docker/compose.git',1,'CHANGELOG.md#2291','2024-12-20T17:11:00Z'),
('compose/v2.29.1','https://github.com/docker/compose.git',1,'CHANGELOG.md#2291','2024-12-20T17:11:00Z'),
('v2.30.0','https://github.com/docker/compose.git',1,'draft','2024-12-20T17:11:00Z');
