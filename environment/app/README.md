# Java Trivia Dungeon

Offline terminal trivia dungeon with rooms, encounters, scoring weights, and a deterministic verification playthrough. Players (and the publication check) resolve trivia questions while walking the dungeon graph.

## Commands

```bash
make verify        # offline build, audit bundled dungeon, run playthrough
./bin/trivia-dungeon audit ...       # audit room/encounter manifests and trivia references
./bin/trivia-dungeon playthrough ... # deterministic verification run
```

## Layout

| Path | Role |
|------|------|
| `bin/trivia-dungeon` | Dungeon command wrapper |
| `config/` | Dungeon TOML and verification answer script |
| `bundle/` | Room, encounter, and scoring manifests |
| `docs/` | Domain contracts for manifests, configuration, and audit state |

See `docs/configuration.md` for precedence and path rules. Exit codes: `0` success, `1` operational failure, `2` content violations.
