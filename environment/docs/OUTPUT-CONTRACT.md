# Output contract

## Input bundle

Read cases.csv and records.csv by header. Required case columns are
case_id, alpha, gamma, budget, min_ess, ridge, history_horizon, and
stability_limit. Required record columns are case_id, policy_id, cluster, t,
state, next_state, action, group, item_id, reward, cost, x1, x2, target_prob,
behavior_prob, and source_id. Extra columns and physical row or column order
are irrelevant.

Identifiers are printable ASCII and contain none of vertical bar, colon, comma,
carriage return, or newline. Cluster, t, state, next_state, action, group,
item_id, and history_horizon are integers. Each case-policy-cluster-t key is
unique. Every case has at least two policies and exactly four clusters; every
policy covers all four clusters and retains both groups after any one cluster
is deleted. Times are strictly increasing within a case-policy-cluster after
sorting. Group is 0 or 1. Probabilities are finite and strictly positive. All
other numeric inputs are finite. Alpha, min_ess, ridge, and history_horizon are
positive; gamma and stability_limit are nonnegative.

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

For row a, divide both entries by 4 plus that row's sum to obtain B.
branching_radius is the Perron root of B. Let m_a be the w-weighted mean of q
in group a and p_a its share of total w. Solve (I-B)u=m. full_value is
p_0*u_0+p_1*u_1.

For each group, sum w by cluster and compute
(sum s_c)^2/sum s_c^2. effective_sample_size is the smaller group value.

## Deletion robustness and selection

Delete each cluster in increasing numeric order. On every retained surface,
refit every held-out ridge system, branching matrix, value, risk, and support
quantity for every policy. For a full-data policy, worst_deletion_radius is the
largest deletion risk and jackknife_instability is the largest absolute
difference between a deletion value and its full value. Define

robust_value = full_value - gamma*jackknife_instability
               - 0.5*max(0,worst_deletion_radius-budget).

A full policy is feasible exactly when its full and worst-deletion risks are at
most budget, its full effective_sample_size is at least min_ess, and its
instability is at most stability_limit. Select among feasible policies when any
exist, otherwise among all policies. Order the pool by greater robust_value,
greater full_value, smaller worst_deletion_radius, greater
effective_sample_size, then bytewise smaller policy_id. feasible_count is the
full-data feasible count.

On a deletion surface, feasibility uses risk at most budget and effective
sample size at least 3*min_ess/4. Select feasible policies when possible,
otherwise all policies; order by greater value, smaller risk, greater effective
sample size, then bytewise policy_id. For the selected deletion policy form

cluster:policy:value_code:risk_code:ess_code

where each code is the round-to-even integer of 10^6 times the corresponding
quantity. Join the four cluster tokens with vertical bars as deletion_code.

## Output and audit

Atomically replace the destination with one unquoted CSV having this exact
header:

case_id,selected_policy,feasible_count,robust_value,full_value,branching_radius,worst_deletion_radius,effective_sample_size,jackknife_instability,deletion_code,audit_signature

Emit rows in cases.csv order. Integer and identifier fields are exact. Numeric
fields are finite decimals with absolute or relative error at most 2e-6.

For the selected full-data policy, round-to-even 10^7 times robust_value,
full_value, branching_radius, worst_deletion_radius, effective_sample_size, and
jackknife_instability. Form

case_id|selected_policy|deletion_code|feasible_count|robust_code|value_code|risk_code|worst_risk_code|ess_code|instability_code

from the displayed decimal integers. Starting with acc=0, process each ASCII
code point x at one-based position k as acc=(131*acc+x+k) modulo 2147483647.
audit_signature is acc as exactly eight lowercase hexadecimal digits.
