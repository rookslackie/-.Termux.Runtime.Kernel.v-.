"""Reproducible tests for the local capsule/DAG world prototype."""

import unittest

from xi_world.demo import open_seed_world
from xi_world.kernel import WorldError


class XiWorldKernelTests(unittest.TestCase):
    def test_world_transitions_persist_with_distinct_actor_identity(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "world.sqlite3"
            kernel = open_seed_world(db_path)
            sown = kernel.apply("core-origin-garden", "hunter", "sow_seed", "sunflower-1",
                                idempotency_key="test-sow")
            watered = kernel.autonomous_turn("core-origin-garden", "axiom", idempotency_key="test-water")
            self.assertIsNotNone(watered)
            self.assertEqual(watered.actor_id, "axiom")
            self.assertEqual(watered.causes, (sown.event_id,))
            state = kernel.get_state("core-origin-garden")
            self.assertEqual(state["entities"]["garden"]["state"]["moisture"], "damp")

            kernel.apply("core-origin-garden", "world:environment", "advance_day", "garden",
                         causes=[watered.event_id], idempotency_key="test-day",
                         data={"seed_id": "sunflower-1"})
            reopened = open_seed_world(db_path)
            final = reopened.get_state("core-origin-garden")
            self.assertEqual(final["entities"]["sunflower-1"]["state"]["status"], "sprouted")
            self.assertEqual([e.actor_id for e in reopened.events("core-origin-garden")[-3:]],
                             ["hunter", "axiom", "world:environment"])
            ancestors = reopened.causal_ancestors("core-origin-garden", reopened.events("core-origin-garden")[-1].event_id)
            self.assertEqual([event.event_id for event in ancestors],
                             [reopened.events("core-origin-garden")[0].event_id, sown.event_id, watered.event_id])
            self.assertTrue(reopened.verify("core-origin-garden")["ok"])


    def test_idempotency_and_invalid_transition_are_atomic(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            kernel = open_seed_world(Path(tmp) / "world.sqlite3")
            first = kernel.apply("core-origin-garden", "hunter", "sow_seed", "sunflower-1",
                                 idempotency_key="same-request")
            duplicate = kernel.apply("core-origin-garden", "hunter", "sow_seed", "sunflower-1",
                                     idempotency_key="same-request")
            self.assertEqual(duplicate.event_id, first.event_id)
            with self.assertRaisesRegex(WorldError, "different transition"):
                kernel.apply("core-origin-garden", "hunter", "water_garden", "garden",
                             idempotency_key="same-request", data={"seed_id": "sunflower-1"})
            count = len(kernel.events("core-origin-garden"))
            with self.assertRaisesRegex(WorldError, "only a carried seed"):
                kernel.apply("core-origin-garden", "hunter", "sow_seed", "sunflower-1",
                             idempotency_key="invalid-resow")
            self.assertEqual(len(kernel.events("core-origin-garden")), count)
            self.assertTrue(kernel.verify("core-origin-garden")["ok"])


    def test_autonomy_is_a_bounded_local_rule_and_noop_leaves_no_event(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            kernel = open_seed_world(Path(tmp) / "world.sqlite3")
            self.assertIsNone(kernel.autonomous_turn("core-origin-garden", "axiom", idempotency_key="before-plant"))
            kernel.apply("core-origin-garden", "hunter", "sow_seed", "sunflower-1", idempotency_key="plant")
            water = kernel.autonomous_turn("core-origin-garden", "axiom", idempotency_key="water")
            self.assertIsNotNone(water)
            self.assertEqual(water.action, "water_garden")
            self.assertIsNone(kernel.autonomous_turn("core-origin-garden", "axiom", idempotency_key="already-damp"))
            with self.assertRaisesRegex(WorldError, "only to a local_agent"):
                kernel.autonomous_turn("core-origin-garden", "hunter", idempotency_key="human-auto")

    def test_event_ledger_and_participant_identity_are_append_only(self):
        import sqlite3
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "world.sqlite3"
            kernel = open_seed_world(path)
            with sqlite3.connect(path) as db:
                with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                    db.execute("UPDATE capsules SET content='rewritten' WHERE sequence=1")
                with self.assertRaisesRegex(sqlite3.IntegrityError, "identities are immutable"):
                    db.execute("UPDATE participants SET display_name='Other' WHERE participant_id='axiom'")


if __name__ == "__main__":
    unittest.main()

