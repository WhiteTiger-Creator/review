# Cluster graph overview

The cluster graph was generated deterministically from the seed recorded in
`/app/graph/seed.txt`. The authoritative record is the dump at
`/app/graph/cluster.nt`.

Approximate contents:

- 40 `:Node` worker nodes
- 150 `:Pod` nodes, of which 30 are pending and 120 are already placed
- `:Label` nodes for the label keys `zone`, `rack`, `disk`, `tier`, `app` and
  `role`; not every worker node carries a label for every key
- `:Taint` nodes using the keys `dedicated`, `maintenance`, `gpu` and `spot`,
  across all three effects
- `:Toleration` nodes using both the `Equal` and `Exists` operators, including
  tolerations whose key or effect is the empty string
- `:AntiAffinity` nodes whose topology keys are drawn from the node label keys

Relationships present: `:hasLabel` and `:hasTaint` from worker nodes,
`:placedOn` from placed pods to their worker node, and `:hasPodLabel`,
`:hasToleration`, `:requiresLabel` and `:hasAntiAffinity` from pods. Labels are
shared nodes, so a pod's required label and a worker node's label are the same
IRI when their key and value agree.

The authoritative graph the runner queries is `cluster.nt`.
