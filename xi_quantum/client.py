"""Small Python client for the owner-authenticated local JSON API."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class LivingCircuitClient:
    def __init__(self, base_url="http://127.0.0.1:7476/api/quantumcompute/v3", *, token=None, token_file=None):
        self.base_url = base_url.rstrip("/")
        self.token = token if token is not None else Path(token_file).read_text().strip() if token_file else None

    def request(self, path, body=None):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.base_url + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            message = json.load(exc).get("error", str(exc))
            raise ValueError(f"Living Circuit HTTP {exc.code}: {message}") from exc

    def capabilities(self):
        return self.request("/capabilities")

    def compile(self, source):
        return self.request("/compile", {"source": source})

    def submit(self, source, request_id):
        return self.request("/jobs", {"source": source, "request_id": request_id})

    def job(self, job_id):
        return self.request("/jobs/" + job_id)

    def events(self, job_id, after=0):
        return self.request(f"/jobs/{job_id}/events?after={after}")

    def cancel(self, job_id):
        return self.request(f"/jobs/{job_id}/cancel", {})

    def resume(self, job_id):
        return self.request(f"/jobs/{job_id}/resume", {})
