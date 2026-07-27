# Output format

Plain text on standard output, one line per reported quantity, in query order.
Every line starts with the query identifier. A query reports its feature
summary first, one line per feature in increasing feature number, and then one
line per held out example in row order. There are three line shapes.

## The per feature summary

```
<qid> V <j> P <n>/<d> S <n>/<d>
```

`j` is the feature number. The value after `P` is how much impurity that
feature removed across the whole fitted model as a primary split, summing over
every decision point that chose it the impurity reduction multiplied by the
number of training examples at that point. The value after `S` is the matching
total earned as a substitute, summing over every decision point that retained
it the association multiplied by the number of training examples there. A
feature that never acts in a role reports `0/1` for it.

## The per example report

```
<qid> Q <i> C <c> N <m> I <n>/<d> E <n>/<d> D <n>/<d> <n>/<d> ...
```

`i` is the row number of the held out example. `c` is the class the model
predicts for it. `m` is how many training examples support that prediction,
meaning the size of the terminal group the example lands in. The value after
`I` is the Gini impurity of that terminal group. The value after `E` is how
strong the weakest evidence used to place this example was: `1/1` when its
recorded measurements answered every question the model asked, otherwise the
smallest association among the substitutes it had to lean on, and `0/1` when
at some point nothing it carried was recorded at all. The values after `D` are
the class distribution of the terminal group, one reduced fraction per class
in increasing class number, and they sum to one.

## A split the fit makes

```
<qid> D <node> V <k> T <t> N <m> G <n>/<d>
```

One line per internal node, in numbering order. `k` is the measurement the node
splits on and `t` its threshold, `m` is how many training rows reached the node,
and the value after `G` is the impurity the split removed per row. Terminal
groups emit no such line. These lines come before the stand-in lines.

## The stand-ins of a node

```
<qid> G <node> R <r> V <k> T <t> D <F|V> A <n>/<d>
```

One line per stand-in kept at an internal node, the nodes in numbering order
and, within a node, in ranked order. `node` is the node's number, `r` is the
stand-in's rank counting from one, `k` is the feature it splits on and `t` its
threshold. `D` is `F` when the stand-in sends its low side the same way the
primary split sends its low side, and `V` when it sends it the other way. The
value after `A` is the association. An internal node that kept nothing emits no
line, and a terminal group never emits one.

## A refused query

```
<qid> REJECT
```

## Rendering

Every reported quantity is an exact rational written as a numerator, a single
slash and a denominator, always in lowest terms with a positive denominator,
so zero is `0/1` and one is `1/1`. Nothing is rounded and no decimal point
appears. Fields are separated by single spaces and no line carries trailing
whitespace. The shipped example outputs show the canonical rendering of every
line shape.
