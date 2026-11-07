"""Recovered GlyphSafe body-hash rule and exact GlyphSHA nibble alphabet."""
import re
from .wire import MAX_PAYLOAD, ProtocolError, sha256

GLYPHS = "∴Ω⧂⋈Ξ⟐⊚◇✦⟁∵☉◬⌬⧉∞"
HEX = "0123456789abcdef"
DIALECT = "xi.glyph-sha256.v1"
LEGACY = "glyphsafe.tessera.v1"
ASCII_WS = " \t\r\n"


def normalize_digest(value):
    if type(value) is not str:
        raise ProtocolError("Expected a SHA-256 string")
    value = value.strip(ASCII_WS)
    if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise ProtocolError("SHA-256 must contain exactly 64 hexadecimal digits")
    return value.lower()


def encode_digest(value):
    symbols = "".join(GLYPHS[HEX.index(x)] for x in normalize_digest(value))
    return "\n".join(symbols[i:i + 8] for i in range(0, 64, 8))


def decode_tile(value):
    if type(value) is not str:
        raise ProtocolError("Expected a glyph tile")
    symbols = "".join(x for x in value if x not in ASCII_WS)
    if len(symbols) != 64 or any(x not in GLYPHS for x in symbols):
        raise ProtocolError("Expected exactly 64 glyphs from the declared v1 alphabet")
    return "".join(HEX[GLYPHS.index(x)] for x in symbols)


def inspect_glyphsafe(raw):
    """Match the historical Python read_text/regex coverage; retain original bytes."""
    if type(raw) is not bytes or len(raw) > MAX_PAYLOAD:
        raise ProtocolError("Expected bounded original bytes")
    result = {"dialect": LEGACY, "raw_sha256": sha256(raw),
              "body_status": "bad_format", "declared_body_sha256": None,
              "computed_body_sha256": None, "ambiguous": False,
              "header_present": False, "coverage": "normalized_glyph_body_only",
              "authorship": "unproven"}
    try:
        # pathlib.Path.read_text uses universal newline translation. No other normalization.
        text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeError:
        return result
    hashes = list(re.finditer(r"hash:\s*SHA256=([0-9a-fA-F]{64})", text))
    bodies = list(re.finditer(r"```glyph\n(.*?)\n```", text, re.S))
    result["header_present"] = "[glyphsafe:v1]" in text
    result["ambiguous"] = len(hashes) > 1 or len(bodies) > 1
    if hashes and bodies:
        want = hashes[0].group(1).lower()
        got = sha256(bodies[0].group(1).encode("utf-8"))
        result.update(declared_body_sha256=want, computed_body_sha256=got,
                      body_status="match" if want == got else "mismatch")
    return result
