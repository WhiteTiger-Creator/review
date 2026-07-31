MATCH (cl:Client)
OPTIONAL MATCH (x:Candidate)-[:OF]->(cl), (x)-[:FROM_SERVER]->(sx:Server)
  WHERE (sx.reachable AND sx.stratum < 16)
WITH cl, count(x) AS m
WITH cl, m, CASE WHEN (2 * 0 < m AND EXISTS { MATCH (q1_k:Candidate)-[:OF]->(cl), (q1_k)-[:FROM_SERVER]->(q1_s:Server) WHERE (q1_s.reachable AND q1_s.stratum < 16) AND COUNT { MATCH (q2_k:Candidate)-[:OF]->(cl), (q2_k)-[:FROM_SERVER]->(q2_s:Server) WHERE (q2_s.reachable AND q2_s.stratum < 16) AND q2_k.lo <= q1_k.lo AND q2_k.hi >= q1_k.lo } >= (m - 0) } AND COUNT { MATCH (q3_k:Candidate)-[:OF]->(cl), (q3_k)-[:FROM_SERVER]->(q3_s:Server) WHERE (q3_s.reachable AND q3_s.stratum < 16) AND NOT (EXISTS { MATCH (q4_k:Candidate)-[:OF]->(cl), (q4_k)-[:FROM_SERVER]->(q4_s:Server) WHERE (q4_s.reachable AND q4_s.stratum < 16) AND q4_k.lo <= q3_k.offset AND COUNT { MATCH (q6_k:Candidate)-[:OF]->(cl), (q6_k)-[:FROM_SERVER]->(q6_s:Server) WHERE (q6_s.reachable AND q6_s.stratum < 16) AND q6_k.lo <= q4_k.lo AND q6_k.hi >= q4_k.lo } >= (m - 0) } AND EXISTS { MATCH (q5_k:Candidate)-[:OF]->(cl), (q5_k)-[:FROM_SERVER]->(q5_s:Server) WHERE (q5_s.reachable AND q5_s.stratum < 16) AND q5_k.hi >= q3_k.offset AND COUNT { MATCH (q7_k:Candidate)-[:OF]->(cl), (q7_k)-[:FROM_SERVER]->(q7_s:Server) WHERE (q7_s.reachable AND q7_s.stratum < 16) AND q7_k.lo <= q5_k.hi AND q7_k.hi >= q5_k.hi } >= (m - 0) }) } <= 0) THEN 0 ELSE -1 END AS fstar
OPTIONAL MATCH (c:Candidate)-[:OF]->(cl), (c)-[:FROM_SERVER]->(sc:Server)
  WHERE (sc.reachable AND sc.stratum < 16) AND fstar >= 0 AND (EXISTS { MATCH (q8_k:Candidate)-[:OF]->(cl), (q8_k)-[:FROM_SERVER]->(q8_s:Server) WHERE (q8_s.reachable AND q8_s.stratum < 16) AND q8_k.lo <= c.offset AND COUNT { MATCH (q10_k:Candidate)-[:OF]->(cl), (q10_k)-[:FROM_SERVER]->(q10_s:Server) WHERE (q10_s.reachable AND q10_s.stratum < 16) AND q10_k.lo <= q8_k.lo AND q10_k.hi >= q8_k.lo } >= (m - fstar) } AND EXISTS { MATCH (q9_k:Candidate)-[:OF]->(cl), (q9_k)-[:FROM_SERVER]->(q9_s:Server) WHERE (q9_s.reachable AND q9_s.stratum < 16) AND q9_k.hi >= c.offset AND COUNT { MATCH (q11_k:Candidate)-[:OF]->(cl), (q11_k)-[:FROM_SERVER]->(q11_s:Server) WHERE (q11_s.reachable AND q11_s.stratum < 16) AND q11_k.lo <= q9_k.hi AND q11_k.hi >= q9_k.hi } >= (m - fstar) })
WITH cl, m, count(c) AS truechimer_count,
     min(CASE WHEN c IS NULL THEN NULL ELSE CAST(sc.stratum + 100 AS STRING) + '|' + CAST(sc.root_dispersion + 1000000000000 AS STRING) + '|' + sc.name END) AS peer_key
RETURN cl.name AS client,
       CASE WHEN peer_key IS NULL THEN 16
            ELSE CAST(substr(peer_key, 1, 3) AS INT64) - 100 + 1 END AS stratum,
       CASE WHEN peer_key IS NULL THEN 'NONE'
            ELSE substr(peer_key, 19, 200) END AS system_peer,
       truechimer_count,
       m - truechimer_count AS falseticker_count
