import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / ".agents" / "skills" / "amazon-listing-doctor" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location("evaluate_batch", SCRIPT_DIR / "evaluate_batch.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class EvaluateBatchTest(unittest.TestCase):

    def test_batch_output_is_aggregate_and_identifier_safe(self):
        private_marker = "PRIVATE-ASIN-OR-SKU"
        samples = [{
            "sample_id": private_marker,
            "input": {},
            "expected": {"release_decision": "NOT_EVALUATED"},
        }]
        result, valid = MODULE.evaluate_samples(samples)
        self.assertTrue(valid)
        self.assertTrue(result["deterministic_rerun"])
        self.assertNotIn(private_marker, str(result))
        self.assertEqual(0, result["expectation_mismatch_count"])


if __name__ == "__main__":
    unittest.main()
