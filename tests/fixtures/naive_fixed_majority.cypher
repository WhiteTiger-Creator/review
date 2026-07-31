MATCH (cl:Client)
OPTIONAL MATCH (x:Candidate)-[:OF]->(cl), (x)-[:FROM_SERVER]->(sx:Server)
  WHERE (sx.reachable AND sx.stratum < 16)
WITH cl, count(x) AS m
OPTIONAL MATCH (c:Candidate)-[:OF]->(cl), (c)-[:FROM_SERVER]->(sc:Server)
  WHERE (sc.reachable AND sc.stratum < 16) AND (EXISTS { MATCH (q1_k:Candidate)-[:OF]->(cl), (q1_k)-[:FROM_SERVER]->(q1_s:Server) WHERE (q1_s.reachable AND q1_s.stratum < 16) AND q1_k.lo <= c.offset AND COUNT { MATCH (q3_k:Candidate)-[:OF]->(cl), (q3_k)-[:FROM_SERVER]->(q3_s:Server) WHERE (q3_s.reachable AND q3_s.stratum < 16) AND q3_k.lo <= q1_k.lo AND q3_k.hi >= q1_k.lo } >= (m / 2 + 1) } AND EXISTS { MATCH (q2_k:Candidate)-[:OF]->(cl), (q2_k)-[:FROM_SERVER]->(q2_s:Server) WHERE (q2_s.reachable AND q2_s.stratum < 16) AND q2_k.hi >= c.offset AND COUNT { MATCH (q4_k:Candidate)-[:OF]->(cl), (q4_k)-[:FROM_SERVER]->(q4_s:Server) WHERE (q4_s.reachable AND q4_s.stratum < 16) AND q4_k.lo <= q2_k.hi AND q4_k.hi >= q2_k.hi } >= (m / 2 + 1) })
WITH cl, m, count(c) AS truechimer_count,
     min(CASE WHEN c IS NULL THEN NULL ELSE CAST(sc.stratum + 100 AS STRING) + '|' + CAST(sc.root_dispersion + 1000000000000 AS STRING) + '|' + sc.name END) AS peer_key
RETURN cl.name AS client,
       CASE WHEN peer_key IS NULL THEN 16
            ELSE CAST(substr(peer_key, 1, 3) AS INT64) - 100 + 1 END AS stratum,
       CASE WHEN peer_key IS NULL THEN 'NONE'
            ELSE substr(peer_key, 19, 200) END AS system_peer,
       truechimer_count,
       m - truechimer_count AS falseticker_count
