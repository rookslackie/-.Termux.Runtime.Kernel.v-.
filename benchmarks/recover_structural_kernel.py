"""Decode the supplied StructuralKernel QR without executing its contents.

Optional recovery-only dependencies: Pillow and zxing-cpp==3.1.1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


if __name__ == "__main__":
    from PIL import Image
    import zxingcpp

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = [r for r in zxingcpp.read_barcodes(Image.open(args.image)) if r.valid]
    if len(results) != 1 or not bytes(results[0].bytes).startswith("Ξ.Kernel.v1:".encode()):
        parser.error("Expected exactly one decodable Ξ.Kernel.v1 QR")
    raw = bytes(results[0].bytes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(raw)
    print(json.dumps({"source_sha256": hashlib.sha256(args.image.read_bytes()).hexdigest(),
                      "payload_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                      "execution": "source decoded and saved"}))
