# Log-loss gradients

For label y and probability p, the score derivative is g = p - y.

For one example:

- bias gradient: g
- linear gradient for i: g xi + l2 wi
- latent gradient for i,f: g xi (sum_j(vj,f xj) - vi,f xi) + l2 vi,f

The self-term subtraction is required. L2 regularization applies to linear and latent weights, never to bias. Mini-batch gradients are accumulated against one unchanged model snapshot and divided by the number of examples in that batch before an update.
