package db

import "embed"

// migrationFiles embeds every migration under migrations/ so the binary
// can apply them without reading from disk at runtime.
//
//go:embed migrations/*.sql
var migrationFiles embed.FS
