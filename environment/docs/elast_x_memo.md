# ELAST-X v2 modeling memo

This is the working spec for ELAST-X v2, the demand model behind the weekly price recommendations.
It supersedes v1 (plain log-linear OLS per segment). The changes in v2 are not cosmetic. They move
the fitted coefficients, so a run that skips any of them is not ELAST-X v2, it is something else that
happens to compile.

The model is a single regularized linear regression of weekly log-demand on log-price and a handful of
covariates. It is fit once over the training weeks of a product-week panel, and it reports per-segment
price elasticities plus a holdout error figure. Everything below is what "fit ELAST-X v2" means in
practice.

## Panel and split

Input is one CSV with a row per product-week. Columns: `product_id`, `segment`, `week`, `price`,
`units`, `competitor_price`, `promo`, `holiday`, `traffic`. Weeks run 0..59. There are four segments:
`grocery`, `apparel`, `electronics`, `home`.

We fit on the first 48 weeks (week < 48) and hold out the last 12 (week >= 48). The holdout weeks are
used only for the reported error metric. They never enter any fit, any percentile, any moment, or any
cross-validation fold.

## Target

Demand is heavy-tailed and some weeks sell nothing, so v1's per-segment log broke on zero-unit weeks and
v2 does not use `log1p` either (a unit offset overweights the tail). The target is

    y = ln(units + 8)

The additive offset of 8 is fixed. It is inside the log, applied to every row, train and holdout alike.
When we invert a prediction back to units we subtract 8.

## Features and parameterization

Four features are log-transformed with natural log: `log_price = ln(price)`,
`log_competitor_price = ln(competitor_price)`, `log_traffic = ln(traffic)`, and a linear time term
`week_trend = week / 60`. Two features stay as raw 0/1 indicators: `promo` and `holiday`.

Price response is per segment, everything else is shared. Concretely the design has one intercept per
segment and one price slope per segment (the coefficient on that segment's standardized log_price), and
then a single shared coefficient for each of `log_competitor_price`, `promo`, `holiday`, `log_traffic`,
`week_trend`. There is no global intercept and no global price term; the four segment intercepts carry
the level and the four segment slopes carry the price response. A row only loads its own segment's
intercept and slope.

## Sample weights

The fit is weighted least squares, not OLS. Two effects combine multiplicatively into one weight per row:

    recency_i = 0.97 ^ (w_max - week_i)
    volume_i  = ln(1 + units_i)
    w_i       = recency_i * volume_i

`w_max` is the latest training week (47 on a full panel, but take it from the data). Recency downweights
older weeks geometrically at 0.97 per week back from `w_max`. Volume upweights weeks that actually sold,
on a log scale so a blockbuster week does not swamp the fit. Floor any weight at or below 1e-6 to 1e-6 so
a zero-unit row keeps a positive weight, then rescale the whole vector so the weights sum to the training
row count (multiply every weight by n / sum(w)). The rescaled weights are what feed the percentiles, the
standardization moments, the ridge normal equations, and the cross-validation error. Same weights
everywhere.

## Winsorization

Prices and traffic have occasional extreme weeks that we clip rather than drop. Winsorize three features
at weighted percentiles computed on the training rows: `log_price` and `log_competitor_price` at the 2.5
and 97.5 percentiles, `log_traffic` at the 5.0 and 100.0 percentiles (so traffic is clipped from below
only). `week_trend`, `promo`, `holiday` are not winsorized.

The weighted percentile is not the usual unweighted rank. Sort the values ascending, let the sorted
weights be w(1)..w(m), and define the cumulative position of the i-th sorted value as

    c_i = ( sum_{j<=i} w_j  -  w_i / 2 ) / sum_j w_j

Then the p-th percentile is found at target t = p/100 by linear interpolation on the c_i: below c_1 clamp
to the smallest value, at or above c_m clamp to the largest, otherwise interpolate between the two
bracketing values. Clip each feature to its [low, high] limit. The limits are learned on train and the
same train limits are reused when the holdout rows are transformed for the error metric.

## Standardization

After winsorizing, standardize the four continuous features (`log_price`, `log_competitor_price`,
`log_traffic`, `week_trend`) to weighted zero mean and unit variance. The moments are weighted and are
computed on the winsorized training values:

    mean = sum_i w_i x_i / sum_i w_i
    var  = sum_i w_i (x_i - mean)^2 / sum_i w_i     (population form, divide by sum of weights)
    z    = (x - mean) / sqrt(var)

Order matters and it is winsorize, then form the weights, then take weighted moments, then standardize.
Standardizing the raw feature and winsorizing afterward, or using unweighted moments, gives a different
scale and a different fit. `promo`, `holiday`, and the segment indicators are used as is, never
standardized. Holdout rows are standardized with the training moments and training winsor limits.

## Ridge fit

The estimator is ridge (L2) on the weighted design. Solve the normal equations

    (X' W X + lambda I) beta = X' W y

where W is the diagonal of sample weights. The penalty lambda multiplies the identity and is applied to
every coefficient including the segment intercepts (no column is left unpenalized). Solve the linear
system directly; any stable dense solver gives the same beta to machine precision, so there is no
iteration tolerance to tune.

## Choosing lambda

lambda is picked from the grid {0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0} by 5-fold cross-validation, and
the folds are blocked in time, not random. Take the sorted list of distinct training weeks and cut it
into 5 contiguous blocks of as equal size as possible; when the count does not divide evenly the earlier
blocks take the extra week. Each block in turn is the validation fold. Around every validation block
apply an embargo of 3 weeks: any training week within 3 of the block's first or last week is dropped from
that fold's training set (it is neither trained on nor validated). The rest of the training rows are the
fold's training set.

For each lambda, fit on each fold's training rows and score the fold's validation rows by weighted mean
squared error of y (weighted by the same sample weights), then average the five fold errors. That average
is the cross-validation error for that lambda and the full curve over the grid is reported.

Selection is the one-standard-error rule, not the raw minimum. Let j be the lambda with the smallest mean
CV error. Compute the standard error of its five fold errors as the sample standard deviation (divide by
5 - 1) over sqrt(5). The threshold is (min mean error + that standard error). Among all lambdas whose mean
CV error is at or below the threshold, choose the largest lambda. That is the working lambda; refit on all
training rows with it.

## Monotonicity

Price elasticities are supposed to be non-positive: raising price should not raise modeled demand. Some
segments, `home` in particular, carry enough confounding that the unconstrained slope comes out positive.
We do not keep a positive price slope. After the full-training refit at the working lambda, look at each
segment's fitted price slope. For every segment whose slope is greater than zero, drop that segment's
price-slope column (force that coefficient to exactly zero) and refit the whole model jointly with those
columns removed, at the same lambda. Segments whose slope was already non-positive keep their columns.
The projection is one refit over all offending segments at once, not one-at-a-time. If no segment
violates, there is nothing to project.

## Elasticities

Report an arc elasticity per segment at that segment's reference price, where the reference price is the
median `price` over the segment's training rows. Predict demand at the reference price and at 1.10 times
it, holding everything else at the training baseline: the covariates at their standardized mean (a z of
zero), `promo` and `holiday` at zero, using only the segment's intercept and price slope. Turn ln(price)
into the model's z the same way training did, with the training winsor limits and the training log_price
moments, and invert the target (subtract the offset) to get units at each price. Then the arc elasticity
is the midpoint (log-free) form

    E = ((Q2 - Q1) / ((Q1 + Q2)/2)) / ((P2 - P1) / ((P1 + P2)/2))

with P1 the reference price, P2 = 1.10 * P1, and Q1, Q2 the demands at those prices. A projected-to-zero
slope gives a flat prediction and therefore an elasticity of zero.

## Holdout error

The reported error is a weighted MAPE over the holdout weeks, computed with the trained model. For each
holdout row predict units (transform the row with the training winsor limits and moments, apply the fitted
coefficients, invert the target). The per-row absolute percentage error uses a floored denominator,

    ape_i = |pred_i - units_i| / max(units_i, 5)

so tiny-demand weeks cannot blow the metric up. Weight each row by its actual `units` and take the
weighted mean, sum(units_i * ape_i) / sum(units_i). Rows with zero units contribute zero weight and drop
out. This is one number over the whole holdout, not per segment.

## Output

Write `/app/artifacts/elasticity.json`, one object with these fields:

- `lambda`: the working lambda (a number from the grid).
- `coefficients`: an object with `intercept_<segment>` and `price_slope_<segment>` for each of the four
  segments, and one entry each for `log_competitor_price`, `promo`, `holiday`, `log_traffic`,
  `week_trend`. These are the post-projection coefficients on the standardized design.
- `cv_mean_error`: an object mapping each grid lambda to its mean cross-validation error.
- `elasticities`: an object mapping each segment to its arc elasticity.
- `holdout_weighted_mape`: the single weighted MAPE number.

All figures are full-precision doubles. The elasticities and coefficients are reported on the standardized
scale described above; do not rescale them back to raw units.
