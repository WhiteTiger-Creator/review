# YINSH tournament simulation layout

Binary: `/app/bin/yinsh-ring`

Game modules under `/app/internal/`:
- season — sealed championship profile, heat epoch, overlays
- board — match fixture load
- slide — ring slides, leave-marker, path flips
- rows — row-of-N detection and ring removal
- victory — ring_target / ring_majority / mutual_draw gates
- scoring — match points, standings, tournament scoreboard

Entry: `/app/cmd/yinsh-ring/main.go`
Rulebook: `/app/docs/championship-rules.md`
