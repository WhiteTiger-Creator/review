package auth

import (
	"bytes"
	"context"
	"crypto/hmac"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

// signdPath returns the path to the HMAC signing helper used for session
// tokens. It's a small standalone binary (see the signd build stage)
// rather than in-process code so the signing key can be rotated
// independently of the application binary.
func signdPath() string {
	if p := os.Getenv("AUTHGW_SIGND_PATH"); p != "" {
		return p
	}
	return "/app/bin/authgw-signd"
}

// SessionClaims is embedded in user-session tokens issued after a
// successful password login.
type SessionClaims struct {
	UserID   int64  `json:"uid"`
	Username string `json:"username"`
	Role     string `json:"role"`
	jwt.RegisteredClaims
}

// ServiceClaims is embedded in RS256 service tokens minted by admins for
// internal service-to-service calls (see /admin/service-tokens).
type ServiceClaims struct {
	Scope string `json:"scope"`
	jwt.RegisteredClaims
}

func base64URL(b []byte) string {
	return base64.RawURLEncoding.EncodeToString(b)
}

func base64URLDecode(s string) ([]byte, error) {
	return base64.RawURLEncoding.DecodeString(s)
}

// signViaHelper returns the hex-encoded HMAC-SHA256 of payload, computed
// by shelling out to authgw-signd.
func signViaHelper(payload string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	cmd := exec.CommandContext(ctx, signdPath())
	cmd.Stdin = strings.NewReader(payload + "\n")
	var out bytes.Buffer
	cmd.Stdout = &out
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("sign via helper: %w", err)
	}
	return strings.TrimSpace(out.String()), nil
}

// IssueSessionToken signs a short-lived HS256 session token for an
// authenticated user via the signing helper.
func (k *Keys) IssueSessionToken(userID int64, username, role string) (string, error) {
	claims := SessionClaims{
		UserID:   userID,
		Username: username,
		Role:     role,
		RegisteredClaims: jwt.RegisteredClaims{
			Issuer:    "authgw",
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(2 * time.Hour)),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
		},
	}

	headerJSON, err := json.Marshal(map[string]string{"alg": "HS256", "typ": "JWT"})
	if err != nil {
		return "", fmt.Errorf("marshal header: %w", err)
	}
	claimsJSON, err := json.Marshal(claims)
	if err != nil {
		return "", fmt.Errorf("marshal claims: %w", err)
	}
	signingInput := base64URL(headerJSON) + "." + base64URL(claimsJSON)

	sigHex, err := signViaHelper(signingInput)
	if err != nil {
		return "", err
	}
	sigBytes, err := hex.DecodeString(sigHex)
	if err != nil {
		return "", fmt.Errorf("decode helper signature: %w", err)
	}

	return signingInput + "." + base64URL(sigBytes), nil
}

// ParseSessionToken verifies an HS256 session token and returns its
// claims. The expected signature is recomputed via the same signing
// helper used at issuance and compared in constant time.
func (k *Keys) ParseSessionToken(raw string) (*SessionClaims, error) {
	parts := strings.Split(raw, ".")
	if len(parts) != 3 {
		return nil, fmt.Errorf("malformed token")
	}
	signingInput := parts[0] + "." + parts[1]

	wantSigHex, err := signViaHelper(signingInput)
	if err != nil {
		return nil, err
	}
	wantSig, err := hex.DecodeString(wantSigHex)
	if err != nil {
		return nil, fmt.Errorf("decode expected signature: %w", err)
	}
	gotSig, err := base64URLDecode(parts[2])
	if err != nil {
		return nil, fmt.Errorf("decode token signature: %w", err)
	}
	if !hmac.Equal(wantSig, gotSig) {
		return nil, fmt.Errorf("signature mismatch")
	}

	claimsJSON, err := base64URLDecode(parts[1])
	if err != nil {
		return nil, fmt.Errorf("decode claims: %w", err)
	}
	claims := &SessionClaims{}
	if err := json.Unmarshal(claimsJSON, claims); err != nil {
		return nil, fmt.Errorf("unmarshal claims: %w", err)
	}

	if claims.Issuer != "authgw" {
		return nil, fmt.Errorf("unexpected issuer")
	}
	if claims.ExpiresAt == nil || claims.ExpiresAt.Before(time.Now()) {
		return nil, fmt.Errorf("token expired")
	}

	return claims, nil
}

// IssueServiceToken signs an RS256 service token used by internal
// integrations. Only admins may mint these (see handlers.AdminServiceToken).
func (k *Keys) IssueServiceToken(scope string) (string, error) {
	claims := ServiceClaims{
		Scope: scope,
		RegisteredClaims: jwt.RegisteredClaims{
			Issuer:    "authgw",
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(10 * time.Minute)),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
		},
	}
	token := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	return token.SignedString(k.RSAPriv)
}

// ParseServiceToken verifies an RS256 service token.
func (k *Keys) ParseServiceToken(raw string) (*ServiceClaims, error) {
	claims := &ServiceClaims{}
	token, err := jwt.ParseWithClaims(raw, claims, func(t *jwt.Token) (interface{}, error) {
		return &k.RSAPriv.PublicKey, nil
	}, jwt.WithValidMethods([]string{"RS256"}), jwt.WithIssuer("authgw"))
	if err != nil {
		return nil, err
	}
	if !token.Valid {
		return nil, fmt.Errorf("invalid token")
	}
	return claims, nil
}
