import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


class DesktopShellTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XI_SHELL_HOME"] = self.tmp.name
        import core
        self.core = importlib.reload(core)

    def tearDown(self):
        self.tmp.cleanup()

    def test_home_is_created_with_tools_off(self):
        self.core.ensure_home()
        config = self.core.load_config()
        self.assertFalse(config["tools_enabled"])
        self.assertEqual(config["allowed_roots"], [])

    def test_source_is_content_addressed(self):
        a = self.core.store_source("pasted_conversation", "x", b"hello")
        b = self.core.store_source("pasted_conversation", "x", b"hello")
        self.assertEqual(a.id, b.id)
        self.assertEqual(a.sha256, b.sha256)

    def test_context_receipt_is_written(self):
        source = self.core.store_source("pasted_conversation", "x", b"hello")
        self.core.add_messages(source.id, "conv-1", [{
            "role":"user", "author":"Hunter", "content":"hello"
        }])
        built = self.core.build_context("conv-1")
        self.assertTrue(Path(built["receipt"]["receipt_path"]).exists())
        self.assertEqual(built["receipt"]["source_message_count"], 1)

    def test_tools_fail_closed(self):
        with self.assertRaises(PermissionError):
            self.core.tool_list_dir(self.tmp.name)

    def test_tools_only_read_allowed_root(self):
        self.core.ensure_home()
        cfg = self.core.load_config()
        cfg["tools_enabled"] = True
        cfg["allowed_roots"] = [self.tmp.name]
        self.core.save_config(cfg)
        p = Path(self.tmp.name) / "note.txt"
        p.write_text("hello", encoding="utf-8")
        result = self.core.tool_read_file(str(p))
        self.assertEqual(result["text"], "hello")
        self.assertTrue(Path(result["receipt_path"]).exists())


if __name__ == "__main__":
    unittest.main()
