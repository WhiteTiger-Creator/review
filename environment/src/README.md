# Source notes

The library is split into two cached object units. `identity.c` owns the public
ABI/target accessors, and `mix.c` owns the numeric ABI helper. Both units embed a
small identity string so release checks can inspect the archive and cache
metadata without executing target-specific binaries.
