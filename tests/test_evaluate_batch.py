import importlib.util
import json
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
from merge_report import DIMENSIONS
from quality_contract import official_report_sha256, sha256_json


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

    def test_quality_summary_mode_regresses_bound_concise_outcomes(self):
        private_marker = "PRIVATE-ASIN-OR-SKU"
        listing = json.loads(
            (ROOT / ".agents" / "skills" / "amazon-listing-doctor" / "examples"
             / "listing-valid.json").read_text(encoding="utf-8")
        )
        report = MODULE.diagnose(listing)
        context = report["quality_contexts"]["CURRENT"]
        title = listing["content"]["title"]
        assessment = {
            "assessment_version": "1.2",
            "assessment_model": "test-model",
            "prompt_version": "quality-v1.3.2",
            "assessed_at": "2026-01-01T00:00:03Z",
            "assessment_target": "CURRENT",
            "scope_fingerprint_sha256": context["scope_fingerprint_sha256"],
            "content_sha256": context["content_sha256"],
            "official_report_sha256": official_report_sha256(report),
            "evidence_manifest_sha256": context["evidence_manifest_sha256"],
            "dimensions": {
                name: {
                    "rating": "WEAK" if name == "clarity_and_readability" else "STRONG",
                    "rationale": "Synthetic bound evidence supports the regression expectation.",
                    "evidence": [{
                        "field_path": "$.current_content.title",
                        "quote_or_value": title,
                        "value_sha256": sha256_json(title),
                    }],
                    "missing_evidence": [],
                }
                for name in DIMENSIONS
            },
            "recommendations": [{
                "priority": "HIGH",
                "dimension": "clarity_and_readability",
                "action": "Improve title clarity using verified content.",
                "completion_criterion": "A reviewer confirms the revised title is clearer.",
            }],
            "limitations": ["Synthetic public regression fixture."],
        }
        samples = [{
            "sample_id": private_marker,
            "input": listing,
            "assessment": assessment,
            "expected_quality": {
                "quality_verdict": "NEEDS_IMPROVEMENT",
                "score_status": "FULL",
                "score_range": [9.0, 9.0],
                "comparable": True,
                "weak_dimensions": ["clarity_and_readability"],
                "primary_reason_dimension": "clarity_and_readability",
                "primary_action_dimension": "clarity_and_readability",
                "suggested_value_allowed": False,
            },
        }]
        result, valid = MODULE.evaluate_samples(samples, "quality-summary")
        self.assertTrue(valid)
        self.assertTrue(result["deterministic_rerun"])
        self.assertEqual("quality-summary", result["mode"])
        self.assertEqual({"FULL": 1}, result["quality_distributions"]["score_status"])
        self.assertNotIn(private_marker, str(result))
        self.assertNotIn(title, str(result))


if __name__ == "__main__":
    unittest.main()
