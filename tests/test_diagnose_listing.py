import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "diagnose_listing.py"
SPEC = importlib.util.spec_from_file_location("diagnose_listing", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DiagnoseListingTest(unittest.TestCase):

    def base(self):
        return {
            "scope": {
                "seller_id": "SELLER_ID",
                "marketplace_id": "MARKETPLACE_ID",
                "sku": "SELLER_SKU",
                "product_type": "PRODUCT_TYPE",
            },
            "content": {
                "title": "Valid title",
                "images": [{"width": 800, "height": 1200, "watermark": False}],
            },
            "official": {
                "listing_issues": [],
                "validation_preview": {"ran": True, "status": "VALID", "issues": []},
                "ptd": {
                    "status": "FRESH",
                    "schema_checksum": "CHECKSUM",
                    "constraints": {
                        "item_name": [{"type": "MAX_LENGTH", "value": 125, "unit": "CODE_POINTS"}]
                    },
                },
            },
        }

    def test_official_error_blocks(self):
        data = self.base()
        data["official"]["validation_preview"] = {
            "ran": True,
            "status": "INVALID",
            "issues": [{"code": "ISSUE_CODE", "severity": "ERROR", "attributeNames": ["item_name"]}],
        }
        report = MODULE.diagnose(data)
        self.assertEqual("BLOCK", report["gate"])
        self.assertEqual(1, report["counts"][MODULE.OFFICIAL_ERROR])

    def test_image_advice_does_not_block(self):
        report = MODULE.diagnose(self.base())
        self.assertEqual("PASS_OFFICIAL_CHECKS", report["gate"])
        self.assertGreater(report["counts"][MODULE.HEURISTIC_ADVICE], 0)

    def test_missing_preview_is_not_pass(self):
        data = self.base()
        data["official"].pop("validation_preview")
        report = MODULE.diagnose(data)
        self.assertEqual("NOT_EVALUATED", report["gate"])

    def test_malformed_official_evidence_is_unknown(self):
        data = self.base()
        data["official"]["listing_issues"] = "not-an-array"
        report = MODULE.diagnose(data)
        self.assertEqual("UNKNOWN", report["gate"])
        self.assertGreater(report["counts"][MODULE.SYSTEM_ERROR], 0)

    def test_ptd_uses_unicode_code_points(self):
        data = self.base()
        data["content"]["title"] = "A😀B"
        data["official"]["ptd"]["constraints"]["item_name"][0]["value"] = 2
        report = MODULE.diagnose(data)
        self.assertEqual("BLOCK", report["gate"])
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
        self.assertEqual("REVIEW", report["gate"])

    def test_data_timestamp_is_preserved(self):
        data = self.base()
        data["data_as_of"] = "2026-01-01T00:00:00Z"
        report = MODULE.diagnose(data)
        self.assertEqual("2026-01-01T00:00:00Z", report["data_as_of"])


if __name__ == "__main__":
    unittest.main()
