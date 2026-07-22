# Factorization-machine score

For input x, bias w0, linear weights wi, and latent weights vi,f:

score = w0 + sum_i(wi xi) + 0.5 sum_f((sum_i(vi,f xi))^2 - sum_i((vi,f xi)^2))

probability = 1 / (1 + exp(-score)).

Compute each latent factor in linear time over nonzero features using the difference-of-squares identity above. Clamp scores to the range [-35, 35] before sigmoid evaluation.
