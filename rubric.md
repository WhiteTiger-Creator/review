# Rubric 1
Agent validates the complete strict match schema and all documented cross references before producing output, +5
Agent computes turn timestamps and rounded tide derived effective depths with ties to even and normalized zero, +5
Agent resolves edge and depth legality from each turn's current positions using the documented status precedence, +3
Agent resolves target contests by initiative player ID and fleet ID while excluding invalid moves, +5
Agent resolves simultaneous occupancy dependencies including chains cycles swaps contest losers and stationary blockers, +5
Agent applies capture retained ownership per turn scoring cumulative scores and final winner tie breaks correctly, +5
Agent emits canonically ordered compact JSON and the documented SHA 256 summary records deterministically, +5
Agent rejects nonpositive worker counts relative paths malformed inputs and forecast failures without leaving stale output, +2
Agent produces fixture specific or input order dependent results, -5
Agent emits output after a failed adjudication or accepts behavior outside the public schemas, -5
Agent resolves simultaneous movement sequentially or permits two fleets to finish on one node, -5
