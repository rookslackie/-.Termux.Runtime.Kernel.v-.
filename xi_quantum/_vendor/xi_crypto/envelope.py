"""Reference envelope: exact bytes, pinned signers, authenticated context."""
import secrets
from dataclasses import dataclass
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from .compat import LEGACY, inspect_glyphsafe
from .wire import (CANONICAL, MAX_PAYLOAD, ProtocolError, b64, canonical, fields,
                   hexbytes, label, parse, sha256, unb64)

PROFILE = "xi.crypto-lattice.envelope.v1"
SUITE = "HKDF-SHA256/ChaCha20Poly1305/Ed25519"
SIGN = b"Xi.CryptoLattice/envelope-signature/v1\x00"
AAD = b"Xi.CryptoLattice/aad/v1\x00"
KDF = b"Xi.CryptoLattice/aead-key/v1\x00"
CONSENT = b"Xi.CryptoLattice/consent-signature/v1\x00"
RECEIPT = b"Xi.CryptoLattice/witness-signature/v1\x00"
VOTE = b"Xi.CryptoLattice/review-signature/v1\x00"
HEAD_FIELDS = {"profile", "suite", "canonical", "message_id", "salt_b64", "nonce_b64",
               "signer_public_key_hex", "sequence", "scope", "audience"}


def public_bytes(key):
    return key.public_key().public_bytes(serialization.Encoding.Raw,
                                         serialization.PublicFormat.Raw)


def key_id(public):
    if type(public) is not bytes or len(public) != 32:
        raise ProtocolError("Expected a 32-byte public key")
    return sha256(b"Xi.CryptoLattice/key-id/v1\x00" + public)


def sign_record(body, key, domain):
    unsigned = {"body": body, "public_key_hex": public_bytes(key).hex()}
    return {**unsigned, "signature_hex": key.sign(domain + canonical(unsigned)).hex()}


def verify_record(record, domain, trusted_keys=None):
    # Consume the same immutable snapshot that was verified, even if caller data changes.
    record = parse(canonical(record))
    fields(record, {"body", "public_key_hex", "signature_hex"})
    pub = hexbytes(record["public_key_hex"])
    if trusted_keys is not None and pub not in trusted_keys:
        raise ProtocolError("Untrusted record signer")
    unsigned = {"body": record["body"], "public_key_hex": record["public_key_hex"]}
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(hexbytes(record["signature_hex"], 64),
                                                     domain + canonical(unsigned))
    except InvalidSignature as exc:
        raise ProtocolError("Invalid record signature") from exc
    return record["body"], pub


@dataclass(frozen=True)
class Policy:
    scope: str
    audience: str
    signer_keys: frozenset
    consent_keys: frozenset

    def __post_init__(self):
        label(self.scope)
        label(self.audience)
        for keys in (self.signer_keys, self.consent_keys):
            if type(keys) is not frozenset or not keys or any(type(k) is not bytes or len(k) != 32 for k in keys):
                raise ProtocolError("Policy requires nonempty pinned public-key sets")


def _head(header):
    fields(header, HEAD_FIELDS)
    if header["profile"] != PROFILE or header["suite"] != SUITE or header["canonical"] != CANONICAL:
        raise ProtocolError("Unsupported envelope profile, suite or canonicalization")
    label(header["scope"])
    label(header["audience"])
    hexbytes(header["message_id"])
    hexbytes(header["signer_public_key_hex"])
    unb64(header["salt_b64"], size=32)
    unb64(header["nonce_b64"], size=12)
    if type(header["sequence"]) is not int or not 0 <= header["sequence"] <= 9007199254740991:
        raise ProtocolError("Invalid sequence")


def derive_key(master_key, header):
    if type(master_key) is not bytes or len(master_key) != 32:
        raise ProtocolError("Expected a random 32-byte master key; passwords need a separate profile")
    return HKDF(algorithm=hashes.SHA256(), length=32,
                salt=unb64(header["salt_b64"], size=32),
                info=KDF + canonical(header)).derive(master_key)


def seal(payload, master_key, signing_key, *, scope, audience, sequence,
         origin_format="opaque", metadata=None):
    if type(payload) is not bytes or len(payload) > MAX_PAYLOAD:
        raise ProtocolError("Expected original bytes of at most 1 MiB")
    if origin_format not in ("opaque", LEGACY, "xi.capsule.v1"):
        raise ProtocolError("Unsupported origin; use opaque preservation")
    if metadata is None:
        metadata = {}
    if type(metadata) is not dict:
        raise ProtocolError("Metadata must be an object")
    header = {"profile": PROFILE, "suite": SUITE, "canonical": CANONICAL,
              "message_id": secrets.token_bytes(32).hex(), "salt_b64": b64(secrets.token_bytes(32)),
              "nonce_b64": b64(secrets.token_bytes(12)), "signer_public_key_hex": public_bytes(signing_key).hex(),
              "sequence": sequence, "scope": scope, "audience": audience}
    _head(header)
    inner = {"payload_b64": b64(payload), "payload_sha256": sha256(payload),
             "origin_format": origin_format, "metadata": metadata}
    cipher = ChaCha20Poly1305(derive_key(master_key, header)).encrypt(
        unb64(header["nonce_b64"], size=12), canonical(inner), AAD + canonical(header))
    unsigned = {"protected": header, "ciphertext_b64": b64(cipher)}
    return canonical({**unsigned, "signature_b64": b64(signing_key.sign(SIGN + canonical(unsigned)))})


@dataclass(frozen=True)
class Restored:
    payload: bytes
    metadata: dict
    origin_format: str
    header: dict
    envelope_sha256: str
    legacy: dict | None


def verify_and_open(wire, master_key, policy):
    """Read-only restoration. Stateful replay/consent enforcement lives in ledger.accept."""
    envelope = parse(wire)
    fields(envelope, {"protected", "ciphertext_b64", "signature_b64"})
    header = envelope["protected"]
    _head(header)
    if header["scope"] != policy.scope or header["audience"] != policy.audience:
        raise ProtocolError("Scope or audience mismatch")
    pub = hexbytes(header["signer_public_key_hex"])
    if pub not in policy.signer_keys:
        raise ProtocolError("Untrusted envelope signer")
    unsigned = {"protected": header, "ciphertext_b64": envelope["ciphertext_b64"]}
    ciphertext = unb64(envelope["ciphertext_b64"])
    if len(ciphertext) < 16:
        raise ProtocolError("Missing authentication tag")
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(unb64(envelope["signature_b64"], size=64),
                                                     SIGN + canonical(unsigned))
    except InvalidSignature as exc:
        raise ProtocolError("Invalid envelope signature") from exc
    try:
        plaintext = ChaCha20Poly1305(derive_key(master_key, header)).decrypt(
            unb64(header["nonce_b64"], size=12), ciphertext, AAD + canonical(header))
    except InvalidTag as exc:
        raise ProtocolError("Ciphertext authentication failed") from exc
    inner = parse(plaintext)
    fields(inner, {"payload_b64", "payload_sha256", "origin_format", "metadata"})
    payload = unb64(inner["payload_b64"], limit=MAX_PAYLOAD)
    hexbytes(inner["payload_sha256"])
    if sha256(payload) != inner["payload_sha256"]:
        raise ProtocolError("Original payload commitment mismatch")
    if inner["origin_format"] not in ("opaque", LEGACY, "xi.capsule.v1") or type(inner["metadata"]) is not dict:
        raise ProtocolError("Invalid inner format or metadata")
    legacy = inspect_glyphsafe(payload) if inner["origin_format"] == LEGACY else None
    return Restored(payload, inner["metadata"], inner["origin_format"], header, sha256(wire), legacy)


def make_consent(wire, principal_key, *, scope, audience):
    label(scope)
    label(audience)
    parse(wire)
    body = {"profile": "xi.crypto-lattice.consent.v1", "operation": "restore",
            "scope": scope, "audience": audience, "envelope_sha256": sha256(wire),
            "grant_id": secrets.token_bytes(32).hex()}
    return sign_record(body, principal_key, CONSENT)


def verify_consent(consent, restored, policy):
    body, pub = verify_record(consent, CONSENT, policy.consent_keys)
    fields(body, {"profile", "operation", "scope", "audience", "envelope_sha256", "grant_id"})
    hexbytes(body["grant_id"])
    if (body["profile"] != "xi.crypto-lattice.consent.v1" or body["operation"] != "restore"
            or body["scope"] != policy.scope or body["audience"] != policy.audience
            or body["envelope_sha256"] != restored.envelope_sha256):
        raise ProtocolError("Consent does not authorize this restoration")
    return key_id(pub)
