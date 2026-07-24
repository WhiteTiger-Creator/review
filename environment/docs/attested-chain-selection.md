# Attested Chain Selection and Tie-Breaking

When more than one valid chain exists from the target leaf to a trusted root anchor, the tool must return exactly one admitted chain.

## Valid Chain Definition

A chain is valid only if `validate_path` succeeds for the ordered certificate list, all structural checks pass, and the terminal certificate ID is listed in the trusted roots file. Chains that fail policy intersection, name constraints, or temporal checks must be discarded before tie-breaking even when they reach a trusted root.

## Tie-Break Rule

Collect every valid chain discovered during search. Compare chains as sequences of certificate `id` strings from leaf to root. Select the chain whose ID sequence is **lexicographically smallest** when compared element-by-element (standard string order on each ID).

Example: between `["leaf-x","int-b","root-a"]` and `["leaf-x","int-a","root-a"]`, choose the second because `"int-a" < "int-b"` at the first differing index.

When several peer intermediates yield otherwise-valid chains to the same root, discard any chain that fails validation first, then apply the same lexicographic rule on the remaining ID sequences. Selection always follows validate-then-lex-min, not discovery order.

Search must explore alternatives (including backtracking past expired intermediates and cross-signed variants) rather than returning the first discovered valid chain when a smaller ID sequence exists. Exploring candidates in reverse lexicographic order and stopping at the first valid chain is incorrect when a lexicographically smaller valid chain also exists.

Invalid chains — including those that fail path length limits, name constraints, or policy intersection — must be discarded before the lexicographic comparison. When the lexicographically smallest ID sequence fails validation, the next-smallest valid sequence must be selected instead.
