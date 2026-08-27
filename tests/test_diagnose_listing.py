import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "amazon-listing-doctor"
    / "scripts"
    / "diagnose_listing.py"
)
SPEC = importlib.util.spec_from_file_location("diagnose_listing", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DiagnoseListingTest(unittest.TestCase):

    PAYLOAD_HASH = "a" * 64

    def base(self):
        return {
            "scope": {
                "seller_id": "SELLER_ID",
                "marketplace_id": "MARKETPLACE_ID",
                "sku": "SELLER_SKU",
                "product_type": "PRODUCT_TYPE",
                "requirements": "LISTING",
                "parentage_level": "CHILD",
                "locale": "en_US",
            },
            "candidate": {
                "operation": "PUT",
                "requirements": "LISTING",
                "parentage_level": "CHILD",
                "payload_sha256": self.PAYLOAD_HASH,
                "created_at": "2026-01-01T00:00:00Z",
            },
            "content": {
                "title": "Valid title",
                "images": [{
                    "is_main": True,
                    "width": 800,
                    "height": 1200,
                    "watermark": False,
                    "white_background": True,
                }],
            },
            "official": {
                "listing_issues": [],
                "validation_preview": {
                    "ran": True,
                    "mode": "VALIDATION_PREVIEW",
                    "operation": "PUT",
                    "payload_sha256": self.PAYLOAD_HASH,
                    "seller_id": "SELLER_ID",
                    "marketplace_id": "MARKETPLACE_ID",
                    "sku": "SELLER_SKU",
                    "product_type": "PRODUCT_TYPE",
                    "request_id": "REQUEST_ID",
                    "submission_id": "PREVIEW_ID",
                    "requested_at": "2026-01-01T00:00:01Z",
                    "responded_at": "2026-01-01T00:00:02Z",
                    "http_status": 200,
                    "status": "VALID",
                    "issues": [],
                },
                "ptd": {
                    "status": "FRESH",
                    "schema_checksum": "CHECKSUM",
                    "constraints": {
                        "item_name": [{"type": "MAX_LENGTH", "value": 125, "unit": "CODE_POINTS"}]
                    },
                },
            },
        }

    def set_preview_status(self, data, status, issues=None):
        data["official"]["validation_preview"]["status"] = status
        data["official"]["validation_preview"]["issues"] = issues or []

    def test_official_error_blocks(self):
        data = self.base()
        self.set_preview_status(data, "INVALID", [
            {"code": "ISSUE_CODE", "severity": "ERROR", "attributeNames": ["item_name"]}
        ])
        report = MODULE.diagnose(data)
        self.assertEqual("BLOCK", report["candidate_preview_gate"])
        self.assertEqual("BLOCK", report["release_decision"])
        self.assertEqual(1, report["counts"][MODULE.OFFICIAL_ERROR])

    def test_image_advice_does_not_block(self):
        report = MODULE.diagnose(self.base())
        self.assertEqual("PASS", report["candidate_preview_gate"])
        self.assertEqual("PASS", report["release_decision"])
        self.assertEqual("PASS_OFFICIAL_CHECKS", report["gate"])
        self.assertGreater(report["counts"][MODULE.HEURISTIC_ADVICE], 0)

    def test_missing_preview_is_not_pass(self):
        data = self.base()
        data["official"].pop("validation_preview")
        report = MODULE.diagnose(data)
        self.assertEqual("NOT_EVALUATED", report["candidate_preview_gate"])
        self.assertEqual("NOT_EVALUATED", report["release_decision"])

    def test_malformed_preview_is_unknown(self):
        data = self.base()
        data["official"]["validation_preview"] = "not-an-object"
        report = MODULE.diagnose(data)
        self.assertEqual("UNKNOWN", report["candidate_preview_gate"])
        self.assertEqual("UNKNOWN", report["release_decision"])

    def test_malformed_official_evidence_is_unknown(self):
        data = self.base()
        data["official"]["listing_issues"] = "not-an-array"
        report = MODULE.diagnose(data)
        self.assertEqual("UNKNOWN", report["current_listing_gate"])
        self.assertEqual("UNKNOWN", report["release_decision"])
        self.assertGreater(report["counts"][MODULE.SYSTEM_ERROR], 0)

    def test_ptd_uses_unicode_code_points(self):
        data = self.base()
        data["content"]["title"] = "A😀B"
        data["official"]["ptd"]["constraints"]["item_name"][0]["value"] = 2
        report = MODULE.diagnose(data)
        self.assertEqual("BLOCK", report["current_listing_gate"])
        self.assertEqual("REVIEW", report["release_decision"])
        violation = next(row for row in report["findings"] if row["code"] == "PTD_CONSTRAINT_VIOLATION")
        self.assertEqual(3, violation["evidence"]["actual"])

    def test_utf8_byte_limit_is_not_character_count(self):
        data = self.base()
        data["content"]["title"] = "é"
        data["official"]["ptd"]["constraints"]["item_name"] = [
            {"type": "MAX_LENGTH", "value": 1, "unit": "UTF8_BYTES"}
        ]
        report = MODULE.diagnose(data)
        violation = next(row for row in report["findings"] if row["code"] == "PTD_CONSTRAINT_VIOLATION")
        self.assertEqual(2, violation["evidence"]["actual"])

    def test_unknown_image_metadata_is_not_default_pass(self):
        data = self.base()
        data["content"]["images"] = [{"is_main": True, "url": "https://example.invalid/image.jpg"}]
        report = MODULE.diagnose(data)
        codes = {row["code"] for row in report["findings"]}
        self.assertIn("IMAGE_DIMENSIONS_MISSING", codes)
        self.assertIn("MAIN_IMAGE_BACKGROUND_UNKNOWN", codes)
        self.assertIn("IMAGE_WATERMARK_UNKNOWN", codes)

    def test_stale_ptd_requires_review(self):
        data = self.base()
        data["official"]["ptd"]["status"] = "STALE_WITHIN_GRACE"
        report = MODULE.diagnose(data)
        self.assertEqual("REVIEW", report["current_listing_gate"])
        self.assertEqual("REVIEW", report["release_decision"])

    def test_data_timestamp_is_preserved(self):
        data = self.base()
        data["data_as_of"] = "2026-01-01T00:00:00Z"
        report = MODULE.diagnose(data)
        self.assertEqual("2026-01-01T00:00:00Z", report["data_as_of"])

    def test_accepted_is_not_a_preview_pass(self):
        data = self.base()
        self.set_preview_status(data, "ACCEPTED")
        report = MODULE.diagnose(data)
        codes = {row["code"] for row in report["findings"]}
        self.assertIn("PREVIEW_MODE_MISMATCH", codes)
        self.assertEqual("UNKNOWN", report["candidate_preview_gate"])
        self.assertEqual("UNKNOWN", report["release_decision"])

    def test_info_issue_maps_to_official_warning(self):
        data = self.base()
        data["official"]["listing_issues"] = [
            {"code": "INFO_CODE", "severity": "INFO", "message": "Review this detail"}
        ]
        report = MODULE.diagnose(data)
        info = next(row for row in report["findings"] if row["code"] == "INFO_CODE")
        self.assertEqual(MODULE.OFFICIAL_WARNING, info["status"])
        self.assertEqual("INFO", info["evidence"]["severity"])
        self.assertEqual("REVIEW", report["current_listing_gate"])

    def test_preview_payload_hash_mismatch_is_unknown(self):
        data = self.base()
        data["official"]["validation_preview"]["payload_sha256"] = "b" * 64
        report = MODULE.diagnose(data)
        codes = {row["code"] for row in report["findings"]}
        self.assertIn("PREVIEW_PAYLOAD_MISMATCH", codes)
        self.assertEqual("UNKNOWN", report["candidate_preview_gate"])
        self.assertEqual("INCOMPLETE", report["official_validation_completeness"])

    def test_current_error_and_valid_put_candidate_have_separate_gates(self):
        data = self.base()
        data["official"]["listing_issues"] = [{
            "code": "OLD_TITLE_ERROR",
            "severity": "ERROR",
            "attributeNames": ["item_name"],
        }]
        report = MODULE.diagnose(data)
        self.assertEqual("BLOCK", report["current_listing_gate"])
        self.assertEqual("PASS", report["candidate_preview_gate"])
        self.assertEqual("REVIEW", report["release_decision"])

    def test_valid_patch_does_not_pass_uncovered_current_error(self):
        data = self.base()
        data["candidate"]["operation"] = "PATCH"
        data["candidate"]["touched_attributes"] = ["purchasable_offer"]
        data["official"]["validation_preview"]["operation"] = "PATCH"
        data["official"]["listing_issues"] = [{
            "code": "OLD_TITLE_ERROR",
            "severity": "ERROR",
            "attributeNames": ["item_name"],
        }]
        report = MODULE.diagnose(data)
        self.assertEqual("PASS", report["candidate_preview_gate"])
        self.assertEqual("REVIEW", report["release_decision"])
        self.assertIn("PATCH_DOES_NOT_COVER_CURRENT_BLOCKERS", report["release_reasons"])
        self.assertNotEqual("PASS_OFFICIAL_CHECKS", report["gate"])

    def test_known_error_beats_system_error_and_marks_incomplete(self):
        data = self.base()
        data["official"]["listing_issues"] = [{
            "code": "KNOWN_ERROR",
            "severity": "ERROR",
            "attributeNames": ["item_name"],
        }]
        data["official"]["ptd"] = "invalid-ptd"
        report = MODULE.diagnose(data)
        self.assertEqual("BLOCK", report["current_listing_gate"])
        self.assertEqual("BLOCK", report["release_decision"])
        self.assertEqual("INCOMPLETE", report["official_validation_completeness"])

    def test_missing_preview_traceability_does_not_pass(self):
        for field in ("issues", "submission_id", "responded_at"):
            with self.subTest(field=field):
                data = self.base()
                data["official"]["validation_preview"].pop(field)
                report = MODULE.diagnose(data)
                self.assertEqual("UNKNOWN", report["candidate_preview_gate"])
                self.assertNotEqual("PASS", report["release_decision"])

    def test_missing_official_scope_does_not_pass(self):
        data = self.base()
        for field in ("product_type", "requirements", "parentage_level"):
            data["scope"].pop(field)
        report = MODULE.diagnose(data)
        self.assertEqual("NOT_EVALUATED", report["candidate_preview_gate"])
        self.assertEqual("INCOMPLETE", report["official_validation_completeness"])

    def test_images_without_main_are_explicitly_not_evaluated(self):
        data = self.base()
        data["content"]["images"] = [{"width": 1600, "height": 1600, "watermark": False}]
        report = MODULE.diagnose(data)
        codes = {row["code"] for row in report["findings"]}
        self.assertIn("MAIN_IMAGE_NOT_IDENTIFIED", codes)


if __name__ == "__main__":
    unittest.main()
