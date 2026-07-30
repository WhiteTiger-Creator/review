A planetary science group models how planet radius varies with planet mass, fitting a Gaussian process regression to real transit survey measurements. Radius is strictly positive and strongly right skewed, so the group never assumes the raw response is the right scale. Each configuration names a catalogue of monotone warps, the regression is fitted in warped space, and every reported quantity is expressed back in radius units.

The measurements sit in the data directory as three comma separated tables covering planets, model configurations, and query masses. The model and the conventions it rests on are fixed in CONTRACT.md under the docs directory: the warp catalogue, the scale each observation's known uncertainty belongs to, the centring rule, the covariance function, how the known noise and the stabilising jitter enter, what the reported evidence is a density over, the selection rule and its tie break, and the output schema. None of it is optional, and no library default may be substituted.

For every configuration and every warp in the catalogue the deliverable is the log marginal likelihood, the predictive median, mode, and two predictive quantiles at each query mass, the predictive mean, and the predictive covariance across the query block, together with the warp the evidence selects. Not all of those quantities exist under every warp, and working out which do is part of the problem.

For λ > 1, the Box–Cox mode may be computed either using the closed-form expression or by numerical optimization. Any numerical optimization must converge accurately enough to satisfy the required output tolerance.

The image carries R and the data. The program belongs at /app/solve.R and runs under Rscript, taking a data directory and an output path.
