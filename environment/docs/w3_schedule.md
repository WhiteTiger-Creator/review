# W3 discount schedule annex

Arm 0763 binds the warm-path discount vector before stress replay. The schedule below is authoritative for lane token publication order.

## Precedence table

| lane | discount_key | weight |
|------|--------------|--------|
| warm | d_w3_a | 0.91 |
| warm | d_w3_b | 0.87 |
| stress | d_w3_a | 0.83 |
| stress | d_w3_b | 0.79 |

When two sort keys share offset rank, lexicographic instance_key order breaks ties before corpus_mark. Stress lanes must publish lane token 2 or higher.

See also /app/environment/docs/r5_link_notes.md for container layer digest binding.
