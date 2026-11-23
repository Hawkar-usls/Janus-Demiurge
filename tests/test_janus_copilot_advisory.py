import importlib.util
import os
import pathlib
import unittest
from unittest.mock import patch

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "janus_copilot_advisory.py"
spec = importlib.util.spec_from_file_location("janus_copilot_advisory", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ContractTests(unittest.TestCase):
    def test_missing_credentials_denied(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(module.authorized())

    def test_advisory_never_claims_authority(self):
        result = module.package_result("suggestion", "auto")
        self.assertFalse(result["applied"])
        self.assertEqual(result["status"], "ADVISORY_ONLY")
        self.assertTrue(result["requires_human_or_policy_gate"])
        self.assertFalse(any(result["permissions"].values()))

    def test_result_is_bounded(self):
        result = module.package_result("x" * (module.MAX_ANSWER + 100), "auto")
        self.assertEqual(len(result["reply"]), module.MAX_ANSWER)


if __name__ == "__main__":
    unittest.main()
