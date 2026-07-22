A dependency resolver decides, build by build, which prerelease it installs for
a release line. This task models that install-preference policy. Nothing is
fetched or executed; scenarios arrive as rows of text on standard input.

Each scenario opens with a line reading SCENARIO and an identifier and closes
with ENDSCENARIO, and is an independent resolver session. Two row kinds sit
between them, processed top to bottom. A REQUIRE row names a version and records
a requirement the resolver must honour for that version's release line;
requirements raised earlier stay in force and can accumulate. A CMP row reads
CMP, a short query label, then two candidate version strings, each
major.minor.patch, a hyphen, and a prerelease tag of dot-separated identifiers
(row grammar in environment/docs).

For each CMP one line is emitted, in scenario and query order: the scenario id,
a bar, the query label, a bar, and the result. The result is one candidate
string copied verbatim when the resolver installs a build; the token NONE when
it installs neither; the token INCOMPARABLE when the candidates differ in
major.minor.patch core. REQUIRE rows emit nothing.

Which build is installed follows from the prerelease install-preference ordering
— read identifier by identifier, left to right, not always agreeing with
standard version precedence — together with the requirements in force. Infer the
precise policy from the worked scenarios under environment/data/examples, which
pair inputs with expected output. Building cargo in release mode offline in the
app directory produces the binary, which reads scenarios from stdin.
