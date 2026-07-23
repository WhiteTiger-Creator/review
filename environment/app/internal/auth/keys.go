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

// Keys holds the RSA keypair used for internal service tokens (see
// /admin/service-tokens and /.well-known/jwks.json) and this process's
// instance identifier (surfaced at /healthz so operators can tell which
// replica answered a given request). Session tokens are signed via the
// authgw-signd helper (see internal/auth/jwt.go).
type Keys struct {
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

	return &Keys{RSAPriv: priv, InstanceID: hex.EncodeToString(idBytes)}, nil
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
