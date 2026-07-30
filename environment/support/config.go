package support

import (
	"fmt"
	"os"

	"github.com/pelletier/go-toml/v2"
)

type Principals struct {
	OutgoingUser         string  `toml:"outgoing_user"`
	OutgoingUID          int     `toml:"outgoing_uid"`
	OutgoingGID          int     `toml:"outgoing_gid"`
	IncomingUser         string  `toml:"incoming_user"`
	IncomingUID          int     `toml:"incoming_uid"`
	IncomingGID          int     `toml:"incoming_gid"`
	SupplementaryGroups  []int   `toml:"supplementary_groups"`
}

type Runtime struct {
	UnitName string `toml:"unit_name"`
}

type Config struct {
	Principals Principals `toml:"principals"`
	Runtime    Runtime    `toml:"runtime"`
}

func LoadConfig(path string) (Config, error) {
	var cfg Config
	b, err := os.ReadFile(path)
	if err != nil {
		return cfg, err
	}
	if err := toml.Unmarshal(b, &cfg); err != nil {
		return cfg, err
	}
	return cfg, nil
}

func (c Config) Validate() error {
	if c.Principals.IncomingUser == "" {
		return fmt.Errorf("incoming_user required")
	}
	if c.Principals.OutgoingUser == "" {
		return fmt.Errorf("outgoing_user required")
	}
	if c.Principals.IncomingUID <= 0 || c.Principals.IncomingGID <= 0 {
		return fmt.Errorf("incoming ids must be positive")
	}
	if c.Principals.OutgoingUID <= 0 || c.Principals.OutgoingGID <= 0 {
		return fmt.Errorf("outgoing ids must be positive")
	}
	if c.Runtime.UnitName == "" {
		c.Runtime.UnitName = "desk.service"
	}
	return nil
}
