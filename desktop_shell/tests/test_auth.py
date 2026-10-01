import importlib
import os
import tempfile
import unittest
from pathlib import Path


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XI_SHELL_HOME"] = self.tmp.name

        import core
        import auth
        self.core = importlib.reload(core)
        self.auth = importlib.reload(auth)

    def tearDown(self):
        self.tmp.cleanup()

    def test_token_is_created_and_stable(self):
        a = self.auth.ensure_token()
        b = self.auth.ensure_token()
        self.assertTrue(a)
        self.assertEqual(a, b)
        self.assertTrue((Path(self.tmp.name) / "access.token").exists())


if __name__ == "__main__":
    unittest.main()
