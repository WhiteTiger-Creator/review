# DNS Name Constraint Enforcement

Name Constraints are asserted by CA certificates to restrict the namespaces allowed for subject names of subsequent certificates in the admitted chain.

## 1. Domain Extraction
For name constraint evaluation, a certificate's name is extracted from its `subject` field:
- The subject field contains a distinguished name. The domain name is the value associated with the `CN=` (Common Name) attribute.
- For example, if `subject` is `"CN=api.sub.example.com"`, the extracted domain name `D` is `"api.sub.example.com"`.
- If the subject is `"CN=example.com"`, the domain `D` is `"example.com"`.
- End-entity leaf certificates in a validation path use DNS hostnames in their `CN=` value (for example `"CN=api.sub.example.com"`).
- Intermediate and root CA certificates may use organizational `CN=` labels that are not DNS hostnames (for example `"CN=Int NC Parent"`). Those CA subject strings are not used during name-constraint matching.

## 2. Match Rules
A domain name `D` matches a constraint pattern `P` if:
- `D` is exactly equal to `P` (case-insensitive), or
- `D` ends with `.` + `P` (case-insensitive), indicating that `D` is a subdomain/subtree of `P`.

### Examples
- `"api.sub.example.com"` matches `"example.com"` (ends with `".example.com"`).
- `"example.com"` matches `"example.com"` (equal).
- `"badexample.com"` does NOT match `"example.com"`.
- `"example.com"` does NOT match `"sub.example.com"`.

## 3. Namespace Validation
For every CA certificate `C_j` in the path `[C_0, C_1, ..., C_k]` (where `j > 0`) that asserts `name_constraints`:

1. Extract the end-entity domain `D` once from the leaf certificate `C_0` subject (`CN=` value).
2. Evaluate every such `C_j` against that same `D`:
   - If `C_j` specifies `permitted_dns` (non-empty), `D` must match at least one pattern in `permitted_dns`.
   - If `C_j` specifies `excluded_dns`, `D` must not match any pattern in `excluded_dns`.
3. Do not extract or match DNS names from intermediate or root CA subjects. Name constraints apply only to the leaf end-entity hostname, including when multiple CA certificates in the chain each assert nested permitted or excluded DNS patterns.
4. If `name_constraints` is null or omitted on `C_j`, that certificate imposes no name constraint for the path.
