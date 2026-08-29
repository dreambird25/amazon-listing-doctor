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
        examples = ROOT / ".agents" / "skills" / "amazon-listing-doctor" / "examples"
        listing = json.loads((examples / "listing-valid.json").read_text(encoding="utf-8"))
        assessment = json.loads(
            (examples / "semantic-assessment.json").read_text(encoding="utf-8")
        )
        samples = [{
            "sample_id": private_marker,
            "input": listing,
            "assessment": assessment,
            "expected_quality": {
                "quality_verdict": "NEEDS_IMPROVEMENT",
                "score_status": "PARTIAL",
                "score_range": [6.2, 6.2],
                "structurally_comparable": False,
                "weak_dimensions": ["content_completeness", "image_information_coverage"],
                "primary_reason_dimension": "content_completeness",
                "primary_action_dimension": "content_completeness",
                "suggested_value_allowed": False,
                "fact_binding_count": 0,
                "unbound_fact_count": 0,
            },
        }]
        result, valid = MODULE.evaluate_samples(samples, "quality-summary")
        self.assertTrue(valid)
        self.assertTrue(result["deterministic_rerun"])
        self.assertEqual("golden-quality", result["mode"])
        self.assertEqual({"PARTIAL": 1}, result["quality_distributions"]["score_status"])
        self.assertNotIn(private_marker, str(result))
        self.assertNotIn(listing["content"]["title"], str(result))

    def test_golden_modes_reject_samples_without_expectations(self):
        sample = {"input": {}}
        for mode in ("golden-official", "golden-quality"):
            with self.subTest(mode=mode):
                result, valid = MODULE.evaluate_samples([sample], mode)
                self.assertFalse(valid)
                self.assertEqual(1, result["malformed_count"])

        result, valid = MODULE.evaluate_samples([{
            "input": {},
            "expected": {
                "release_decision": "NOT_EVALUATED",
                "release_decison": "NOT_EVALUATED",
            },
        }], "golden-official")
        self.assertFalse(valid)
        self.assertEqual(1, result["malformed_count"])

    def test_observation_mode_accepts_samples_without_expectations(self):
        result, valid = MODULE.evaluate_samples([{"input": {}}], "observation")
        self.assertTrue(valid)
        self.assertEqual("observation", result["mode"])
        self.assertEqual(0, result["malformed_count"])

    def test_quality_observation_aggregates_without_expected_quality(self):
        private_marker = "PRIVATE-ASIN-OR-SKU"
        examples = ROOT / ".agents" / "skills" / "amazon-listing-doctor" / "examples"
        listing = json.loads((examples / "listing-valid.json").read_text(encoding="utf-8"))
        assessment = json.loads(
            (examples / "semantic-assessment.json").read_text(encoding="utf-8")
        )

        result, valid = MODULE.evaluate_samples([{
            "sample_id": private_marker,
            "input": listing,
            "assessment": assessment,
        }], "quality-observation")

        self.assertTrue(valid)
        self.assertEqual("quality-observation", result["mode"])
        self.assertEqual(0, result["expectation_mismatch_count"])
        self.assertEqual(0, result["quality_merge_failure_count"])
        self.assertEqual(
            {"NEEDS_IMPROVEMENT": 1},
            result["quality_distributions"]["quality_verdict"],
        )
        self.assertEqual(
            {"WEAK": 1},
            result["quality_distributions"]["dimension_ratings"]
            ["image_information_coverage"],
        )
        self.assertEqual(
            {"False": 1}, result["quality_distributions"]["candidate_available"]
        )
        self.assertNotIn(private_marker, str(result))
        self.assertNotIn(listing["content"]["title"], str(result))

    def test_quality_observation_rejects_missing_or_invalid_assessment_safely(self):
        result, valid = MODULE.evaluate_samples(
            [{"input": {}}], "quality-observation"
        )
        self.assertFalse(valid)
        self.assertEqual(1, result["malformed_count"])

        private_marker = "PRIVATE-ASIN-OR-SKU"
        result, valid = MODULE.evaluate_samples([{
            "sample_id": private_marker,
            "input": {},
            "assessment": {"private_text": "DO-NOT-EMIT"},
        }], "quality-observation")
        self.assertFalse(valid)
        self.assertEqual(1, result["quality_merge_failure_count"])
        self.assertEqual("SYSTEM_ERROR", result["quality_merge_failures"][0]["merge_status"])
        self.assertNotIn(private_marker, str(result))
        self.assertNotIn("DO-NOT-EMIT", str(result))

    def test_empty_dataset_never_reports_success(self):
        for mode in (
                "observation", "quality-observation", "golden-official", "golden-quality",
        ):
            with self.subTest(mode=mode):
                result, valid = MODULE.evaluate_samples([], mode)
                self.assertFalse(valid)
                self.assertEqual("EMPTY", result["dataset_status"])

    def test_hmac_sample_reference_is_stable_and_identifier_safe(self):
        private_marker = "PRIVATE-ASIN-OR-SKU"
        private_key = "k" * 32
        samples = [{
            "sample_id": private_marker,
            "input": {},
            "expected": {"release_decision": "NOT_EVALUATED"},
        }]
        first, first_valid = MODULE.evaluate_samples(samples, sample_ref_key=private_key)
        second, second_valid = MODULE.evaluate_samples(samples, sample_ref_key=private_key)
        self.assertTrue(first_valid and second_valid)
        self.assertEqual("HMAC_SHA256", first["sample_reference_method"])
        self.assertEqual("V1", first["hmac_domain_separation"])
        self.assertEqual(first, second)
        self.assertNotIn(private_marker, str(first))

        private_suggestion = "PRIVATE-SUGGESTED-VALUE"
        report = {
            "quality_verdict": "ADEQUATE",
            "executive_summary": {
                "evaluated_dimension_average": {},
                "primary_reason": {},
                "primary_action": {"suggested_value": private_suggestion},
            },
        }
        without_key = MODULE.quality_snapshot(report)
        with_key = MODULE.quality_snapshot(report, private_key)
        self.assertIsNone(without_key["suggested_value_hmac_sha256"])
        self.assertEqual(64, len(with_key["suggested_value_hmac_sha256"]))
        self.assertNotIn(private_suggestion, str(with_key))

        sample_digest = MODULE.private_hmac(
            private_suggestion, private_key, MODULE.SAMPLE_REF_HMAC_DOMAIN
        )
        suggestion_digest = MODULE.private_hmac(
            private_suggestion, private_key, MODULE.SUGGESTED_VALUE_HMAC_DOMAIN
        )
        self.assertNotEqual(sample_digest, suggestion_digest)

    def test_quality_snapshot_uses_content_lane_when_official_evidence_is_missing(self):
        report = {
            "quality_verdict": "PARTIALLY_EVALUATED",
            "executive_summary": {
                "evaluated_dimension_average": {"status": "PARTIAL", "value": 7.0},
                "primary_reason": {
                    "source": "OFFICIAL_EVIDENCE",
                    "code": "LISTING_SNAPSHOT_MISSING",
                },
                "primary_action": {"action_code": "REVIEW_OFFICIAL_EVIDENCE"},
                "quality_primary_reason": {
                    "dimension": "clarity_and_readability",
                    "rating": "ADEQUATE",
                },
                "quality_primary_action": {
                    "dimension": "clarity_and_readability",
                    "action_code": "IMPROVE_CLARITY_WITH_BOUND_FACTS",
                },
                "official_primary_reason": {
                    "status": "NOT_EVALUATED",
                    "code": "LISTING_SNAPSHOT_MISSING",
                    "finding_source": "LISTINGS_ITEMS",
                },
                "official_primary_action": {
                    "action_code": "REVIEW_OFFICIAL_EVIDENCE",
                },
            },
        }

        snapshot = MODULE.quality_snapshot(report)

        self.assertEqual("clarity_and_readability", snapshot["primary_reason_dimension"])
        self.assertEqual(
            "IMPROVE_CLARITY_WITH_BOUND_FACTS", snapshot["primary_action_code"]
        )
        self.assertEqual("LISTING_SNAPSHOT_MISSING", snapshot["official_reason_code"])
        self.assertEqual("REVIEW_OFFICIAL_EVIDENCE", snapshot["official_action_code"])

    def test_hmac_key_must_have_at_least_32_utf8_bytes(self):
        with self.assertRaisesRegex(ValueError, "at least 32 UTF-8 bytes"):
            MODULE.evaluate_samples([{"input": {}}], "observation", "too-short")


if __name__ == "__main__":
    unittest.main()
