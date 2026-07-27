A classification tree is a model fitted from labelled examples, and this
project reports what one learns from a training table with unrecorded
measurements. The hard part is statistical: a gap is not noise, so an example
missing the measurement a decision rests on still carries class information and
must be classified, not discarded. So beside each primary split the model learns
a ranked list of substitutes over the remaining measurements, each with an
association saying how faithfully it stands in.

Four things are reported. First, for every measurement, how much impurity it
removed in its own right and how much it earned standing in for others, which
together say how far the model leans on it. Second, for every held out example,
the class predicted, how many training examples support it, the impurity and
class distribution of the group it lands in, and how strong the weakest
evidence used to place it was. Third, every split the fit makes, with the
measurement it uses and the impurity it removes. Fourth, the ranked
substitutes each split kept, with the association of each.

Every reported quantity is an exact rational in lowest terms with a positive
denominator. A query names the training table, the held out table, and the
limits the fit obeys; a malformed query yields a single refusal line.

The learning contract and the grammars sit under /app/docs, with ten worked
queries under /app/examples. Every part of the fit must be computed by the code
you write here, never obtained from an existing learning implementation. The
model is written under /app/src, and fitting a large table has to stay under
1200000000 callgrind instruction reads.
