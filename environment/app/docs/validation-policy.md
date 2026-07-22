# Validation Policy

Validation traces represent staged study excerpts that were held out from model training. The validation report should be produced by running the final adapted duration-aware model, Viterbi decoder, and forward-backward calculation used for inference, not by reading validation labels directly into predictions or posterior values. Validation contributes only aggregate values to validation_metrics.json; it never adds rows or events to the three inference CSV files.

Accuracy is the number of matching Viterbi state predictions divided by the number of validation rows. For each state, F1 is 2 * precision * recall / (precision + recall). If a state has zero true positives, zero predicted positives, and zero actual positives in a custom fixture, use F1 = 0 for that state. Macro_f1 is the average of the three state F1 values in documented state order.

For every validation sequence, forward-backward returns its natural-log likelihood. mean_negative_log_likelihood is the negative sum of those sequence log likelihoods divided by the total number of validation rows. At every validation row, entropy is -sum(p * ln(p)) over the three clinical-state posterior probabilities, treating a zero-probability term as zero. mean_posterior_entropy is the average of those row entropies over all validation rows.
