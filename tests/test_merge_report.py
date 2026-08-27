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
            "scope": {"asin": "ASIN_PLACEHOLDER"},
            "current_listing_gate": "NO_KNOWN_OFFICIAL_ISSUES",
            "candidate_preview_gate": "PASS",
            "candidate_local_validation_gate": "PASS",
            "release_decision": "PASS",
            "official_validation_completeness": "COMPLETE",
            "official_evidence_coverage": {},
            "ptd_validation_coverage": {},
            "counts": {},
            "findings": [],
        }

    def assessment(self, rating="STRONG"):
        return {
            "assessment_version": "1.1",
            "assessment_model": "test-model",
            "prompt_version": "quality-v1.3.1",
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
        self.assertEqual(10.0, merged["executive_summary"]["quality_score"]["value"])
        self.assertFalse(merged["executive_summary"]["quality_score"]["official"])

    def test_any_weak_needs_improvement(self):
        assessment = self.assessment("ADEQUATE")
        assessment["dimensions"]["intent_coverage"]["rating"] = "WEAK"
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertTrue(valid)
        self.assertEqual("NEEDS_IMPROVEMENT", merged["quality_verdict"])
        self.assertEqual(
            "intent_coverage", merged["executive_summary"]["primary_reason"]["dimension"]
        )

    def test_score_uses_documented_rating_points(self):
        assessment = self.assessment("ADEQUATE")
        assessment["dimensions"]["content_completeness"]["rating"] = "STRONG"
        assessment["dimensions"]["intent_coverage"]["rating"] = "WEAK"
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertTrue(valid)
        score = merged["executive_summary"]["quality_score"]
        self.assertEqual(6.9, score["value"])
        self.assertEqual({"STRONG": 10.0, "ADEQUATE": 7.0, "WEAK": 3.0}, score["rating_points"])

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
        self.assertEqual("SCORED", merged["executive_summary"]["quality_score"]["status"])

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

    def test_assessment_trace_metadata_is_required_and_preserved(self):
        assessment = self.assessment()
        assessment.pop("assessment_model")
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("assessment_model is required" in error for error in merged["errors"]))

        assessment = self.assessment()
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertTrue(valid)
        self.assertEqual("test-model", merged["quality_assessment_trace"]["assessment_model"])

    def test_assessed_at_requires_timezone(self):
        assessment = self.assessment()
        assessment["assessed_at"] = "2026-01-01T00:00:00"
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("timezone-aware" in error for error in merged["errors"]))

    def test_fewer_than_five_dimensions_is_not_scored(self):
        assessment = self.assessment("ADEQUATE")
        for name in MODULE.DIMENSIONS[4:]:
            assessment["dimensions"][name] = {
                "rating": "NOT_EVALUATED",
                "rationale": "",
                "evidence": [],
                "missing_evidence": ["required evidence"],
            }
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertTrue(valid)
        score = merged["executive_summary"]["quality_score"]
        self.assertEqual("NOT_SCORED", score["status"])
        self.assertIsNone(score["value"])
        self.assertEqual(4, score["evaluated_dimensions"])

    def test_suggested_rewrite_requires_source_evidence(self):
        assessment = self.assessment("ADEQUATE")
        assessment["recommendations"] = [{
            "priority": "HIGH",
            "dimension": "clarity_and_readability",
            "attribute": "item_name",
            "current_problem": "The title omits a verified capacity.",
            "action": "Rewrite the title using supplied facts.",
            "suggested_value": "Example Brand Bottle, 24 oz",
            "completion_criterion": "The title passes PTD and Preview.",
        }]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("source_evidence" in error for error in merged["errors"]))

        assessment["recommendations"][0]["source_evidence"] = [{
            "field": "attributes.capacity",
            "quote_or_value": "24 oz",
        }]
        assessment["dimensions"]["clarity_and_readability"]["evidence"].append({
            "field": "attributes.capacity",
            "quote_or_value": "24 oz",
        })
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertTrue(valid)
        action = merged["executive_summary"]["primary_action"]
        self.assertEqual("Example Brand Bottle, 24 oz", action["suggested_value"])
        self.assertTrue(action["rewrite_is_advisory"])

    def test_suggested_rewrite_rejects_unverified_source_value(self):
        assessment = self.assessment("ADEQUATE")
        assessment["recommendations"] = [{
            "priority": "HIGH",
            "dimension": "clarity_and_readability",
            "attribute": "item_name",
            "current_problem": "The title omits a verified capacity.",
            "action": "Rewrite the title using supplied facts.",
            "suggested_value": "Example Brand Bottle, 48 oz",
            "source_evidence": [{"field": "attributes.capacity", "quote_or_value": "48 oz"}],
            "completion_criterion": "The title passes PTD and Preview.",
        }]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("must match evidence" in error for error in merged["errors"]))

    def test_suggested_rewrite_cannot_target_unassessed_dimension(self):
        assessment = self.assessment("ADEQUATE")
        assessment["dimensions"]["clarity_and_readability"] = {
            "rating": "NOT_EVALUATED",
            "rationale": "",
            "evidence": [],
            "missing_evidence": ["localized title"],
        }
        assessment["recommendations"] = [{
            "priority": "HIGH",
            "dimension": "clarity_and_readability",
            "attribute": "item_name",
            "current_problem": "The title was not supplied.",
            "action": "Rewrite the title.",
            "suggested_value": "Example Brand Bottle, 24 oz",
            "source_evidence": [{"field": "capacity", "quote_or_value": "24 oz"}],
            "completion_criterion": "A localized title is supplied.",
        }]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("NOT_EVALUATED" in error for error in merged["errors"]))

    def test_summary_does_not_change_official_gates(self):
        report = self.official_report()
        report["release_decision"] = "BLOCK"
        report["findings"] = [{
            "status": "OFFICIAL_ERROR",
            "code": "PTD_CONSTRAINT_VIOLATION",
            "message": "The candidate violates a bound constraint.",
        }]
        merged, valid = MODULE.merge_report(report, self.assessment())
        self.assertTrue(valid)
        self.assertEqual("BLOCK", merged["release_decision"])
        self.assertEqual("BLOCK", merged["executive_summary"]["official"]["release_decision"])
        self.assertEqual("OFFICIAL_EVIDENCE", merged["executive_summary"]["primary_reason"]["source"])
        self.assertEqual(
            "FIX_OFFICIAL_BLOCKER_AND_REVALIDATE",
            merged["executive_summary"]["primary_action"]["action_code"],
        )

    def test_nonapplicable_official_finding_is_not_primary(self):
        report = self.official_report()
        report["release_decision"] = "BLOCK"
        report["findings"] = [
            {
                "status": "OFFICIAL_ERROR",
                "code": "STALE_FOREIGN_ERROR",
                "message": "This error belongs to another candidate.",
                "applies_to_candidate": False,
            },
            {
                "status": "OFFICIAL_ERROR",
                "code": "PTD_CONSTRAINT_VIOLATION",
                "message": "The current candidate violates a constraint.",
                "applies_to_candidate": True,
            },
        ]
        merged, valid = MODULE.merge_report(report, self.assessment())
        self.assertTrue(valid)
        self.assertEqual(
            "PTD_CONSTRAINT_VIOLATION",
            merged["executive_summary"]["primary_reason"]["code"],
        )


if __name__ == "__main__":
    unittest.main()
