# Loader cache maintenance

The loader cache belongs to the stable service root and names `/opt/ledger/current/lib`, never an individual release slot or a capability directory. Promotion and rollback regenerate it. Removing the cache, running without it, or rebuilding it with `ldconfig -r ROOT` must not change either selected three-library stack.
