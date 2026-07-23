Bring the wind-farm icing formal scoring libraries under `/app/environment` into compliance so they correctly regenerate the sealed icing witness bundle at `/app/output/k_out.json`. The work is numeric policy for BER annex discharge, FTRL arm scoring, fold digests, certified envelope caps, and stress reachability containment across site packs.

Annex slices use BER-style indefinite-length encodings in each site pack `xslice.bin` under `/app/environment/k8`. Numeric policy lives in `/app/environment/docs/q_rules.md`. Long-context annex encoding reference is `/app/environment/docs/x_corpus.md` (authoritative over stale ordering notes in `/app/environment/docs/ops_notes.md`). SQLite lineage catalog lives at `/app/environment/var/k9.db` with migrations in `/app/environment/var/mig/`. Output shape is `/app/environment/schemas/k_out.schema.json`.

Requirements:
- Fix the scoring libraries under `/app/environment` so `/app/environment/exec/k_run.sh --site-root /app/environment/k8 --out /app/output/k_out.json` regenerates a policy-valid icing witness bundle. After library fixes, rebuild and install the updated scientific binaries the driver invokes. Hand-written or static JSON drops are insufficient; scoring deletes any prior bundle and reruns that driver before checking output.
- Closed site packs must show zero catalog obligation violations after regeneration.
- Synth arm score observations must stay within each site's certified envelope cap from its schedule.
- Fold digests must be stable when equivalent annex row presentations are permuted via `/app/environment/k8/_orbits/` fixtures.
- Admission labels must not flip when annex rows are permuted for the same site using `_orbits` fixtures.
- Stress trajectories must remain inside certified site envelopes in the sealed bundle.
- Catalog digest must include every lineage row after SQLite replay.
- Emit schema_version, sites, stress, and lineage_rows per `/app/environment/schemas/k_out.schema.json`. Site, stress, fold, and catalog field semantics are defined in `q_rules.md`.
- Library modules must implement the contracts in `q_rules.md`, not only the shell driver wrapper.
