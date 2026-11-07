"""GlyphSafe v2: exact-byte preservation, ML-KEM-768, ML-DSA-65, AEAD.

Uses pyca/cryptography's implementations. The recovered v1 wire, codec,
envelope, and witness ledger remain in _vendor.xi_crypto without alteration.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import secrets

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives.asymmetric import mldsa, mlkem
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ._vendor.xi_crypto.compat import encode_digest, decode_tile, inspect_glyphsafe
from ._vendor.xi_crypto.wire import (ProtocolError, b64, canonical, fields, hexbytes,
                                    label, parse, sha256, unb64, MAX_PAYLOAD)

PROFILE = "xi.glyphsafe.envelope.v2"
SUITE = "ML-KEM-768/HKDF-SHA256/ChaCha20Poly1305/ML-DSA-65"
CONTEXT = b"Xi.GlyphSafe/envelope/v2"
HEAD = {"schema", "suite", "sender", "recipient", "scope", "audience", "sequence",
        "nonce", "salt", "kem_ciphertext"}


@dataclass(frozen=True)
class Identity:
    signing: object
    encryption: object

    @classmethod
    def generate(cls):
        return cls(mldsa.MLDSA65PrivateKey.generate(), mlkem.MLKEM768PrivateKey.generate())

    def public(self):
        return {"schema": "xi.identity.v2", "signing_key": b64(self.signing.public_key().public_bytes_raw()),
                "encryption_key": b64(self.encryption.public_key().public_bytes_raw())}

    @property
    def node_id(self):
        return sha256(b"Xi.Identity/v2\x00" + canonical(self.public()))

    @classmethod
    def load_or_create(cls, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not path.exists():
            identity = cls.generate()
            body = {"schema": "xi.identity.secret.v2", "signing_seed": b64(identity.signing.private_bytes_raw()),
                    "encryption_seed": b64(identity.encryption.private_bytes_raw())}
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                return cls.load_or_create(path)
            with os.fdopen(fd, "wb") as file:
                file.write(canonical(body))
                file.flush()
                os.fsync(file.fileno())
            return identity
        body = parse(path.read_bytes())
        fields(body, {"schema", "signing_seed", "encryption_seed"})
        if body["schema"] != "xi.identity.secret.v2":
            raise ProtocolError("Unsupported secret-key profile")
        return cls(mldsa.MLDSA65PrivateKey.from_seed_bytes(unb64(body["signing_seed"], size=32)),
                   mlkem.MLKEM768PrivateKey.from_seed_bytes(unb64(body["encryption_seed"], size=64)))


def public_id(public):
    fields(public, {"schema", "signing_key", "encryption_key"})
    if public["schema"] != "xi.identity.v2":
        raise ProtocolError("Unsupported public identity")
    unb64(public["signing_key"], size=1952)
    unb64(public["encryption_key"], size=1184)
    return sha256(b"Xi.Identity/v2\x00" + canonical(public))


def _key(shared, header):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=unb64(header["salt"], size=32),
                info=b"Xi.GlyphSafe/AEAD-key/v2\x00" + canonical(header)).derive(shared)


def seal(raw: bytes, sender: Identity, recipient: dict, *, sequence: int,
         scope="QuantumCompute", audience="local-peer", metadata=None):
    if type(raw) is not bytes or len(raw) > MAX_PAYLOAD:
        raise ProtocolError("GlyphSafe expects exact payload bytes up to 1 MiB")
    if type(sequence) is not int or not 0 <= sequence <= 9007199254740991:
        raise ProtocolError("Invalid transport sequence")
    label(scope)
    label(audience)
    if metadata is not None and type(metadata) is not dict:
        raise ProtocolError("Envelope metadata must be an object")
    recipient_id = public_id(recipient)
    shared, kem_ciphertext = mlkem.MLKEM768PublicKey.from_public_bytes(
        unb64(recipient["encryption_key"], size=1184)).encapsulate()
    header = {"schema": PROFILE, "suite": SUITE, "sender": sender.public(),
              "recipient": recipient_id, "scope": scope, "audience": audience,
              "sequence": sequence, "nonce": b64(secrets.token_bytes(12)),
              "salt": b64(secrets.token_bytes(32)), "kem_ciphertext": b64(kem_ciphertext)}
    inner = {"payload": b64(raw), "payload_sha256": sha256(raw), "metadata": metadata or {}}
    ciphertext = ChaCha20Poly1305(_key(shared, header)).encrypt(
        unb64(header["nonce"], size=12), canonical(inner), canonical(header))
    unsigned = {"protected": header, "ciphertext": b64(ciphertext)}
    signature = sender.signing.sign(canonical(unsigned), context=CONTEXT)
    return canonical({**unsigned, "signature": b64(signature)})


def restore(wire: bytes, recipient: Identity, trusted_senders: dict, *,
            scope="QuantumCompute", audience="local-peer"):
    envelope = parse(wire)
    fields(envelope, {"protected", "ciphertext", "signature"})
    header = envelope["protected"]
    fields(header, HEAD)
    if header["schema"] != PROFILE or header["suite"] != SUITE:
        raise ProtocolError("Unsupported GlyphSafe suite")
    if header["scope"] != scope or header["audience"] != audience:
        raise ProtocolError("Scope or audience mismatch")
    if header["recipient"] != recipient.node_id:
        raise ProtocolError("Packet is addressed to a different identity")
    if type(header["sequence"]) is not int or not 0 <= header["sequence"] <= 9007199254740991:
        raise ProtocolError("Invalid transport sequence")
    sender_id = public_id(header["sender"])
    if trusted_senders.get(sender_id) != header["sender"]:
        raise ProtocolError("Sender is not pinned for this bridge")
    unsigned = {"protected": header, "ciphertext": envelope["ciphertext"]}
    try:
        mldsa.MLDSA65PublicKey.from_public_bytes(unb64(header["sender"]["signing_key"], size=1952)).verify(
            unb64(envelope["signature"], size=3309), canonical(unsigned), context=CONTEXT)
    except InvalidSignature as exc:
        raise ProtocolError("GlyphSafe signature failed") from exc
    shared = recipient.encryption.decapsulate(unb64(header["kem_ciphertext"], size=1088))
    try:
        raw_inner = ChaCha20Poly1305(_key(shared, header)).decrypt(
            unb64(header["nonce"], size=12), unb64(envelope["ciphertext"]), canonical(header))
    except InvalidTag as exc:
        raise ProtocolError("GlyphSafe ciphertext failed authentication") from exc
    inner = parse(raw_inner)
    fields(inner, {"payload", "payload_sha256", "metadata"})
    raw = unb64(inner["payload"], limit=MAX_PAYLOAD)
    hexbytes(inner["payload_sha256"])
    if sha256(raw) != inner["payload_sha256"] or type(inner["metadata"]) is not dict:
        raise ProtocolError("Payload commitment or metadata is invalid")
    return {"raw": raw, "sha256": sha256(raw), "glyphsha": encode_digest(sha256(raw)),
            "sender": sender_id, "sequence": header["sequence"], "metadata": inner["metadata"],
            "legacy": inspect_glyphsafe(raw), "envelope_sha256": sha256(wire)}


__all__ = ["Identity", "seal", "restore", "public_id", "encode_digest", "decode_tile", "inspect_glyphsafe"]
