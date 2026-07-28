-- trust store remediation patch
INSERT OR IGNORE INTO distrust_fingerprint (fingerprint, source) VALUES ('282b7727e49e973baf41a55c66563f598eb8f8b8c5d9f7fd2df183d692b72dff', 'warrant_honored');
INSERT OR IGNORE INTO distrust_name (common_name, source) VALUES ('inter-a2', 'warrant_honored');
INSERT OR IGNORE INTO distrust_fingerprint (fingerprint, source) VALUES ('bf96bac4fa33f43c01e968216be265abb1c1f4973208499423b493d33f451c41', 'warrant_honored');
INSERT OR IGNORE INTO distrust_name (common_name, source) VALUES ('xc-alpha', 'exposure_containment');
INSERT OR IGNORE INTO distrust_name (common_name, source) VALUES ('xc-epsil', 'exposure_containment');
