"""Independent reference implementation of the Acme wallet presentation profile.

Everything the broker has to produce is recomputed here from the same public specifications
(SD-JWT, RFC 7515/7518/7638) so the tests never compare against a stored answer. The module also
mints fresh credentials, which lets every test drive the tool with inputs it has never seen.
"""

import base64
import hashlib
import itertools
import json
import os
import random
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa, utils

JAR = "/app/broker/target/sd-jwt-broker.jar"
KEY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "issuer-keys")
ISSUER_JWKS = "/app/broker/issuer-jwks.json"


# --------------------------------------------------------------------------------------- encoding


def b64u(raw):
    """Unpadded base64url of the given bytes."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64u_decode(text):
    """Decode an unpadded base64url string."""
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def uint(value, width):
    """Fixed-width big-endian encoding of a non-negative integer."""
    return value.to_bytes(width, "big")


def canonical(value):
    """The profile's canonical JSON: sorted members, no padding, literal non-ASCII."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# ------------------------------------------------------------------------------------------- keys


class SigningKey:
    """An issuer or holder key, either freshly generated or loaded from a PEM file."""

    def __init__(self, kid, kty="EC", alg=None, use=None, pem=None):
        self.kid = kid
        self.kty = kty
        self.alg = alg or ("RS256" if kty == "RSA" else "ES256")
        self.use = use
        if pem is not None:
            with open(pem, "rb") as handle:
                self.private = serialization.load_pem_private_key(handle.read(), password=None)
        elif kty == "RSA":
            self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        else:
            self.private = ec.generate_private_key(ec.SECP256R1())
        self.public = self.private.public_key()

    def jwk(self, include_alg=True):
        """The public JWK the issuer publishes."""
        if self.kty == "RSA":
            numbers = self.public.public_numbers()
            entry = {
                "kty": "RSA",
                "n": b64u(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
                "e": b64u(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
            }
        else:
            numbers = self.public.public_numbers()
            entry = {
                "kty": "EC",
                "crv": "P-256",
                "x": b64u(uint(numbers.x, 32)),
                "y": b64u(uint(numbers.y, 32)),
            }
        entry["kid"] = self.kid
        if include_alg:
            entry["alg"] = self.alg
        if self.use:
            entry["use"] = self.use
        return entry

    def private_jwk(self):
        """The holder's private JWK, as stored in the wallet."""
        entry = self.jwk()
        if self.kty == "EC":
            entry["d"] = b64u(uint(self.private.private_numbers().private_value, 32))
        else:
            entry["d"] = b64u(
                uint(
                    self.private.private_numbers().d,
                    (self.private.private_numbers().d.bit_length() + 7) // 8,
                )
            )
        return entry

    def thumbprint(self):
        """RFC 7638 thumbprint of the public key."""
        entry = self.jwk()
        if self.kty == "RSA":
            members = {"e": entry["e"], "kty": "RSA", "n": entry["n"]}
        else:
            members = {"crv": "P-256", "kty": "EC", "x": entry["x"], "y": entry["y"]}
        return b64u(hashlib.sha256(canonical(members)).digest())

    def sign(self, signing_input, alg=None):
        """Raw JWS signature bytes for the given signing input."""
        alg = alg or self.alg
        if alg == "RS256":
            return self.private.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        if alg == "ES256":
            der = self.private.sign(signing_input, ec.ECDSA(hashes.SHA256()))
            r, s = utils.decode_dss_signature(der)
            return uint(r, 32) + uint(s, 32)
        raise ValueError("unsupported alg " + alg)


def published_key_set():
    """The issuer key set shipped with the environment, as the broker will read it."""
    with open(ISSUER_JWKS) as handle:
        return json.load(handle)


def tck_keys():
    """The two MicroProfile TCK signing keys whose public halves the issuer publishes."""
    return {
        "rskey": SigningKey("rskey", "RSA", alg="RS256", use="sig", pem=os.path.join(KEY_DIR, "privateKey4k.pem")),
        "eckey": SigningKey("eckey", "EC", alg="ES256", use="sig", pem=os.path.join(KEY_DIR, "ecPrivateKey.pem")),
    }


def jws(key, payload, alg=None, kid=True, typ=None, extra_header=None):
    """A compact JWS over the given payload."""
    header = {"alg": alg or key.alg}
    if typ:
        header["typ"] = typ
    if kid:
        header["kid"] = key.kid
    if extra_header:
        header.update(extra_header)
    head = b64u(canonical(header))
    body = b64u(canonical(payload))
    signing_input = (head + "." + body).encode("ascii")
    return head + "." + body + "." + b64u(key.sign(signing_input, alg or key.alg))


# ------------------------------------------------------------------------------------- disclosures


SPACING = {"spaced": (", ", ": "), "compact": (",", ":")}


def disclosure(parts, spacing="spaced"):
    """A disclosure as the issuer wrote it; the layout of the JSON is the issuer's choice."""
    text = json.dumps(parts, separators=SPACING[spacing])
    return b64u(text.encode("utf-8"))


def digest(disclosure_text):
    """The SD-JWT digest of a disclosure, taken over its base64url characters."""
    return b64u(hashlib.sha256(disclosure_text.encode("ascii")).digest())


class Issued:
    """One issued credential: the signed JWT, its disclosures and the reference resolution of it."""

    def __init__(self, jwt, disclosures, paths, parents, resolved):
        self.jwt = jwt
        self.disclosures = disclosures
        self.paths = paths
        self.parents = parents
        self.resolved = resolved

    def issuance(self, withheld=()):
        """The issuance form the wallet stores, optionally without disclosures it never received."""
        held = [text for text in self.disclosures if self.paths[digest(text)] not in withheld]
        return self.jwt + "~" + "".join(text + "~" for text in held)


def join_path(prefix, name):
    """Extend a claim path with an object member name."""
    return name if not prefix else prefix + "." + name


class _Issuer:
    """Rewrites a plain claim set into the selectively disclosable form the issuer signs."""

    def __init__(self, sd_paths, decoys, seed, spacing):
        self.sd_paths = set(sd_paths)
        self.decoys = decoys
        self.spacing = spacing
        self.random = random.Random(seed)
        self.disclosures = []
        self.paths = {}
        self.parents = {}

    def salt(self):
        """A fresh 128-bit salt."""
        return b64u(bytes(self.random.getrandbits(8) for _ in range(16)))

    def decoy(self):
        """A digest of a disclosure the holder was never given."""
        return b64u(hashlib.sha256(bytes(self.random.getrandbits(8) for _ in range(32))).digest())

    def build(self, value, path, parent):
        """Return the issuer-side form of a value at the given claim path."""
        if isinstance(value, dict):
            members = {}
            hidden = []
            for name in value:
                child = join_path(path, name)
                if child in self.sd_paths:
                    text = disclosure(
                        [self.salt(), name, self.build(value[name], child, child)], self.spacing
                    )
                    self.disclosures.append(text)
                    self.paths[digest(text)] = child
                    self.parents[child] = parent
                    hidden.append(digest(text))
                else:
                    members[name] = self.build(value[name], child, parent)
            for _ in range(self.decoys if hidden else 0):
                hidden.append(self.decoy())
            if hidden:
                members["_sd"] = sorted(hidden)
            return members
        if isinstance(value, list):
            elements = []
            for index, element in enumerate(value):
                child = f"{path}[{index}]"
                if child in self.sd_paths:
                    text = disclosure([self.salt(), self.build(element, child, child)], self.spacing)
                    self.disclosures.append(text)
                    self.paths[digest(text)] = child
                    self.parents[child] = parent
                    elements.append({"...": digest(text)})
                else:
                    elements.append(self.build(element, child, parent))
            return elements
        return value


def issue(
    key,
    claims,
    sd_paths=(),
    decoys=0,
    seed=7,
    alg=None,
    kid=True,
    header=None,
    sd_alg="sha-256",
    spacing="spaced",
):
    """Mint a credential whose named claim paths are selectively disclosable."""
    issuer = _Issuer(sd_paths, decoys, seed, spacing)
    payload = issuer.build(dict(claims), "", None)
    if sd_alg is not None:
        payload["_sd_alg"] = sd_alg
    jwt = jws(key, payload, alg=alg, kid=kid, extra_header=header)
    return Issued(jwt, issuer.disclosures, issuer.paths, issuer.parents, json.loads(json.dumps(claims)))


# ------------------------------------------------------------------------------------- resolution


class Rejected(Exception):
    """Raised with the profile status when a credential cannot be accepted."""

    def __init__(self, status):
        super().__init__(status)
        self.status = status


def _is_placeholder(value):
    """True for an array element that stands in for an undisclosed value."""
    return isinstance(value, dict) and list(value) == ["..."] and isinstance(value["..."], str)


class _Resolver:
    """Applies disclosures to an issuer-signed payload, recording where each one landed."""

    def __init__(self, by_digest):
        self.by_digest = by_digest
        self.seen = set()
        self.used = {}
        self.paths = {}
        self.parents = {}

    def take(self, value, path, parent):
        """Record one digest occurrence and return its disclosure, if the holder has it."""
        if value in self.seen:
            raise Rejected("invalid_disclosure")
        self.seen.add(value)
        parts = self.by_digest.get(value)
        if parts is None:
            return None
        self.used[value] = path
        self.paths[path] = value
        self.parents[path] = parent
        return parts

    def walk(self, value, path, parent):
        """Return the resolved form of a value at the given claim path."""
        if isinstance(value, dict):
            members = {}
            for name, member in value.items():
                if name == "_sd" or (path == "" and name == "_sd_alg"):
                    continue
                if name == "...":
                    raise Rejected("invalid_disclosure")
                members[name] = self.walk(member, join_path(path, name), parent)
            hidden = value.get("_sd", [])
            if not isinstance(hidden, list) or any(not isinstance(item, str) for item in hidden):
                raise Rejected("invalid_disclosure")
            for item in hidden:
                child = join_path(path, "?")
                parts = self.take(item, child, parent)
                if parts is None:
                    continue
                if len(parts) != 3 or not isinstance(parts[1], str):
                    raise Rejected("invalid_disclosure")
                name = parts[1]
                if name in ("_sd", "...") or name in members:
                    raise Rejected("invalid_disclosure")
                real = join_path(path, name)
                self.paths[real] = self.paths.pop(child)
                self.parents[real] = self.parents.pop(child)
                self.used[item] = real
                members[name] = self.walk(parts[2], real, real)
            return members
        if isinstance(value, list):
            elements = []
            for element in value:
                child = f"{path}[{len(elements)}]"
                if _is_placeholder(element):
                    parts = self.take(element["..."], child, parent)
                    if parts is None:
                        continue
                    if len(parts) != 2:
                        raise Rejected("invalid_disclosure")
                    elements.append(self.walk(parts[1], child, child))
                else:
                    elements.append(self.walk(element, child, parent))
            return elements
        return value


def resolve(payload, parsed):
    """Resolve every disclosure into the payload, or reject the credential."""
    by_digest = {}
    for text, parts in parsed.items():
        if digest(text) in by_digest:
            raise Rejected("invalid_disclosure")
        by_digest[digest(text)] = parts
    resolver = _Resolver(by_digest)
    resolved = resolver.walk(payload, "", None)
    if len(resolver.used) != len(by_digest):
        raise Rejected("invalid_disclosure")
    return resolved, resolver.paths, resolver.parents


# ---------------------------------------------------------------------------------------- selection


def split_path(path):
    """Split a claim path into its member names and array indices."""
    parts = []
    token = ""
    index = 0
    while index < len(path):
        char = path[index]
        if char == ".":
            parts.append(token)
            token = ""
        elif char == "[":
            if token:
                parts.append(token)
                token = ""
            close = path.index("]", index)
            parts.append(int(path[index + 1 : close]))
            index = close
        else:
            token += char
        index += 1
    if token:
        parts.append(token)
    return parts


def lookup(resolved, path):
    """The value at a claim path, or None when the path is absent."""
    current = resolved
    for part in split_path(path):
        if isinstance(part, int):
            if not isinstance(current, list) or part >= len(current):
                return None
            current = current[part]
        else:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
    return current


def ancestors(path):
    """Every claim path that contains the given one, itself included."""
    out = []
    current = ""
    for part in split_path(path):
        current = f"{current}[{part}]" if isinstance(part, int) else join_path(current, part)
        out.append(current)
    return out


def needed(path, resolved, paths):
    """The disclosures that have to travel for the given claim path to be visible."""
    out = set()
    for step in ancestors(path):
        if step in paths:
            out.add(step)
    value = lookup(resolved, path)
    if isinstance(value, list):
        for index in range(len(value)):
            element = f"{path}[{index}]"
            if element in paths:
                out.add(element)
    return out


def select(resolved, paths, policy):
    """The smallest disclosure set satisfying the policy, or the paths that make it impossible."""
    required = list(policy.get("required", []))
    groups = [list(group) for group in policy.get("alternatives", [])]
    missing = [path for path in required if lookup(resolved, path) is None]
    for group in groups:
        if all(lookup(resolved, option) is None for option in group):
            missing.extend(group)
    if missing:
        return None, sorted(set(missing))
    base = set()
    for path in required:
        base |= needed(path, resolved, paths)
    best = None
    for combo in itertools.product(*[range(len(group)) for group in groups]):
        chosen = set(base)
        possible = True
        for position, option in enumerate(combo):
            path = groups[position][option]
            if lookup(resolved, path) is None:
                possible = False
                break
            chosen |= needed(path, resolved, paths)
        if not possible:
            continue
        key = (len(chosen), combo)
        if best is None or key < best[0]:
            best = (key, chosen)
    return best[1], []


# ------------------------------------------------------------------------------------- evaluation

SIGNATURE_ALGS = ("RS256", "ES256")


def usable_keys(jwks):
    """The subset of a published JWK Set this profile verifies signatures with."""
    out = {}
    for entry in jwks.get("keys", []):
        if not isinstance(entry.get("kid"), str) or entry.get("use") == "enc":
            continue
        if entry.get("alg") is not None and entry["alg"] not in SIGNATURE_ALGS:
            continue
        rsa_key = entry.get("kty") == "RSA" and "n" in entry and "e" in entry
        ec_key = entry.get("kty") == "EC" and entry.get("crv") == "P-256"
        if rsa_key or ec_key:
            out[entry["kid"]] = entry
    return out


def candidates(keys, alg):
    """The published keys that can serve the given signature algorithm."""
    kty = "RSA" if alg == "RS256" else "EC"
    return {kid: entry for kid, entry in keys.items() if entry["kty"] == kty and entry.get("alg", alg) == alg}


def thumbprint_of(entry):
    """RFC 7638 thumbprint of a published JWK."""
    if entry["kty"] == "RSA":
        members = {"e": entry["e"], "kty": "RSA", "n": entry["n"]}
    else:
        members = {"crv": entry["crv"], "kty": "EC", "x": entry["x"], "y": entry["y"]}
    return b64u(hashlib.sha256(canonical(members)).digest())


def public_key_of(entry):
    """A cryptography public key built from a published JWK."""
    if entry["kty"] == "RSA":
        numbers = rsa.RSAPublicNumbers(
            int.from_bytes(b64u_decode(entry["e"]), "big"), int.from_bytes(b64u_decode(entry["n"]), "big")
        )
        return numbers.public_key()
    numbers = ec.EllipticCurvePublicNumbers(
        int.from_bytes(b64u_decode(entry["x"]), "big"),
        int.from_bytes(b64u_decode(entry["y"]), "big"),
        ec.SECP256R1(),
    )
    return numbers.public_key()


def verify_signature(token, entry, alg):
    """True when the compact JWS verifies under the published key."""
    head, body, signature = token.split(".")
    signing_input = (head + "." + body).encode("ascii")
    key = public_key_of(entry)
    try:
        if alg == "RS256":
            key.verify(b64u_decode(signature), signing_input, padding.PKCS1v15(), hashes.SHA256())
        else:
            raw = b64u_decode(signature)
            if len(raw) != 64:
                return False
            der = utils.encode_dss_signature(
                int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")
            )
            key.verify(der, signing_input, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


ALPHABET = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


def is_b64u(text):
    """True when a segment is non-empty unpadded base64url."""
    return bool(text) and all(char in ALPHABET for char in text)


def json_object(segment):
    """Decode a base64url segment that has to hold a JSON object."""
    value = json.loads(b64u_decode(segment))
    if not isinstance(value, dict):
        raise Rejected("malformed")
    return value


def name_of(resolved):
    """The principal name, following the MicroProfile JsonWebToken contract."""
    for claim in ("upn", "preferred_username", "sub"):
        if isinstance(resolved.get(claim), str):
            return resolved[claim]
    return None


def by_bytes(values):
    """Sort strings by their UTF-8 bytes."""
    return sorted(values, key=lambda item: item.encode("utf-8"))


def evaluate(text, keys, policy, config):
    """The report entry and presentation for one stored credential."""
    try:
        return _evaluate(text, keys, policy, config)
    except Rejected as failure:
        return {"status": failure.status}, None


def _evaluate(text, keys, policy, config):
    """Run the acceptance ladder over one credential."""
    if not text.endswith("~"):
        raise Rejected("malformed")
    segments = text[:-1].split("~")
    jwt = segments[0]
    disclosures = segments[1:]
    if jwt.count(".") != 2 or any(not is_b64u(part) for part in jwt.split(".")):
        raise Rejected("malformed")
    if any(not is_b64u(part) for part in disclosures):
        raise Rejected("malformed")
    try:
        header = json_object(jwt.split(".")[0])
        payload = json_object(jwt.split(".")[1])
    except Rejected:
        raise
    except (ValueError, TypeError) as broken:
        raise Rejected("malformed") from broken
    parsed = {}
    for item in disclosures:
        try:
            parts = json.loads(b64u_decode(item))
        except (ValueError, TypeError) as broken:
            raise Rejected("malformed") from broken
        if not isinstance(parts, list) or len(parts) not in (2, 3) or not isinstance(parts[0], str):
            raise Rejected("malformed")
        if len(parts) == 3 and not isinstance(parts[1], str):
            raise Rejected("malformed")
        parsed[item] = parts
    if header.get("alg") not in SIGNATURE_ALGS or "crit" in header:
        raise Rejected("unsupported_algorithm")
    if payload.get("_sd_alg", "sha-256") != "sha-256":
        raise Rejected("unsupported_algorithm")
    usable = candidates(keys, header["alg"])
    kid = header.get("kid")
    if kid is None:
        entry = next(iter(usable.values())) if len(usable) == 1 else None
    else:
        entry = usable.get(kid)
    if entry is None:
        raise Rejected("unknown_key")
    if not verify_signature(jwt, entry, header["alg"]):
        raise Rejected("bad_signature")
    resolved, paths, _ = resolve(payload, parsed)
    if not isinstance(resolved.get("iss"), str):
        raise Rejected("missing_claim")
    for claim in ("iat", "exp"):
        if not isinstance(resolved.get(claim), int) or isinstance(resolved.get(claim), bool):
            raise Rejected("missing_claim")
    if name_of(resolved) is None:
        raise Rejected("missing_claim")
    holder = resolved.get("cnf")
    if not isinstance(holder, dict) or not isinstance(holder.get("jwk"), dict):
        raise Rejected("missing_claim")
    if resolved["iss"] != config["issuer"]:
        raise Rejected("invalid_issuer")
    if resolved["exp"] <= config["instant"]:
        raise Rejected("expired")
    chosen, missing = select(resolved, paths, policy)
    if missing:
        return {"status": "insufficient", "missing": by_bytes(missing)}, None
    by_text = {digest(item): item for item in disclosures}
    selected = by_bytes([by_text[paths[path]] for path in chosen])
    prefix = jwt + "~" + "".join(item + "~" for item in selected)
    sd_hash = b64u(hashlib.sha256(prefix.encode("ascii")).digest())
    entry_out = {
        "status": "presented",
        "alg": header["alg"],
        "kid": entry["kid"],
        "name": name_of(resolved),
        "groups": by_bytes(resolved.get("groups", [])),
        "disclosed": by_bytes(chosen),
        "sd_hash": sd_hash,
    }
    return entry_out, (prefix, sd_hash, holder["jwk"])


def expected_report(credentials, jwks, jwks_uri, policy, config):
    """The whole report the broker must write for a batch of credentials."""
    keys = usable_keys(jwks)
    entries = []
    presentations = {}
    for name in sorted(credentials, key=lambda item: item.encode("utf-8")):
        entry, presented = evaluate(credentials[name], keys, policy, config)
        entry["id"] = name
        entries.append(entry)
        if presented:
            presentations[name] = presented
    published = [{"kid": entry["kid"], "thumbprint": thumbprint_of(entry)} for entry in keys.values()]
    report = {
        "jwks_uri": jwks_uri,
        "keys": sorted(published, key=lambda item: item["kid"].encode("utf-8")),
        "credentials": entries,
    }
    return report, presentations


# ------------------------------------------------------------------------------------ test harness


class JwksServer:
    """A local stand-in for the issuer's published key set."""

    def __init__(self, jwks):
        self.body = canonical(jwks)
        self.hits = 0
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                server.hits += 1
                self.send_response(200)
                self.send_header("Content-Type", "application/jwk-set+json")
                self.send_header("Content-Length", str(len(server.body)))
                self.end_headers()
                self.wfile.write(server.body)

            def log_message(self, *args):
                pass

        self.http = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.http.server_address[1]}/jwks.json"

    def __enter__(self):
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.http.shutdown()
        self.http.server_close()


DEFAULT_CONFIG = {
    "issuer": "https://issuer.acme.example",
    "audience": "https://verifier.partner.example/present",
    "nonce": "n-0S6_WzA2Mj",
    "instant": 1770000000,
}


def write_inputs(directory, credentials, policy, config, jwks_uri, holder):
    """Lay out a run directory the way the broker expects to find one."""
    os.makedirs(os.path.join(directory, "credentials"), exist_ok=True)
    for name, text in credentials.items():
        with open(os.path.join(directory, "credentials", name + ".sdjwt"), "w") as handle:
            handle.write(text + "\n")
    with open(os.path.join(directory, "policy.json"), "w") as handle:
        handle.write(canonical(policy).decode("utf-8"))
    with open(os.path.join(directory, "holder.jwk"), "w") as handle:
        handle.write(canonical(holder.private_jwk()).decode("utf-8"))
    lines = [
        "mp.jwt.verify.publickey.location=" + jwks_uri,
        "mp.jwt.verify.issuer=" + config["issuer"],
        "wallet.audience=" + config["audience"],
        "wallet.nonce=" + config["nonce"],
        "wallet.instant=" + str(config["instant"]),
        "wallet.holder.key=" + os.path.join(directory, "holder.jwk"),
    ]
    path = os.path.join(directory, "wallet.properties")
    with open(path, "w") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


def run_broker(directory, credentials, policy, jwks_uri, holder, config=None):
    """Run the packaged broker over a freshly written run directory."""
    config = config or DEFAULT_CONFIG
    properties = write_inputs(directory, credentials, policy, config, jwks_uri, holder)
    out = os.path.join(directory, "out")
    process = subprocess.run(
        [
            "java",
            "-jar",
            JAR,
            "--config",
            properties,
            "--credentials",
            os.path.join(directory, "credentials"),
            "--policy",
            os.path.join(directory, "policy.json"),
            "--out",
            out,
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    report = None
    report_path = os.path.join(out, "report.json")
    if os.path.isfile(report_path):
        with open(report_path, "rb") as handle:
            report = handle.read()
    return process, report, out


def read_presentation(out, name):
    """The presentation the broker wrote for one credential."""
    path = os.path.join(out, "presentations", name + ".sdjwt")
    if not os.path.isfile(path):
        return None
    with open(path) as handle:
        return handle.read().strip()


def check_key_binding(presentation, expected_prefix, holder_jwk, config):
    """Verify the key binding JWT a presentation carries, returning its payload."""
    marker = presentation.rindex("~")
    prefix = presentation[: marker + 1]
    kb = presentation[marker + 1 :]
    assert prefix == expected_prefix, "presented prefix differs from the reference selection"
    header = json_object(kb.split(".")[0])
    assert header.get("typ") == "kb+jwt", "key binding JWT must carry typ kb+jwt"
    assert header.get("alg") == "ES256", "key binding JWT must be signed with ES256"
    assert verify_signature(kb, holder_jwk, "ES256"), "key binding signature does not verify"
    payload = json_object(kb.split(".")[1])
    assert payload.get("aud") == config["audience"]
    assert payload.get("nonce") == config["nonce"]
    assert payload.get("iat") == config["instant"]
    assert payload.get("sd_hash") == b64u(hashlib.sha256(prefix.encode("ascii")).digest())
    return payload
