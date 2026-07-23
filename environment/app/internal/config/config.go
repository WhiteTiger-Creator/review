// Package config loads authgw's runtime configuration from environment
// variables.
package config

import "os"

// Config holds the settings authgw needs to start.
type Config struct {
	// Addr is the address net/http should listen on, e.g. ":8080".
	Addr string
	// DBPath is the filesystem path to the SQLite database file.
	DBPath string
}

// Load reads configuration from the environment, applying defaults for
// anything unset.
func Load() Config {
	return Config{
		Addr:   ":" + getenv("PORT", "8080"),
		DBPath: getenv("AUTHGW_DB_PATH", "/app/data/authgw.db"),
	}
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
