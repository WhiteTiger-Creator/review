// Sealed retention daemon: decides what happens to one log file.
//
// Reads {"service":.., "size_mb":.., "age_days":.., "disk_pct":..} as JSON on
// stdin and writes {"decision":"KEEP"|"ROTATE"|"COMPRESS"|"DELETE"} on stdout --
// the daemon's decision for that log file -- so the agent can probe what it
// does without ever seeing the rules. A global query budget is enforced; once
// spent, every further call prints "LIMIT" and exits non-zero.
//
// This is the source of record for the hidden decision function. It is never
// part of the agent-facing build context: it is compiled here, offline, into a
// static stripped binary that is the only thing shipped into
// environment/daemon/. Built at image-build time, installed execute-only +
// set-uid to the "oracle" user with its source never present, so the agent can
// run it but cannot read the hidden rules, disassemble them, or trace them.
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strconv"
	"strings"
)

const (
	queryBudget = 120
	countPath   = "/opt/retention/.count"
)

// Ordinary services follow the general thresholds. Two services are special:
// "auth" rotates far sooner because its logs are high-volume and sensitive,
// and is exempt from the age-based purge because it is subject to a
// compliance retention hold; "billing" is protected under disk pressure
// because it is subject to a separate compliance requirement -- it is
// rotated instead of deleted. The two exemptions are deliberately not shared:
// auth's hold only covers routine purging, not an emergency reclaim under
// disk pressure, and billing's protection only covers disk pressure, not
// routine purging.
//
// Disk pressure itself has two tiers, not one: an earlier, elevated-but-not-
// critical tier tightens the general size threshold (making rotation/purge
// trigger at a smaller size) without overriding the decision outright, and
// a later, critical tier overrides every log's decision unconditionally
// (except billing's carve-out). The two tiers are independent: billing's
// carve-out belongs to the critical tier only -- at the elevated tier
// billing is an ordinary service and its threshold tightens like anyone
// else's. auth is unaffected by either disk tier for its own threshold,
// since its fixed threshold already applies regardless of disk (v4 review
// finding -- see README).
const (
	generalSizeThresholdMB  = 100
	authSizeThresholdMB     = 20
	moderateSizeThresholdMB = 25
	compressAgeDays         = 30
	purgeAgeDays            = 90
	moderateDiskPct         = 85
	criticalDiskPct         = 90
)

func decide(service string, sizeMB, ageDays, diskPct int) string {
	sizeThreshold := generalSizeThresholdMB
	if service == "auth" {
		sizeThreshold = authSizeThresholdMB
	} else if diskPct >= moderateDiskPct {
		// Elevated but not-yet-critical disk pressure tightens the general
		// size threshold for every non-auth service, including "billing" --
		// billing's pressure carve-out below is scoped to the CRITICAL tier
		// specifically, not this earlier one. auth is unaffected here: its
		// own fixed, lower threshold already applies regardless of disk.
		sizeThreshold = moderateSizeThresholdMB
	}

	// A log oversized enough to rotate AND already old enough to compress is
	// purged outright instead of rotated -- rotating a huge, already-stale
	// file barely reclaims anything, so it is deleted instead. This is a
	// numeric interaction between size and age, independent of service
	// identity: it applies uniformly, including to auth (auth's own purge
	// exemption below covers only the flat age>=90 rule, not this one).
	base := "KEEP"
	if sizeMB >= sizeThreshold {
		if ageDays >= compressAgeDays {
			base = "DELETE"
		} else {
			base = "ROTATE"
		}
	} else if ageDays >= compressAgeDays {
		base = "COMPRESS"
	}

	// A log old enough to purge is deleted outright, regardless of its size --
	// except auth's, which is under a compliance retention hold exempting it
	// from routine purging (but not from disk-pressure reclaim below).
	if ageDays >= purgeAgeDays && service != "auth" {
		base = "DELETE"
	}

	// Under critical disk pressure, every log is reclaimed immediately --
	// except a protected service's, which is rotated instead of deleted so its
	// retention requirement is never violated even while under pressure.
	if diskPct >= criticalDiskPct {
		if service == "billing" {
			return "ROTATE"
		}
		return "DELETE"
	}
	return base
}

// bump increments the persistent query counter and reports whether the call is
// within budget. It fails CLOSED: if the counter cannot be read, parsed, or
// written (for example when the daemon is run without its set-uid oracle
// elevation, so the oracle-owned counter is inaccessible), the call is denied so
// the budget cannot be bypassed.
func bump() bool {
	raw, err := os.ReadFile(countPath)
	if err != nil {
		return false
	}
	n, err := strconv.Atoi(strings.TrimSpace(string(raw)))
	if err != nil {
		return false
	}
	if n >= queryBudget {
		return false
	}
	if err := os.WriteFile(countPath, []byte(strconv.Itoa(n+1)), 0600); err != nil {
		return false
	}
	return true
}

type req struct {
	Service string `json:"service"`
	SizeMB  int    `json:"size_mb"`
	AgeDays int    `json:"age_days"`
	DiskPct int    `json:"disk_pct"`
}
type resp struct {
	Decision string `json:"decision"`
}

func main() {
	if !bump() {
		fmt.Println("LIMIT")
		os.Exit(2)
	}
	raw, err := io.ReadAll(os.Stdin)
	if err != nil {
		fmt.Println("REJECT")
		os.Exit(1)
	}
	var in req
	if err := json.Unmarshal(raw, &in); err != nil || in.Service == "" ||
		in.SizeMB < 0 || in.AgeDays < 0 || in.DiskPct < 0 || in.DiskPct > 100 {
		fmt.Println("REJECT")
		os.Exit(1)
	}
	json.NewEncoder(os.Stdout).Encode(resp{Decision: decide(in.Service, in.SizeMB, in.AgeDays, in.DiskPct)})
}
