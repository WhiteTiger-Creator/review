# Deterministic SGD schedule

Initialize bias and linear weights to zero. Initialize latent weight at feature index i and factor f as:

0.05 * (2 * unit(seed xor ((i + 1) * 0x9E3779B97F4A7C15) xor ((f + 1) * 0xBF58476D1CE4E5B9)) - 1)

All arithmetic uses wrapping unsigned 64-bit operations. unit applies SplitMix64 finalization to its argument and returns the top 53 bits divided by 2^53.

At the start of each epoch, shuffle example indices using a state initialized to seed xor (epoch + 1) * 0x94D049BB133111EB. For i descending from len-1 to 1, advance the state with SplitMix64 and swap i with state modulo (i + 1).

Use learning rate lr / (1 + 0.1 * epoch), where epoch starts at zero. Process contiguous shuffled mini-batches. The final short batch divides by its actual size.
