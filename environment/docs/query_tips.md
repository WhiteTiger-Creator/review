# Query tips

General Cypher dialect notes for this Kuzu 0.6.1 database, not specific to the
question in instruction.md. They record engine behaviour that is easy to
mistake for a mistake of your own.

Use `AS` to alias a returned expression, for example `RETURN s.name AS system_peer`.

Use `WITH` to pass intermediate values from one part of a query to the next,
and to group and aggregate before returning. A `WITH` that contains an
aggregate groups by every other expression it projects.

`OPTIONAL MATCH` keeps rows from the preceding part of the query even when its
pattern matches nothing, binding the unmatched variables to null. `count(x)`
over a nullable variable counts only the non-null bindings, and `min(x)`
ignores nulls.

An `EXISTS { MATCH ... }` subquery inside a `WHERE` clause tests whether a
pattern can be found, and `NOT EXISTS { MATCH ... }` tests that it cannot. A
`COUNT { MATCH ... }` subquery evaluates to the number of matches as an
ordinary integer expression rather than as an aggregate. Both may reference
variables already bound in the outer query, and both may be nested inside one
another.

This Kuzu version rejects an aggregate computed over another aggregate, such as
`max(...)` applied to a value that a previous `WITH` produced with `count(...)`,
raising `Expression ... contains nested aggregation`.

This Kuzu version also rejects renaming an aggregate-derived value on its own,
as in `WITH count(x) AS n RETURN n AS total`, raising `Cannot evaluate
expression with type PROPERTY`. Give an aggregate its final column name in the
`WITH` that computes it. Using such a value inside a larger expression, for
example `n - k AS remainder`, `CASE WHEN n = 0 THEN ... END AS flag`, or
`substr(n, 1, 2) AS head`, is accepted.

Deeply nested subqueries are accepted inside a `WHERE` clause but may raise the
same `PROPERTY` error when placed directly in a `RETURN` projection.

String concatenation with `+` in this version treats a null operand as an empty
string instead of yielding null, so guard a concatenation over possibly-null
values with an explicit `CASE`.

`FROM`, `TO` and `IN` are reserved words and cannot be used bare as identifiers.

Use `LIMIT` while exploring the graph interactively through runquery.sh, then
remove it before writing the final query to answer.cypher, since the requested
output should include every client.
