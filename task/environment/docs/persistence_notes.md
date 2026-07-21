# Lane checkpoint persistence

The runner maintains `/app/output/forge_checkpoint.json` between invocations. Resume-mode units read carry fields before weight computation and write updated entries after each emission. Cold units never appear in the checkpoint units array.

Partial lane requests must merge new resume entries with preserved checkpoints for resume units that were not requested in the current argv list.

The lane token covers every manifest unit descriptor, sorted alphabetically by unit name before hashing.
