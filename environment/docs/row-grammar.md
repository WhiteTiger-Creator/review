# Input row grammar

Input arrives on standard input as one or more scenarios. Each scenario is a
block delimited by a `SCENARIO <id>` line and a matching `ENDSCENARIO` line, and
is an independent resolver session: rows are processed top to bottom and state
does not carry across scenarios. Two row kinds may appear between the delimiters:

- `REQUIRE <version>` records a requirement the resolver must honour for the
  release line named by `<version>`'s `major.minor.patch` core. Requirements
  raised earlier in a scenario remain in force for the rows that follow.
- `CMP <qid> <left> <right>` records one comparison query. `<qid>` is a short
  identifier that labels the query within its scenario. `<left>` and `<right>`
  are two candidate builds the resolver is choosing between.

Every version is written in the usual `major.minor.patch` form followed by a
hyphen and a prerelease tag made of dot-separated identifiers drawn from the
alphabet `[0-9A-Za-z-]`. Numeric identifiers never carry a leading zero. Build
metadata is never present.

Row order is preserved in the output. Every token is an ASCII word with no
embedded spaces, and fields are separated by single spaces. Nothing is fetched
or built for real; the answer to each query is a pure function of the version
strings the scenario names and the order in which its rows appear.
