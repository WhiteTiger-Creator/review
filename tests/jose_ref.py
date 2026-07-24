"""Reference JOSE fixtures for the JWE unsealer task.

Seals fresh ECDH-1PU JWE messages on every run and recomputes the expected report and transcript
digest from the same public specifications the tool has to follow, so a stored answer cannot pass.
Sender static keys are served from a local counting registry; one test resolves a real key over the
network. This module is mounted with the tests at verify time and is never part of the task image.
"""

import base64
import hashlib
import json
import os
import struct
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.keywrap import aes_key_wrap

JAR = "/app/unsealer/target/jwe-unsealer.jar"
CURVE = ec.SECP256R1()
ALG = "ECDH-1PU+A256KW"
ENC = "A256GCM"


def b64u(raw):
    """Base64url without padding, the only encoding JOSE uses."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64ud(value):
    if isinstance(value, str):
        value = value.encode("ascii")
    return base64.urlsafe_b64decode(value + b"=" * (-len(value) % 4))


def i2osp(value, length):
    return value.to_bytes(length, "big")


def canonical(obj):
    """Sorted-key, compact, ASCII-safe JSON: the exact bytes the report is compared against."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def thumbprint(jwk):
    """RFC 7638 SHA-256 thumbprint of a P-256 key: required members only, ordered, no whitespace."""
    required = {"crv": jwk["crv"], "kty": "EC", "x": jwk["x"], "y": jwk["y"]}
    return b64u(hashlib.sha256(canonical(required)).digest())


class EcKey:
    """A freshly generated P-256 key plus the public and private JWKs the task exchanges."""

    def __init__(self, kid):
        self.kid = kid
        self.private = ec.generate_private_key(CURVE)
        self.public = self.private.public_key()

    def public_jwk(self, kid=True):
        numbers = self.public.public_numbers()
        jwk = {"kty": "EC", "crv": "P-256", "x": b64u(i2osp(numbers.x, 32)), "y": b64u(i2osp(numbers.y, 32))}
        if kid:
            jwk["kid"] = self.kid
        return jwk

    def private_jwk(self):
        jwk = self.public_jwk()
        jwk["d"] = b64u(i2osp(self.private.private_numbers().private_value, 32))
        return jwk

    def thumbprint(self):
        return thumbprint(self.public_jwk(kid=False))


def jwk_to_public(jwk):
    x = int.from_bytes(b64ud(jwk["x"]), "big")
    y = int.from_bytes(b64ud(jwk["y"]), "big")
    return ec.EllipticCurvePublicNumbers(x, y, CURVE).public_key()


def concat_kdf(z, algorithm_id, apu, apv, key_bits):
    """NIST SP 800-56A Concat KDF with SHA-256, one repetition for a 256-bit key."""
    def prefixed(data):
        return struct.pack(">I", len(data)) + data

    other = prefixed(algorithm_id.encode("ascii")) + prefixed(apu) + prefixed(apv) + struct.pack(">I", key_bits)
    return hashlib.sha256(struct.pack(">I", 1) + z + other).digest()[: key_bits // 8]


def claims(**overrides):
    """A representative decrypted payload; pass None to drop a claim."""
    payload = {"iss": "did:example:alice", "sub": "24400320", "upn": "alice@acme.example",
               "groups": ["staff", "admin"]}
    payload.update(overrides)
    return {name: value for name, value in payload.items() if value is not None}


def principal(payload):
    """The reported name (upn, then preferred_username, then sub), sub, and byte-sorted groups."""
    name = None
    for key in ("upn", "preferred_username", "sub"):
        if isinstance(payload.get(key), str):
            name = payload[key]
            break
    sub = payload["sub"] if isinstance(payload.get("sub"), str) else None
    groups = sorted([g for g in payload.get("groups", []) if isinstance(g, str)], key=lambda s: s.encode("utf-8"))
    return name, sub, groups


def seal(kind, recipients, sender, plaintext, apu=b"", apv=b"", aad=None, alg=ALG, enc=ENC,
         skid=None, drop_skid=False, epk=None, bad_epk_crv=False, tamper_tag=False, corrupt_ek=False):
    """Seals an ECDH-1PU JWE. recipients receive under their public keys; sender is the static key.

    kind is 'compact', 'flattened' or 'general'. Returns the compact string or the JSON object.
    """
    if epk is None:
        epk = EcKey("epk")
    protected = {"alg": alg, "enc": enc}
    if apu:
        protected["apu"] = b64u(apu)
    if apv:
        protected["apv"] = b64u(apv)
    if not drop_skid:
        protected["skid"] = skid if skid is not None else sender.kid
    epk_jwk = epk.public_jwk(kid=False)
    if bad_epk_crv:
        epk_jwk["crv"] = "P-384"
    protected["epk"] = epk_jwk
    if kind == "compact":
        protected["kid"] = recipients[0].kid

    protected_b64 = b64u(canonical(protected))
    cek = os.urandom(32)
    iv = os.urandom(12)
    aad_bytes = protected_b64.encode("ascii") if aad is None else (protected_b64 + "." + b64u(aad)).encode("ascii")
    ct_tag = AESGCM(cek).encrypt(iv, plaintext, aad_bytes)
    ciphertext, tag = ct_tag[:-16], ct_tag[-16:]
    if tamper_tag:
        tag = bytes([tag[0] ^ 0xFF]) + tag[1:]

    entries = []
    for recipient in recipients:
        ze = epk.private.exchange(ec.ECDH(), recipient.public)
        zs = sender.private.exchange(ec.ECDH(), recipient.public)
        kek = concat_kdf(ze + zs, ALG, apu, apv, 256)
        wrapped = aes_key_wrap(kek, cek)
        if corrupt_ek:
            wrapped = bytes([wrapped[0] ^ 0xFF]) + wrapped[1:]
        entries.append((recipient.kid, wrapped))

    if kind == "compact":
        kid, wrapped = entries[0]
        return ".".join([protected_b64, b64u(wrapped), b64u(iv), b64u(ciphertext), b64u(tag)])
    if kind == "flattened":
        kid, wrapped = entries[0]
        obj = {"protected": protected_b64, "header": {"kid": kid}, "encrypted_key": b64u(wrapped),
               "iv": b64u(iv), "ciphertext": b64u(ciphertext), "tag": b64u(tag)}
        if aad is not None:
            obj["aad"] = b64u(aad)
        return obj
    if kind == "general":
        obj = {"protected": protected_b64,
               "recipients": [{"header": {"kid": kid}, "encrypted_key": b64u(wrapped)} for kid, wrapped in entries],
               "iv": b64u(iv), "ciphertext": b64u(ciphertext), "tag": b64u(tag)}
        if aad is not None:
            obj["aad"] = b64u(aad)
        return obj
    raise ValueError(kind)


# ---- expected outcomes -------------------------------------------------------------------------

def unsealed(recipient, sender, payload):
    """The report view of a message the inbox unseals, plus its plaintext for the digest."""
    name, sub, groups = principal(payload)
    result = {"status": "unsealed", "recipient_kid": recipient.kid, "sender_kid": sender.kid,
              "sender_thumbprint": sender.thumbprint(), "name": name, "sub": sub, "groups": groups}
    return result, canonical(payload)


def rejected(status, recipient=None, sender=None):
    """The report view of a message the inbox refuses at some stage of the ladder."""
    result = {"status": status}
    if recipient is not None:
        result["recipient_kid"] = recipient.kid
    if sender is not None:
        result["sender_kid"] = sender.kid
        result["sender_thumbprint"] = sender.thumbprint()
    return result, None


def assemble(items):
    """Turns (jwe, result, plaintext) triples into the message list, expected report and digest."""
    messages, results, stream = [], [], bytearray()
    for index, (jwe, result, plaintext) in enumerate(items):
        messages.append(jwe)
        entry = dict(result)
        entry["index"] = index
        results.append(entry)
        stream += entry["status"].encode("ascii") + b"\n"
        if entry["status"] == "unsealed":
            stream += plaintext + b"\n"
    report = {"results": results}
    return messages, report, hashlib.sha256(bytes(stream)).hexdigest()


# ---- local sender registry ---------------------------------------------------------------------

def _handler_for(registry):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            if self.path != "/jwks":
                self.send_error(404)
                return
            with registry.lock:
                registry.count += 1
            body = json.dumps({"keys": registry.keys}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    return Handler


class Registry:
    """A local sender registry endpoint that counts how many times its key set is fetched."""

    def __init__(self, keys):
        self.keys = keys
        self.count = 0
        self.lock = threading.Lock()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_for(self))
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}/jwks"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def close(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def run_unsealer(workdir, recipient_private_jwks, senders, messages):
    """Runs the built jar and returns (process, raw report bytes, parsed report, digest string)."""
    workdir = str(workdir)
    keys_path = os.path.join(workdir, "keys.json")
    senders_path = os.path.join(workdir, "senders.json")
    messages_path = os.path.join(workdir, "messages.txt")
    report_path = os.path.join(workdir, "report.json")
    digest_path = os.path.join(workdir, "digest.txt")

    with open(keys_path, "w", encoding="utf-8") as handle:
        json.dump({"keys": recipient_private_jwks}, handle)
    with open(senders_path, "w", encoding="utf-8") as handle:
        json.dump({"senders": senders}, handle)
    with open(messages_path, "w", encoding="utf-8") as handle:
        lines = [m if isinstance(m, str) else json.dumps(m) for m in messages]
        handle.write("\n".join(lines) + "\n")

    process = subprocess.run(
        ["java", "-jar", JAR, "--keys", keys_path, "--senders", senders_path,
         "--messages", messages_path, "--out", report_path, "--digest", digest_path],
        capture_output=True, text=True, timeout=180, check=False,
    )

    report_bytes = None
    report = None
    if os.path.exists(report_path):
        with open(report_path, "rb") as handle:
            report_bytes = handle.read()
        if report_bytes.strip():
            report = json.loads(report_bytes)
    digest = None
    if os.path.exists(digest_path):
        with open(digest_path, encoding="utf-8") as handle:
            digest = handle.read().strip()
    return process, report_bytes, report, digest


def statuses(report):
    """The per-message outcome in index order."""
    return [entry["status"] for entry in sorted(report["results"], key=lambda item: item["index"])]
