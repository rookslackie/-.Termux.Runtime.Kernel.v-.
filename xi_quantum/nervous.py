"""Ξ.Nervous capability-gap routing derived from Ξ.Skill.DiscoverFunction.

This module classifies capability state only. It does not dynamically import,
execute, register, deploy, or authorize a proposed operation.
"""
from __future__ import annotations

import re

from .common import Profile, QuantumComputeError, canonical, digest


SCHEMA = "xi.nervous.discover-function.v1"
STATES = ("EXISTING", "UNRESOLVED", "PROPOSED", "TESTED", "AUTHORIZED", "REGISTERED", "FAILED")
ROUTES = {"EXISTING": "TRANSMIT", "UNRESOLVED": "REST", "PROPOSED": "FORGE"}


def _string_list(value, name):
    if value is None:
        return []
    if type(value) is not list or any(type(item) is not str or not item for item in value):
        raise QuantumComputeError(f"{name} must be a list of nonempty strings")
    if len(value) != len(set(value)):
        raise QuantumComputeError(f"{name} must not contain duplicates")
    return value


def _records(value, name, limit):
    if value is None:
        return []
    if type(value) is not list or len(value) > limit or any(type(item) is not dict for item in value):
        raise QuantumComputeError(f"{name} must be a list of at most {limit} objects")
    canonical(value)
    return value


def _candidate_name(request):
    slug = re.sub(r"[^a-z0-9]+", "_", request.casefold()).strip("_")
    return f"bridge_{slug or 'capability'}"


def discover_function(*, request, capabilities=None, authorized_capabilities=None,
                      observations=None, constraints=None, tests=None, request_id=None,
                      profile=Profile()):
    if type(request) is not str or not request.strip() or len(request) > 256:
        raise QuantumComputeError("DiscoverFunction request must be nonempty text up to 256 characters")
    request = request.strip()
    capabilities = _string_list(capabilities, "capabilities")
    authorized_capabilities = _string_list(authorized_capabilities, "authorized_capabilities")
    observations = _records(observations, "observations", 256)
    tests = _records(tests, "tests", 128)
    constraints = {} if constraints is None else constraints
    if type(constraints) is not dict:
        raise QuantumComputeError("constraints must be an object")
    canonical(constraints)
    if request_id is None:
        request_id = digest({"request": request, "observations": observations})[:24]
    if type(request_id) is not str or not request_id or len(request_id) > 128:
        raise QuantumComputeError("request_id must be nonempty text up to 128 characters")

    if request in capabilities:
        state = "EXISTING"
        function_name = request
        next_step = "Use the existing callable within the caller's execution grant."
    elif request not in authorized_capabilities:
        state = "UNRESOLVED"
        function_name = None
        next_step = f"Obtain an authorized capability receipt for {request} before synthesis."
    else:
        state = "PROPOSED"
        function_name = _candidate_name(request)
        next_step = "Forge and test the bounded candidate before any registration or deployment."

    evidence = {
        "observations_sha256": digest(observations),
        "constraints_sha256": digest(constraints),
        "tests_sha256": digest(tests),
        "capabilities_sha256": digest(capabilities),
        "authorized_capabilities_sha256": digest(authorized_capabilities),
    }
    return {
        "schema": SCHEMA,
        "skill": "xi-discover-function",
        "skill_version": "0.1.0",
        "request_id": request_id,
        "request": request,
        "state": state,
        "route": ROUTES[state],
        "function_name": function_name,
        "evidence": evidence,
        "tests_declared": len(tests),
        "tests_executed": 0,
        "authorization": "present_for_synthesis" if request in authorized_capabilities else "not_present",
        "registered": False,
        "next_step": next_step,
        "invariants": [
            "proposal_is_not_execution",
            "tested_is_not_deployed",
            "unresolved_is_lawful",
            "manifest_does_not_transfer_authority",
            "provenance_and_null_state_preserved",
        ],
        "resources": {"memory_budget_mib": profile.memory_mib},
    }
