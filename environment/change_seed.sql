BEGIN;
INSERT INTO change_meta VALUES
 ('change_generation','11'),
 ('authorization_protocol','CC-4'),
 ('approval_policy','WEIGHTED-DISTINCT-GROUPS'),
 ('seal_digest_class','commissioning-seal-v2');

INSERT INTO change_ticket VALUES
 ('chg-2026-071','north-quay','Q4','K9B','APPROVED','2026-06-18T00:00:00Z','2026-06-18T08:00:00Z','2026-06-16T18:00:00Z',60,4,0),
 ('chg-2026-070','north-quay','Q4','K9B','APPROVED','2026-06-17T00:00:00Z','2026-06-18T02:59:59Z','2026-06-15T20:00:00Z',100,4,0),
 ('chg-2026-072','north-quay','Q4','K9B','HOLD','2026-06-18T00:00:00Z','2026-06-18T08:00:00Z','2026-06-17T20:00:00Z',120,4,0),
 ('chg-2026-055','north-quay','Q4','K9A','APPROVED','2026-06-18T00:00:00Z','2026-06-18T08:00:00Z','2026-06-17T21:00:00Z',130,4,0),
 ('chg-2026-073','north-quay','Q4','K9B','APPROVED','2026-06-18T00:00:00Z','2026-06-18T08:00:00Z','2026-06-18T04:00:00Z',150,4,1);

INSERT INTO approval_role VALUES
 ('OPS',2,'operations'),
 ('SRE',1,'operations'),
 ('SECURITY',2,'security'),
 ('AUDIT',1,'assurance');

INSERT INTO approval_event VALUES
 ('ev-a1','chg-2026-071','alice.ops','OPS','approve','2026-06-16T19:00:00Z',70),
 ('ev-b1','chg-2026-071','bob.sec','SECURITY','approve','2026-06-17T09:00:00Z',60),
 ('ev-b2','chg-2026-071','bob.sec','SECURITY','revoke','2026-06-17T23:00:00Z',80),
 ('ev-b3','chg-2026-071','bob.sec','SECURITY','reinstate','2026-06-18T02:15:00Z',90),
 ('ev-c1','chg-2026-071','carol.sre','SRE','approve','2026-06-17T15:00:00Z',95),
 ('ev-d1','chg-2026-071','dana.audit','AUDIT','approve','2026-06-18T04:30:00Z',100),
 ('ev-old-a','chg-2026-070','old.ops','OPS','approve','2026-06-17T01:00:00Z',100),
 ('ev-old-b','chg-2026-070','old.sec','SECURITY','approve','2026-06-17T01:05:00Z',100),
 ('ev-hold-a','chg-2026-072','hold.ops','OPS','approve','2026-06-18T01:00:00Z',100),
 ('ev-hold-b','chg-2026-072','hold.sec','SECURITY','approve','2026-06-18T01:05:00Z',100);

INSERT INTO activation_candidate VALUES
 ('act-071-recovery-b4','chg-2026-071','sock-recovery','B4','BLUE','2026-06-17T22:00:00Z',50,'2026-06-18T00:00:00Z','2026-06-18T08:00:00Z',0),
 ('act-071-data-b5','chg-2026-071','sock-data','B5','BLUE','2026-06-18T01:00:00Z',100,'2026-06-18T00:00:00Z','2026-06-18T08:00:00Z',0),
 ('act-071-recovery-b5-old','chg-2026-071','sock-recovery','B5','BLUE','2026-06-16T20:00:00Z',130,'2026-06-18T00:00:00Z','2026-06-18T08:00:00Z',0),
 ('act-071-recovery-b4-future','chg-2026-071','sock-recovery','B4','BLUE','2026-06-18T04:00:00Z',150,'2026-06-18T04:00:00Z','2026-06-18T08:00:00Z',0),
 ('act-070-recovery-b4','chg-2026-070','sock-recovery','B4','GREEN','2026-06-17T20:00:00Z',100,'2026-06-17T00:00:00Z','2026-06-18T02:59:59Z',0),
 ('act-disabled','chg-2026-071','sock-recovery','B4','RED','2026-06-18T02:00:00Z',200,'2026-06-18T00:00:00Z','2026-06-18T08:00:00Z',1);

INSERT INTO authorization_rule VALUES
 ('change-generation','CC-1.3','exact',1),
 ('ticket-selection','CC-3.8','temporal',2),
 ('approval-state','CC-5.4','latest-event',3),
 ('approval-quorum','CC-6.9','weighted-distinct-groups',4),
 ('activation-selection','CC-8.2','socket-and-tier',5);
COMMIT;
