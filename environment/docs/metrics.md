# Evaluation metrics

Evaluation uses probability >= 0.5 as the positive prediction.

Log-loss is the mean of -y ln(p) - (1-y) ln(1-p), after clamping probability to [1e-15, 1-1e-15].

AUC uses average ranks for tied probabilities:

(sum of positive ranks - positive_count * (positive_count + 1) / 2) / (positive_count * negative_count)

If either class is absent, AUC is zero.

The output is UTF-8 and ends with one newline:

count N
logloss VALUE
auc VALUE
tp N
tn N
fp N
fn N

Floating metrics use twelve digits after the decimal.
