package main

import "sort"

type settlement struct {
	h           *host
	up          map[string]bool
	everUp      map[string]bool
	detached    map[string]bool
	pending     map[string]string
	ladder      map[string][]string
	bearer      map[string]string
	raised      map[string]bool
	everRaised  map[string]bool
	vlanUp      map[string]bool
	vlanEver    map[string]bool
	claimed     map[record]bool
	everClaimed map[record]bool
	claimedAt   map[record]int
}

func newSettlement(h *host) *settlement {
	s := &settlement{
		h:           h,
		up:          map[string]bool{},
		everUp:      map[string]bool{},
		detached:    map[string]bool{},
		pending:     map[string]string{},
		ladder:      map[string][]string{},
		bearer:      map[string]string{},
		raised:      map[string]bool{},
		everRaised:  map[string]bool{},
		vlanUp:      map[string]bool{},
		vlanEver:    map[string]bool{},
		claimed:     map[record]bool{},
		everClaimed: map[record]bool{},
		claimedAt:   map[record]int{},
	}
	for _, iface := range h.ifaceOrder {
		s.up[iface] = h.openUp[iface]
		s.everUp[iface] = h.openUp[iface]
		s.detached[iface] = false
	}
	for _, bond := range h.bondOrder {
		s.ladder[bond] = []string{}
		s.bearer[bond] = ""
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
		if h.openClaimed[one] {
			s.claimedAt[one] = 0
		} else {
			s.claimedAt[one] = -1
		}
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
	return len(s.counted(bond)) >= s.h.floor[bond]
}

func (s *settlement) stands(name string) bool {
	if s.h.isIface[name] {
		return s.up[name]
	}
	if s.h.isBond[name] {
		return s.bears(name)
	}
	return s.vlanUp[name]
}

func (s *settlement) depth(iface string) int {
	if s.h.isIface[iface] {
		return 1
	}
	if s.h.isBond[iface] {
		return 2
	}
	return 3
}

func (s *settlement) enrol(bond string, member string) bool {
	holder := s.bondOf(member)
	if holder == bond {
		return true
	}
	return holder == ""
}

func (s *settlement) seat(bond string, member string) {
	s.ladder[bond] = drop(s.ladder[bond], member)
	declared := s.h.declared[bond]
	mine := len(declared) + 1
	for at, one := range declared {
		if one == member {
			mine = at
		}
	}
	spot := len(s.ladder[bond])
	for at, other := range s.ladder[bond] {
		theirs := len(declared) + 1
		for k, one := range declared {
			if one == other {
				theirs = k
			}
		}
		if theirs > mine {
			spot = at
			break
		}
	}
	rest := append([]string{}, s.ladder[bond][spot:]...)
	s.ladder[bond] = append(append(s.ladder[bond][:spot:spot], member), rest...)
}

func (s *settlement) raiseBond(bond string) {
	s.everRaised[bond] = true
	s.raised[bond] = true
	if len(s.ladder[bond]) == 0 {
		for _, member := range s.h.declared[bond] {
			if s.enrol(bond, member) {
				s.ladder[bond] = append(s.ladder[bond], member)
			}
		}
		s.bearer[bond] = ""
	}
}

func (s *settlement) apply(one step, number int) {
	switch one.kind {
	case "link-down":
		if !s.up[one.first] {
			return
		}
		s.up[one.first] = false
		bond := s.bondOf(one.first)
		if bond != "" {
			s.ladder[bond] = drop(s.ladder[bond], one.first)
			if s.bearer[bond] == one.first {
				s.bearer[bond] = ""
			}
			s.pending[one.first] = bond
		}
	case "link-up":
		if s.up[one.first] {
			return
		}
		s.up[one.first] = true
		s.everUp[one.first] = true
		bond, waiting := s.pending[one.first]
		delete(s.pending, one.first)
		if waiting && s.bondOf(one.first) == "" && s.enrol(bond, one.first) {
			s.seat(bond, one.first)
		}
	case "detach":
		if holds(s.ladder[one.first], one.second) {
			s.ladder[one.first] = drop(s.ladder[one.first], one.second)
			if s.bearer[one.first] == one.second {
				s.bearer[one.first] = ""
			}
			s.detached[one.second] = true
		}
		delete(s.pending, one.second)
	case "attach":
		if s.raised[one.first] && s.enrol(one.first, one.second) {
			s.seat(one.first, one.second)
			delete(s.pending, one.second)
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
			s.claimedAt[claim] = number
		}
	case "release":
		s.claimed[record{one.first, one.second}] = false
	}
}

func (s *settlement) weigh() {
	for _, bond := range s.h.bondOrder {
		if !s.bears(bond) {
			s.bearer[bond] = ""
			continue
		}
		standing := s.counted(bond)
		if len(standing) == 0 {
			s.bearer[bond] = ""
		} else {
			s.bearer[bond] = standing[0]
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
	for number, one := range s.h.steps {
		s.apply(one, number+1)
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
		case !s.stands(one.iface):
			state[one] = "DROPPED"
			token[one] = "drop.released"
		default:
			standing = append(standing, ranked{rank, one})
		}
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
			if s.claimedAt[left.one] != s.claimedAt[right.one] {
				return s.claimedAt[left.one] < s.claimedAt[right.one]
			}
			return left.rank < right.rank
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
			token[entry.one] = "oust.place"
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
	if count < s.h.floor[bond] {
		return "DOWN", "down.lowered"
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

func (s *settlement) claimedOn(name string) int {
	held := 0
	for _, one := range s.h.records {
		if one.iface == name && s.claimed[one] {
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
	if !s.stands(s.h.parent[vlan]) {
		return "DOWN"
	}
	if s.standingOn(vlan, addrState) > 0 {
		return "UP"
	}
	return "QUIET"
}
