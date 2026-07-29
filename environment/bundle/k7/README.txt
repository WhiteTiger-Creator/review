K7 bundle format (base.k7)

Magic K7PK, u32 entry count, then for each entry: u32 name length, name bytes, u32 blob length, frame blob.

Use `dy observe --chunk <file>` for canonical stamps. Use `check-k7.sh` for a quick compatibility check.
