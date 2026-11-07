"""A new, explicitly versioned canonical JSON subset. Not a legacy Xi AST."""
import base64
import hashlib
import json
import re

MAX_PAYLOAD = 1024 * 1024
MAX_WIRE = 4 * 1024 * 1024
CANONICAL = "xi.ascii-json.v1"


class ProtocolError(ValueError):
    pass


def _valid(value, depth=0):
    if depth > 24:
        raise ProtocolError("JSON nesting limit exceeded")
    if value is None or type(value) is bool:
        return
    if type(value) is int and abs(value) <= 9007199254740991:
        return
    if type(value) is str:
        try:
            value.encode("utf-8", "strict")
        except UnicodeError as exc:
            raise ProtocolError("Unpaired Unicode surrogate") from exc
        if len(value) > MAX_WIRE:
            raise ProtocolError("String limit exceeded")
        return
    if type(value) is list:
        for item in value:
            _valid(item, depth + 1)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,127}", key):
                raise ProtocolError("JSON object keys must be ASCII identifiers")
            _valid(item, depth + 1)
        return
    raise ProtocolError("Only bounded integers, strings, booleans, null, lists and objects are allowed")


def canonical(value):
    _valid(value)
    wire = json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(wire) > MAX_WIRE:
        raise ProtocolError("JSON byte limit exceeded")
    return wire


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ProtocolError("Duplicate JSON key")
        result[key] = value
    return result


def parse(wire):
    if type(wire) is not bytes or len(wire) > MAX_WIRE:
        raise ProtocolError("Expected bounded JSON bytes")
    try:
        value = json.loads(wire.decode("ascii"), object_pairs_hook=_pairs)
        if canonical(value) != wire:
            raise ProtocolError("Non-canonical JSON")
        return value
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ProtocolError("Malformed JSON") from exc


def fields(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ProtocolError("Unexpected object fields")


def b64(data):
    return base64.b64encode(data).decode("ascii")


def unb64(value, size=None, limit=MAX_WIRE):
    if type(value) is not str or len(value) > (limit + 2) // 3 * 4:
        raise ProtocolError("Base64 limit or type error")
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, UnicodeError) as exc:
        raise ProtocolError("Malformed base64") from exc
    if len(data) > limit or (size is not None and len(data) != size) or b64(data) != value:
        raise ProtocolError("Non-canonical base64 or wrong length")
    return data


def hexbytes(value, size=32):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{" + str(size * 2) + r"}", value):
        raise ProtocolError("Expected fixed-length lowercase hex")
    return bytes.fromhex(value)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def label(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}", value):
        raise ProtocolError("Expected a bounded ASCII scope or audience")
    return value
