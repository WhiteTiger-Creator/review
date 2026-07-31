#!/bin/bash
set -euo pipefail

cd /app
mkdir -p /app/matchcmd /app/bin /app/out

cat > /app/matchcmd/go.mod <<'EOF'
module lantern-referee

go 1.24
EOF

cat > /app/matchcmd/main.go <<'EOF'
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

var reasonOrder = []string{
	"unknown_house",
	"style_miss",
	"late",
	"spent",
	"space_miss",
	"level_miss",
	"heat_limit",
	"badge_miss",
	"pair_miss",
	"booster_missing",
	"empty_piece",
}

type Club struct {
	ID          string   `json:"id"`
	House        string   `json:"house"`
	Disabled    bool     `json:"disabled"`
	AllowedStyles []string `json:"allowed_styles"`
	MaxHeat     int      `json:"max_heat"`
}

type Limits struct {
	PerHouse    map[string]int `json:"per_house"`
	PerSpace    map[string]int `json:"per_space"`
	PerSubject map[string]int `json:"per_subject"`
	PerSubjectHouse map[string]map[string]int `json:"per_subject_house"`
	PerSubjectStyle map[string]map[string]int `json:"per_subject_style"`
	PerHouseSpace map[string]map[string]int `json:"per_house_space"`
	PerHouseStyle map[string]map[string]int `json:"per_house_style"`
	PerRound map[string]int `json:"per_round"`
	SubjectRoundGap map[string]int `json:"subject_round_gap"`
	PerBadges map[string]int `json:"per_badge"`
	AllowedTransitions map[string][]string `json:"allowed_transitions"`
	AllowedHouseHandoffs map[string][]string `json:"allowed_house_handoffs"`
	HouseHeatBudget map[string]int `json:"house_heat_budget"`
	StanceSpaceGap map[string]map[string]int `json:"stance_space_gap"`
	SplitBadges []string `json:"split_badge"`
	FamilyCap map[string]int `json:"family_cap"`
	ClubRoundGap map[string]int `json:"club_round_gap"`
	BlockedHousePairs [][]string `json:"blocked_house_pairs"`
	RoundHeatBudget map[string]int `json:"round_heat_budget"`
	MutexLabels []string `json:"mutex_labels"`
}

type Piece struct {
	ID        string   `json:"id"`
	Subject   string   `json:"subject"`
	Club    string   `json:"club"`
	Style       string   `json:"style"`
	NotBefore int      `json:"start_tick"`
	NotAfter  int      `json:"end_tick"`
	RevokedAt *int     `json:"spent_tick"`
	Spaces     []string `json:"spaces"`
	Stances     []string `json:"stances"`
	Clearance int      `json:"level"`
	Binding   string   `json:"pair"`
	Remaining int      `json:"remaining"`
	Escort    bool     `json:"booster"`
	Labels    []string `json:"labels"`
	Cooldown  int      `json:"cooldown"`
}

type Turn struct {
	ID             string `json:"id"`
	Subject        string `json:"subject"`
	Space           string `json:"space"`
	Stance           string `json:"stance"`
	At             int    `json:"at"`
	Clearance      int    `json:"level"`
	Binding        string `json:"pair"`
	EscortRequired bool   `json:"booster_required"`
	Priority       int    `json:"priority"`
	Heat           int    `json:"heat"`
	Badges       []string `json:"badge"`
	Round          int      `json:"round"`
	Links       []string `json:"links"`
	WaiveLabel     string   `json:"link_label"`
}

type Ledger struct {
	PlayableHouses []string      `json:"playable_houses"`
	StyleOrder     []string      `json:"style_order"`
	Clubs      []Club      `json:"clubs"`
	Limits       Limits        `json:"limits"`
	Exclusions   []Exclusion   `json:"exclusions"`
	Cohorts      []Cohort      `json:"cohorts"`
	ReviewBoards []ReviewBoard `json:"review_boards"`
	SurgeWindows []SurgeWindow `json:"surge_windows"`
	RelayPaths   []RelayPath   `json:"relay_paths"`
	ScoreTracks  []ScoreTrack  `json:"score_tracks"`
	BackupSets   []BackupSet   `json:"backup_sets"`
	ClaimMarkets []ClaimMarket `json:"claim_markets"`
	RoundLadders []RoundLadder `json:"round_ladders"`
	Pieces       []Piece       `json:"pieces"`
	Turns     []Turn     `json:"turns"`
}

type Exclusion struct {
	Left        string `json:"left"`
	Right       string `json:"right"`
	UnlessLabel string `json:"unless_label"`
}

type Cohort struct {
	Members  []string `json:"members"`
	MinScore int      `json:"min_score"`
	MaxScore int      `json:"max_score"`
	MinHouses int      `json:"min_houses"`
	MinStyles  int      `json:"min_styles"`
	MaxHeat  int      `json:"max_heat"`
}

type ReviewBoard struct {
	Name          string   `json:"name"`
	Members       []string `json:"members"`
	ChairLabel    string   `json:"chair_label"`
	MinChairs     int      `json:"min_chairs"`
	MinHouses      int      `json:"min_houses"`
	MinStyles       int      `json:"min_styles"`
	MaxSameClub int      `json:"max_same_club"`
}

type SurgeWindow struct {
	Name           string `json:"name"`
	Rounds         []int  `json:"rounds"`
	MaxHeat        int    `json:"max_heat"`
	MinHouses       int    `json:"min_houses"`
	MinSpaces       int    `json:"min_spaces"`
	MaxSameSubject int    `json:"max_same_subject"`
	AnchorLabel    string `json:"anchor_label"`
}

type RelayPath struct {
	Name              string   `json:"name"`
	Members           []string `json:"members"`
	MinScore          int      `json:"min_score"`
	MaxRoundSpan      int      `json:"max_round_span"`
	MinDistinctPieces int      `json:"min_distinct_pieces"`
	EdgeLabelPrefix   string   `json:"edge_label_prefix"`
}

type ScoreTrack struct {
	Name      string   `json:"name"`
	Members   []string `json:"members"`
	Start     int      `json:"start"`
	MinValue  int      `json:"min_value"`
	MaxValue  int      `json:"max_value"`
	FinishMin int      `json:"finish_min"`
	FinishMax int      `json:"finish_max"`
}

type BackupSet struct {
	Name            string   `json:"name"`
	Members         []string `json:"members"`
	MinBackups      int      `json:"min_backups"`
	MinBackupHouses  int      `json:"min_backup_houses"`
	MaxBackupBurden int      `json:"max_backup_burden"`
	BackupLabel     string   `json:"backup_label"`
}

type ClaimMarket struct {
	Name           string   `json:"name"`
	Members        []string `json:"members"`
	MinClaims      int      `json:"min_claims"`
	MinClaimHouses int      `json:"min_claim_houses"`
	MaxClaimBurden int      `json:"max_claim_burden"`
	ClaimLabel     string   `json:"claim_label"`
}

type RoundLadder struct {
	Name            string   `json:"name"`
	Members         []string `json:"members"`
	MinScore        int      `json:"min_score"`
	Pattern         string   `json:"pattern"`
	MaxRoundGap     int      `json:"max_round_gap"`
	FreeLabelPrefix string   `json:"free_label_prefix"`
}

type ScoreItem struct {
	TurnID string `json:"turn_id"`
	PieceID   string `json:"piece_id"`
	House      string `json:"house"`
	Space      string `json:"space"`
	Priority  int    `json:"priority"`
	Heat      int    `json:"heat"`
}

type DenyItem struct {
	TurnID string   `json:"turn_id"`
	Reasons   []string `json:"reasons"`
}

type Summary struct {
	ScoredCount    int `json:"scored_count"`
	Priority         int `json:"priority"`
	Heat             int `json:"heat"`
	StyleBurden      int `json:"style_burden"`
	DistinctPieces   int `json:"distinct_pieces"`
}

type Scorecard struct {
	Scored []ScoreItem `json:"scored"`
	Missed   []DenyItem  `json:"missed"`
	Summary  Summary     `json:"summary"`
}

type Score struct {
	Priority int
	Heat     int
	Burden   int
	Distinct int
	Joined   string
	Valid    bool
}

func contains(list []string, value string) bool {
	for _, item := range list {
		if item == value {
			return true
		}
	}
	return false
}

func trackDelta(trackName string, req Turn, tok Piece) int {
	prefix := "track:" + trackName + ":" + req.ID + ":"
	matches := []string{}
	for _, label := range tok.Labels {
		if strings.HasPrefix(label, prefix) {
			matches = append(matches, label)
		}
	}
	if len(matches) == 0 {
		return req.Priority - req.Heat
	}
	sort.Strings(matches)
	valueText := strings.TrimPrefix(matches[0], prefix)
	value, err := strconv.Atoi(valueText)
	if err != nil {
		return req.Priority - req.Heat
	}
	return value
}

func indexes(ledger Ledger) (map[string]Club, map[string]bool, map[string]int) {
	clubs := map[string]Club{}
	for _, club := range ledger.Clubs {
		clubs[club.ID] = club
	}
	playable := map[string]bool{}
	for _, house := range ledger.PlayableHouses {
		playable[house] = true
	}
	styleLevel := map[string]int{}
	for idx, style := range ledger.StyleOrder {
		styleLevel[style] = idx + 1
	}
	return clubs, playable, styleLevel
}

func optionFailures(ledger Ledger, tok Piece, req Turn) []string {
	clubs, playable, styleLevel := indexes(ledger)
	club, clubOK := clubs[tok.Club]
	seen := map[string]bool{}
	if !clubOK || club.Disabled || !playable[club.House] {
		seen["unknown_house"] = true
	}
	if _, ok := styleLevel[tok.Style]; !ok || !clubOK || !contains(club.AllowedStyles, tok.Style) {
		seen["style_miss"] = true
	}
	if req.At < tok.NotBefore || req.At > tok.NotAfter {
		seen["late"] = true
	}
	if tok.RevokedAt != nil && req.At >= *tok.RevokedAt {
		seen["spent"] = true
	}
	if !contains(tok.Spaces, req.Space) || !contains(tok.Stances, req.Stance) {
		seen["space_miss"] = true
	}
	if tok.Clearance < req.Clearance {
		seen["level_miss"] = true
	}
	if !clubOK || req.Heat > club.MaxHeat {
		seen["heat_limit"] = true
	}
	for _, badge := range req.Badges {
		if !contains(tok.Labels, badge) {
			seen["badge_miss"] = true
			break
		}
	}
	if tok.Binding != req.Binding {
		seen["pair_miss"] = true
	}
	if req.EscortRequired && !tok.Escort {
		seen["booster_missing"] = true
	}
	if tok.Remaining <= 0 {
		seen["empty_piece"] = true
	}
	out := []string{}
	for _, reason := range reasonOrder {
		if seen[reason] {
			out = append(out, reason)
		}
	}
	return out
}

func playableChoices(ledger Ledger) [][]int {
	choices := make([][]int, len(ledger.Turns))
	for reqIdx, req := range ledger.Turns {
		choices[reqIdx] = []int{-1}
		for tokIdx, tok := range ledger.Pieces {
			if tok.Subject == req.Subject && len(optionFailures(ledger, tok, req)) == 0 {
				choices[reqIdx] = append(choices[reqIdx], tokIdx)
			}
		}
	}
	return choices
}

func scorePlan(ledger Ledger, assignment []int) Score {
	clubs, _, styleLevel := indexes(ledger)
	pieceUse := map[string]int{}
	pieceRounds := map[string][]int{}
	houseUse := map[string]int{}
	spaceUse := map[string]int{}
	subjectUse := map[string]int{}
	subjectHouseUse := map[string]int{}
	subjectStyleUse := map[string]int{}
	houseSpaceUse := map[string]int{}
	houseStyleUse := map[string]int{}
	roundUse := map[string]int{}
	badgeUse := map[string]int{}
	houseHeatUse := map[string]int{}
	familyUse := map[string]int{}
	roundHeatUse := map[string]int{}
	mutexLabels := map[string]bool{}
	mutexUse := map[string][]Piece{}
	for _, label := range ledger.Limits.MutexLabels {
		mutexLabels[label] = true
	}
	selected := map[string]Piece{}
	selectedTurns := map[string]Turn{}
	selectedInputOrder := map[string]int{}
	used := map[string]bool{}
	joined := []string{}
	score := Score{Valid: true}
	for reqIdx, tokIdx := range assignment {
		if tokIdx < 0 {
			continue
		}
		req := ledger.Turns[reqIdx]
		tok := ledger.Pieces[tokIdx]
		club := clubs[tok.Club]
		pieceUse[tok.ID]++
		pieceRounds[tok.ID] = append(pieceRounds[tok.ID], req.Round)
		houseUse[club.House]++
		spaceUse[req.Space]++
		subjectUse[req.Subject]++
		subjectHouseKey := req.Subject + "\x00" + club.House
		subjectHouseUse[subjectHouseKey]++
		subjectStyleKey := req.Subject + "\x00" + tok.Style
		subjectStyleUse[subjectStyleKey]++
		houseSpaceKey := club.House + "\x00" + req.Space
		houseSpaceUse[houseSpaceKey]++
		houseStyleKey := club.House + "\x00" + tok.Style
		houseStyleUse[houseStyleKey]++
		roundKey := fmt.Sprint(req.Round)
		roundUse[roundKey]++
		selected[req.ID] = tok
		selectedTurns[req.ID] = req
		selectedInputOrder[req.ID] = reqIdx
		if pieceUse[tok.ID] > tok.Remaining {
			return Score{}
		}
		if houseUse[club.House] > ledger.Limits.PerHouse[club.House] {
			return Score{}
		}
		if spaceUse[req.Space] > ledger.Limits.PerSpace[req.Space] {
			return Score{}
		}
		if subjectUse[req.Subject] > ledger.Limits.PerSubject[req.Subject] {
			return Score{}
		}
		subjectHouseLimit := 0
		if houseLimits, ok := ledger.Limits.PerSubjectHouse[req.Subject]; ok {
			subjectHouseLimit = houseLimits[club.House]
		}
		if subjectHouseUse[subjectHouseKey] > subjectHouseLimit {
			return Score{}
		}
		subjectStyleLimit := 0
		if styleLimits, ok := ledger.Limits.PerSubjectStyle[req.Subject]; ok {
			subjectStyleLimit = styleLimits[tok.Style]
		}
		if subjectStyleUse[subjectStyleKey] > subjectStyleLimit {
			return Score{}
		}
		houseSpaceLimit := 0
		if spaceLimits, ok := ledger.Limits.PerHouseSpace[club.House]; ok {
			houseSpaceLimit = spaceLimits[req.Space]
		}
		if houseSpaceUse[houseSpaceKey] > houseSpaceLimit {
			return Score{}
		}
		houseStyleLimit := 0
		if styleLimits, ok := ledger.Limits.PerHouseStyle[club.House]; ok {
			houseStyleLimit = styleLimits[tok.Style]
		}
		if houseStyleUse[houseStyleKey] > houseStyleLimit {
			return Score{}
		}
		if roundUse[roundKey] > ledger.Limits.PerRound[roundKey] {
			return Score{}
		}
		if !contains(tok.Labels, "round-heat-waive:"+roundKey) {
			roundHeatUse[roundKey] += req.Heat
			if roundHeatUse[roundKey] > ledger.Limits.RoundHeatBudget[roundKey] {
				return Score{}
			}
		}
		for _, label := range tok.Labels {
			if !strings.HasPrefix(label, "family:") {
				continue
			}
			family := strings.TrimPrefix(label, "family:")
			familyUse[family]++
			if familyUse[family] > ledger.Limits.FamilyCap[family] {
				return Score{}
			}
		}
		for _, label := range tok.Labels {
			if mutexLabels[label] {
				mutexUse[label] = append(mutexUse[label], tok)
			}
		}
		if !contains(tok.Labels, "heat-waive") {
			houseHeatUse[club.House] += req.Heat
			if houseHeatUse[club.House] > ledger.Limits.HouseHeatBudget[club.House] {
				return Score{}
			}
		}
		for _, badge := range req.Badges {
			if contains(tok.Labels, "pool:"+badge) {
				continue
			}
			badgeUse[badge]++
			if badgeUse[badge] > ledger.Limits.PerBadges[badge] {
				return Score{}
			}
		}
		rounds := pieceRounds[tok.ID]
		for i := 0; i < len(rounds); i++ {
			for j := i + 1; j < len(rounds); j++ {
				diff := rounds[i] - rounds[j]
				if diff < 0 {
					diff = -diff
				}
				if diff <= tok.Cooldown {
					return Score{}
				}
			}
		}
		score.Priority += req.Priority
		score.Heat += req.Heat
		score.Burden += styleLevel[tok.Style]
		used[tok.ID] = true
		joined = append(joined, req.ID+"="+tok.ID)
	}
	for label, pieces := range mutexUse {
		if len(pieces) <= 1 {
			continue
		}
		for _, tok := range pieces {
			if !contains(tok.Labels, "mutex-ok:"+label) {
				return Score{}
			}
		}
	}
	for _, exclusion := range ledger.Exclusions {
		left, leftOK := selected[exclusion.Left]
		right, rightOK := selected[exclusion.Right]
		if !leftOK || !rightOK {
			continue
		}
		if !contains(left.Labels, exclusion.UnlessLabel) || !contains(right.Labels, exclusion.UnlessLabel) {
			return Score{}
		}
	}
	selectedHouses := map[string][]Piece{}
	for _, tok := range selected {
		house := clubs[tok.Club].House
		selectedHouses[house] = append(selectedHouses[house], tok)
	}
	for _, pair := range ledger.Limits.BlockedHousePairs {
		if len(pair) != 2 {
			continue
		}
		leftPieces, leftOK := selectedHouses[pair[0]]
		rightPieces, rightOK := selectedHouses[pair[1]]
		if !leftOK || !rightOK {
			continue
		}
		label := "bridge:" + pair[0] + ":" + pair[1]
		leftBridge := false
		for _, tok := range leftPieces {
			if contains(tok.Labels, label) {
				leftBridge = true
			}
		}
		rightBridge := false
		for _, tok := range rightPieces {
			if contains(tok.Labels, label) {
				rightBridge = true
			}
		}
		if !leftBridge || !rightBridge {
			return Score{}
		}
	}
	selectedIDs := []string{}
	for id := range selected {
		selectedIDs = append(selectedIDs, id)
	}
	splitBadges := map[string]bool{}
	for _, badge := range ledger.Limits.SplitBadges {
		splitBadges[badge] = true
	}
	for i := 0; i < len(selectedIDs); i++ {
		for j := i + 1; j < len(selectedIDs); j++ {
			leftReq := selectedTurns[selectedIDs[i]]
			rightReq := selectedTurns[selectedIDs[j]]
			leftTok := selected[selectedIDs[i]]
			rightTok := selected[selectedIDs[j]]
			leftHouse := clubs[leftTok.Club].House
			rightHouse := clubs[rightTok.Club].House
			if leftTok.Club == rightTok.Club {
				diff := leftReq.Round - rightReq.Round
				if diff < 0 {
					diff = -diff
				}
				label := "club-burst:" + leftTok.Club
				if diff <= ledger.Limits.ClubRoundGap[leftTok.Club] && (!contains(leftTok.Labels, label) || !contains(rightTok.Labels, label)) {
					return Score{}
				}
			}
			for _, badge := range leftReq.Badges {
				if !splitBadges[badge] || !contains(rightReq.Badges, badge) || leftHouse != rightHouse {
					continue
				}
				label := "share:" + badge
				if !contains(leftTok.Labels, label) || !contains(rightTok.Labels, label) {
					return Score{}
				}
			}
			if leftReq.Stance == rightReq.Stance && leftReq.Space == rightReq.Space {
				diff := leftReq.Round - rightReq.Round
				if diff < 0 {
					diff = -diff
				}
				label := "parallel:" + leftReq.Stance + ":" + leftReq.Space
				if diff <= ledger.Limits.StanceSpaceGap[leftReq.Stance][leftReq.Space] && (!contains(leftTok.Labels, label) || !contains(rightTok.Labels, label)) {
					return Score{}
				}
			}
			if leftReq.Subject != rightReq.Subject {
				continue
			}
			if contains(leftTok.Labels, "rapid") && contains(rightTok.Labels, "rapid") {
				continue
			}
			diff := leftReq.Round - rightReq.Round
			if diff < 0 {
				diff = -diff
			}
			if diff <= ledger.Limits.SubjectRoundGap[leftReq.Subject] {
				return Score{}
			}
		}
	}
	subjectIDs := map[string][]string{}
	for turnID, req := range selectedTurns {
		subjectIDs[req.Subject] = append(subjectIDs[req.Subject], turnID)
	}
	for _, turnIDs := range subjectIDs {
		sort.Slice(turnIDs, func(i, j int) bool {
			left := selectedTurns[turnIDs[i]]
			right := selectedTurns[turnIDs[j]]
			if left.Round != right.Round {
				return left.Round < right.Round
			}
			return selectedInputOrder[turnIDs[i]] < selectedInputOrder[turnIDs[j]]
		})
		for i := 0; i+1 < len(turnIDs); i++ {
			leftReq := selectedTurns[turnIDs[i]]
			rightReq := selectedTurns[turnIDs[i+1]]
			leftTok := selected[turnIDs[i]]
			rightTok := selected[turnIDs[i+1]]
			leftHouse := clubs[leftTok.Club].House
			rightHouse := clubs[rightTok.Club].House
			transition := "route:" + leftReq.Space + ":" + rightReq.Space
			hasRouteLabel := contains(leftTok.Labels, transition) || contains(rightTok.Labels, transition)
			if !hasRouteLabel && !contains(ledger.Limits.AllowedTransitions[leftReq.Space], rightReq.Space) {
				return Score{}
			}
			if leftHouse != rightHouse {
				handoff := leftHouse + "->" + rightHouse
				handoffLabel := "handoff:" + leftHouse + ":" + rightHouse
				if !contains(leftTok.Labels, handoffLabel) && !contains(rightTok.Labels, handoffLabel) && !contains(ledger.Limits.AllowedHouseHandoffs[leftReq.Subject], handoff) {
					return Score{}
				}
			}
		}
	}
	for _, req := range ledger.Turns {
		tok, ok := selected[req.ID]
		if !ok {
			continue
		}
		if req.WaiveLabel != "" && contains(tok.Labels, req.WaiveLabel) {
			continue
		}
		for _, requiredID := range req.Links {
			requiredReq, ok := selectedTurns[requiredID]
			if !ok {
				return Score{}
			}
			if requiredReq.Round > req.Round && !contains(tok.Labels, "late-link:"+requiredID) {
				return Score{}
			}
		}
	}
	for _, cohort := range ledger.Cohorts {
		count := 0
		cohortHeat := 0
		houses := map[string]bool{}
		styles := map[string]bool{}
		for _, member := range cohort.Members {
			if tok, ok := selected[member]; ok {
				count++
				cohortHeat += selectedTurns[member].Heat
				houses[clubs[tok.Club].House] = true
				styles[tok.Style] = true
			}
		}
		if count == 0 {
			continue
		}
		if count < cohort.MinScore || count > cohort.MaxScore {
			return Score{}
		}
		if len(houses) < cohort.MinHouses || len(styles) < cohort.MinStyles {
			return Score{}
		}
		if cohortHeat > cohort.MaxHeat {
			return Score{}
		}
	}
	for _, board := range ledger.ReviewBoards {
		memberPieces := []Piece{}
		for _, member := range board.Members {
			if tok, ok := selected[member]; ok {
				memberPieces = append(memberPieces, tok)
			}
		}
		if len(memberPieces) == 0 {
			continue
		}
		chairCount := 0
		houses := map[string]bool{}
		styles := map[string]bool{}
		clubCounts := map[string]int{}
		for _, tok := range memberPieces {
			if contains(tok.Labels, board.ChairLabel) {
				chairCount++
			}
			houses[clubs[tok.Club].House] = true
			styles[tok.Style] = true
			clubCounts[tok.Club]++
		}
		if chairCount < board.MinChairs || len(houses) < board.MinHouses || len(styles) < board.MinStyles {
			return Score{}
		}
		for _, count := range clubCounts {
			if count > board.MaxSameClub {
				return Score{}
			}
		}
	}
	for _, window := range ledger.SurgeWindows {
		roundSet := map[int]bool{}
		for _, round := range window.Rounds {
			roundSet[round] = true
		}
		windowIDs := []string{}
		for turnID, req := range selectedTurns {
			if roundSet[req.Round] {
				windowIDs = append(windowIDs, turnID)
			}
		}
		if len(windowIDs) == 0 {
			continue
		}
		houses := map[string]bool{}
		spaces := map[string]bool{}
		subjectCounts := map[string]int{}
		windowHeat := 0
		hasAnchor := false
		for _, turnID := range windowIDs {
			req := selectedTurns[turnID]
			tok := selected[turnID]
			houses[clubs[tok.Club].House] = true
			spaces[req.Space] = true
			subjectCounts[req.Subject]++
			if !contains(tok.Labels, "surge-waive:"+window.Name) {
				windowHeat += req.Heat
			}
			if contains(tok.Labels, window.AnchorLabel) {
				hasAnchor = true
			}
		}
		if windowHeat > window.MaxHeat || len(houses) < window.MinHouses || len(spaces) < window.MinSpaces || !hasAnchor {
			return Score{}
		}
		for subject, count := range subjectCounts {
			if count <= window.MaxSameSubject {
				continue
			}
			repeatLabel := "surge-repeat:" + window.Name + ":" + subject
			for _, turnID := range windowIDs {
				req := selectedTurns[turnID]
				if req.Subject == subject && !contains(selected[turnID].Labels, repeatLabel) {
					return Score{}
				}
			}
		}
	}
	for _, path := range ledger.RelayPaths {
		memberIDs := []string{}
		for _, member := range path.Members {
			if _, ok := selected[member]; ok {
				memberIDs = append(memberIDs, member)
			}
		}
		if len(memberIDs) == 0 {
			continue
		}
		if len(memberIDs) < path.MinScore {
			return Score{}
		}
		minRound := selectedTurns[memberIDs[0]].Round
		maxRound := minRound
		pieces := []Piece{}
		distinctPieces := map[string]bool{}
		for _, member := range memberIDs {
			req := selectedTurns[member]
			tok := selected[member]
			if req.Round < minRound {
				minRound = req.Round
			}
			if req.Round > maxRound {
				maxRound = req.Round
			}
			pieces = append(pieces, tok)
			distinctPieces[tok.ID] = true
		}
		if maxRound-minRound > path.MaxRoundSpan {
			wideLabel := "relay-wide:" + path.Name
			for _, tok := range pieces {
				if !contains(tok.Labels, wideLabel) {
					return Score{}
				}
			}
		}
		if len(distinctPieces) < path.MinDistinctPieces {
			return Score{}
		}
		for i := 0; i+1 < len(memberIDs); i++ {
			leftID := memberIDs[i]
			rightID := memberIDs[i+1]
			leftReq := selectedTurns[leftID]
			rightReq := selectedTurns[rightID]
			leftTok := selected[leftID]
			rightTok := selected[rightID]
			edgeLabel := path.EdgeLabelPrefix + ":" + leftID + ":" + rightID
			if !contains(leftTok.Labels, edgeLabel) && !contains(rightTok.Labels, edgeLabel) {
				return Score{}
			}
			if leftReq.Subject != rightReq.Subject {
				continue
			}
			subjectLabel := "relay-subject:" + path.Name + ":" + leftReq.Subject
			if !contains(leftTok.Labels, subjectLabel) || !contains(rightTok.Labels, subjectLabel) {
				return Score{}
			}
		}
	}
	for _, track := range ledger.ScoreTracks {
		memberIDs := []string{}
		for _, member := range track.Members {
			if _, ok := selected[member]; ok {
				memberIDs = append(memberIDs, member)
			}
		}
		if len(memberIDs) == 0 {
			continue
		}
		sort.Slice(memberIDs, func(i, j int) bool {
			left := selectedTurns[memberIDs[i]]
			right := selectedTurns[memberIDs[j]]
			if left.Round != right.Round {
				return left.Round < right.Round
			}
			return selectedInputOrder[memberIDs[i]] < selectedInputOrder[memberIDs[j]]
		})
		value := track.Start
		for _, member := range memberIDs {
			req := selectedTurns[member]
			tok := selected[member]
			if contains(tok.Labels, "track-reset:"+track.Name) {
				value = track.Start
			}
			value += trackDelta(track.Name, req, tok)
			if !contains(tok.Labels, "track-guard:"+track.Name) && (value < track.MinValue || value > track.MaxValue) {
				return Score{}
			}
		}
		if value < track.FinishMin || value > track.FinishMax {
			return Score{}
		}
	}
	for _, backupSet := range ledger.BackupSets {
		memberIDs := []string{}
		for _, member := range backupSet.Members {
			if _, ok := selected[member]; ok {
				memberIDs = append(memberIDs, member)
			}
		}
		if len(memberIDs) == 0 {
			continue
		}
		for _, turnID := range memberIDs {
			req := selectedTurns[turnID]
			selectedPieceID := selected[turnID].ID
			backups := []Piece{}
			for _, tok := range ledger.Pieces {
				if tok.ID == selectedPieceID || !contains(tok.Labels, backupSet.BackupLabel) || tok.Subject != req.Subject {
					continue
				}
				if len(optionFailures(ledger, tok, req)) == 0 {
					backups = append(backups, tok)
				}
			}
			sort.Slice(backups, func(i, j int) bool {
				return backups[i].ID < backups[j].ID
			})
			if len(backups) < backupSet.MinBackups {
				return Score{}
			}
			houses := map[string]bool{}
			backupBurden := 0
			for i := 0; i < backupSet.MinBackups; i++ {
				tok := backups[i]
				houses[clubs[tok.Club].House] = true
				backupBurden += styleLevel[tok.Style]
			}
			if len(houses) < backupSet.MinBackupHouses || backupBurden > backupSet.MaxBackupBurden {
				return Score{}
			}
		}
	}
	for _, market := range ledger.ClaimMarkets {
		memberIDs := []string{}
		for _, member := range market.Members {
			if _, ok := selected[member]; ok {
				memberIDs = append(memberIDs, member)
			}
		}
		if len(memberIDs) == 0 {
			continue
		}
		sort.Slice(memberIDs, func(i, j int) bool {
			return selectedInputOrder[memberIDs[i]] < selectedInputOrder[memberIDs[j]]
		})
		claimed := []Piece{}
		claimedIDs := map[string]bool{}
		for _, turnID := range memberIDs {
			req := selectedTurns[turnID]
			selectedPieceID := selected[turnID].ID
			reserves := []Piece{}
			for _, tok := range ledger.Pieces {
				if tok.ID == selectedPieceID || claimedIDs[tok.ID] || tok.Subject != req.Subject || !contains(tok.Labels, market.ClaimLabel) {
					continue
				}
				if len(optionFailures(ledger, tok, req)) == 0 {
					reserves = append(reserves, tok)
				}
			}
			sort.Slice(reserves, func(i, j int) bool {
				return reserves[i].ID < reserves[j].ID
			})
			if len(reserves) == 0 {
				return Score{}
			}
			claimed = append(claimed, reserves[0])
			claimedIDs[reserves[0].ID] = true
		}
		if len(claimed) < market.MinClaims {
			return Score{}
		}
		houses := map[string]bool{}
		claimBurden := 0
		for _, tok := range claimed {
			houses[clubs[tok.Club].House] = true
			claimBurden += styleLevel[tok.Style]
		}
		if len(houses) < market.MinClaimHouses || claimBurden > market.MaxClaimBurden {
			return Score{}
		}
	}
	for _, ladder := range ledger.RoundLadders {
		memberIDs := []string{}
		for _, member := range ladder.Members {
			if _, ok := selected[member]; ok {
				memberIDs = append(memberIDs, member)
			}
		}
		if len(memberIDs) == 0 {
			continue
		}
		sort.Slice(memberIDs, func(i, j int) bool {
			left := selectedTurns[memberIDs[i]]
			right := selectedTurns[memberIDs[j]]
			if left.Round != right.Round {
				return left.Round < right.Round
			}
			return selectedInputOrder[memberIDs[i]] < selectedInputOrder[memberIDs[j]]
		})
		if len(memberIDs) < ladder.MinScore {
			return Score{}
		}
		for idx := 0; idx+1 < len(memberIDs); idx++ {
			leftID := memberIDs[idx]
			rightID := memberIDs[idx+1]
			leftReq := selectedTurns[leftID]
			rightReq := selectedTurns[rightID]
			leftTok := selected[leftID]
			rightTok := selected[rightID]
			if rightReq.Round-leftReq.Round > ladder.MaxRoundGap && !contains(leftTok.Labels, "ladder-wide:"+ladder.Name) && !contains(rightTok.Labels, "ladder-wide:"+ladder.Name) {
				return Score{}
			}
			wantsUp := idx%2 == 0
			if ladder.Pattern == "down-up" {
				wantsUp = !wantsUp
			}
			leftStyle := styleLevel[leftTok.Style]
			rightStyle := styleLevel[rightTok.Style]
			movementOK := rightStyle > leftStyle
			if !wantsUp {
				movementOK = rightStyle < leftStyle
			}
			if movementOK {
				continue
			}
			freeLabel := ladder.FreeLabelPrefix + ":" + leftID + ":" + rightID
			if !contains(leftTok.Labels, freeLabel) || !contains(rightTok.Labels, freeLabel) {
				return Score{}
			}
		}
	}
	sort.Strings(joined)
	score.Joined = strings.Join(joined, "|")
	score.Distinct = len(used)
	return score
}

func better(option Score, incumbent Score) bool {
	if !option.Valid {
		return false
	}
	if !incumbent.Valid {
		return true
	}
	if option.Priority != incumbent.Priority {
		return option.Priority > incumbent.Priority
	}
	if option.Heat != incumbent.Heat {
		return option.Heat < incumbent.Heat
	}
	if option.Burden != incumbent.Burden {
		return option.Burden < incumbent.Burden
	}
	if option.Distinct != incumbent.Distinct {
		return option.Distinct < incumbent.Distinct
	}
	return option.Joined < incumbent.Joined
}

func findBest(ledger Ledger) []int {
	choices := playableChoices(ledger)
	bestAssignment := make([]int, len(ledger.Turns))
	current := make([]int, len(ledger.Turns))
	bestScore := Score{}
	var walk func(int)
	walk = func(pos int) {
		if pos == len(choices) {
			score := scorePlan(ledger, current)
			if better(score, bestScore) {
				bestScore = score
				copy(bestAssignment, current)
			}
			return
		}
		for _, choice := range choices[pos] {
			current[pos] = choice
			walk(pos + 1)
		}
	}
	walk(0)
	return bestAssignment
}

func missReasons(ledger Ledger, req Turn, hasPlayable bool) []string {
	if hasPlayable {
		return []string{"not_selected"}
	}
	seenSubject := false
	seenReasons := map[string]bool{}
	for _, tok := range ledger.Pieces {
		if tok.Subject != req.Subject {
			continue
		}
		seenSubject = true
		for _, reason := range optionFailures(ledger, tok, req) {
			seenReasons[reason] = true
		}
	}
	if !seenSubject {
		return []string{"no_subject_piece"}
	}
	out := []string{}
	for _, reason := range reasonOrder {
		if seenReasons[reason] {
			out = append(out, reason)
		}
	}
	return out
}

func buildScorecard(ledger Ledger, assignment []int) Scorecard {
	clubs, _, styleLevel := indexes(ledger)
	choices := playableChoices(ledger)
	scorecard := Scorecard{Scored: []ScoreItem{}, Missed: []DenyItem{}}
	used := map[string]bool{}
	for reqIdx, req := range ledger.Turns {
		tokIdx := assignment[reqIdx]
		if tokIdx >= 0 {
			tok := ledger.Pieces[tokIdx]
			house := clubs[tok.Club].House
			scorecard.Scored = append(scorecard.Scored, ScoreItem{
				TurnID: req.ID,
				PieceID:   tok.ID,
				House:      house,
				Space:      req.Space,
				Priority:  req.Priority,
				Heat:      req.Heat,
			})
			scorecard.Summary.Priority += req.Priority
			scorecard.Summary.Heat += req.Heat
			scorecard.Summary.StyleBurden += styleLevel[tok.Style]
			used[tok.ID] = true
		} else {
			scorecard.Missed = append(scorecard.Missed, DenyItem{
				TurnID: req.ID,
				Reasons:   missReasons(ledger, req, len(choices[reqIdx]) > 1),
			})
		}
	}
	scorecard.Summary.ScoredCount = len(scorecard.Scored)
	scorecard.Summary.DistinctPieces = len(used)
	return scorecard
}

func main() {
	inputPath := flag.String("input", "", "ledger path")
	outputPath := flag.String("output", "/app/out/scorecard.json", "scorecard path")
	flag.Parse()
	if *inputPath == "" {
		fmt.Fprintln(os.Stderr, "--input is required")
		os.Exit(2)
	}
	raw, err := os.ReadFile(*inputPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	var ledger Ledger
	if err := json.Unmarshal(raw, &ledger); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	scorecard := buildScorecard(ledger, findBest(ledger))
	if err := os.MkdirAll(filepath.Dir(*outputPath), 0755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	out, err := json.MarshalIndent(scorecard, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := os.WriteFile(*outputPath, append(out, '\n'), 0644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
EOF

cd /app/matchcmd
/usr/local/go/bin/go build -trimpath -o /app/bin/lantern-referee .
