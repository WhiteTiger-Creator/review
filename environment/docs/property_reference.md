# Property reference

Worked single-hop queries shown only to illustrate the property and
relationship names in context. None of these answer the question in
instruction.md.

Listing every client by name:

```
MATCH (c:Client) RETURN c.id AS id, c.name AS name
```

Listing every server with the properties that describe it:

```
MATCH (s:Server)
RETURN s.name AS server, s.stratum AS stratum,
       s.root_dispersion AS root_dispersion, s.reachable AS reachable
```

Listing the candidates a given client holds, with their intervals and offsets:

```
MATCH (k:Candidate)-[:OF]->(c:Client {name: 'some-client'})
RETURN k.id AS candidate, k.lo AS lo, k.hi AS hi, k.offset AS offset
```

Joining a candidate to the server it was measured against:

```
MATCH (k:Candidate)-[:OF]->(c:Client {name: 'some-client'}),
      (k)-[:FROM_SERVER]->(s:Server)
RETURN k.lo AS lo, k.hi AS hi, k.offset AS offset,
       s.name AS server, s.stratum AS stratum
```

Counting the candidates a given client holds:

```
MATCH (c:Client {name: 'some-client'})
RETURN COUNT { MATCH (k:Candidate)-[:OF]->(c) } AS candidates
```

Counting how many of a client's intervals cover a given position:

```
MATCH (c:Client {name: 'some-client'})
RETURN COUNT {
  MATCH (k:Candidate)-[:OF]->(c) WHERE k.lo <= 0 AND k.hi >= 0
} AS coverage_at_zero
```

Listing the clients that measured a given server:

```
MATCH (k:Candidate)-[:FROM_SERVER]->(s:Server {name: 'some-server'}),
      (k)-[:OF]->(c:Client)
RETURN c.name AS client
```
