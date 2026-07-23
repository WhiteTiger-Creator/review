package auth

import (
	"strings"
	"testing"
)

// flipMiddleChar mutates a character near the middle of s to a different
// value, avoiding the last base64url character (whose low-order padding
// bits are ignored by the decoder and so may not change the decoded bytes).
func flipMiddleChar(s string) string {
	i := len(s) / 2
	repl := byte('A')
	if s[i] == 'A' {
		repl = 'B'
	}
	return s[:i] + string(repl) + s[i+1:]
}

func TestSessionTokenRoundTrip(t *testing.T) {
	keys, err := NewKeys()
	if err != nil {
		t.Fatalf("NewKeys: %v", err)
	}

	raw, err := keys.IssueSessionToken(7, "carol", "user")
	if err != nil {
		t.Fatalf("IssueSessionToken: %v", err)
	}

	claims, err := keys.ParseSessionToken(raw)
	if err != nil {
		t.Fatalf("ParseSessionToken: %v", err)
	}
	if claims.UserID != 7 || claims.Username != "carol" || claims.Role != "user" {
		t.Errorf("claims = %+v, want UserID=7 Username=carol Role=user", claims)
	}
}

func TestSessionTokenRejectsTamperedSignature(t *testing.T) {
	keys, err := NewKeys()
	if err != nil {
		t.Fatalf("NewKeys: %v", err)
	}
	raw, err := keys.IssueSessionToken(7, "carol", "user")
	if err != nil {
		t.Fatalf("IssueSessionToken: %v", err)
	}

	parts := strings.Split(raw, ".")
	if len(parts) != 3 {
		t.Fatalf("expected a 3-part JWT, got %d parts", len(parts))
	}
	parts[2] = flipMiddleChar(parts[2])
	tampered := strings.Join(parts, ".")

	if _, err := keys.ParseSessionToken(tampered); err == nil {
		t.Error("ParseSessionToken accepted a token with a corrupted signature")
	}
}

func TestServiceTokenRoundTrip(t *testing.T) {
	keys, err := NewKeys()
	if err != nil {
		t.Fatalf("NewKeys: %v", err)
	}

	raw, err := keys.IssueServiceToken("internal")
	if err != nil {
		t.Fatalf("IssueServiceToken: %v", err)
	}

	claims, err := keys.ParseServiceToken(raw)
	if err != nil {
		t.Fatalf("ParseServiceToken: %v", err)
	}
	if claims.Scope != "internal" {
		t.Errorf("Scope = %q, want %q", claims.Scope, "internal")
	}
}
