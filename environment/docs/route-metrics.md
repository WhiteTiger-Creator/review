# Route metrics

Mandatory landings compare occupied coordinates after each step index across every shortest winning route. When all routes share one coordinate at that index, that step is mandatory. Visiting the same cell at different indices does not create a mandatory landing.

Decision points look at the complete state before each canonical move. An alternative is a legal move from that exact state that still admits a winning continuation whose remaining length equals the remaining shortest-route budget. When two or more such moves exist, the decision lists every qualifying move in canonical order, including the canonical choice itself.
