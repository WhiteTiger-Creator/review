A dependency resolver decides, build by build, which prerelease it installs for
a release line. Complete the resolver's install-preference policy so every
scenario resolves correctly. Nothing is fetched or executed; each scenario is a
self-contained resolver session, supplied as rows of text on standard input.

Each scenario opens with a line reading SCENARIO and an identifier and closes
with ENDSCENARIO. Two row kinds sit between them, resolved top to bottom. A
REQUIRE row names a version and records a requirement the resolver must honour
for that version's release line; requirements raised earlier stay in force and
accumulate. A CMP row reads CMP, a short query label, then two candidate version
strings, each major.minor.patch, a hyphen, and a prerelease tag of dot-separated
identifiers (row grammar in environment/docs).

For each CMP the resolver reports one line, in scenario and query order: the
scenario id, a bar, the query label, a bar, and the resolution. The resolution is
one candidate string copied verbatim when the resolver installs a build; the
token NONE when it installs neither; the token INCOMPARABLE when the candidates
differ in major.minor.patch core. REQUIRE rows report nothing.

Which build is installed follows from the prerelease install-preference ordering
over identifiers — not always agreeing with standard version precedence —
together with the requirements in force. The worked scenarios under
environment/data/examples pair inputs with resolutions; use them to pin the exact
policy. The resolver is a Rust crate; building it in release mode offline in the
app directory produces the binary.
