package main

import (
	"fmt"
	"sort"
	"strconv"
	"strings"
)

var ifaceStates = []string{"BEARING", "SPARE", "BARE", "DARK", "UNWIRED"}
var bondStates = []string{"FULL", "THIN", "STINTED", "DOWN", "UNMADE"}
var vlanStates = []string{"UP", "QUIET", "DOWN", "UNMADE"}
var addrStates = []string{"STANDING", "OUSTED", "SET-ASIDE", "DROPPED", "UNCLAIMED"}

var ifaceWidths = []int{12, 6, 12, 3, 8, 18}
var ifaceAlign = "LLLRLL"
var ifaceNames = []string{"iface", "slot", "bond", "plc", "state", "rule"}

var bondWidths = []int{12, 3, 3, 3, 3, 12, 8, 18}
var bondAlign = "LRRRRLLL"
var bondNames = []string{"bond", "dec", "enr", "cnt", "flr", "bearer", "state", "rule"}

var vlanWidths = []int{12, 12, 5, 3, 6}
var vlanAlign = "LLRRL"
var vlanNames = []string{"vlan", "parent", "tag", "std", "state"}

var addrWidths = []int{18, 12, 2, 10, 18}
var addrAlign = "LLRLL"
var addrNames = []string{"address", "iface", "dep", "state", "rule"}

func laidOut(values []string, widths []int, aligns string) string {
	fields := make([]string, 0, len(values))
	for i, text := range values {
		pad := widths[i] - len(text)
		if pad < 0 {
			pad = 0
		}
		if aligns[i] == 'L' {
			fields = append(fields, text+strings.Repeat(" ", pad))
		} else {
			fields = append(fields, strings.Repeat(" ", pad)+text)
		}
	}
	return strings.TrimRight(strings.Join(fields, " "), " ")
}

func tallyLine(heading string, states []string, counts map[string]int) string {
	parts := []string{heading}
	for _, state := range states {
		parts = append(parts, state, strconv.Itoa(counts[state]))
	}
	return strings.Join(parts, " ")
}

func buildReport(s *settlement) string {
	h := s.h
	addrState, addrToken := s.settleAddresses()
	lines := []string{}

	carrying := 0
	for _, bond := range h.bondOrder {
		if s.bearer[bond] != "" {
			carrying++
		}
	}
	lines = append(lines, fmt.Sprintf(
		"host %s interfaces %d bonds %d vlans %d addresses %d carrying %d",
		h.name, len(h.ifaceOrder), len(h.bondOrder), len(h.vlanOrder),
		len(h.records), carrying))

	lines = append(lines, laidOut(ifaceNames, ifaceWidths, ifaceAlign))
	ifaceTally := map[string]int{}
	for _, iface := range h.ifaceOrder {
		state, token := s.settleIface(iface, addrState)
		ifaceTally[state]++
		bond := s.bondOf(iface)
		place := "-"
		shown := "-"
		if bond != "" {
			shown = bond
			for at, member := range s.ladder[bond] {
				if member == iface {
					place = strconv.Itoa(at + 1)
				}
			}
		}
		lines = append(lines, laidOut(
			[]string{iface, h.slot[iface], shown, place, state, token},
			ifaceWidths, ifaceAlign))
	}

	lines = append(lines, laidOut(bondNames, bondWidths, bondAlign))
	bondTally := map[string]int{}
	for _, bond := range h.bondOrder {
		state, token := s.settleBond(bond)
		bondTally[state]++
		bearer := s.bearer[bond]
		if bearer == "" {
			bearer = "-"
		}
		lines = append(lines, laidOut(
			[]string{bond,
				strconv.Itoa(len(h.declared[bond])),
				strconv.Itoa(len(s.ladder[bond])),
				strconv.Itoa(len(s.counted(bond))),
				strconv.Itoa(h.floor[bond]),
				bearer, state, token},
			bondWidths, bondAlign))
	}

	lines = append(lines, laidOut(vlanNames, vlanWidths, vlanAlign))
	vlanTally := map[string]int{}
	for _, vlan := range h.vlanOrder {
		state := s.settleVlan(vlan, addrState)
		vlanTally[state]++
		lines = append(lines, laidOut(
			[]string{vlan, h.parent[vlan], strconv.Itoa(h.tag[vlan]),
				strconv.Itoa(s.standingOn(vlan, addrState)), state},
			vlanWidths, vlanAlign))
	}

	lines = append(lines, laidOut(addrNames, addrWidths, addrAlign))
	shelf := append([]record{}, h.records...)
	sort.SliceStable(shelf, func(i, j int) bool {
		if shelf[i].addr != shelf[j].addr {
			return shelf[i].addr < shelf[j].addr
		}
		return shelf[i].iface < shelf[j].iface
	})
	addrTally := map[string]int{}
	for _, one := range shelf {
		addrTally[addrState[one]]++
		lines = append(lines, laidOut(
			[]string{one.addr, one.iface, strconv.Itoa(s.depth(one.iface)),
				addrState[one], addrToken[one]},
			addrWidths, addrAlign))
	}

	lines = append(lines, tallyLine("interfaces", ifaceStates, ifaceTally))
	lines = append(lines, tallyLine("bonds", bondStates, bondTally))
	lines = append(lines, tallyLine("vlans", vlanStates, vlanTally))
	lines = append(lines, tallyLine("addresses", addrStates, addrTally))
	return strings.Join(lines, "\n") + "\n"
}
