# Tables shipped with the project

Every table is a comma separated file whose header names the feature columns
and then the label column, followed by one example per line. A feature entry of
minus one marks a measurement that was never recorded.

| Table | Examples | Features | Classes | Unrecorded entries |
|---|---|---|---|---|
| clean01 | 15 | 4 | 2 | 0 |
| clean02 | 13 | 4 | 3 | 0 |
| clean03 | 13 | 4 | 3 | 0 |
| clean04 | 13 | 4 | 2 | 0 |
| clean05 | 18 | 4 | 3 | 0 |
| clean06 | 10 | 4 | 2 | 0 |
| clean07 | 15 | 4 | 3 | 0 |
| clean08 | 16 | 4 | 3 | 0 |
| clean09 | 15 | 4 | 3 | 0 |
| fwdo01 | 17 | 4 | 2 | 9 |
| fwdo02 | 20 | 4 | 2 | 26 |
| fwdo03 | 14 | 4 | 2 | 6 |
| left01 | 20 | 4 | 2 | 26 |
| left02 | 14 | 4 | 2 | 15 |
| left03 | 12 | 4 | 2 | 7 |
| node01 | 17 | 4 | 2 | 9 |
| node02 | 20 | 4 | 2 | 26 |
| node03 | 14 | 4 | 2 | 6 |
| nonn01 | 14 | 4 | 2 | 15 |
| nonn02 | 12 | 4 | 2 | 7 |
| nonn03 | 10 | 4 | 2 | 6 |
| wide5 | 12 | 5 | 2 | 0 |

Tables named clean carry the ordinary case. The remaining tables each stress one
corner of the fit: heavy gaps in the deciding measurement, measurements that
mirror each other, substitutes that only just fail to help, and examples with
nothing recorded at all. The table with five feature columns exists so that a
mismatched pairing can be refused.

