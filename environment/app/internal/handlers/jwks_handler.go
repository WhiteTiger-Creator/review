package handlers

import (
	"crypto/rsa"
	"encoding/base64"
	"net/http"
)

// b64url is base64url encoding without padding, as required by RFC 7518
// for JWK "n"/"e" members.
func b64url(b []byte) string {
	return base64.RawURLEncoding.EncodeToString(b)
}

// JWKS publishes the RSA public key used for RS256 service tokens so
// downstream integrations can verify them independently.
func (s *Server) JWKS(w http.ResponseWriter, r *http.Request) {
	pub := s.Keys.RSAPriv.Public().(*rsa.PublicKey)
	nBytes := pub.N.Bytes()
	eBytes := []byte{byte(pub.E >> 16), byte(pub.E >> 8), byte(pub.E)}
	for len(eBytes) > 1 && eBytes[0] == 0 {
		eBytes = eBytes[1:]
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"keys": []map[string]string{
			{
				"kty": "RSA",
				"use": "sig",
				"alg": "RS256",
				"kid": "authgw-service-key",
				"n":   b64url(nBytes),
				"e":   b64url(eBytes),
			},
		},
	})
}
