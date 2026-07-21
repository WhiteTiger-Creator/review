# Forge emit workspace

The CMake tree under `/app/environment` builds `forge_emit`, an offline lane audit tool that reads a release manifest and companion unit record files, then emits JSON at `/app/output/forge_emit.json` while persisting resume checkpoints at `/app/output/forge_checkpoint.json`.

Supporting helpers are split across several compile units linked into the driver. Headers under `/app/environment/include` define shared record and report shapes.

See `/app/environment/docs/emit_contract.md` for operator notes and `/app/environment/docs/persistence_notes.md` for checkpoint behavior.
