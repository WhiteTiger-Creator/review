# UTC and leap table format

The leap table is UTF-8 text. Empty lines and lines whose first non-space character is `#` are ignored. Every other line contains exactly an effective UTC instant and a decimal TAI-minus-UTC offset separated by whitespace. Effective instants use `YYYY-MM-DDT00:00:00Z`, are strictly increasing, and offsets never decrease or rise by more than one between adjacent rows.

Ordinary UTC timestamps use `YYYY-MM-DDTHH:MM:SSZ` and convert to TAI as the corresponding POSIX second plus the offset effective at that UTC instant. A timestamp ending in `23:59:60Z` is valid only when the next UTC midnight is present in the table with an offset exactly one greater than the preceding offset. It maps between `23:59:59Z` and the following `00:00:00Z` as one distinct TAI second. Reverse conversion must reproduce `23:59:60Z` for that instant. Calendar-invalid timestamps and undeclared leap seconds are errors.
