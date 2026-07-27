# Constituent catalog format

The catalog path is a directory. Every regular file ending in `.json` is decoded as a strict constituent entry; other files are ignored. Catalog JSON rejects duplicate keys, unknown fields, trailing values, and wrong types.

An entry contains exactly `schema_version`, `name`, `speed_deg_per_hour`, `epoch_tai`, and `nodal`. `schema_version` is 1. `name` is nonempty and unique across the directory. Speed is finite. Epoch TAI is a nonnegative integer. `nodal` contains at least two nodes in strictly increasing TAI order.

Each nodal node contains exactly `tai`, `factor`, `factor_slope_per_sec`, `phase_deg`, and `phase_slope_deg_per_sec`. Every number is finite, factor is nonnegative, and TAI is an integer. The interpolation semantics are defined in the forecast contract.
