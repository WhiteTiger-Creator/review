BEGIN;
INSERT INTO catalog_meta VALUES
 ('catalog_generation','29'),
 ('handbook_revision','HRH-2026.07-R11'),
 ('catalog_digest_class','sealed-ops-v7'),
 ('audit_policy','STRICT'),
 ('catalog_batch_protocol','2');

INSERT INTO deployment_context VALUES
 ('st-042',1,'C7','N2','U','Q4','relayops','relay',29,'2026-06-18T03:40:00Z','LOCAL','BLUE','2026-06-01T00:00:00Z'),
 ('st-105',0,'C3','N1','T','Q2','relay','relay',14,'2025-11-02T01:00:00Z','SYSTEM','GREEN','2025-10-01T00:00:00Z');

INSERT INTO site_alias VALUES
 ('north-quay','st-042','2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',70,0),
 ('north-quay','st-105','2024-01-01T00:00:00Z','2025-12-31T23:59:59Z',99,0),
 ('st-042','st-042','2020-01-01T00:00:00Z','2099-12-31T23:59:59Z',10,0),
 ('north-quay-old','st-042','2024-01-01T00:00:00Z','2026-12-31T23:59:59Z',100,1);

INSERT INTO socket_policy VALUES
 ('LOCAL','U','L','D','R',1),
 ('LOCAL','U','L','C','R',0),
 ('LOCAL','U','L','M','R',0),
 ('LOCAL','U','A','D','S',0),
 ('LOCAL','U','T','D','R',0),
 ('SYSTEM','T','T','D','R',1);

INSERT INTO socket_candidate VALUES
 ('sock-control','st-042','{root}/run/harbor-relay/control.sock','L','C','R','0660','control-listener',99,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('sock-data','st-042','{root}/run/harbor-relay/data-plane.sock','L','D','R','0660','data-plane',96,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('sock-recovery','st-042','{root}/run/harbor-relay/recovery.sock','L','D','R','0660','recovery-plane',74,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('sock-metrics','st-042','{root}/run/harbor-relay/metrics.sock','L','M','R','0660','metrics-listener',98,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('sock-legacy','st-042','{root}/run/harbor-relay/legacy.sock','A','D','S','0666','legacy-plane',20,'2024-01-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('sock-tcp','st-042','127.0.0.1:4818','T','D','R','0000','loopback-data',90,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('sock-future','st-042','{root}/run/harbor-relay/future.sock','L','D','R','0660','future-plane',120,'2027-01-01T00:00:00Z','2027-12-31T23:59:59Z',0);

INSERT INTO body_tier VALUES
 ('B1',8192,1),('B2',16384,2),('B3',32768,3),('B4',65536,4),('B5',131072,5),('B6',262144,6);

INSERT INTO limit_candidate VALUES
 ('lim-old','st-042','C7','N2','Q4',512,43,5,4,3,8,64,128,'B2',3,2,95,'2025-01-01T00:00:00Z','2026-05-31T23:59:59Z',0),
 ('lim-r11','st-042','C7','N2','Q4',640,47,5,4,3,11,64,256,'B3',7,4,80,'2026-06-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('lim-wrong-platform','st-042','C7','N1','Q4',768,51,4,3,2,9,128,512,'B4',2,1,99,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('lim-disabled','st-042','C7','N2','Q4',900,10,2,1,1,1,256,1024,'B1',1,1,120,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',1);

INSERT INTO limit_adjustment VALUES
 ('adj-custody','st-042','CUSTODY',9,0,2048,60,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('adj-multi-request','st-042','MULTI_REQUEST',5,1,4096,50,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('adj-replacement','st-042','ROUTE_REPLACEMENT',3,0,0,40,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('adj-unused-segment','st-042','MULTI_SEGMENT',7,2,8192,90,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('adj-expired','st-042','CUSTODY',100,10,50000,200,'2025-01-01T00:00:00Z','2025-12-31T23:59:59Z',0);

INSERT INTO timeout_band VALUES
 ('T1',450),('T2',725),('T3',1200),('T4',1850),('T5',2750),('T6',4100);
INSERT INTO auth_mode VALUES
 ('A0','strip'),('A1','preserve'),('A2','service'),('A3','custody-token'),('A4','dual-proof');

INSERT INTO route_family_rule VALUES
 ('fr-current','C7','N2','U','Q4','COLD-QUAY','custody','K9B',6,'2026-06-05T00:00:00Z',70,'2026-06-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('fr-old','C7','N2','U','Q4','COLD-QUAY','custody','K9A',6,'2026-05-01T00:00:00Z',99,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('fr-wild-incident','C7','N2','U','*','COLD-QUAY','custody','K8',5,'2026-06-10T00:00:00Z',100,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('fr-warm','C7','N2','U','Q4','WARM-PIER','custody','M4',6,'2026-06-05T00:00:00Z',80,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('fr-disabled','C7','N2','U','Q4','COLD-QUAY','custody','Z9',9,'2026-07-01T00:00:00Z',120,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z',1);

INSERT INTO route_candidate VALUES
 ('rt-200','st-042','K9B','BLUE','base','GET','/v1/berth/status','http://127.0.0.1:5902/status','A1','T2',1,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z','2026-05-20T00:00:00Z',60),
 ('rt-201','st-042','K9B','BLUE','base','POST','/v1/berth/arrivals','http://127.0.0.1:5901/intake/arrivals-v2','A3','T4',1,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z','2026-05-10T00:00:00Z',70),
 ('rt-202','st-042','K9B','BLUE','base','POST','/v1/berth/manifest','http://127.0.0.1:5901/intake/manifest-v1','A3','T5',1,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z','2026-05-12T00:00:00Z',80),
 ('rt-203','st-042','K9B','BLUE','required','GET','/v1/berth/capabilities','http://127.0.0.1:5902/capabilities','A1','T3',1,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z','2026-05-15T00:00:00Z',55),
 ('rt-204','st-042','K9B','BLUE','replacement','POST','/v1/berth/manifest','http://127.0.0.1:5901/intake/manifest-v2','A4','T6',1,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z','2026-06-12T00:00:00Z',20),
 ('rt-205','st-042','K9B','BLUE','base','GET','/v1/berth/debug','http://127.0.0.1:5999/debug','A0','T1',1,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z','2026-05-01T00:00:00Z',90),
 ('rt-210','st-042','K9B','BLUE','base','POST','/v1/berth/arrivals','http://127.0.0.1:5891/older/arrivals','A1','T3',1,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z','2026-04-01T00:00:00Z',99),
 ('rt-211','st-042','K9B','GREEN','base','POST','/v1/berth/arrivals','http://127.0.0.1:5991/green/arrivals','A2','T4',1,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z','2026-06-15T00:00:00Z',120),
 ('rt-220','st-042','K9A','BLUE','base','POST','/v1/berth/arrivals','http://127.0.0.1:4891/legacy/arrivals','A1','T3',1,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z','2026-04-15T00:00:00Z',100),
 ('rt-221','st-042','K8','BLUE','base','POST','/v1/berth/arrivals','http://127.0.0.1:4791/wild/arrivals','A0','T2',1,'2026-01-01T00:00:00Z','2026-12-31T23:59:59Z','2026-06-16T00:00:00Z',100);

INSERT INTO route_directive VALUES
 ('dir-manifest-replace','st-042','K9B','replace','rt-202','rt-204','2026-06-13T00:00:00Z',70,'2026-06-13T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('dir-policy-withdraw','st-042','K9B','withdraw','rt-205',NULL,'2026-06-14T00:00:00Z',60,'2026-06-14T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('dir-capability-require','st-042','K9B','require','rt-203',NULL,'2026-06-11T00:00:00Z',50,'2026-06-11T00:00:00Z','2026-12-31T23:59:59Z',0),
 ('dir-expired','st-042','K9B','replace','rt-201','rt-210','2025-05-01T00:00:00Z',200,'2025-01-01T00:00:00Z','2025-12-31T23:59:59Z',0);

INSERT INTO route_dependency VALUES
 ('rt-201','rt-203'),
 ('rt-204','rt-200');

INSERT INTO audit_rule VALUES
 ('catalog-generation','CAT-2.7','exact',1),
 ('identity-alias','ID-4.9','resolved',2),
 ('socket-last-evidence','SOCK-8.12','chronological',3),
 ('route-family','ROUTE-11.6','specific',4),
 ('directive-closure','ROUTE-13.8','closed',5),
 ('dependency-closure','ROUTE-14.4','closed',6),
 ('fd-budget','LIM-17.5','calculated',7),
 ('body-envelope','LIM-19.3','tiered',8),
 ('publication-digests','PUB-23.7','sealed',9),
 ('relay-validation','PUB-24.2','validated',10);
COMMIT;
