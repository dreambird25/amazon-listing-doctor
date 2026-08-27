import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "amazon-listing-doctor"
    / "scripts"
    / "merge_report.py"
)
SPEC = importlib.util.spec_from_file_location("merge_report", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class MergeReportTest(unittest.TestCase):

    def official_report(self):
        return {
            "current_listing_gate": "NO_KNOWN_OFFICIAL_ISSUES",
            "candidate_preview_gate": "PASS",
            "release_decision": "PASS",
            "official_validation_completeness": "COMPLETE",
            "official_evidence_coverage": {},
            "ptd_validation_coverage": {},
            "counts": {},
            "findings": [],
        }

    def assessment(self, rating="STRONG"):
        return {
            "assessment_version": "1.0",
            "assessed_at": "2026-01-01T00:00:00Z",
            "dimensions": {
                name: {
                    "rating": rating,
                    "rationale": "Direct evidence supports this rating.",
                    "evidence": [{"field": "title", "quote_or_value": "Example title"}],
                    "missing_evidence": [],
                }
                for name in MODULE.DIMENSIONS
            },
            "recommendations": [],
            "limitations": ["No business performance metrics were supplied."],
        }

    def test_all_strong_is_strong_and_complete(self):
        merged, valid = MODULE.merge_report(self.official_report(), self.assessment())
        self.assertTrue(valid)
        self.assertEqual("OK", merged["merge_status"])
        self.assertEqual("STRONG", merged["quality_verdict"])
        self.assertEqual("COMPLETE", merged["quality_evidence_completeness"])
        self.assertEqual("NOT_EVALUATED", merged["performance_verdict"])
        self.assertEqual("PASS", merged["release_decision"])

    def test_any_weak_needs_improvement(self):
        assessment = self.assessment("ADEQUATE")
        assessment["dimensions"]["intent_coverage"]["rating"] = "WEAK"
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertTrue(valid)
        self.assertEqual("NEEDS_IMPROVEMENT", merged["quality_verdict"])

    def test_partial_without_weak_is_partially_evaluated(self):
        assessment = self.assessment("ADEQUATE")
        row = assessment["dimensions"]["localization_quality"]
        row.update({
            "rating": "NOT_EVALUATED",
            "rationale": "",
            "evidence": [],
            "missing_evidence": ["locale-specific content"],
        })
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertTrue(valid)
        self.assertEqual("PARTIALLY_EVALUATED", merged["quality_verdict"])
        self.assertEqual("PARTIAL", merged["quality_evidence_completeness"])

    def test_evaluated_rating_requires_direct_evidence(self):
        assessment = self.assessment()
        assessment["dimensions"]["content_completeness"]["evidence"] = []
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertEqual("SYSTEM_ERROR", merged["merge_status"])
        self.assertTrue(any("content_completeness requires evidence" in error for error in merged["errors"]))

    def test_all_dimensions_are_required(self):
        assessment = self.assessment()
        assessment["dimensions"].pop("buyer_question_coverage")
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("missing dimensions" in error for error in merged["errors"]))

    def test_official_report_contract_is_required(self):
        merged, valid = MODULE.merge_report({}, self.assessment())
        self.assertFalse(valid)
        self.assertTrue(any("official report is missing fields" in error for error in merged["errors"]))


if __name__ == "__main__":
    unittest.main()
