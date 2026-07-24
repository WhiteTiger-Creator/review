# Certificate Policy Intersection

Certificate Policies specify the rules and purposes under which a certificate is issued. Policy Constraints restrict the set of valid policies along the admitted chain.

## 1. Policy OIDs and anyPolicy
- A policy is represented by an Object Identifier (OID) string (e.g., `"1.2.3.4"`).
- The special policy OID `"2.5.29.32.0"` represents the `anyPolicy` wild card.

## 2. Policy Intersection Algorithm
For a chain `[C_0, C_1, ..., C_k]` (where `C_0` is the target leaf and `C_k` is the trusted root):

We define the valid policy set `V_i` at each certificate in the chain, starting from the root `C_k` and moving downwards to the leaf `C_0`.

1. **Initialization**:
   - `V_k` is the set of policy OIDs listed in the root certificate `C_k.certificate_policies`.
   - If `C_k` has no policies specified, `V_k` is empty.

2. **Downwards Propagation**:
   - For `i` from `k - 1` down to `0`:
     - Let `P_i` be the set of policies in `C_i.certificate_policies`. If none are specified, `P_i` is empty.
     - If `V_{i+1}` is empty:
       - `V_i = P_i`
     - Else if `V_{i+1}` contains `anyPolicy` (`"2.5.29.32.0"`):
       - `V_i = P_i`
     - Else if `P_i` contains `anyPolicy` (`"2.5.29.32.0"`):
       - `V_i = V_{i+1}`
     - Else:
       - `V_i = V_{i+1} ∩ P_i` (the intersection of the two sets).

3. **Validation Verdict**:
   - After computing `V_i`, if `V_i` is empty and `P_i` was non-empty, the policy intersection check fails.
   - If both `V_{i+1}` and `P_i` are empty, `V_i` remains empty and propagation continues without failure.

## 3. Explicit Policy Requirement
A CA certificate `C_j` (where `j > 0`) may assert a `require_explicit_policy` value `R` (an integer `>= 0`).

When `C_j` specifies `require_explicit_policy` as `R` and the distance from `C_j` to the leaf satisfies `j >= R`:

- The **leaf certificate `C_0` must declare** at least one explicit policy OID in its own `certificate_policies` field (an OID other than `"2.5.29.32.0"` / `anyPolicy`).
- This requirement is evaluated against the leaf's asserted policies, **not** against the computed set `V_0` after intersection and anyPolicy propagation.
- A leaf whose `certificate_policies` contains only `anyPolicy` fails the requirement even when upstream propagation would leave a non-empty computed `V_0` containing explicit OIDs inherited from parent CAs.
