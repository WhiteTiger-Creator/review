# Output contract

## Input bundle

Read cases.csv and records.csv by header. Required case columns are
case_id, alpha, gamma, budget, min_ess, ridge, history_horizon, and
stability_limit, pair_budget, interaction_limit, switch_gain,
dispersion_penalty, dispersion_limit, max_concentration, and mixture_units.
Required record columns are case_id, policy_id, cluster, t, state, next_state,
action, group, item_id, reward, cost, x1, x2, target_prob, behavior_prob, and
source_id. Extra columns and physical row or column order are irrelevant.

Identifiers are printable ASCII and contain none of vertical bar, colon, comma,
plus sign, at sign, carriage return, or newline. Cluster, t, state, next_state,
action, group, item_id, history_horizon, and mixture_units are integers. Each
case-policy-cluster-t key is unique. Every record's case_id must reference a
case_id present in cases.csv. Every case has exactly four policies and exactly
four clusters; every policy covers all clusters and retains both groups after
any one cluster or any two clusters are deleted. Times are strictly increasing
within a case-policy-cluster after sorting. Group is 0 or 1. Probabilities are
finite and strictly positive. All other numeric inputs are finite. Alpha,
min_ess, ridge, and history_horizon are positive. Gamma, budget, pair_budget,
stability_limit, interaction_limit, switch_gain, dispersion_penalty, and
dispersion_limit are nonnegative. Mixture_units is between 4 and 8 inclusive.
Max_concentration is between 0.25 and 1 inclusive.

Reject a bundle with a missing required header or any violation above: exit
nonzero and do not create or replace the requested output.

## Cross-fitted marked scores

All calculations below are per case-policy. Set w to target_prob/behavior_prob
and y to reward minus gamma times cost. The feature row is

(1, x1, x2, x1*x2, I(action=next_state)).

For each retained cluster, fit on all other retained clusters the weighted ridge
system

(sum w*x*x' + ridge*diag(0,1,1,1,1))*beta = sum w*x*y.

The held-out event score is q = x*beta + w*(y-x*beta). Fit every held-out
cluster separately. This rule is reapplied from scratch on each deletion
surface.

## Marked branching functional

Initialize every entry of a 2 by 2 matrix H to 0.005. Within each cluster sort
by t. For every earlier event i and later event j whose positive lag does not
exceed history_horizon, add to H[group_i,group_j]

sqrt(w_i*w_j) * exp(-alpha*(t_j-t_i))
* (1 + gamma*I(next_state_i=state_j))
* (1 + 0.15*abs(q_i-q_j)).

For row a, divide both entries by 4 plus that row's sum to obtain B. Let m_a be
the w-weighted mean of q in group a and p_a its share of total w. The base
policy value is p' (I-B)^(-1) m.

Retain B, m, p, the base policy value, and every group-by-cluster weight total
for the portfolio calculation.

## Randomized policy portfolios

Sort the four policy identifiers bytewise. A portfolio is every vector of four
nonnegative integer counts summing to mixture_units. Its weights lambda are the
counts divided by mixture_units. Its portfolio code lists only positive counts
as policy@count, in sorted policy order, joined by plus signs.

On each surface, combine the four independently fitted policy models. First set

Bbar = sum_p lambda_p B_p.

For every policy pair p<r add the elementwise matrix

switch_gain * lambda_p * lambda_r * sqrt(B_p * B_r)

to Bbar. Set mbar=sum_p lambda_p m_p and pbar=sum_p lambda_p p_p. The
portfolio branching radius is the Perron root of Bbar, and its value is
pbar' (I-Bbar)^(-1) mbar.

For each group and retained cluster, mix the corresponding policy weight totals
with lambda. Its group support is (sum s_c)^2/sum s_c^2, and
effective_sample_size is the smaller group support. Let z_p be the base policy
value on this surface and zbar=sum_p lambda_p z_p. Define

policy_dispersion = sqrt(sum_p lambda_p * (z_p-zbar)^2)

and mixture_concentration=sum_p lambda_p^2.
Discard portfolios whose concentration exceeds max_concentration. The
remaining portfolios are the selection pool on every surface; valid bundles
always retain at least one.

## Full, single-deletion, and pair-deletion surfaces

Use clusters in increasing numeric order. Evaluate the full surface, the four
surfaces obtained by deleting one cluster, and the six surfaces obtained by
deleting each numeric cluster pair. On every retained surface, refit every
held-out ridge system, branching matrix, value, risk, and support quantity for
every base policy, then rebuild every portfolio. In particular, a pair-deletion
fit holds out each retained cluster and trains that held-out score model only
on the other retained cluster.

For a fixed portfolio, let V be its full value, V[-c] its value after deleting
cluster c, and V[-c,-d] its value after deleting clusters c and d. Define:

- worst_deletion_radius as the largest risk among the four single deletions;
- worst_pair_radius as the largest risk among the six pair deletions;
- pair_effective_sample_size as the smallest effective sample size among the
  six pair deletions;
- jackknife_instability as max_c |V[-c]-V|;
- second_order_instability as
  max_{c<d} |V[-c,-d]-V[-c]-V[-d]+V|.

The full robust value is

robust_value = full_value - gamma*jackknife_instability
               - 0.5*(1+gamma)*second_order_instability
               - 0.5*max(0,worst_deletion_radius-budget)
               - 0.75*max(0,worst_pair_radius-pair_budget)
               - dispersion_penalty*policy_dispersion.

A full portfolio is feasible exactly when its full and worst single-deletion
risks are at most budget, its worst pair-deletion risk is at most pair_budget,
its full effective_sample_size is at least min_ess, its
pair_effective_sample_size is at least min_ess/2, its
jackknife_instability is at most stability_limit, and its
second_order_instability is at most interaction_limit. Its full
policy_dispersion is at most dispersion_limit, and its mixture_concentration is
at most max_concentration. Select among feasible portfolios when any exist,
otherwise among all portfolios. Order the pool by greater robust_value, greater
full_value, smaller policy_dispersion, smaller mixture_concentration, smaller
second_order_instability, smaller worst_pair_radius, smaller
worst_deletion_radius, greater pair_effective_sample_size, greater
effective_sample_size, then bytewise smaller portfolio code. Feasible_count is
the number of full-data feasible portfolios.

## Nested deletion certificates

On a single-deletion surface c, each portfolio has three child pair-deletion
surfaces {c,d}. Its child instability is
max_{d != c}|V[-c,-d]-V[-c]|, its child worst risk is the largest child risk,
and its child minimum effective sample size is the smallest child effective
sample size. Define its nested robust value as

V[-c] - gamma*child_instability
      - 0.75*max(0,child_worst_risk-pair_budget)
      - dispersion_penalty*policy_dispersion[-c].

It is feasible exactly when its own risk is at most budget, its child worst
risk is at most pair_budget, its own effective sample size is at least
3*min_ess/4, its child minimum effective sample size is at least min_ess/2, and
its child instability is at most stability_limit. Its policy dispersion is at
most dispersion_limit and concentration is at most max_concentration. Select
feasible portfolios when possible, otherwise all portfolios. Order by greater
nested robust value, greater V[-c], smaller policy dispersion, smaller
concentration, smaller child instability, smaller child worst risk, smaller own
risk, greater child minimum effective sample size, greater own effective sample
size, then bytewise portfolio code. For the selected single-deletion portfolio
form

cluster:portfolio:robust_code:value_code:risk_code:child_risk_code:child_instability_code:ess_code:dispersion_code:concentration_code

where each code is the round-to-even integer of 10^6 times the corresponding
quantity. Join the four cluster tokens with vertical bars as deletion_code.

On a pair-deletion surface, feasibility uses risk at most pair_budget and
effective sample size at least min_ess/2, policy dispersion at most
dispersion_limit, and concentration at most max_concentration. Select feasible
portfolios when possible, otherwise all portfolios. Order by greater value,
smaller policy dispersion, smaller concentration, smaller risk, greater
effective sample size, then bytewise portfolio code. For the selected portfolio
form

cluster1+cluster2:portfolio:value_code:risk_code:ess_code:dispersion_code:concentration_code

with numeric clusters increasing inside a pair and pairs in lexicographic
numeric combination order. Join the six tokens with vertical bars as
pair_deletion_code.

## Output and audit

Atomically replace the destination with one unquoted CSV having this exact
header:

case_id,selected_portfolio,feasible_count,robust_value,full_value,branching_radius,worst_deletion_radius,worst_pair_radius,effective_sample_size,pair_effective_sample_size,jackknife_instability,second_order_instability,policy_dispersion,mixture_concentration,deletion_code,pair_deletion_code,audit_signature

Emit rows in cases.csv order. Integer and identifier fields are exact. Numeric
fields are finite decimals with absolute or relative error at most 2e-6.

For the selected full-data portfolio, round-to-even 10^7 times robust_value,
full_value, branching_radius, worst_deletion_radius, effective_sample_size,
jackknife_instability, worst_pair_radius, pair_effective_sample_size, and
second_order_instability, policy_dispersion, and mixture_concentration. Form

case_id|selected_portfolio|deletion_code|pair_deletion_code|feasible_count|robust_code|value_code|risk_code|worst_risk_code|ess_code|instability_code|worst_pair_risk_code|pair_ess_code|second_order_code|dispersion_code|concentration_code

from the displayed decimal integers. Starting with acc=0, process each ASCII
code point x at one-based position k as acc=(131*acc+x+k) modulo 2147483647.
audit_signature is acc as exactly eight lowercase hexadecimal digits.
