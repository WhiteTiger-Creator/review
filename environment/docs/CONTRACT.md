# Warped-response Gaussian process regression: model contract

This file is normative. It fixes the model, the conventions it is built on, and
the quantities to report. No library default may be substituted for anything
stated here.

## 1. Input tables

All three tables live in the data directory passed to the program.

`planets.csv`: planet_name, facility, log_mass_earth, radius_earth,
radius_sigma_earth. One row per planet. `facility` is the discovery facility
the planet belongs to and is the key `configurations.csv` selects on.
`log_mass_earth` is the regression input x. `radius_earth` is the response y
and is strictly positive. `radius_sigma_earth` is the known measurement
standard deviation of the response, expressed on the radius scale.

`configurations.csv`: config_id, facility, n_train, signal_variance,
lengthscale, jitter, warp_catalogue, boxcox_lambda, quantile_low,
quantile_high, tie_tolerance. One row per configuration.

`queries.csv`: config_id, query_index, log_mass_earth. Query inputs, several
rows per configuration.

## 2. Training set selection

For a configuration, the training set is the first `n_train` rows of
`planets.csv` whose `facility` equals the configuration's `facility`, taken in
the order they appear in the file. Row order is part of the contract; do not
re-sort.

## 3. Warp catalogue

`warp_catalogue` is a semicolon separated list of warp names, in catalogue
order. Each warp g is a strictly increasing map from the positive reals into
the reals.

    identity   g(y) = y
    log        g(y) = log(y)
    boxcox     g(y) = (y^lam - 1) / lam

where `lam` is `boxcox_lambda` and is strictly positive. `log` is the natural
logarithm.

## 4. Model, per configuration and per warp

The model is a Gaussian process regression of the warped response on
`log_mass_earth`, fitted independently for each configuration and each warp in
that configuration's catalogue. Let y be the training responses, sigma the
training `radius_sigma_earth` values, and x the training `log_mass_earth`
values.

Warped scale. The response the model is fitted to is g(y), one value per
training row.

Noise. Each observation carries a known measurement uncertainty. `sigma` is a
standard deviation on the radius scale, while the model is fitted on the warped
scale, so each observation's uncertainty must be expressed on the warped scale
before it enters the model. That transfer is made to first order in `sigma`.
Taking the published value unchanged as a warped-scale standard deviation is a
different model and is not the one specified here, and neither is any endpoint
or higher-order construction.

Offset. The offset subtracted from the warped training responses is their
arithmetic mean, formed after warping and never before. The same offset is
added back when the fitted model predicts on the warped scale.

Covariance. The kernel is squared exponential with the parameterisation

    k(a, b) = signal_variance * exp(-0.5 * ((a - b) / lengthscale)^2)

The training covariance combines this kernel over the training inputs with the
per-observation known noise on its diagonal and the configuration's `jitter`,
also on the diagonal. That matrix is used for every linear solve and for the
log determinant, so the jitter is part of the evidence. The jitter is never
added to any reported predictive variance or covariance.

## 5. Evidence

For each warp in the catalogue, report the log marginal likelihood that the
fitted model assigns to that configuration's training observations.

The likelihood is a density over the recorded radii themselves, not over their
warped values. Section 6 compares these numbers across the warps in the
catalogue, so all of them must be densities of the same observed quantity on
the same scale, or the comparison is meaningless.

## 6. Selection

Let the leading evidence be the largest of the catalogue. `selected_warp` is
the warp appearing earliest in `warp_catalogue` among those whose evidence is
no less than the leading evidence minus `tie_tolerance`.

## 7. Predictive distribution

Conditioning the fitted model on its training rows gives a joint predictive
distribution over the configuration's query inputs, taken in `query_index`
order. That distribution lives on the warped scale. Every quantity in section 8
is reported on the radius scale.

## 8. Reported quantities, per configuration and per warp

Report all of the following for every warp in the catalogue, not only for the
selected one. Each refers to the predictive distribution of radius, that is, to
the model's predictive distribution mapped back onto the radius scale.

Every warp is increasing, so `median[j]`, `quantile_low[j]` and
`quantile_high[j]` are the inverse warp applied to the median and to the
corresponding quantiles of the warped-scale predictive at query index j.
`mode[j]`, `mean[j]` and `covariance[i][j]` are not images of any warped-scale
quantity; each is a property of the distribution of radius itself.

`median[j]` is the median of the predictive distribution of radius at query
index j.

`mode[j]` is the mode of that same distribution: the radius at which its
probability density attains its greatest value.

`quantile_low[j]` and `quantile_high[j]` are the quantiles of that same
distribution at the probability levels `quantile_low` and `quantile_high`.

`mean[j]` is the mean of that same distribution.

`covariance[i][j]` is the covariance between predicted radius at query index i
and predicted radius at query index j, under the joint predictive distribution
over the whole query block. It is a property of the joint distribution; the
per-query variances alone do not determine it.

Definedness. Not every one of these quantities exists for every warp in the
catalogue, and a quantity may fail to exist at some query indices and not at
others. Where a quantity is not defined for the model as specified, report JSON
null in its place, following section 9. Establishing which quantities are
undefined, for which warps, and at which query indices follows from the model
and the warp catalogue, and is part of the task. Do not substitute a truncated
integral, a plug-in value, or a neighbouring quantity for one that is
undefined.

Each warp is inverted on the natural domain of its own defining expression in
section 3, not on the image of the forward map. The identity and log inverses
are therefore defined at every real argument, and a reported radius that comes
out negative under such a warp is a value of the quantity, not an undefined
one.

## 9. Output

The program takes two positional arguments: the data directory first, then the
output path. Write one JSON object to that output path. The block
below fixes the shape of the output only. Its names and numbers are invented
for illustration and correspond to no configuration in the data.

    {
      "configurations": [
        {
          "config_id": "cfg_...",
          "selected_warp": "...",
          "warps": [
            {
              "warp": "identity",
              "evidence": -111.111,
              "median": [ ... ],
              "mode": [ ... ],
              "quantile_low": [ ... ],
              "quantile_high": [ ... ],
              "mean": [ ... ],
              "covariance": [ [ ... ], ... ]
            }
          ]
        }
      ]
    }

Configurations appear in the order they occur in `configurations.csv`. Warps
appear in catalogue order. Array entries follow `query_index` ascending. Numbers
are JSON numbers, not strings. Write every real value with at least fifteen
significant digits, so that rounding of the printed form is never what decides
the comparison in section 10.

Nulls follow the definedness rule in section 8. When a reported quantity is
undefined for a warp as a whole, its value is JSON null in place of the entire
array or matrix that would otherwise stand there. When a single entry of an
array quantity is undefined and the rest are not, that entry is JSON null
inside the array and the remaining entries carry their numbers as usual.

## 10. Agreement

Every reported number is checked against an independent recomputation. Values
agree when the relative difference is at most 1e-8, or the absolute difference
is at most 1e-10 for quantities whose magnitude is below one. Covariance entries
are compared with an absolute tolerance scaled by the square root of the product
of the two matching diagonal entries.
