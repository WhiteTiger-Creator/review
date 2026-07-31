package main

import "sort"

type settlement struct {
	h           *host
	up          map[string]bool
	everUp      map[string]bool
	detached    map[string]bool
	bondAt      map[string]int
	ladder      map[string][]string
	bearer      map[string]string
	stinted     map[string]bool
	raised      map[string]bool
	everRaised  map[string]bool
	vlanUp      map[string]bool
	vlanEver    map[string]bool
	claimed     map[record]bool
	everClaimed map[record]bool
}

func newSettlement(h *host) *settlement {
	s := &settlement{
		h:           h,
		up:          map[string]bool{},
		everUp:      map[string]bool{},
		detached:    map[string]bool{},
		bondAt:      map[string]int{},
		ladder:      map[string][]string{},
		bearer:      map[string]string{},
		stinted:     map[string]bool{},
		raised:      map[string]bool{},
		everRaised:  map[string]bool{},
		vlanUp:      map[string]bool{},
		vlanEver:    map[string]bool{},
		claimed:     map[record]bool{},
		everClaimed: map[record]bool{},
	}
	for _, iface := range h.ifaceOrder {
		s.up[iface] = h.openUp[iface]
		s.everUp[iface] = h.openUp[iface]
		s.detached[iface] = false
	}
	for at, bond := range h.bondOrder {
		s.bondAt[bond] = at
		s.ladder[bond] = []string{}
		s.bearer[bond] = ""
		s.stinted[bond] = false
		s.raised[bond] = false
		s.everRaised[bond] = false
	}
	for _, vlan := range h.vlanOrder {
		s.vlanUp[vlan] = h.vlanOpen[vlan]
		s.vlanEver[vlan] = h.vlanOpen[vlan]
	}
	for _, one := range h.records {
		s.claimed[one] = h.openClaimed[one]
		s.everClaimed[one] = h.openClaimed[one]
	}
	return s
}

func drop(list []string, name string) []string {
	out := []string{}
	for _, one := range list {
		if one != name {
			out = append(out, one)
		}
	}
	return out
}

func holds(list []string, name string) bool {
	for _, one := range list {
		if one == name {
			return true
		}
	}
	return false
}

func (s *settlement) bondOf(iface string) string {
	for _, bond := range s.h.bondOrder {
		if holds(s.ladder[bond], iface) {
			return bond
		}
	}
	return ""
}

func (s *settlement) counted(bond string) []string {
	out := []string{}
	for _, member := range s.ladder[bond] {
		if s.up[member] {
			out = append(out, member)
		}
	}
	return out
}

func (s *settlement) bears(bond string) bool {
	if !s.raised[bond] || len(s.ladder[bond]) == 0 {
		return false
	}
	return !s.stinted[bond]
}

func (s *settlement) depth(iface string) int {
	if s.h.isIface[iface] {
		return 1
	}
	if s.h.isBond[iface] {
		return 2
	}
	return 1 + s.depth(s.h.parent[iface])
}

func (s *settlement) enrol(bond string, member string) bool {
	holder := s.bondOf(member)
	if holder == bond {
		return true
	}
	if holder != "" {
		if s.bondAt[bond] <= s.bondAt[holder] {
			return false
		}
		s.ladder[holder] = drop(s.ladder[holder], member)
		if s.bearer[holder] == member {
			s.bearer[holder] = ""
		}
	}
	return true
}

func (s *settlement) raiseBond(bond string) {
	s.everRaised[bond] = true
	s.raised[bond] = true
	s.stinted[bond] = false
	s.ladder[bond] = []string{}
	for _, member := range s.h.declared[bond] {
		if s.enrol(bond, member) {
			s.ladder[bond] = append(s.ladder[bond], member)
		}
	}
	s.bearer[bond] = ""
}

func (s *settlement) apply(one step) {
	switch one.kind {
	case "link-down":
		if s.up[one.first] {
			s.up[one.first] = false
		}
	case "link-up":
		if !s.up[one.first] {
			s.up[one.first] = true
			s.everUp[one.first] = true
		}
	case "detach":
		if holds(s.ladder[one.first], one.second) {
			s.ladder[one.first] = drop(s.ladder[one.first], one.second)
			if s.bearer[one.first] == one.second {
				s.bearer[one.first] = ""
			}
			s.detached[one.second] = true
		}
	case "attach":
		if s.raised[one.first] && s.enrol(one.first, one.second) {
			s.ladder[one.first] = drop(s.ladder[one.first], one.second)
			s.ladder[one.first] = append([]string{one.second}, s.ladder[one.first]...)
		}
	case "raise":
		if s.h.isBond[one.first] {
			s.raiseBond(one.first)
		} else {
			s.vlanUp[one.first] = true
			s.vlanEver[one.first] = true
		}
	case "lower":
		if s.h.isBond[one.first] {
			s.raised[one.first] = false
			s.bearer[one.first] = ""
		} else {
			s.vlanUp[one.first] = false
		}
	case "claim":
		claim := record{one.first, one.second}
		if !s.claimed[claim] {
			s.claimed[claim] = true
			s.everClaimed[claim] = true
		}
	case "release":
		s.claimed[record{one.first, one.second}] = false
	}
}

func (s *settlement) weigh() {
	for _, bond := range s.h.bondOrder {
		if s.raised[bond] && len(s.ladder[bond]) > 0 {
			if len(s.counted(bond)) < s.h.floor[bond] {
				s.stinted[bond] = true
			}
		}
	}
	for _, bond := range s.h.bondOrder {
		if !s.bears(bond) {
			s.bearer[bond] = ""
			continue
		}
		standing := s.counted(bond)
		if s.bearer[bond] != "" && holds(standing, s.bearer[bond]) {
			continue
		}
		if len(standing) == 0 {
			s.bearer[bond] = ""
		} else {
			s.bearer[bond] = standing[len(standing)-1]
		}
	}
}

func (s *settlement) run() *settlement {
	for _, bond := range s.h.bondOrder {
		if s.h.openRaised[bond] {
			s.raiseBond(bond)
		}
	}
	s.weigh()
	for _, one := range s.h.steps {
		s.apply(one)
		s.weigh()
	}
	return s
}

type ranked struct {
	rank int
	one  record
}

func (s *settlement) settleAddresses() (map[record]string, map[record]string) {
	state := map[record]string{}
	token := map[record]string{}
	standing := []ranked{}
	for rank, one := range s.h.records {
		switch {
		case !s.everClaimed[one]:
			state[one] = "UNCLAIMED"
			token[one] = "cold.never-claimed"
		case !s.claimed[one]:
			state[one] = "DROPPED"
			token[one] = "drop.released"
		default:
			standing = append(standing, ranked{rank, one})
		}
	}

	for _, bond := range s.h.bondOrder {
		if !s.stinted[bond] {
			continue
		}
		aside := map[record]bool{}
		seen := 0
		for _, entry := range standing {
			if entry.one.iface != bond {
				continue
			}
			seen++
			if seen > 1 {
				state[entry.one] = "SET-ASIDE"
				token[entry.one] = "aside.stinted"
				aside[entry.one] = true
			}
		}
		kept := []ranked{}
		for _, entry := range standing {
			if !aside[entry.one] {
				kept = append(kept, entry)
			}
		}
		standing = kept
	}

	heldBack := map[record]bool{}
	for _, entry := range standing {
		heldBack[entry.one] = s.h.isBond[entry.one.iface] && s.stinted[entry.one.iface]
	}

	order := []string{}
	groups := map[string][]ranked{}
	for _, entry := range standing {
		if _, seen := groups[entry.one.addr]; !seen {
			order = append(order, entry.one.addr)
		}
		groups[entry.one.addr] = append(groups[entry.one.addr], entry)
	}
	for _, addr := range order {
		group := groups[addr]
		sort.SliceStable(group, func(i, j int) bool {
			left, right := group[i], group[j]
			if heldBack[left.one] != heldBack[right.one] {
				return !heldBack[left.one]
			}
			leftDepth, rightDepth := s.depth(left.one.iface), s.depth(right.one.iface)
			if leftDepth != rightDepth {
				return leftDepth > rightDepth
			}
			return left.rank > right.rank
		})
		winner := group[0].one
		state[winner] = "STANDING"
		if len(group) == 1 {
			token[winner] = "stand.sole"
		} else {
			token[winner] = "stand.won"
		}
		for _, entry := range group[1:] {
			state[entry.one] = "OUSTED"
			switch {
			case heldBack[entry.one] && !heldBack[winner]:
				token[entry.one] = "oust.stinted"
			case s.depth(winner.iface) > s.depth(entry.one.iface):
				token[entry.one] = "oust.depth"
			default:
				token[entry.one] = "oust.place"
			}
		}
	}
	return state, token
}

func (s *settlement) settleBond(bond string) (string, string) {
	if !s.everRaised[bond] {
		return "UNMADE", "cold.never-raised"
	}
	if !s.raised[bond] {
		return "DOWN", "down.lowered"
	}
	if len(s.ladder[bond]) == 0 {
		return "DOWN", "down.no-member"
	}
	count := len(s.counted(bond))
	if s.stinted[bond] {
		if count < s.h.floor[bond] {
			return "STINTED", "stint.floor-lost"
		}
		return "STINTED", "stint.held-over"
	}
	if count < len(s.h.declared[bond]) {
		return "THIN", "thin.short"
	}
	return "FULL", "full.assembled"
}

func (s *settlement) standingOn(name string, addrState map[record]string) int {
	held := 0
	for _, one := range s.h.records {
		if one.iface == name && addrState[one] == "STANDING" {
			held++
		}
	}
	return held
}

func (s *settlement) settleIface(iface string, addrState map[record]string) (string, string) {
	if !s.everUp[iface] {
		return "UNWIRED", "cold.never-up"
	}
	if !s.up[iface] {
		return "DARK", "dark.link-down"
	}
	bond := s.bondOf(iface)
	if bond != "" {
		if s.bearer[bond] == iface {
			return "BEARING", "bear.carry"
		}
		if s.bearer[bond] == "" {
			return "SPARE", "spare.vacant"
		}
		return "SPARE", "spare.ladder"
	}
	if s.standingOn(iface, addrState) > 0 {
		return "BEARING", "bear.own"
	}
	if s.detached[iface] {
		return "BARE", "bare.detached"
	}
	return "BARE", "bare.idle"
}

func (s *settlement) settleVlan(vlan string, addrState map[record]string) string {
	if !s.vlanEver[vlan] {
		return "UNMADE"
	}
	if !s.vlanUp[vlan] {
		return "DOWN"
	}
	if s.standingOn(vlan, addrState) > 0 {
		return "UP"
	}
	return "QUIET"
}
