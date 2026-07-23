package main

import (
	"bufio"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/netip"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

var reasonOrder = []string{
	"unknown-source",
	"unknown-subject",
	"unknown-route",
	"source-blocked",
	"subject-blocked",
	"untrusted-domain",
	"identity-mismatch",
	"route-mismatch",
	"subject-not-allowed",
	"cluster-not-allowed",
	"env-not-allowed",
	"attestation-too-low",
	"scope-missing",
	"assertion-malformed",
	"assertion-claim-mismatch",
	"assertion-expired",
	"audience-not-allowed",
	"bad-signature",
	"delegation-not-allowed",
	"delegation-invalid",
	"delegation-scope-missing",
	"network-too-risky",
	"approval-invalid",
	"approval-missing",
	"nonce-replay",
}

type Policy struct {
	AsOf               string                 `json:"as_of"`
	TrustedDomains     []string               `json:"trusted_domains"`
	AllowedAudiences   []string               `json:"allowed_audiences"`
	NetworkZones       []NetworkZone          `json:"network_zones"`
	DefaultNetworkRisk int                    `json:"default_network_risk"`
	ScopeImplications  map[string][]string    `json:"scope_implications"`
	Routes             map[string]RoutePolicy `json:"routes"`
}

type NetworkZone struct {
	CIDR string `json:"cidr"`
	Risk int    `json:"risk"`
}

type RoutePolicy struct {
	Method                 string   `json:"method"`
	PathPrefix             string   `json:"path_prefix"`
	AllowedSubjectGroups   []string `json:"allowed_subject_groups"`
	AllowedSourceClusters  []string `json:"allowed_source_clusters"`
	AllowedEnvs            []string `json:"allowed_envs"`
	RequiredScopes         []string `json:"required_scopes"`
	MaxNetworkRisk         int      `json:"max_network_risk"`
	MaxAssertionAgeSeconds int      `json:"max_assertion_age_seconds"`
	RequireAttestation     string   `json:"require_attestation"`
	AllowDelegation        bool     `json:"allow_delegation"`
	MaxDelegationHops      int      `json:"max_delegation_hops"`
	RequiredApprovalRoles  []string `json:"required_approval_roles"`
}

type WorkloadBundle struct {
	Workloads []Workload `json:"workloads"`
}

type Workload struct {
	SpiffeID    string   `json:"spiffe_id"`
	Service     string   `json:"service"`
	Namespace   string   `json:"namespace"`
	TrustDomain string   `json:"trust_domain"`
	Cluster     string   `json:"cluster"`
	Env         string   `json:"env"`
	Groups      []string `json:"groups"`
	Status      string   `json:"status"`
	Attestation string   `json:"attestation"`
	Keys        []Key    `json:"keys"`
}

type Approver struct {
	ApproverID string   `json:"approver_id"`
	Roles      []string `json:"roles"`
	Status     string   `json:"status"`
	Keys       []Key    `json:"keys"`
}

type Key struct {
	KeyID        string `json:"key_id"`
	SecretB64URL string `json:"secret_b64url"`
	Status       string `json:"status"`
	NotBefore    string `json:"not_before"`
	ExpiresAt    string `json:"expires_at"`
}

type Call struct {
	RequestID       string       `json:"request_id"`
	RouteID         string       `json:"route_id"`
	SourceID        string       `json:"source_id"`
	SubjectID       string       `json:"subject_id"`
	KeyID           string       `json:"key_id"`
	Method          string       `json:"method"`
	Path            string       `json:"path"`
	Audience        string       `json:"audience"`
	Nonce           string       `json:"nonce"`
	OriginIP        string       `json:"origin_ip"`
	AssertionB64URL string       `json:"assertion_b64url"`
	SignatureB64URL string       `json:"signature_b64url"`
	Delegations     []Delegation `json:"delegations"`
	Approvals       []Approval   `json:"approvals"`
}

type Delegation struct {
	GrantID         string   `json:"grant_id"`
	From            string   `json:"from"`
	To              string   `json:"to"`
	KeyID           string   `json:"key_id"`
	Scopes          []string `json:"scopes"`
	NotBefore       string   `json:"not_before"`
	ExpiresAt       string   `json:"expires_at"`
	SignatureB64URL string   `json:"signature_b64url"`
}

type Approval struct {
	ApprovalID      string `json:"approval_id"`
	ApproverID      string `json:"approver_id"`
	KeyID           string `json:"key_id"`
	Role            string `json:"role"`
	Decision        string `json:"decision"`
	IssuedAt        string `json:"issued_at"`
	ExpiresAt       string `json:"expires_at"`
	Ticket          string `json:"ticket"`
	SignatureB64URL string `json:"signature_b64url"`
}

type Assertion struct {
	RequestID string   `json:"request_id"`
	SourceID  string   `json:"source_id"`
	SubjectID string   `json:"subject_id"`
	RouteID   string   `json:"route_id"`
	KeyID     string   `json:"key_id"`
	Method    string   `json:"method"`
	Path      string   `json:"path"`
	Audience  string   `json:"audience"`
	Nonce     string   `json:"nonce"`
	IssuedAt  string   `json:"issued_at"`
	Scopes    []string `json:"scopes"`
}

type ValidApproval struct {
	Approval Approval
	Expires  time.Time
}

type DecisionRow struct {
	RequestID              string   `json:"request_id"`
	Decision               string   `json:"decision"`
	Reasons                []string `json:"reasons"`
	RouteID                string   `json:"route_id"`
	SourceID               string   `json:"source_id"`
	SubjectID              string   `json:"subject_id"`
	NetworkRisk            int      `json:"network_risk"`
	EffectiveScopes        []string `json:"effective_scopes"`
	AcceptedDelegationIDs  []string `json:"accepted_delegation_ids"`
	ValidApprovalIDs       []string `json:"valid_approval_ids"`
	AuthorizationExpiresAt *string  `json:"authorization_expires_at"`
}

type Summary struct {
	TotalRequests     int            `json:"total_requests"`
	Allowed           int            `json:"allowed"`
	Denied            int            `json:"denied"`
	AllowedRequestIDs []string       `json:"allowed_request_ids"`
	DeniedRequestIDs  []string       `json:"denied_request_ids"`
	ReasonCounts      map[string]int `json:"reason_counts"`
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: workload-gate <input_dir> <output_dir>")
		os.Exit(2)
	}
	if err := run(os.Args[1], os.Args[2]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(inputDir, outputDir string) error {
	var policy Policy
	if err := readJSON(filepath.Join(inputDir, "mesh_policy.json"), &policy); err != nil {
		return err
	}
	var workloadBundle WorkloadBundle
	if err := readJSON(filepath.Join(inputDir, "workloads.json"), &workloadBundle); err != nil {
		return err
	}
	var approverList []Approver
	if err := readJSON(filepath.Join(inputDir, "approvers.json"), &approverList); err != nil {
		return err
	}
	calls, err := readCalls(filepath.Join(inputDir, "calls.jsonl"))
	if err != nil {
		return err
	}

	asOf, err := time.Parse(time.RFC3339, policy.AsOf)
	if err != nil {
		return err
	}
	workloads := map[string]Workload{}
	for _, workload := range workloadBundle.Workloads {
		workloads[workload.SpiffeID] = workload
	}
	approvers := map[string]Approver{}
	for _, approver := range approverList {
		approvers[approver.ApproverID] = approver
	}
	trusted := stringSet(policy.TrustedDomains)
	allowedAudiences := stringSet(policy.AllowedAudiences)
	seenNonce := map[string]bool{}

	rows := make([]DecisionRow, 0, len(calls))
	summary := Summary{
		TotalRequests:     len(calls),
		AllowedRequestIDs: []string{},
		DeniedRequestIDs:  []string{},
		ReasonCounts:      map[string]int{},
	}
	for _, reason := range reasonOrder {
		summary.ReasonCounts[reason] = 0
	}

	for _, call := range calls {
		row := evaluateCall(call, policy, asOf, workloads, approvers, trusted, allowedAudiences, seenNonce)
		rows = append(rows, row)
		if row.Decision == "allow" {
			summary.Allowed++
			summary.AllowedRequestIDs = append(summary.AllowedRequestIDs, row.RequestID)
		} else {
			summary.Denied++
			summary.DeniedRequestIDs = append(summary.DeniedRequestIDs, row.RequestID)
		}
		for _, reason := range row.Reasons {
			summary.ReasonCounts[reason]++
		}
	}

	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return err
	}
	if err := writeJSONL(filepath.Join(outputDir, "workload_decisions.jsonl"), rows); err != nil {
		return err
	}
	return writeJSON(filepath.Join(outputDir, "workload_summary.json"), summary)
}

func evaluateCall(call Call, policy Policy, asOf time.Time, workloads map[string]Workload, approvers map[string]Approver, trusted map[string]bool, allowedAudiences map[string]bool, seenNonce map[string]bool) DecisionRow {
	flags := map[string]bool{}
	source, sourceKnown := workloads[call.SourceID]
	subject, subjectKnown := workloads[call.SubjectID]
	routeValue, routeKnown := policy.Routes[call.RouteID]
	var route *RoutePolicy
	if routeKnown {
		route = &routeValue
	}

	if !sourceKnown {
		flags["unknown-source"] = true
	}
	if !subjectKnown {
		flags["unknown-subject"] = true
	}
	if !routeKnown {
		flags["unknown-route"] = true
	}
	if sourceKnown && source.Status != "active" {
		flags["source-blocked"] = true
	}
	if subjectKnown && subject.Status != "active" {
		flags["subject-blocked"] = true
	}
	if (sourceKnown && !trusted[source.TrustDomain]) || (subjectKnown && !trusted[subject.TrustDomain]) {
		flags["untrusted-domain"] = true
	}
	if (sourceKnown && !identityMatches(source)) || (subjectKnown && !identityMatches(subject)) {
		flags["identity-mismatch"] = true
	}

	networkRisk := networkRisk(policy, call.OriginIP)
	if route != nil {
		if call.Method != route.Method || !strings.HasPrefix(call.Path, route.PathPrefix) {
			flags["route-mismatch"] = true
		}
		if subjectKnown && !overlap(subject.Groups, route.AllowedSubjectGroups) {
			flags["subject-not-allowed"] = true
		}
		if sourceKnown && !contains(route.AllowedSourceClusters, source.Cluster) {
			flags["cluster-not-allowed"] = true
		}
		if sourceKnown && !contains(route.AllowedEnvs, source.Env) {
			flags["env-not-allowed"] = true
		}
		if sourceKnown && attestationRank(source.Attestation) < attestationRank(route.RequireAttestation) {
			flags["attestation-too-low"] = true
		}
		if networkRisk > route.MaxNetworkRisk {
			flags["network-too-risky"] = true
		}
	}

	assertion, assertionOK, issuedAt := decodeAssertion(call.AssertionB64URL)
	assertionScopes := []string{}
	if !assertionOK {
		flags["assertion-malformed"] = true
	} else {
		assertionScopes = expandScopes(policy.ScopeImplications, assertion.Scopes)
		if assertion.RequestID != call.RequestID ||
			assertion.SourceID != call.SourceID ||
			assertion.SubjectID != call.SubjectID ||
			assertion.RouteID != call.RouteID ||
			assertion.KeyID != call.KeyID ||
			assertion.Method != call.Method ||
			assertion.Path != call.Path ||
			assertion.Audience != call.Audience ||
			assertion.Nonce != call.Nonce {
			flags["assertion-claim-mismatch"] = true
		}
		if route != nil {
			if issuedAt.After(asOf) || asOf.Sub(issuedAt) > time.Duration(route.MaxAssertionAgeSeconds)*time.Second {
				flags["assertion-expired"] = true
			}
		}
	}
	if !allowedAudiences[call.Audience] {
		flags["audience-not-allowed"] = true
	}
	if sourceKnown && assertionOK {
		signing := strings.Join([]string{call.RequestID, call.SourceID, call.KeyID, call.AssertionB64URL, call.Nonce}, "\n")
		secret, keyOK := activeKeySecret(source.Keys, call.KeyID, issuedAt)
		if !keyOK || !validHMAC(secret, signing, call.SignatureB64URL) {
			flags["bad-signature"] = true
		}
	}
	if route != nil && !subset(route.RequiredScopes, assertionScopes) {
		flags["scope-missing"] = true
	}

	effectiveScopes := append([]string{}, assertionScopes...)
	acceptedDelegationIDs := []string{}
	delegationExpiries := []time.Time{}
	if !assertionOK {
		effectiveScopes = []string{}
	}
	if call.SourceID == call.SubjectID {
		if len(call.Delegations) > 0 {
			flags["delegation-invalid"] = true
		}
	} else {
		if route != nil && !route.AllowDelegation {
			flags["delegation-not-allowed"] = true
		}
		chainValid, ids, hopScopes, expiries := validateDelegationChain(call, route, workloads, trusted, asOf, policy.ScopeImplications)
		if !chainValid {
			flags["delegation-invalid"] = true
			effectiveScopes = []string{}
		} else {
			if assertionOK {
				effectiveScopes = intersect(effectiveScopes, hopScopes)
			}
			delegationExpiries = expiries
			if route != nil && !subset(route.RequiredScopes, hopScopes) {
				flags["delegation-scope-missing"] = true
			}
			if route != nil && route.AllowDelegation {
				acceptedDelegationIDs = ids
			}
		}
	}

	validApprovals, anyInvalidApproval := validateApprovals(call, approvers, asOf)
	if anyInvalidApproval {
		flags["approval-invalid"] = true
	}
	validApprovalIDs := make([]string, 0, len(validApprovals))
	for _, valid := range validApprovals {
		validApprovalIDs = append(validApprovalIDs, valid.Approval.ApprovalID)
	}
	sort.Strings(validApprovalIDs)
	if route != nil && !approvalCoverage(route.RequiredApprovalRoles, validApprovals) {
		flags["approval-missing"] = true
	}

	nonceKey := call.SourceID + "\x00" + call.Audience + "\x00" + call.Nonce
	if seenNonce[nonceKey] {
		flags["nonce-replay"] = true
	}
	seenNonce[nonceKey] = true

	reasons := orderedReasons(flags)
	decision := "deny"
	var expires *string
	if len(reasons) == 0 {
		decision = "allow"
		expiry := issuedAt.Add(time.Duration(route.MaxAssertionAgeSeconds) * time.Second)
		for _, grantExpiry := range delegationExpiries {
			if grantExpiry.Before(expiry) {
				expiry = grantExpiry
			}
		}
		requiredRoles := stringSet(route.RequiredApprovalRoles)
		for _, valid := range validApprovals {
			if requiredRoles[valid.Approval.Role] && valid.Expires.Before(expiry) {
				expiry = valid.Expires
			}
		}
		formatted := expiry.UTC().Format("2006-01-02T15:04:05Z")
		expires = &formatted
	}

	return DecisionRow{
		RequestID:              call.RequestID,
		Decision:               decision,
		Reasons:                reasons,
		RouteID:                call.RouteID,
		SourceID:               call.SourceID,
		SubjectID:              call.SubjectID,
		NetworkRisk:            networkRisk,
		EffectiveScopes:        effectiveScopes,
		AcceptedDelegationIDs:  acceptedDelegationIDs,
		ValidApprovalIDs:       validApprovalIDs,
		AuthorizationExpiresAt: expires,
	}
}

func validateDelegationChain(call Call, route *RoutePolicy, workloads map[string]Workload, trusted map[string]bool, asOf time.Time, scopeImplications map[string][]string) (bool, []string, []string, []time.Time) {
	if len(call.Delegations) == 0 {
		return false, nil, nil, nil
	}
	if route != nil && len(call.Delegations) > route.MaxDelegationHops {
		return false, nil, nil, nil
	}
	expectedFrom := call.SubjectID
	ids := make([]string, 0, len(call.Delegations))
	expiries := make([]time.Time, 0, len(call.Delegations))
	var hopScopeIntersection []string
	for index, grant := range call.Delegations {
		if grant.GrantID == "" || grant.From == "" || grant.To == "" || grant.KeyID == "" || grant.NotBefore == "" || grant.ExpiresAt == "" || len(grant.Scopes) == 0 {
			return false, nil, nil, nil
		}
		if grant.From != expectedFrom {
			return false, nil, nil, nil
		}
		fromWorkload, fromKnown := workloads[grant.From]
		toWorkload, toKnown := workloads[grant.To]
		if !fromKnown || !toKnown || fromWorkload.Status != "active" || toWorkload.Status != "active" {
			return false, nil, nil, nil
		}
		if !trusted[fromWorkload.TrustDomain] || !trusted[toWorkload.TrustDomain] {
			return false, nil, nil, nil
		}
		notBefore, err1 := time.Parse(time.RFC3339, grant.NotBefore)
		expiresAt, err2 := time.Parse(time.RFC3339, grant.ExpiresAt)
		if err1 != nil || err2 != nil || asOf.Before(notBefore) || !asOf.Before(expiresAt) {
			return false, nil, nil, nil
		}
		signedScopes := normalize(grant.Scopes)
		if len(signedScopes) == 0 {
			return false, nil, nil, nil
		}
		signing := strings.Join([]string{
			grant.GrantID,
			call.RequestID,
			grant.From,
			grant.To,
			grant.KeyID,
			strings.Join(signedScopes, ","),
			grant.NotBefore,
			grant.ExpiresAt,
		}, "\n")
		secret, keyOK := activeKeySecret(fromWorkload.Keys, grant.KeyID, notBefore)
		if !keyOK || !validHMAC(secret, signing, grant.SignatureB64URL) {
			return false, nil, nil, nil
		}
		scopes := expandScopes(scopeImplications, signedScopes)
		if index == 0 {
			hopScopeIntersection = scopes
		} else {
			hopScopeIntersection = intersect(hopScopeIntersection, scopes)
		}
		ids = append(ids, grant.GrantID)
		expiries = append(expiries, expiresAt)
		expectedFrom = grant.To
	}
	if expectedFrom != call.SourceID {
		return false, nil, nil, nil
	}
	return true, ids, hopScopeIntersection, expiries
}

func validateApprovals(call Call, approvers map[string]Approver, asOf time.Time) ([]ValidApproval, bool) {
	valid := []ValidApproval{}
	anyInvalid := false
	for _, approval := range call.Approvals {
		approver, known := approvers[approval.ApproverID]
		issuedAt, err1 := time.Parse(time.RFC3339, approval.IssuedAt)
		expiresAt, err2 := time.Parse(time.RFC3339, approval.ExpiresAt)
		ok := known &&
			approver.Status == "active" &&
			approval.Decision == "approve" &&
			contains(approver.Roles, approval.Role) &&
			err1 == nil &&
			err2 == nil &&
			!asOf.Before(issuedAt) &&
			asOf.Before(expiresAt)
		if ok {
			signing := strings.Join([]string{
				approval.ApprovalID,
				call.RequestID,
				approval.ApproverID,
				approval.KeyID,
				approval.Role,
				approval.Decision,
				approval.IssuedAt,
				approval.ExpiresAt,
				approval.Ticket,
			}, "\n")
			secret, keyOK := activeKeySecret(approver.Keys, approval.KeyID, issuedAt)
			ok = keyOK && validHMAC(secret, signing, approval.SignatureB64URL)
		}
		if ok {
			valid = append(valid, ValidApproval{Approval: approval, Expires: expiresAt})
		} else {
			anyInvalid = true
		}
	}
	return valid, anyInvalid
}

func approvalCoverage(required []string, approvals []ValidApproval) bool {
	if len(required) == 0 {
		return true
	}
	used := map[string]bool{}
	var search func(int) bool
	search = func(index int) bool {
		if index == len(required) {
			return true
		}
		role := required[index]
		for _, approval := range approvals {
			if approval.Approval.Role == role && !used[approval.Approval.ApproverID] {
				used[approval.Approval.ApproverID] = true
				if search(index + 1) {
					return true
				}
				delete(used, approval.Approval.ApproverID)
			}
		}
		return false
	}
	return search(0)
}

func decodeAssertion(text string) (Assertion, bool, time.Time) {
	var assertion Assertion
	raw, err := base64.RawURLEncoding.DecodeString(text)
	if err != nil {
		return assertion, false, time.Time{}
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(raw, &fields); err != nil {
		return assertion, false, time.Time{}
	}
	required := []string{"request_id", "source_id", "subject_id", "route_id", "key_id", "method", "path", "audience", "nonce", "issued_at", "scopes"}
	if len(fields) != len(required) {
		return assertion, false, time.Time{}
	}
	for _, key := range required {
		if _, ok := fields[key]; !ok {
			return assertion, false, time.Time{}
		}
	}
	if err := json.Unmarshal(raw, &assertion); err != nil {
		return assertion, false, time.Time{}
	}
	if assertion.RequestID == "" || assertion.SourceID == "" || assertion.SubjectID == "" || assertion.RouteID == "" || assertion.KeyID == "" ||
		assertion.Method == "" || assertion.Path == "" || assertion.Audience == "" || assertion.Nonce == "" || assertion.IssuedAt == "" {
		return assertion, false, time.Time{}
	}
	if assertion.Scopes == nil {
		return assertion, false, time.Time{}
	}
	issuedAt, err := time.Parse(time.RFC3339, assertion.IssuedAt)
	if err != nil {
		return assertion, false, time.Time{}
	}
	for _, scope := range assertion.Scopes {
		if scope == "" {
			return assertion, false, time.Time{}
		}
	}
	return assertion, true, issuedAt
}

func readJSON(path string, value any) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(data, value)
}

func readCalls(path string) ([]Call, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 0, 64*1024), 4*1024*1024)
	calls := []Call{}
	lineNo := 0
	for scanner.Scan() {
		lineNo++
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var call Call
		if err := json.Unmarshal([]byte(line), &call); err != nil {
			return nil, fmt.Errorf("calls.jsonl line %d: %w", lineNo, err)
		}
		calls = append(calls, call)
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return calls, nil
}

func writeJSONL(path string, rows []DecisionRow) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	encoder := json.NewEncoder(file)
	for _, row := range rows {
		if err := encoder.Encode(row); err != nil {
			return err
		}
	}
	return nil
}

func writeJSON(path string, value any) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	encoder := json.NewEncoder(file)
	return encoder.Encode(value)
}

func validHMAC(secretB64URL, signing, got string) bool {
	secret, err := base64.RawURLEncoding.DecodeString(secretB64URL)
	if err != nil {
		return false
	}
	mac := hmac.New(sha256.New, secret)
	_, _ = mac.Write([]byte(signing))
	expected := base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
	return hmac.Equal([]byte(expected), []byte(got))
}

func activeKeySecret(keys []Key, keyID string, at time.Time) (string, bool) {
	for _, key := range keys {
		if key.KeyID != keyID || key.Status != "active" {
			continue
		}
		notBefore, err1 := time.Parse(time.RFC3339, key.NotBefore)
		expiresAt, err2 := time.Parse(time.RFC3339, key.ExpiresAt)
		if err1 == nil && err2 == nil && !at.Before(notBefore) && at.Before(expiresAt) {
			return key.SecretB64URL, true
		}
	}
	return "", false
}

func identityMatches(workload Workload) bool {
	expected := "spiffe://" + workload.TrustDomain + "/ns/" + workload.Namespace + "/sa/" + workload.Service
	return workload.SpiffeID == expected
}

func networkRisk(policy Policy, ipText string) int {
	ip, err := netip.ParseAddr(ipText)
	if err != nil {
		return policy.DefaultNetworkRisk
	}
	bestBits := -1
	bestRisk := policy.DefaultNetworkRisk
	for _, zone := range policy.NetworkZones {
		prefix, err := netip.ParsePrefix(zone.CIDR)
		if err == nil && prefix.Contains(ip) && prefix.Bits() > bestBits {
			bestBits = prefix.Bits()
			bestRisk = zone.Risk
		}
	}
	return bestRisk
}

func attestationRank(value string) int {
	switch value {
	case "hardware":
		return 2
	case "baseline":
		return 1
	default:
		return 0
	}
}

func orderedReasons(flags map[string]bool) []string {
	out := []string{}
	for _, reason := range reasonOrder {
		if flags[reason] {
			out = append(out, reason)
		}
	}
	return out
}

func normalize(values []string) []string {
	set := map[string]bool{}
	for _, value := range values {
		if value != "" {
			set[value] = true
		}
	}
	out := make([]string, 0, len(set))
	for value := range set {
		out = append(out, value)
	}
	sort.Strings(out)
	return out
}

func expandScopes(implications map[string][]string, values []string) []string {
	set := stringSet(normalize(values))
	stack := make([]string, 0, len(set))
	for scope := range set {
		stack = append(stack, scope)
	}
	for len(stack) > 0 {
		scope := stack[len(stack)-1]
		stack = stack[:len(stack)-1]
		for _, implied := range implications[scope] {
			if implied != "" && !set[implied] {
				set[implied] = true
				stack = append(stack, implied)
			}
		}
	}
	out := make([]string, 0, len(set))
	for scope := range set {
		out = append(out, scope)
	}
	sort.Strings(out)
	return out
}

func intersect(left, right []string) []string {
	rightSet := stringSet(right)
	out := []string{}
	for _, value := range normalize(left) {
		if rightSet[value] {
			out = append(out, value)
		}
	}
	return out
}

func subset(required, have []string) bool {
	haveSet := stringSet(have)
	for _, value := range normalize(required) {
		if !haveSet[value] {
			return false
		}
	}
	return true
}

func overlap(left, right []string) bool {
	rightSet := stringSet(right)
	for _, value := range left {
		if rightSet[value] {
			return true
		}
	}
	return false
}

func contains(values []string, wanted string) bool {
	for _, value := range values {
		if value == wanted {
			return true
		}
	}
	return false
}

func stringSet(values []string) map[string]bool {
	set := map[string]bool{}
	for _, value := range values {
		set[value] = true
	}
	return set
}
