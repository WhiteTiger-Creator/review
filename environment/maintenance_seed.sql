BEGIN;
INSERT INTO schedule_meta VALUES
 ('schedule_generation','11'),
 ('window_protocol','MW-4'),
 ('acknowledgment_policy','WEIGHTED-DISTINCT-GROUPS'),
 ('window_digest_class','commissioning-window-v2');

INSERT INTO maintenance_order VALUES
 ('mw-2026-071','north-quay','Q4','K9B','SCHEDULED','2026-06-18T00:00:00Z','2026-06-18T08:00:00Z','2026-06-16T18:00:00Z',60,4,0),
 ('mw-2026-070','north-quay','Q4','K9B','SCHEDULED','2026-06-17T00:00:00Z','2026-06-18T02:59:59Z','2026-06-15T20:00:00Z',100,4,0),
 ('mw-2026-072','north-quay','Q4','K9B','HOLD','2026-06-18T00:00:00Z','2026-06-18T08:00:00Z','2026-06-17T20:00:00Z',120,4,0),
 ('mw-2026-055','north-quay','Q4','K9A','SCHEDULED','2026-06-18T00:00:00Z','2026-06-18T08:00:00Z','2026-06-17T21:00:00Z',130,4,0),
 ('mw-2026-073','north-quay','Q4','K9B','SCHEDULED','2026-06-18T00:00:00Z','2026-06-18T08:00:00Z','2026-06-18T04:00:00Z',150,4,1);

INSERT INTO ack_role VALUES
 ('OPS',2,'operations'),
 ('SRE',1,'operations'),
 ('NETWORK',2,'network'),
 ('AUDIT',1,'assurance');

INSERT INTO ack_event VALUES
 ('ev-a1','mw-2026-071','alice.ops','OPS','acknowledge','2026-06-16T19:00:00Z',70),
 ('ev-b1','mw-2026-071','bob.net','NETWORK','acknowledge','2026-06-17T09:00:00Z',60),
 ('ev-b2','mw-2026-071','bob.net','NETWORK','withdraw','2026-06-17T23:00:00Z',80),
 ('ev-b3','mw-2026-071','bob.net','NETWORK','restore','2026-06-18T02:15:00Z',90),
 ('ev-c1','mw-2026-071','carol.sre','SRE','acknowledge','2026-06-17T15:00:00Z',95),
 ('ev-d1','mw-2026-071','dana.audit','AUDIT','acknowledge','2026-06-18T04:30:00Z',100),
 ('ev-old-a','mw-2026-070','old.ops','OPS','acknowledge','2026-06-17T01:00:00Z',100),
 ('ev-old-b','mw-2026-070','old.net','NETWORK','acknowledge','2026-06-17T01:05:00Z',100),
 ('ev-hold-a','mw-2026-072','hold.ops','OPS','acknowledge','2026-06-18T01:00:00Z',100),
 ('ev-hold-b','mw-2026-072','hold.net','NETWORK','acknowledge','2026-06-18T01:05:00Z',100);

INSERT INTO service_slot VALUES
 ('slot-071-window-b4','mw-2026-071','sock-window','B4','BLUE','2026-06-17T22:00:00Z',50,'2026-06-18T00:00:00Z','2026-06-18T08:00:00Z',0),
 ('slot-071-data-b5','mw-2026-071','sock-data','B5','BLUE','2026-06-18T01:00:00Z',100,'2026-06-18T00:00:00Z','2026-06-18T08:00:00Z',0),
 ('slot-071-window-b5-old','mw-2026-071','sock-window','B5','BLUE','2026-06-16T20:00:00Z',130,'2026-06-18T00:00:00Z','2026-06-18T08:00:00Z',0),
 ('slot-071-window-b4-future','mw-2026-071','sock-window','B4','BLUE','2026-06-18T04:00:00Z',150,'2026-06-18T04:00:00Z','2026-06-18T08:00:00Z',0),
 ('slot-070-window-b4','mw-2026-070','sock-window','B4','GREEN','2026-06-17T20:00:00Z',100,'2026-06-17T00:00:00Z','2026-06-18T02:59:59Z',0),
 ('slot-disabled','mw-2026-071','sock-window','B4','RED','2026-06-18T02:00:00Z',200,'2026-06-18T00:00:00Z','2026-06-18T08:00:00Z',1);

INSERT INTO schedule_rule VALUES
 ('schedule-generation','MW-1.3','exact',1),
 ('order-selection','MW-3.8','temporal',2),
 ('ack-state','MW-5.4','latest-event',3),
 ('ack-weight','MW-6.9','weighted-distinct-groups',4),
 ('slot-selection','MW-8.2','socket-and-tier',5);
COMMIT;
