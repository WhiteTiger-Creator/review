# Learning contract

The program fits a binary classification tree on a training table whose feature
entries may be unrecorded, and reports two things about the fitted model: how
much each measurement contributes to it, and the class it predicts for each
held out example together with the evidence behind that prediction.

An unrecorded entry is written as minus one. Every other feature entry is a
non-negative integer. All arithmetic below is exact and rational, so nothing
is rounded anywhere.

## Growing one node

A node holds a set of training rows. It becomes a leaf when its depth reaches
the query's depth limit, when every row in it shares one class, when it holds
fewer rows than the query's minimum, or when no candidate split exists. A leaf
predicts the class most common among its rows, and a tie goes to the smallest
class number.

The number of classes is fixed by the training table alone: it is one more than
the largest label appearing there. A label that occurs only in the probe table
does not widen any reported distribution.

Otherwise the node picks a primary split. For a feature, only the rows of the
node whose entry for that feature is recorded take part in scoring it. The
candidate thresholds for that feature are its recorded values at the node
except the largest, and a candidate sends a row left when its entry is at most
the threshold. The candidate is scored by the drop in Gini impurity between
the scoring rows and the two sides it makes, each side weighted by its share
of the scoring rows. The node keeps the candidate with the largest drop; an
exact tie goes to the smallest feature number and then to the smallest
threshold.

## Stand-in splits

A row whose primary feature is unrecorded still has to be sent down. Each
internal node therefore keeps a ranked list of stand-in splits, at most one
for each of the other features, chosen to reproduce the primary split's two
way division of the node as closely as possible.

A candidate feature is judged only on the node's shared rows: those rows of the
node for which the primary feature and the candidate feature are both recorded.
Rows missing either one take no part in judging that candidate, and each
candidate therefore has its own shared rows. A candidate with no shared rows is
not considered, nor is one whose shared rows carry fewer than two distinct
recorded values, nor is one whose shared rows are all sent to the same side by
the primary split.

For a candidate feature the node considers each of its thresholds and both
readings of that threshold, the plain reading that sends at most the threshold
left and the reversed reading that sends it right. Every reading places each
shared row on a side, and the reading is measured by how many shared rows it
places on the side the primary split gives them. For that feature the node
keeps the reading that places the most shared rows correctly, resolving an
exact tie by the smaller threshold and then by the plain reading.

Association is measured on those same shared rows and on nothing else. Among
the shared rows the primary split sends some left and the rest right; the
default branch for this comparison is whichever of those two sides is larger,
so the number of shared rows it places wrongly is the size of the smaller side.
The association of the kept stand-in is how many more shared rows it places
correctly than that default branch does, divided by how many shared rows that
default branch places wrongly. Neither count is taken over the node's other
rows. A stand-in that does not improve on the default branch is dropped. The survivors are ranked by association from
largest down, then by feature number, then by threshold, then plain reading
before reversed. That ranked list is reported for every internal node, so the
nodes need names: number them in the order the fit creates them, the root zero,
each node's left subtree numbered in full before its right subtree begins.
Terminal groups carry a number too but report no stand-ins.

## Placing an example

At an internal node a row goes by the primary split when its entry for the
primary feature is recorded. Otherwise it goes by the first stand-in in the
node's ranked list whose own feature is recorded for that row. When none of
them is recorded the row takes the node's default branch, which is the side
that received more of the node's rows under the primary split, a tie going
left. Training rows and held out rows travel by exactly the same procedure.

## Refusal

A malformed query is refused. The input format notes list every condition.
