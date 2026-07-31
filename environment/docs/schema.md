# Cluster graph schema

The graph at `/app/graph/cluster.nt` is an RDF N-Triples dump of the cluster
state this placement audit runs against. All terms use the namespace
`http://ex.org/k8s#`, abbreviated `:` below.

## Node types

Every node carries an `rdf:type`:

- `:Node` is a worker node that pods can be placed on.
- `:Pod` is a workload. It is either pending, meaning it is waiting to be
  placed, or already placed on a worker node.
- `:Label` is a key and value pair. A label node is shared: any worker node or
  pod carrying the same key and value points at the same `:Label` IRI.
- `:Taint` is a restriction attached to a worker node.
- `:Toleration` is a pod's declaration that it accepts some taint.
- `:AntiAffinity` is a pending pod's placement restriction.

## Predicates

| Triple | Meaning |
|---|---|
| `?node :hasLabel ?label` | the worker node carries that label |
| `?node :hasTaint ?taint` | the worker node carries that taint |
| `?pod :pending ?boolean` | whether the pod is waiting to be placed |
| `?pod :placedOn ?node` | the worker node the pod already sits on |
| `?pod :hasPodLabel ?label` | the pod carries that label |
| `?pod :hasToleration ?toleration` | the pod declares that toleration |
| `?pod :requiresLabel ?label` | the pod requires that label on its host |
| `?pod :hasAntiAffinity ?antiAffinity` | the pod's anti-affinity restriction |
| `?label :key ?string`, `?label :value ?string` | the label's key and value |
| `?taint :key ?string`, `?taint :value ?string`, `?taint :effect ?string` | the taint's key, value and effect |
| `?toleration :key ?string`, `?toleration :operator ?string`, `?toleration :value ?string`, `?toleration :effect ?string` | the toleration's four fields |
| `?antiAffinity :selectorLabel ?label`, `?antiAffinity :topologyKey ?string` | the selector label and the topology key |

## Value domains

A taint's `:effect` is one of `NoSchedule`, `PreferNoSchedule` or `NoExecute`.
A toleration's `:operator` is either `Equal` or `Exists`. A toleration's `:key`
and `:effect` may each be the empty string; its `:value` is meaningful only
under the `Equal` operator.

## Multiplicity and shape

A worker node carries zero or more taints and zero or more labels, and never
carries two labels that share a key, so a node has at most one value for any
given label key. A node may carry no label at all for a given key. A pending
pod carries zero or more tolerations, zero or more required labels, and at most
one anti-affinity restriction. A placed pod carries `:placedOn`, zero or more
pod labels and zero or more tolerations. A pending pod never carries
`:placedOn`. Many pods may sit on one worker node.

Identity is by IRI. `:placedOn` is directed and recorded in one direction only.
The graph records exactly the labels, taints, tolerations, required labels,
anti-affinity restrictions and existing placements, and nothing else.
