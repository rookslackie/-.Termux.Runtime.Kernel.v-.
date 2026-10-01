import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


class ThreadImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XI_SHELL_HOME"] = self.tmp.name

        import core
        import thread_import
        self.core = importlib.reload(core)
        self.thread_import = importlib.reload(thread_import)
        self.core.ensure_home()

    def tearDown(self):
        self.tmp.cleanup()

    def test_parses_human_and_companion_roles(self):
        text = """Hunter:
Hello.

Anam:
Hi.

Hunter:
What do you find here?
"""
        messages = self.thread_import._parse_pasted_dialogue(text)
        self.assertEqual([m["role"] for m in messages], ["user", "assistant", "user"])
        self.assertEqual(messages[0]["author"], "Hunter")
        self.assertEqual(messages[1]["author"], "Anam")

    def test_preserves_multiline_turns(self):
        text = """Hunter:
First line.
Second line.

Anam:
Reply line.
"""
        messages = self.thread_import._parse_pasted_dialogue(text)
        self.assertIn("Second line.", messages[0]["content"])
        self.assertEqual(messages[1]["role"], "assistant")


if __name__ == "__main__":
    unittest.main()
