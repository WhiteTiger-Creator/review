#!/bin/bash
set -euo pipefail

cd /app

# --- Fix 1: internal/auth/keys.go ---------------------------------------
# The session HMAC secret must be independent random material generated
# in-process, not delegated to the external authgw-signd helper (whose
# key is a fixed constant compiled into the binary at /app/bin/authgw-signd
# and recoverable with `strings`/a disassembler).
cat > internal/auth/keys.go <<'EOF'
// Package auth holds signing-key material and JWT issuance/verification
// helpers for authgw.
package auth

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"encoding/hex"
	"encoding/pem"
	"fmt"
)

// Keys holds the symmetric secret used for user-session tokens, the RSA
// keypair used for internal service tokens (see /admin/service-tokens and
// /.well-known/jwks.json), and this process's instance identifier
// (surfaced at /healthz so operators can tell which replica answered a
// given request).
type Keys struct {
	HMACSecret []byte
	RSAPriv    *rsa.PrivateKey
	InstanceID string
}

// NewKeys generates fresh signing material for a server process.
func NewKeys() (*Keys, error) {
	priv, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return nil, fmt.Errorf("generate rsa key: %w", err)
	}

	idBytes := make([]byte, 8)
	if _, err := rand.Read(idBytes); err != nil {
		return nil, fmt.Errorf("generate instance id: %w", err)
	}

	secret := make([]byte, 32)
	if _, err := rand.Read(secret); err != nil {
		return nil, fmt.Errorf("generate hmac secret: %w", err)
	}

	return &Keys{
		HMACSecret: secret,
		RSAPriv:    priv,
		InstanceID: hex.EncodeToString(idBytes),
	}, nil
}

// PublicKeyPEM returns the PKIX/PEM encoding of the RSA public key, the
// same encoding published (in JWK form) at /.well-known/jwks.json.
func (k *Keys) PublicKeyPEM() ([]byte, error) {
	der, err := x509.MarshalPKIXPublicKey(&k.RSAPriv.PublicKey)
	if err != nil {
		return nil, fmt.Errorf("marshal public key: %w", err)
	}
	return pem.EncodeToMemory(&pem.Block{Type: "PUBLIC KEY", Bytes: der}), nil
}
EOF

# --- Fix 2: internal/auth/jwt.go ----------------------------------------
# Sign and verify session tokens natively with the in-process HMAC secret
# instead of shelling out to authgw-signd. The signing method is pinned
# server-side so a token's own "alg" header can never select the
# verification key material.
cat > internal/auth/jwt.go <<'EOF'
package auth

import (
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

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

// IssueSessionToken signs a short-lived HS256 session token for an
// authenticated user.
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
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString(k.HMACSecret)
}

// ParseSessionToken verifies an HS256 session token and returns its claims.
// The signing method is pinned server-side so a token's own "alg" header
// can never select the verification key material.
func (k *Keys) ParseSessionToken(raw string) (*SessionClaims, error) {
	claims := &SessionClaims{}
	token, err := jwt.ParseWithClaims(raw, claims, func(t *jwt.Token) (interface{}, error) {
		return k.HMACSecret, nil
	}, jwt.WithValidMethods([]string{"HS256"}), jwt.WithIssuer("authgw"))
	if err != nil {
		return nil, err
	}
	if !token.Valid {
		return nil, fmt.Errorf("invalid token")
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
EOF

# --- Fix 3: internal/session/session.go ---------------------------------
# Use a placeholder-bound query instead of interpolating the caller's
# remember_token into the SQL text. A keyword blocklist is not sufficient
# on its own (it's case-sensitive and doesn't touch the quote character),
# so it's removed rather than patched.
cat > internal/session/session.go <<'EOF'
// Package session manages "remember me" tokens, a fallback login path that
// lets a browser reauthenticate without a fresh HS256 session token.
package session

import (
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"fmt"
)

// Identity is the (user_id, role) pair a valid remember token resolves to.
type Identity struct {
	UserID int64
	Role   string
}

// NewToken generates a fresh 32-byte random remember token, hex encoded.
func NewToken() (string, error) {
	buf := make([]byte, 32)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	return hex.EncodeToString(buf), nil
}

// Create stores a new remember-me session for userID/role and returns the
// token to set as a cookie.
func Create(conn *sql.DB, userID int64, role string) (string, error) {
	token, err := NewToken()
	if err != nil {
		return "", err
	}
	if _, err := conn.Exec(`INSERT INTO sessions (remember_token, user_id, role) VALUES (?, ?, ?)`,
		token, userID, role); err != nil {
		return "", fmt.Errorf("store remember token: %w", err)
	}
	return token, nil
}

// Lookup resolves a remember token to its owning identity. The token is
// bound with a placeholder so caller-supplied input is never interpolated
// into the query text.
func Lookup(conn *sql.DB, token string) (*Identity, error) {
	row := conn.QueryRow(`SELECT user_id, role FROM sessions WHERE remember_token = ?`, token)
	var id Identity
	if err := row.Scan(&id.UserID, &id.Role); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("lookup remember token: %w", err)
	}
	return &id, nil
}
EOF

# --- Verify the fix builds and behaves correctly ------------------------
go build ./...
go vet ./...
go test ./...

rm -rf /tmp/solve-check
mkdir -p /tmp/solve-check
go build -o /tmp/solve-check/authgw ./cmd/authgw

AUTHGW_DB_PATH=/tmp/solve-check/authgw.db PORT=18080 /tmp/solve-check/authgw &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

for i in $(seq 1 20); do
	if curl -fs http://127.0.0.1:18080/healthz >/dev/null 2>&1; then
		break
	fi
	sleep 0.5
done

# Legitimate admin login must still work.
ADMIN_LOGIN=$(curl -fs -X POST http://127.0.0.1:18080/auth/login \
	-d '{"username":"admin","password":"CorrectHorseBattery9"}')
ADMIN_TOKEN=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['token'])" "$ADMIN_LOGIN")
ADMIN_STATUS=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18080/admin/users \
	-H "Authorization: Bearer $ADMIN_TOKEN")
if [ "$ADMIN_STATUS" != "200" ]; then
	echo "legitimate admin login broke after the fix (status $ADMIN_STATUS)" >&2
	exit 1
fi

# A token forged with the authgw-signd helper's recovered key must now be
# rejected, whether or not the fixed code still shells out to it.
FORGED_STATUS=$(python3 <<'PYEOF'
import base64, hashlib, hmac, json, time, urllib.request, urllib.error

def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

recovered_key = b"authgw-signd-secret-4Kp9XvQ7RtmZs2"
header = {"alg": "HS256", "typ": "JWT"}
now = int(time.time())
payload = {"uid": 1, "username": "admin", "role": "admin", "iss": "authgw", "exp": now + 3600, "iat": now}
signing_input = b64url(json.dumps(header, separators=(",", ":")).encode()) + "." + \
    b64url(json.dumps(payload, separators=(",", ":")).encode())
sig = hmac.new(recovered_key, signing_input.encode(), hashlib.sha256).digest()
token = f"{signing_input}.{b64url(sig)}"

req = urllib.request.Request("http://127.0.0.1:18080/admin/users", headers={"Authorization": f"Bearer {token}"})
try:
    urllib.request.urlopen(req)
    print(200)
except urllib.error.HTTPError as exc:
    print(exc.code)
PYEOF
)
if [ "$FORGED_STATUS" = "200" ]; then
	echo "a token forged with the recovered authgw-signd key was still accepted after the fix" >&2
	exit 1
fi

# The SQL-injection remember-token attack must now be rejected.
INJECT_STATUS=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18080/admin/users \
	-H "Cookie: remember_token=x'/**/union/**/select/**/id,'admin'/**/from/**/users/**/where/**/username='admin")
if [ "$INJECT_STATUS" = "200" ]; then
	echo "SQL-injection remember-token attack still succeeded after the fix" >&2
	exit 1
fi

echo "fix verified: legitimate admin access works, both attacks are rejected"
