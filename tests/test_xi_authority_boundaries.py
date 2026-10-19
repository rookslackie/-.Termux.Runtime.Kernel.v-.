"""Persistence and authority-boundary checks for the local Xi kernel.

The actor-label test documents the trusted local API boundary; it does not
misdescribe a participant label as authenticated OS identity.
"""

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from xi_field.runtime import bootstrap_field
from xi_world.demo import open_seed_world
from xi_world.kernel import WorldError


class XiBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "world.sqlite3"
        self.kernel = open_seed_world(self.path)
        self.world = "core-origin-garden"

    def tearDown(self):
        self.temp.cleanup()

    def test_unknown_participant_and_wrong_named_role_are_rejected(self):
        before = self.kernel.get_state(self.world)
        for actor in ("unknown", "hunter"):
            with self.subTest(actor=actor), self.assertRaises(WorldError):
                self.kernel.apply(self.world, actor, "advance_day", "garden", idempotency_key=actor,
                                  data={"seed_id": "sunflower-1"})
        self.assertEqual(self.kernel.get_state(self.world), before)

    def test_local_api_actor_label_is_attribution_not_authentication(self):
        event = self.kernel.apply(self.world, "world:environment", "advance_day", "garden",
                                  idempotency_key="label-only", data={"seed_id": "sunflower-1"})
        self.assertEqual(event.actor_id, "world:environment")
        # No OS principal/credential has been verified by this local Python API.
        self.assertTrue(self.kernel.verify(self.world)["ok"])

    def test_out_of_band_entity_mutation_is_detected_without_rewriting_it(self):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE entities SET state_json=? WHERE entity_id='garden'",
                       (json.dumps({"day": 999, "moisture": "dry"}),))
        verification = self.kernel.verify(self.world)
        self.assertFalse(verification["ok"])
        self.assertIn("materialized entity mismatch at garden", verification["errors"])
        self.assertEqual(self.kernel.get_state(self.world)["entities"]["garden"]["state"]["day"], 999)

    def test_missing_or_inserted_entity_is_detected(self):
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM entities WHERE entity_id='garden'")
            db.execute("INSERT INTO entities VALUES (?, 'injected', 'seed', '{}')", (self.world,))
        errors = self.kernel.verify(self.world)["errors"]
        self.assertIn("materialized entity mismatch at garden", errors)
        self.assertIn("materialized entity mismatch at injected", errors)

    def test_sqlite_capsule_trigger_rejects_updates_but_is_not_os_isolation(self):
        with sqlite3.connect(self.path) as db:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                db.execute("UPDATE capsules SET actor_id='unknown'")
            db.execute("DROP TRIGGER capsules_append_only_update")
            db.execute("UPDATE capsules SET actor_id='unknown'")
        self.assertFalse(self.kernel.verify(self.world)["ok"])

    def test_stale_head_decision_is_atomic_and_identical_retry_remains_valid(self):
        head = self.kernel.get_state(self.world)["head"]["event_hash"]
        first = self.kernel.apply(self.world, "hunter", "sow_seed", "sunflower-1",
                                  idempotency_key="sow", expected_head_hash=head)
        before = self.kernel.get_state(self.world)
        with self.assertRaisesRegex(WorldError, "stale decision"):
            self.kernel.apply(self.world, "world:environment", "advance_day", "garden",
                              idempotency_key="stale", expected_head_hash=head,
                              data={"seed_id": "sunflower-1"})
        self.assertEqual(self.kernel.get_state(self.world), before)
        replay = self.kernel.apply(self.world, "hunter", "sow_seed", "sunflower-1",
                                   idempotency_key="sow", expected_head_hash=head)
        self.assertEqual(replay, first)

    def test_field_symbolic_operators_keep_optimistic_head_check(self):
        field = bootstrap_field(Path(self.temp.name) / "field.sqlite3")
        head = field.kernel.get_state(field.world_id)["head"]["event_hash"]
        event = field.execute("reference", idempotency_key="ref", expected_head_hash=head)
        self.assertEqual(field.receipt(event)["actor_id"], "world:field-runtime")
        with self.assertRaisesRegex(WorldError, "stale decision"):
            field.execute("hadamard", idempotency_key="stale-h", expected_head_hash=head)
        self.assertTrue(field.kernel.verify(field.world_id)["ok"])

    def test_replay_across_process_exit_rejects_changed_intent(self):
        code = '''import json,sys,os
from xi_world.demo import open_seed_world
from xi_world.kernel import WorldError
k=open_seed_world(sys.argv[1])
try:
 e=k.apply('core-origin-garden','hunter',sys.argv[2],'sunflower-1',idempotency_key='process-stable')
 result={'event_id':e.event_id,'event_hash':e.event_hash,'pid':os.getpid()}
except WorldError as exc:
 result={'error':str(exc),'pid':os.getpid()}
print(json.dumps(result))
'''
        def child(action):
            return json.loads(subprocess.check_output([sys.executable, "-c", code, str(self.path), action],
                                                      cwd=Path(__file__).resolve().parents[1], timeout=15))
        first, second = child("sow_seed"), child("sow_seed")
        self.assertNotEqual(first["pid"], second["pid"])
        self.assertEqual(first["event_hash"], second["event_hash"])
        conflict = child("advance_day")
        self.assertIn("different transition", conflict["error"])
        self.assertEqual(len(self.kernel.events(self.world)), 2)


if __name__ == "__main__":
    unittest.main()
