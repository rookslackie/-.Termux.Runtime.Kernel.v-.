"""ThinkSync bridge: pinned peers, encrypted outbox, drift/fork-aware recovery.

Transport is an explicit byte handoff. Receiving stores evidence and original
bytes; running a received program requires a separate local ExecutionGrant.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from .common import canonical, digest, QuantumComputeError, VerifiedCheckpoint
from .glyphsafe import Identity, public_id, seal, restore


class ThinkSync:
    def __init__(self, runtime, identity: Identity, *, trusted_senders=None,
                 scope="QuantumCompute", audience="local-peer"):
        self.runtime = runtime
        self.identity = identity
        self.trusted_senders = dict(trusted_senders or {})
        self.scope, self.audience = scope, audience

    def queue(self, raw, recipient, *, checkpoint=None, request_key=None):
        if checkpoint is not None:
            from .tessera import compile_program
            self.runtime._validate_checkpoint(compile_program(raw), checkpoint)
        recipient_id = public_id(recipient)
        self.runtime.ingest(raw)
        package = canonical({"schema": "xi.thinksync.transfer.v2",
            "source": base64.b64encode(raw).decode("ascii"), "source_sha256": digest(raw),
            "checkpoint": checkpoint})
        request_hash = digest({"package_sha256": digest(package), "recipient": recipient_id,
                               "scope": self.scope, "audience": self.audience})
        request_key = request_hash if request_key is None else request_key
        with self.runtime.kernel._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT wire,request_sha256 FROM quantum_outbox WHERE request_key=?", (request_key,)).fetchone()
            if prior:
                if prior["request_sha256"] != request_hash:
                    raise QuantumComputeError("Outbox request key already identifies a different transfer")
                return prior["wire"]
            row = db.execute("SELECT sequence FROM quantum_counters WHERE recipient=?", (recipient_id,)).fetchone()
            sequence = row["sequence"] + 1 if row else 1
            wire = seal(package, self.identity, recipient, sequence=sequence,
                        scope=self.scope, audience=self.audience,
                        metadata={"transport": "ThinkSync", "source_profile": "exact-bytes"})
            db.execute("INSERT OR REPLACE INTO quantum_counters VALUES (?,?)", (recipient_id, sequence))
            db.execute("INSERT INTO quantum_outbox VALUES (?,?,?,?)", (request_key, recipient_id, wire, request_hash))
            db.execute("COMMIT")
        return wire

    def _open(self, wire):
        restored = restore(wire, self.identity, self.trusted_senders, scope=self.scope, audience=self.audience)
        try:
            package = json.loads(restored["raw"])
            if canonical(package) != restored["raw"] or set(package) != {"schema", "source", "source_sha256", "checkpoint"}:
                raise ValueError("noncanonical transfer")
            if package["schema"] != "xi.thinksync.transfer.v2":
                raise ValueError("unknown transfer schema")
            raw = base64.b64decode(package["source"], validate=True)
            if base64.b64encode(raw).decode("ascii") != package["source"] or digest(raw) != package["source_sha256"]:
                raise ValueError("source commitment failed")
        except (ValueError, TypeError, KeyError) as exc:
            raise QuantumComputeError("Invalid ThinkSync package") from exc
        if package["checkpoint"] is not None:
            from .tessera import compile_program
            self.runtime._validate_checkpoint(compile_program(raw), package["checkpoint"])
        return restored, package, raw

    def receive(self, wire):
        restored, package, raw = self._open(wire)
        packet_id, sender, sequence = restored["envelope_sha256"], restored["sender"], restored["sequence"]
        duplicate = False
        with self.runtime.kernel._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT * FROM quantum_imports WHERE packet_digest=?", (packet_id,)).fetchone()
            if previous:
                duplicate = True
            else:
                head = db.execute("SELECT MAX(sequence) FROM quantum_imports WHERE sender=?", (sender,)).fetchone()[0]
                if head is not None and sequence <= head:
                    raise QuantumComputeError("ThinkSync sequence is stale or conflicts with an accepted packet")
                db.execute("INSERT OR IGNORE INTO quantum_sources VALUES (?,?)", (digest(raw), raw))
                db.execute("INSERT INTO quantum_imports VALUES (?,?,?,?,?,?)", (
                    packet_id, sender, sequence, digest(raw), canonical(package["checkpoint"]), wire))
            db.execute("COMMIT")
        return {"schema": "xi.thinksync.receipt.v2", "packet_sha256": packet_id,
                "source_sha256": digest(raw), "sender": sender, "recipient": self.identity.node_id,
                "sequence": sequence, "duplicate": duplicate, "exact_bytes_restored": True,
                "checkpoint_retained": package["checkpoint"] is not None,
                "execution_authorized_by_receipt": False}

    def checkpoint(self, packet_id):
        with self.runtime.kernel._connect() as db:
            row = db.execute("SELECT received_wire FROM quantum_imports WHERE packet_digest=?", (packet_id,)).fetchone()
        if row is None:
            raise QuantumComputeError("Unknown received packet")
        restored, package, _ = self._open(row[0])
        if package["checkpoint"] is None:
            raise QuantumComputeError("This packet preserves source bytes without a computation checkpoint")
        return VerifiedCheckpoint(package["checkpoint"], restored["sender"], packet_id)


def sweep_inbox(bridge: ThinkSync, folder):
    """One bridge-daemon tick. Keep incoming bytes; receipt/restore never executes."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    journal_path = bridge.runtime.home / "bridge-journal.json"
    journal = json.loads(journal_path.read_text()) if journal_path.exists() else {}
    trust_id = digest(bridge.trusted_senders)
    receipts, failures = [], []
    for path in sorted(folder.glob("*.glyphsafe")):
        if path.is_symlink() or not path.is_file():
            continue
        wire = path.read_bytes()
        fingerprint = digest({"wire": digest(wire), "trust": trust_id})
        if journal.get(str(path.resolve())) == fingerprint:
            continue
        try:
            receipt = bridge.receive(wire)
        except ValueError as exc:
            failures.append({"file": path.name, "sha256": digest(wire), "error": str(exc)})
            continue
        receipts.append(receipt)
        journal[str(path.resolve())] = fingerprint
    temporary = journal_path.with_suffix(".tmp")
    temporary.write_bytes(canonical(journal))
    temporary.replace(journal_path)
    return {"schema": "xi.thinksync.sweep.v2", "received": receipts, "failures": failures,
            "movement": "yield" if receipts else "rest", "return_operator": "⟁∴Ω"}
