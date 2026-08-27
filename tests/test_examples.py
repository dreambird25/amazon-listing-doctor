import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "amazon-listing-doctor"
SCRIPT = SKILL / "scripts" / "diagnose_listing.py"
SPEC = importlib.util.spec_from_file_location("diagnose_listing_examples", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

MERGE_SCRIPT = SKILL / "scripts" / "merge_report.py"
MERGE_SPEC = importlib.util.spec_from_file_location("merge_report_examples", MERGE_SCRIPT)
MERGE_MODULE = importlib.util.module_from_spec(MERGE_SPEC)
assert MERGE_SPEC.loader is not None
MERGE_SPEC.loader.exec_module(MERGE_MODULE)


class ExampleFixtureTest(unittest.TestCase):

    def test_example_gates(self):
        expected = {
            "listing-valid.json": (
                "NO_KNOWN_OFFICIAL_ISSUES", "PASS", "REVIEW"
            ),
            "listing-full-schema-valid.json": (
                "NO_KNOWN_OFFICIAL_ISSUES", "PASS", "PASS"
            ),
            "listing-blocked.json": ("BLOCK", "BLOCK", "BLOCK"),
            "listing-incomplete.json": (
                "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED"
            ),
            "listing-practice-sanitized.json": (
                "BLOCK", "NOT_EVALUATED", "BLOCK"
            ),
        }
        for filename, gates in expected.items():
            with self.subTest(filename=filename):
                data = json.loads((SKILL / "examples" / filename).read_text(encoding="utf-8"))
                report = MODULE.diagnose(data)
                self.assertEqual(gates[0], report["current_listing_gate"])
                self.assertEqual(gates[1], report["candidate_preview_gate"])
                self.assertEqual(gates[2], report["release_decision"])
                expected_full = filename == "listing-full-schema-valid.json"
                self.assertEqual(
                    "FULL_JSON_SCHEMA" if expected_full else "LIGHTWEIGHT_SUBSET",
                    report["ptd_validation_coverage"]["mode"],
                )
                self.assertEqual(
                    expected_full, report["ptd_validation_coverage"]["full_schema_validation"]
                )

    def test_semantic_example_merges_with_valid_report(self):
        listing = json.loads((SKILL / "examples" / "listing-valid.json").read_text(encoding="utf-8"))
        assessment = json.loads(
            (SKILL / "examples" / "semantic-assessment.json").read_text(encoding="utf-8")
        )
        official_report = MODULE.diagnose(listing)
        merged, valid = MERGE_MODULE.merge_report(official_report, assessment)
        self.assertTrue(valid)
        self.assertEqual("NEEDS_IMPROVEMENT", merged["quality_verdict"])
        self.assertEqual("PARTIAL", merged["quality_evidence_completeness"])


if __name__ == "__main__":
    unittest.main()
