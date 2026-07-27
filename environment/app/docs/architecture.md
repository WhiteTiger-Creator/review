# Architecture

Binary: `/app/bin/yinsh-ring`

Packages under `/app/internal/`:
- c3n — sealed profile load and seal check
- h7b — scenario fixture load
- u2m — ring slides, leave-marker, flips
- y5r — row-of-N detection and ring removal
- d9g — victory gates
- q6p — scoring, standings, report writer

Entry: `/app/cmd/yinsh-ring/main.go`
