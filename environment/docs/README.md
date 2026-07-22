# Beacon audit workstation

`beacon-audit` retains and verifies a fixed NIST Beacon 2.0 interval. Its Go source is installed under `/app`; use `go test ./...` and rebuild `/usr/local/bin/beacon-audit` after repairs. Acquisition and verification are separate so the exact network evidence remains inspectable after the ceremony.

The tool accepts only HTTPS resources on the case's configured origin. Network responses and retained evidence files are capped at 2 MiB. It writes new evidence through temporary files and refuses redirects away from that origin.
