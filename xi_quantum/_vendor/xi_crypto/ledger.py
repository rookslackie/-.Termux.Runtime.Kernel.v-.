"""SQLite replay gate and signed witness receipts, with externally retained checkpoints."""
import secrets
import sqlite3
from .envelope import (CONSENT, RECEIPT, public_bytes, key_id, sign_record, verify_record,
                       verify_and_open, verify_consent)
from .wire import ProtocolError, canonical, fields, hexbytes, parse, sha256

CHECKPOINT = b"Xi.CryptoLattice/checkpoint-signature/v1\x00"
ZERO = "0" * 64
BODY_FIELDS = {"profile", "ledger_id", "position", "previous_sha256", "envelope_sha256",
               "signer_key_id", "scope", "audience", "message_id", "sequence", "outcome",
               "legacy_body_status", "consent"}


class WitnessLedger:
    def __init__(self, path, witness_key):
        self.key = witness_key
        self.pub = public_bytes(witness_key)
        self.db = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.db.execute("""CREATE TABLE IF NOT EXISTS events (
            position INTEGER PRIMARY KEY, issuer TEXT NOT NULL, scope TEXT NOT NULL,
            audience TEXT NOT NULL, message_id TEXT NOT NULL, sequence INTEGER NOT NULL,
            receipt BLOB NOT NULL,
            UNIQUE(issuer, scope, audience, message_id), UNIQUE(issuer, scope, audience, sequence))""")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            meta = dict(self.db.execute("SELECT name, value FROM metadata"))
            if not meta:
                self.ledger_id = secrets.token_bytes(32).hex()
                self.db.executemany("INSERT INTO metadata VALUES (?,?)",
                                    [("ledger_id", self.ledger_id), ("witness_public_key_hex", self.pub.hex())])
            else:
                if set(meta) != {"ledger_id", "witness_public_key_hex"} or meta["witness_public_key_hex"] != self.pub.hex():
                    raise ProtocolError("Ledger witness key or metadata mismatch")
                hexbytes(meta["ledger_id"])
                self.ledger_id = meta["ledger_id"]
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def audit(self, expected_checkpoint=None):
        previous, count, heads, sequences, ids = ZERO, 0, {0: ZERO}, {}, set()
        meta = dict(self.db.execute("SELECT name, value FROM metadata"))
        if meta != {"ledger_id": self.ledger_id, "witness_public_key_hex": self.pub.hex()}:
            raise ProtocolError("Ledger metadata altered")
        for position, issuer, scope, audience, message_id, sequence, wire in self.db.execute(
                "SELECT position,issuer,scope,audience,message_id,sequence,receipt FROM events ORDER BY position"):
            count += 1
            record = parse(wire)
            body, _ = verify_record(record, RECEIPT, frozenset({self.pub}))
            fields(body, BODY_FIELDS)
            if (position != count or type(body["position"]) is not int or body["position"] != position
                    or body["profile"] != "xi.crypto-lattice.witness.v1" or body["ledger_id"] != self.ledger_id
                    or body["previous_sha256"] != previous or body["outcome"] != "restored"):
                raise ProtocolError("Broken witness chain")
            if (body["signer_key_id"], body["scope"], body["audience"], body["message_id"], body["sequence"]) != (
                    issuer, scope, audience, message_id, sequence):
                raise ProtocolError("Ledger replay indices altered")
            identity = (issuer, scope, audience)
            if sequence <= sequences.get(identity, -1) or (identity, message_id) in ids:
                raise ProtocolError("Ledger replay invariant violated")
            sequences[identity] = sequence
            ids.add((identity, message_id))
            grant, _ = verify_record(body["consent"], CONSENT)
            fields(grant, {"profile", "operation", "scope", "audience", "envelope_sha256", "grant_id"})
            if (grant["profile"] != "xi.crypto-lattice.consent.v1" or grant["operation"] != "restore"
                    or (grant["scope"], grant["audience"], grant["envelope_sha256"]) != (
                        scope, audience, body["envelope_sha256"])):
                raise ProtocolError("Receipt consent binding altered")
            previous = sha256(wire)
            heads[position] = previous
        if expected_checkpoint is not None:
            anchor, _ = verify_record(expected_checkpoint, CHECKPOINT, frozenset({self.pub}))
            fields(anchor, {"profile", "ledger_id", "position", "head_sha256"})
            if (anchor["profile"] != "xi.crypto-lattice.checkpoint.v1" or anchor["ledger_id"] != self.ledger_id
                    or type(anchor["position"]) is not int or anchor["position"] < 0
                    or heads.get(anchor["position"]) != anchor["head_sha256"]):
                raise ProtocolError("External checkpoint missing or changed")
        return {"profile": "xi.crypto-lattice.checkpoint.v1", "ledger_id": self.ledger_id,
                "position": count, "head_sha256": previous}

    def checkpoint(self):
        return sign_record(self.audit(), self.key, CHECKPOINT)

    def accept(self, wire, master_key, policy, consent, *, expected_checkpoint=None):
        # Verify and authorize before reserving replay state. Failed inputs never consume a slot.
        consent = parse(canonical(consent))
        restored = verify_and_open(wire, master_key, policy)
        verify_consent(consent, restored, policy)
        header = restored.header
        issuer = key_id(hexbytes(header["signer_public_key_hex"]))
        self.db.execute("BEGIN IMMEDIATE")
        try:
            current = self.audit(expected_checkpoint)
            last = self.db.execute("SELECT MAX(sequence) FROM events WHERE issuer=? AND scope=? AND audience=?",
                                   (issuer, policy.scope, policy.audience)).fetchone()[0]
            if last is not None and header["sequence"] <= last:
                raise ProtocolError("Replay or stale sequence")
            body = {"profile": "xi.crypto-lattice.witness.v1", "ledger_id": self.ledger_id,
                    "position": current["position"] + 1, "previous_sha256": current["head_sha256"],
                    "envelope_sha256": restored.envelope_sha256, "signer_key_id": issuer,
                    "scope": policy.scope, "audience": policy.audience, "message_id": header["message_id"],
                    "sequence": header["sequence"], "outcome": "restored", "consent": consent,
                    "legacy_body_status": restored.legacy["body_status"] if restored.legacy else "not_applicable"}
            receipt = sign_record(body, self.key, RECEIPT)
            self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?)", (
                body["position"], issuer, policy.scope, policy.audience, body["message_id"],
                body["sequence"], canonical(receipt)))
            self.db.execute("COMMIT")
            return restored, receipt
        except Exception as exc:
            self.db.execute("ROLLBACK")
            if isinstance(exc, sqlite3.IntegrityError):
                raise ProtocolError("Duplicate message or sequence") from exc
            raise
