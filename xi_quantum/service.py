"""Framework-free local HTTP adapter for the Living Circuit workbench."""
from __future__ import annotations

import base64
import hmac
from importlib.resources import files
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
from urllib.parse import parse_qs, urlsplit

from .common import Profile, QuantumComputeError, canonical
from .tessera import compile_program
from .workbench import Workbench, capabilities


EXAMPLES = {"living-circuit": "QuantumCompute.LivingCircuit.v3.xi",
            "new-glyph": "QuantumCompute.NewGlyph.v3.xi",
            "spectral": "QuantumCompute.Spectral.v3.xi",
            "fullcycle-v2": "QuantumCompute.FullCycle.v2.xi"}
BASE = "/api/quantumcompute/v3"


def owner_token(home):
    path = Path(home) / "owner.token"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return owner_token(home)
        with os.fdopen(fd, "w") as out:
            out.write(secrets.token_urlsafe(32))
    token = path.read_text().strip()
    if len(token) < 32:
        raise QuantumComputeError("Local owner token must contain at least 32 characters")
    return token


def openapi():
    definitions = {
        "/capabilities": {"get": "Inspect operators, dialects, profiles, and crypto suite"},
        "/examples": {"get": "List executable example names"},
        "/examples/{name}": {"get": "Read an executable example source"},
        "/compile": {"post": "Compile source and inspect expanded glyph bindings"},
        "/jobs": {"get": "List durable jobs", "post": "Submit source with an idempotent request_id"},
        "/jobs/{job_id}": {"get": "Read status and numerical receipts"},
        "/jobs/{job_id}/events": {"get": "Read events after an integer cursor"},
        "/jobs/{job_id}/source": {"get": "Read the exact preserved source"},
        "/jobs/{job_id}/cancel": {"post": "Request cancellation between operators"},
        "/jobs/{job_id}/resume": {"post": "Resume a paused or interrupted job"},
        "/jobs/{job_id}/export": {"post": "Encrypt a source/checkpoint packet to the supplied recipient"},
        "/identity": {"get": "Read this workbench's public PQC identity"},
        "/transfers/receive": {"post": "Verify and retain an encrypted packet from the supplied pinned sender"},
    }
    paths = {}
    public = {"/capabilities", "/examples", "/examples/{name}"}
    for path, methods in definitions.items():
        paths[BASE+path] = {}
        for method, summary in methods.items():
            operation = {"summary": summary, "responses": {"200": {"description": "JSON result"},
                "400": {"description": "Invalid input"}, "401": {"description": "Owner authentication required"}},
                "security": [] if path in public else [{"OwnerToken": []}]}
            parameters = []
            for name in ("job_id", "name"):
                if "{"+name+"}" in path:
                    parameters.append({"name": name, "in": "path", "required": True, "schema": {"type": "string"}})
            if path.endswith("/events"):
                parameters.append({"name": "after", "in": "query", "schema": {"type": "integer", "minimum": 0}})
            if path == "/jobs" and method == "get":
                parameters.append({"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100}})
            if parameters:
                operation["parameters"] = parameters
            if method == "post":
                properties = {}
                required = []
                if path in ("/compile", "/jobs"):
                    properties["source"] = {"type": "string"}
                    required.append("source")
                if path == "/jobs":
                    properties["request_id"] = {"type": "string", "maxLength": 128}
                if path.endswith("/export"):
                    properties["recipient"] = {"type": "object"}
                    required.append("recipient")
                if path == "/transfers/receive":
                    properties = {"packet_base64": {"type": "string"}, "sender": {"type": "object"}}
                    required = list(properties)
                operation["requestBody"] = {"required": bool(required), "content": {"application/json": {
                    "schema": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}}}
            paths[BASE+path][method] = operation
    return {"openapi": "3.1.0", "info": {"title": "Xi Living Circuit Engine", "version": "3.0.0"},
            "components": {"securitySchemes": {"OwnerToken": {"type": "http", "scheme": "bearer"}}}, "paths": paths}


def make_server(workbench, *, host="127.0.0.1", port=7476, token=None, allowed_origin=None):
    token = owner_token(workbench.home) if token is None else token
    if type(token) is not str or len(token) < 32:
        raise QuantumComputeError("HTTP owner token must contain at least 32 characters")
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise QuantumComputeError("This adapter binds to loopback; use an authenticated local reverse proxy for remote access")

    class Handler(BaseHTTPRequestHandler):
        server_version = "XiLivingCircuit/3"

        def log_message(self, *_):
            pass

        def _reply(self, status, value):
            raw = canonical(value)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if allowed_origin and self.headers.get("Origin") == allowed_origin:
                self.send_header("Access-Control-Allow-Origin", allowed_origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(raw)

        def do_OPTIONS(self):
            if not allowed_origin or self.headers.get("Origin") != allowed_origin:
                self._reply(403, {"error": "Origin not configured"})
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Access-Control-Allow-Headers", "Authorization,Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.end_headers()

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def _dispatch(self, method):
            try:
                parsed = urlsplit(self.path)
                path = parsed.path
                if method == "GET" and path == "/health":
                    self._reply(200, {"ok": True, "engine": "Xi Living Circuit", "version": "3.0.0"})
                    return
                if not path.startswith(BASE + "/"):
                    self._reply(404, {"error": "Unknown route"})
                    return
                relative = path[len(BASE):]
                public = method == "GET" and (relative in ("/capabilities", "/openapi.json", "/examples") or relative.startswith("/examples/"))
                if not public and not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                    self._reply(401, {"error": "Owner token required"})
                    return
                body = {}
                if method == "POST":
                    if self.headers.get_content_type() != "application/json":
                        raise QuantumComputeError("POST requests require application/json")
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 <= length <= 3 * 1024 * 1024:
                        self._reply(413, {"error": "Request exceeds 3 MiB"})
                        return
                    body = json.loads(self.rfile.read(length) or b"{}")
                    if type(body) is not dict:
                        raise QuantumComputeError("Request must be a JSON object")
                query = parse_qs(parsed.query)
                if method == "GET" and relative == "/capabilities":
                    result = capabilities()
                elif method == "GET" and relative == "/openapi.json":
                    result = openapi()
                elif method == "GET" and relative == "/examples":
                    result = {"examples": list(EXAMPLES)}
                elif method == "GET" and relative.startswith("/examples/"):
                    name = relative.split("/")[-1]
                    if name not in EXAMPLES:
                        raise KeyError("Unknown example")
                    result = {"name": name, "source": files("xi_quantum.programs").joinpath(EXAMPLES[name]).read_text(encoding="utf-8")}
                elif method == "POST" and relative == "/compile":
                    if set(body) != {"source"} or type(body["source"]) is not str:
                        raise QuantumComputeError("compile requires only source text")
                    result = compile_program(body["source"].encode()).as_dict()
                elif relative == "/jobs":
                    if method == "POST":
                        if set(body) - {"source", "request_id"} or "source" not in body:
                            raise QuantumComputeError("submit requires source and optional request_id")
                        result = workbench.submit(**body)
                    else:
                        result = {"jobs": workbench.list(int(query.get("limit", ["20"])[0]))}
                elif method == "GET" and relative == "/identity":
                    result = workbench.identity().public()
                elif method == "POST" and relative == "/transfers/receive":
                    if set(body) != {"packet_base64", "sender"}:
                        raise QuantumComputeError("receive requires packet_base64 and sender")
                    wire = base64.b64decode(body["packet_base64"], validate=True)
                    result = workbench.receive(wire, body["sender"])
                elif relative.startswith("/jobs/"):
                    parts = relative.strip("/").split("/")
                    job_id = parts[1]
                    action = parts[2] if len(parts) == 3 else "" if len(parts) == 2 else "invalid"
                    if method == "GET" and action == "":
                        result = workbench.get(job_id)
                    elif method == "GET" and action == "events":
                        events = workbench.events(job_id, int(query.get("after", ["0"])[0]))
                        result = {"events": events, "next_cursor": events[-1]["sequence"] if events else int(query.get("after", ["0"])[0])}
                    elif method == "GET" and action == "source":
                        result = {"source": workbench.source(job_id)}
                    elif method == "POST" and action in ("cancel", "resume") and not body:
                        result = getattr(workbench, action)(job_id)
                    elif method == "POST" and action == "export" and set(body) == {"recipient"}:
                        wire = workbench.export(job_id, body["recipient"])
                        result = {"packet_base64": base64.b64encode(wire).decode(), "sender": workbench.identity().public()}
                    else:
                        raise KeyError("Unknown route")
                else:
                    raise KeyError("Unknown route")
                self._reply(200, result)
            except KeyError as exc:
                self._reply(404, {"error": str(exc)})
            except (ValueError, TypeError, OSError) as exc:
                self._reply(400, {"error": str(exc)})

    return ThreadingHTTPServer((host, port), Handler)


def serve(home, *, profile=Profile(), host="127.0.0.1", port=7476, allowed_origin=None):
    workbench = Workbench(home, profile=profile)
    server = make_server(workbench, host=host, port=port, allowed_origin=allowed_origin)
    print(json.dumps({"service": "Xi Living Circuit", "url": f"http://{host}:{server.server_port}{BASE}",
        "owner_token_file": str(Path(home) / "owner.token"), "interface": "HTTP JSON; OpenAPI; cursor events"}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        workbench.close()
