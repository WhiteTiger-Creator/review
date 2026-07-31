# Placement rules

The exact rules the audit applies to decide, for one pending pod and one worker
node, whether that pod is feasible on that node. They are referenced by the
question in instruction.md and they are complete: nothing outside this file and
schema.md affects the answer.

Taint matching. A toleration matches a taint when two conditions both hold. The
effect condition: the toleration's effect is the empty string, or the
toleration's effect equals the taint's effect. The key condition: either the
toleration's key is the empty string and its operator is `Exists`, in which case
the key condition holds for every taint whatever its key and value; or the
toleration's key equals the taint's key and, when the operator is `Exists`, the
value is not consulted, while when the operator is `Equal`, the toleration's
value must equal the taint's value. A pod tolerates a taint when at least one of
that pod's tolerations matches it.

Admission. A pending pod is excluded from a worker node unless every taint on
that node whose effect is `NoSchedule` or `NoExecute` is tolerated by that pod.
A taint whose effect is `PreferNoSchedule` never excludes a pod from a node.

Residency. A pod that is already placed on a worker node remains resident on it
unless some taint on that node whose effect is `NoExecute` is not tolerated by
that pod, in which case the pod is evicted and is no longer resident anywhere. A
taint whose effect is `NoSchedule` or `PreferNoSchedule` never evicts a pod that
is already placed, however that pod's tolerations read. Residency is decided per
pod against the node it sits on, so two pods on the same node may differ.
Eviction is judged from the placements the graph records, and no pod is ever
moved or re-placed by this audit.

Required labels. A pending pod is excluded from a worker node unless every label
the pod requires is also carried by that node.

Anti-affinity. When a pending pod carries an anti-affinity restriction with
selector label S and topology key T, the pod is excluded from a worker node in
either of two cases. First, when that node carries no label whose key is T at
all. Second, when some resident pod carrying label S sits on a worker node whose
label for key T has the same value as the candidate node's label for key T. That
comparison is over the value of the T label, so the pod carrying S may sit on a
different node from the candidate one. A pod that is not resident occupies
nothing and never triggers this exclusion. A pending pod carrying no
anti-affinity restriction is never excluded by this rule, and pending pods place
no restriction on one another.

Feasibility and the verdict. A pending pod is feasible on a worker node when the
admission, required-label and anti-affinity rules above all allow it. The
feasible node count is the number of worker nodes the pod is feasible on, and a
pod is schedulable exactly when that count is greater than zero. Every pending
pod is reported, including one whose count is zero.
