"""Export causal computation evidence without local keys or transport queues."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile


def export(home, output):
    output.mkdir(parents=True, exist_ok=True)
    manifest = []
    for node in ("node-a", "node-b"):
        with tempfile.TemporaryDirectory() as folder:
            snapshot = Path(folder) / "quantum.sqlite3"
            source = sqlite3.connect(home / node / "quantum.sqlite3")
            destination = sqlite3.connect(snapshot)
            try:
                source.backup(destination)
                for table in ("quantum_outbox", "quantum_imports", "quantum_counters"):
                    destination.execute("DELETE FROM " + table)
                destination.commit()
                destination.execute("VACUUM")
                destination.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            finally:
                destination.close()
                source.close()
            raw = snapshot.read_bytes()
        packed = output / (node + ".sqlite3.gz")
        with packed.open("wb") as stream:
            with gzip.GzipFile(fileobj=stream, mode="wb", mtime=0) as gz:
                gz.write(raw)
        manifest.append({"node": node, "database_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                         "gzip_bytes": packed.stat().st_size,
                         "gzip_sha256": hashlib.sha256(packed.read_bytes()).hexdigest(),
                         "content": "WorldKernel events, state and exact sources; local transport tables empty"})
    (output / "ledgers.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.home, args.output)))
