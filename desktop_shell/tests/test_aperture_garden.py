import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


class FakeResponse:
    def __init__(self, text):
        self._text = text

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "message":{"content":self._text},
            "eval_count":10,
            "prompt_eval_count":20,
        }


class FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, json):
        return FakeResponse("reply from " + json["model"])


class ApertureGardenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XI_SHELL_HOME"] = self.tmp.name
        import core
        import runtime
        import aperture_garden
        self.core = importlib.reload(core)
        self.runtime = importlib.reload(runtime)
        self.aperture = importlib.reload(aperture_garden)
        self.core.ensure_home()

    def tearDown(self):
        self.tmp.cleanup()

    def test_compare_is_receipted_and_does_not_append_turns(self):
        src = self.core.store_source("pasted_conversation", "seed", b"hello")
        self.core.add_messages(src.id, "conv-1", [{
            "role":"user","author":"Hunter","content":"hello"
        }])

        before = self.core.recent_local_turns("conv-1")

        with patch.object(self.aperture, "list_ollama_models", return_value=[
            {"name":"mistral:latest"},
            {"name":"qwen3:8b"},
        ]), patch.object(self.aperture.httpx, "Client", FakeClient):
            result = self.aperture.compare_apertures(
                "conv-1",
                "What do you find here?",
                models=["mistral:latest","qwen3:8b"],
            )

        after = self.core.recent_local_turns("conv-1")
        self.assertEqual(before, after)
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(all(x["ok"] for x in result["results"]))
        self.assertEqual(
            len({x["context_sha256"] for x in result["results"]}),
            1,
        )
        self.assertTrue(Path(result["receipt_path"]).exists())
        self.assertEqual(result["mutation"], "none")


if __name__ == "__main__":
    unittest.main()
