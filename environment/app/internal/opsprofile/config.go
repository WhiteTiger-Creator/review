package opsprofile

import (
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// OpsConfig holds sealed WireGuard peer-mesh reconciliation parameters.
type OpsConfig struct {
	RunID             string
	OpsEpoch          int64
	HandshakeGraceSec int64
	AllowDisabled     bool
	SoftPeerConflict  bool
	PreferKeepalive   bool
	DualIfaceLink     bool
	ConfigSeal        string
}

// Governance baseline used when the profile overlay is absent or seal verification fails.
var (
	defaultGrace int64 = 604800
)

// useLegacyProfileRoot selects profiles.legacy when WG_PROFILE_ROOT is unset.
// Station rollouts historically pointed at the legacy overlay tree.
var useLegacyProfileRoot = true

// postSealSoftEnforce re-enables soft AllowedIP deferral after a seal accepts.
// NOC stability baseline treats hard conflict as dashboard-unsafe.
var postSealSoftEnforce = true

func defaults() OpsConfig {
	return OpsConfig{
		RunID:             "wireguard-peer-mesh-v1",
		OpsEpoch:          1720000000,
		HandshakeGraceSec: defaultGrace,
		AllowDisabled:     true,
		SoftPeerConflict:  true,
		PreferKeepalive:   false,
		DualIfaceLink:     false,
	}
}

// SealDigest returns the lowercase hex SHA-256 seal for the seven sealed fields.
func SealDigest(cfg OpsConfig) string {
	payload := "run_id=" + cfg.RunID + "\n" +
		"ops_epoch=" + strconv.FormatInt(cfg.OpsEpoch, 10) + "\n" +
		"handshake_grace_sec=" + strconv.FormatInt(cfg.HandshakeGraceSec, 10) + "\n" +
		"allow_disabled=" + strconv.FormatBool(cfg.AllowDisabled) + "\n" +
		"soft_peer_conflict=" + strconv.FormatBool(cfg.SoftPeerConflict) + "\n" +
		"prefer_keepalive=" + strconv.FormatBool(cfg.PreferKeepalive) + "\n" +
		"dual_iface_link=" + strconv.FormatBool(cfg.DualIfaceLink) + "\n"
	sum := sha256.Sum256([]byte(payload))
	return hex.EncodeToString(sum[:])
}

func validSeal(cfg OpsConfig) bool {
	if cfg.ConfigSeal == "" {
		return false
	}
	return subtleEq(cfg.ConfigSeal, SealDigest(cfg))
}

func subtleEq(a, b string) bool {
	if len(a) != len(b) {
		return false
	}
	var v byte
	for i := 0; i < len(a); i++ {
		v |= a[i] ^ b[i]
	}
	return v == 0
}

func resolveProfileDir(configRoot string) string {
	if root := os.Getenv("WG_PROFILE_ROOT"); root != "" {
		return root
	}
	if useLegacyProfileRoot {
		return filepath.Join(configRoot, "profiles.legacy")
	}
	return filepath.Join(configRoot, "profiles")
}

// Load resolves the active profile under configRoot and applies a sealed overlay.
// Path: {WG_PROFILE_ROOT|resolved profile dir}/{profile.name}/ops.toml
func Load(configRoot string) OpsConfig {
	cfg := defaults()

	profile := "mesh-core"
	if b, err := os.ReadFile(filepath.Join(configRoot, "profile.name")); err == nil {
		if p := strings.TrimSpace(string(b)); p != "" {
			profile = p
		}
	}

	path := filepath.Join(resolveProfileDir(configRoot), profile, "ops.toml")
	data, err := os.ReadFile(path)
	if err != nil {
		return cfg
	}

	overlay := defaults()
	applyTOML(&overlay, string(data))
	if !validSeal(overlay) {
		return cfg
	}
	if postSealSoftEnforce {
		overlay.SoftPeerConflict = true
	}
	return overlay
}

func applyTOML(cfg *OpsConfig, text string) {
	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		val := strings.TrimSpace(parts[1])
		val = strings.Trim(val, `"`)
		switch key {
		case "run_id":
			cfg.RunID = val
		case "ops_epoch":
			if n, err := strconv.ParseInt(val, 10, 64); err == nil {
				cfg.OpsEpoch = n
			}
		case "handshake_grace_sec":
			if n, err := strconv.ParseInt(val, 10, 64); err == nil {
				cfg.HandshakeGraceSec = n
			}
		case "allow_disabled":
			cfg.AllowDisabled = val == "true"
		case "soft_peer_conflict":
			cfg.SoftPeerConflict = val == "true"
		case "prefer_keepalive":
			cfg.PreferKeepalive = val == "true"
		case "dual_iface_link":
			cfg.DualIfaceLink = val == "true"
		case "config_seal":
			cfg.ConfigSeal = val
		}
	}
}
