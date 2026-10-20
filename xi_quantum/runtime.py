"""FullCycle execution and return over TESSERA plans and WorldKernel SQLite."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import fcntl
from pathlib import Path

from xi_world.kernel import WorldError, WorldKernel
from . import algorithms
from .common import Profile, QuantumComputeError, VerifiedCheckpoint, digest, integer
from .tessera import compile_program, GLYPHS
from ._vendor.event_fabric import EventEnvelope, EventReceipt, NodeState, PhaseAwareEventFabric


ACTOR = "world:quantumcompute"
ENTITY = "quantum-stack"


@dataclass(frozen=True)
class ExecutionGrant:
    """Local caller authority; received capsules and checksums never supply this."""
    program_sha256: str
    operations: frozenset


class Runtime:
    def __init__(self, home, *, profile=Profile()):
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        self.profile = profile
        self.kernel = WorldKernel(self.home / "quantum.sqlite3")
        with self.kernel._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS quantum_sources (
                    digest TEXT PRIMARY KEY, raw BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS quantum_imports (
                    packet_digest TEXT PRIMARY KEY, sender TEXT NOT NULL, sequence INTEGER NOT NULL,
                    source_digest TEXT NOT NULL, checkpoint BLOB NOT NULL, received_wire BLOB NOT NULL,
                    UNIQUE(sender,sequence));
                CREATE TABLE IF NOT EXISTS quantum_outbox (
                    request_key TEXT PRIMARY KEY, recipient TEXT NOT NULL, wire BLOB NOT NULL,
                    request_sha256 TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS quantum_counters (
                    recipient TEXT PRIMARY KEY, sequence INTEGER NOT NULL);
            """)

    def ingest(self, raw):
        if type(raw) is not bytes or len(raw) > 1024 * 1024:
            raise QuantumComputeError("Store at most 1 MiB of exact source per capsule")
        source_id = digest(raw)
        with self.kernel._connect() as db:
            db.execute("INSERT OR IGNORE INTO quantum_sources VALUES (?, ?)", (source_id, raw))
        return source_id

    def source(self, source_id):
        with self.kernel._connect() as db:
            row = db.execute("SELECT raw FROM quantum_sources WHERE digest=?", (source_id,)).fetchone()
        if row is None or digest(row[0]) != source_id:
            raise QuantumComputeError("Source is missing or its commitment failed")
        return row[0]

    def _execute(self, step):
        name, params = step["operator"], step["parameters"]
        if name in ("Grover", "Shor", "JacobianFlow"):
            function = {"Grover": algorithms.grover, "Shor": algorithms.shor,
                        "JacobianFlow": algorithms.jacobian_flow}[name]
            return function(**params, profile=self.profile)
        if name == "PhaseCodeBenchmark":
            from xi_field.noise_benchmark import run
            return run(**params, database=None, ledger_trials=0)
        if name == "ObserverBenchmark":
            from .observer import run
            return run(**params, profile=self.profile)
        return {"state": "sealed" if name == "Seal" else "rest", "return_operator": "⟁∴Ω"}

    def run(self, raw, *, grant: ExecutionGrant, stop_after=None, recovered=None):
        with (self.home / "execution.lock").open("a") as lease:
            try:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise QuantumComputeError("Another executor is active in this local home") from exc
            try:
                return self._run(raw, grant=grant, stop_after=stop_after, recovered=recovered)
            finally:
                fcntl.flock(lease, fcntl.LOCK_UN)

    def _run(self, raw, *, grant: ExecutionGrant, stop_after=None, recovered=None):
        if stop_after is not None:
            integer(stop_after, "stop_after", 0)
        plan = compile_program(raw)
        required = frozenset(step["operator"] for step in plan.steps)
        if not isinstance(grant, ExecutionGrant) or grant.program_sha256 != plan.program_sha256 or not required <= grant.operations:
            raise QuantumComputeError("Local execution grant does not cover this exact program and operation set")
        self.ingest(raw)
        world_id = "quantum-" + digest({"program": plan.program_sha256, "plan": plan.plan_sha256,
                                        "profile": asdict(self.profile)})[:32]
        try:
            state = self.kernel.get_state(world_id)["entities"][ENTITY]["state"]
        except WorldError:
            self.kernel.create_world(world_id, "Ξ.QuantumCompute FullCycle", participants=[{
                "participant_id": ACTOR, "display_name": "Xi QuantumCompute", "kind": "local_runtime",
                "identity": {"grammar": plan.dialect, "engine_sha256": plan.engine_sha256}}], entities=[{
                    "entity_id": ENTITY, "kind": "quantum_session", "state": {
                        "executor_id": ACTOR, "source_sha256": plan.program_sha256,
                        "plan_sha256": plan.plan_sha256, "engine_sha256": plan.engine_sha256,
                        "steps": list(plan.steps), "completed": [], "closed": False, "fabric_phases": {},
                    }}])
            state = self.kernel.get_state(world_id)["entities"][ENTITY]["state"]
        fabric = PhaseAwareEventFabric([
            NodeState(name, phase=state["fabric_phases"].get(name, 0), accepted_operators={name},
                      accepted_payload_types={"capsule"}, boundaries={"local.execute"}) for name in GLYPHS
        ])
        for item in state["completed"]:
            fabric.receipts.append(EventReceipt(**item["route"]))
        if recovered is not None and not isinstance(recovered, VerifiedCheckpoint):
            raise QuantumComputeError("Peer recovery needs a verified ThinkSync checkpoint")
        imported = self._validate_checkpoint(plan, recovered.checkpoint) if recovered is not None else []
        for index, local in enumerate(state["completed"]):
            if index < len(imported) and digest(local["result"]) != digest(imported[index]["result"]):
                raise QuantumComputeError("Parallax: local and peer result branches differ; both are retained")
        executed, restored, start = 0, 0, len(state["completed"])
        for step in plan.steps[start:]:
            if stop_after is not None and executed + restored >= stop_after:
                break
            index, name = step["index"], step["operator"]
            if index < len(imported):
                result = imported[index]["result"]
                origin = {"kind": "peer_checkpoint", "original_event_id": imported[index]["event_id"],
                          "original_route_digest": imported[index]["route"]["digest"],
                          "sender": recovered.sender, "envelope_sha256": recovered.envelope_sha256}
                restored += 1
            else:
                result, origin = self._execute(step), "local_execution"
                executed += 1
            envelope = EventEnvelope(anchor=plan.anchor, operator="≈∅" if name == "Rest" else name, source=ACTOR, target=name,
                payload_type="capsule", payload={"result_sha256": digest(result)},
                capsule_refs=(plan.program_sha256,), phase=step["phase"],
                boundary={"requires": ["local.execute"], "wake": True},
                provenance={"dialect": plan.dialect, "plan_sha256": plan.plan_sha256,
                            "engine_sha256": plan.engine_sha256})
            route = fabric.submit(envelope)
            self.kernel.apply(world_id, ACTOR, "quantum.transition", ENTITY,
                idempotency_key=f"step-{index}", data={"index": index, "operator": name,
                    "result": result, "origin": origin, "event": envelope.as_dict(), "route": route.as_dict(),
                    "fabric_phases": {name: node.phase for name, node in fabric.nodes.items()}})
            if name == "Rest" or route.next_operator in ("Parallax", "Question"):
                break
        state = self.kernel.get_state(world_id)["entities"][ENTITY]["state"]
        integrity = self.kernel.verify(world_id)
        if not integrity["ok"]:
            raise QuantumComputeError("Quantum capsule ledger failed integrity verification")
        return {"schema": "xi.quantumcompute.receipt.v2", "world_id": world_id,
                "source_sha256": plan.program_sha256, "plan_sha256": plan.plan_sha256,
                "engine_sha256": plan.engine_sha256, "closed": state["closed"],
                "completed_steps": len(state["completed"]), "executed_this_call": executed,
                "restored_from_peer_this_call": restored, "steps": state["completed"], "integrity": integrity}

    def checkpoint(self, receipt):
        state = self.kernel.get_state(receipt["world_id"])["entities"][ENTITY]["state"]
        if not self.kernel.verify(receipt["world_id"])["ok"]:
            raise QuantumComputeError("Cannot export a broken capsule chain")
        return {"schema": "xi.quantumcompute.checkpoint.v2", "source_sha256": state["source_sha256"],
                "plan_sha256": state["plan_sha256"], "engine_sha256": state["engine_sha256"],
                "profile": asdict(self.profile), "world_id": receipt["world_id"],
                "events": [asdict(event) for event in self.kernel.events(receipt["world_id"])]}

    def _validate_checkpoint(self, plan, checkpoint):
        from xi_world.kernel import Event, _hash
        if (checkpoint.get("schema") != "xi.quantumcompute.checkpoint.v2"
                or checkpoint.get("source_sha256") != plan.program_sha256
                or checkpoint.get("plan_sha256") != plan.plan_sha256
                or checkpoint.get("engine_sha256") != plan.engine_sha256
                or checkpoint.get("profile") != asdict(self.profile)):
            raise QuantumComputeError("Peer checkpoint belongs to different source, engine, or resource profile")
        previous, known, completed, state = None, set(), [], None
        for sequence, item in enumerate(checkpoint.get("events", []), 1):
            event = Event(**item)
            if (event.world_id != checkpoint.get("world_id") or event.sequence != sequence or event.previous_hash != previous
                    or _hash(self.kernel._event_material(event)) != event.event_hash
                    or any(parent not in known for parent in event.causes)):
                raise QuantumComputeError("Peer checkpoint hash chain or causal order failed")
            if sequence == 1:
                initial = event.data.get("initial_entities", {}).get(ENTITY, {})
                if (event.action != "world.genesis" or initial.get("source_sha256") != plan.program_sha256
                        or initial.get("plan_sha256") != plan.plan_sha256
                        or initial.get("engine_sha256") != plan.engine_sha256
                        or initial.get("steps") != list(plan.steps)):
                    raise QuantumComputeError("Peer checkpoint is missing genesis")
                state = initial
            else:
                if event.action != "quantum.transition" or not event.causes:
                    raise QuantumComputeError("Unexpected event in peer computation checkpoint")
                # Re-evaluate protocol and result commitments without re-running computation.
                from .ledger import transition
                if len(completed) >= len(plan.steps):
                    raise QuantumComputeError("Peer checkpoint extends past the compiled program")
                if event.target_id != ENTITY:
                    raise QuantumComputeError("Peer event targets a different state entity")
                state = transition(state, event.actor_id, event.data, event.event_id)
                if event.echo.get(ENTITY) != state:
                    raise QuantumComputeError("Peer state echo does not follow its committed transition")
                completed = state["completed"]
            known.add(event.event_id)
            previous = event.event_hash
        if not known:
            raise QuantumComputeError("Peer checkpoint is empty")
        return completed
