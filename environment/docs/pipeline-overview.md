# Curtailment desk simulator engine

This workspace runs the `pvsim` driver for the curtailment desk.
The driver launches `/app/build/regret_solver` and manages save shards
under `/app/runtime/journal/`.

## Running emit and verify

Rebuild `/app/build/regret_solver` after source changes, then:

```
pvsim emit
pvsim verify --fuzz
```

Default paths use bundled fixtures, corpora, annex slice, and runtime outputs
under `/app/`.

## Products

- `/app/runtime/dossier/dossier.json`
- `/app/runtime/transcript/transcript.json`

Record shapes and numeric contract are defined in the annex companions under
`/app/annex/`. Do not treat emitter-local shortcuts as authoritative when they
disagree with the formal contract or the independent verify probe.
