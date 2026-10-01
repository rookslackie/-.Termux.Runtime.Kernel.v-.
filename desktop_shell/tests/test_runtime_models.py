import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from runtime import _normalize_ollama_models


class RuntimeModelTests(unittest.TestCase):
    def test_normalize_ollama_models(self):
        payload = {
            "models": [
                {
                    "name":"qwen3:8b",
                    "size":123,
                    "details":{
                        "family":"qwen3",
                        "parameter_size":"8.2B",
                        "quantization_level":"Q4_K_M",
                    },
                },
                {
                    "model":"deepseek-r1:8b",
                    "size":456,
                    "details":{
                        "family":"qwen2",
                        "parameter_size":"8.2B",
                        "quantization_level":"Q4_K_M",
                    },
                },
            ]
        }
        rows = _normalize_ollama_models(payload)
        self.assertEqual([r["name"] for r in rows], ["deepseek-r1:8b", "qwen3:8b"])
        self.assertEqual(rows[1]["family"], "qwen3")


if __name__ == "__main__":
    unittest.main()
