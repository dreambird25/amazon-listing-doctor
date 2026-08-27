import importlib.util
import json
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
        data = {
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
                "listing_snapshot": {
                    "seller_id": "SELLER_ID",
                    "marketplace_id": "MARKETPLACE_ID",
                    "sku": "SELLER_SKU",
                    "request_id": "LISTING_REQUEST_ID",
                    "fetched_at": "2026-01-01T00:00:00Z",
                    "expires_at": "2026-01-01T00:10:00Z",
                    "included_data": ["attributes", "issues", "summaries"],
                    "issues": [],
                },
                "validation_preview": {
                    "ran": True,
                    "mode": "VALIDATION_PREVIEW",
                    "operation": "PUT",
                    "payload_sha256": self.PAYLOAD_HASH,
                    "seller_id": "SELLER_ID",
                    "marketplace_id": "MARKETPLACE_ID",
                    "sku": "SELLER_SKU",
                    "product_type": "PRODUCT_TYPE",
                    "requirements": "LISTING",
                    "request_id": "REQUEST_ID",
                    "submission_id": "PREVIEW_ID",
                    "requested_at": "2026-01-01T00:00:01Z",
                    "responded_at": "2026-01-01T00:00:02Z",
                    "expires_at": "2026-01-01T00:10:00Z",
                    "http_status": 200,
                    "status": "VALID",
                    "issues": [],
                },
                "ptd": {
                    "status": "FRESH",
                    "schema_checksum": "CHECKSUM",
                    "meta_schema_checksum": "META_SCHEMA_CHECKSUM",
                    "resolved_version": "VERSION",
                    "latest": True,
                    "release_candidate": False,
                    "fetched_at": "2026-01-01T00:00:00Z",
                    "expires_at": "2026-01-01T00:10:00Z",
                    "scope": {
                        "seller_id": "SELLER_ID",
                        "marketplace_id": "MARKETPLACE_ID",
                        "product_type": "PRODUCT_TYPE",
                        "product_type_version": "VERSION",
                        "requirements": "LISTING",
                        "requirements_enforced": "ENFORCED",
                        "parentage_level": "CHILD",
                        "locale": "en_US",
                    },
                    "constraints": {
                        "item_name": [{"type": "MAX_LENGTH", "value": 125, "unit": "CODE_POINTS"}]
                    },
                },
            },
            "data_as_of": "2026-01-01T00:00:03Z",
        }
        self.refresh_preview_binding(data)
        return data

    def refresh_preview_binding(self, data):
        data["official"]["validation_preview"]["request_fingerprint_sha256"] = (
            MODULE.request_fingerprint(data["scope"], data["candidate"])
        )

    def set_preview_status(self, data, status, issues=None):
        data["official"]["validation_preview"]["status"] = status
        data["official"]["validation_preview"]["issues"] = issues or []

    def enable_full_schema_validation(self, data):
        data["current_content"] = data.pop("content")
        data["candidate"]["content"] = {"title": "Valid title"}
        ptd = data["official"]["ptd"]
        ptd["validation_target"] = "CANDIDATE"
        ptd["full_schema_validation"] = {
            "complete": True,
            "valid": True,
            "validator": "external-validator",
            "validator_version": "1.0.0",
            "schema_draft": "2019-09",
            "amazon_vocabulary": True,
            "schema_checksum": ptd["schema_checksum"],
            "meta_schema_checksum": ptd["meta_schema_checksum"],
            "payload_sha256": data["candidate"]["payload_sha256"],
            "validated_at": "2026-01-01T00:00:02.500000Z",
            "errors": [],
        }

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
        self.assertEqual("REVIEW", report["release_decision"])
        self.assertEqual(["FULL_PTD_SCHEMA_VALIDATION_REQUIRED"], report["release_reasons"])
        self.assertEqual("REVIEW", report["gate"])
        self.assertEqual("INCOMPLETE", report["official_validation_completeness"])
        self.assertGreater(report["counts"][MODULE.HEURISTIC_ADVICE], 0)

    def test_quality_context_is_deterministic_and_contains_no_raw_values(self):
        data = self.base()
        first_report = MODULE.diagnose(data)
        second_report = MODULE.diagnose(data)
        first = first_report["quality_contexts"]["CURRENT"]
        second = second_report["quality_contexts"]["CURRENT"]
        self.assertEqual(first, second)
        self.assertEqual(first_report["official_report_sha256"], second_report["official_report_sha256"])
        self.assertEqual(64, len(first_report["official_report_sha256"]))
        self.assertEqual("CURRENT", first["assessment_target"])
        self.assertEqual(64, len(first["content_sha256"]))
        self.assertIn("$.current_content.title", {
            item["field_path"] for item in first["evidence_manifest"]
        })
        self.assertNotIn("Valid title", json.dumps(first))

    def test_candidate_quality_context_is_separate_from_current_content(self):
        data = self.base()
        data["current_content"] = data.pop("content")
        data["candidate"]["content"] = {"title": "Candidate title"}
        report = MODULE.diagnose(data)
        contexts = report["quality_contexts"]
        self.assertNotEqual(contexts["CURRENT"]["content_sha256"], contexts["CANDIDATE"]["content_sha256"])
        self.assertIn("$.candidate.content.title", {
            item["field_path"] for item in contexts["CANDIDATE"]["evidence_manifest"]
        })

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
        data["official"]["listing_snapshot"] = "not-an-object"
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
        data["official"]["ptd"]["stale_grace_deadline"] = "2026-01-01T00:20:00Z"
        report = MODULE.diagnose(data)
        self.assertEqual("REVIEW", report["current_listing_gate"])
        self.assertEqual("REVIEW", report["release_decision"])

    def test_data_timestamp_is_preserved(self):
        data = self.base()
        data["data_as_of"] = "2026-01-01T00:00:00Z"
        report = MODULE.diagnose(data)
        self.assertEqual("2026-01-01T00:00:00Z", report["data_as_of"])

    def test_missing_data_as_of_cannot_pass_freshness_gates(self):
        data = self.base()
        data.pop("data_as_of")
        report = MODULE.diagnose(data)
        self.assertEqual("NOT_EVALUATED", report["current_listing_gate"])
        self.assertEqual("NOT_EVALUATED", report["candidate_preview_gate"])
        self.assertEqual("INCOMPLETE", report["official_validation_completeness"])

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
        data["official"]["listing_snapshot"]["issues"] = [
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
        data["official"]["listing_snapshot"]["issues"] = [{
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
        data["official"]["validation_preview"].pop("requirements")
        self.refresh_preview_binding(data)
        data["official"]["listing_snapshot"]["issues"] = [{
            "code": "OLD_TITLE_ERROR",
            "severity": "ERROR",
            "attributeNames": ["item_name"],
        }]
        report = MODULE.diagnose(data)
        self.assertEqual("PASS", report["candidate_preview_gate"])
        self.assertEqual("REVIEW", report["release_decision"])
        self.assertIn("PATCH_DOES_NOT_COVER_CURRENT_BLOCKERS", report["release_reasons"])
        self.assertNotEqual("PASS_OFFICIAL_CHECKS", report["gate"])

    def test_patch_alias_can_cover_current_issue_attribute(self):
        data = self.base()
        data["candidate"]["operation"] = "PATCH"
        data["candidate"]["touched_attributes"] = ["item_highlight"]
        data["attribute_aliases"] = {"item_highlight": "title_differentiation"}
        data["official"]["validation_preview"]["operation"] = "PATCH"
        data["official"]["validation_preview"].pop("requirements")
        data["official"]["listing_snapshot"]["issues"] = [{
            "code": "OLD_ATTRIBUTE_ERROR",
            "severity": "ERROR",
            "attributeNames": ["title_differentiation"],
        }]
        self.refresh_preview_binding(data)
        report = MODULE.diagnose(data)
        self.assertNotIn("PATCH_DOES_NOT_COVER_CURRENT_BLOCKERS", report["release_reasons"])
        self.assertEqual("CURRENT_LISTING_HAS_HISTORICAL_BLOCKERS", report["release_reasons"][0])

    def test_known_error_beats_system_error_and_marks_incomplete(self):
        data = self.base()
        data["official"]["listing_snapshot"]["issues"] = [{
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
        self.assertIn(report["candidate_preview_gate"], {"NOT_EVALUATED", "UNKNOWN"})
        self.assertEqual("INCOMPLETE", report["official_validation_completeness"])

    def test_images_without_main_are_explicitly_not_evaluated(self):
        data = self.base()
        data["content"]["images"] = [{"width": 1600, "height": 1600, "watermark": False}]
        report = MODULE.diagnose(data)
        codes = {row["code"] for row in report["findings"]}
        self.assertIn("MAIN_IMAGE_NOT_IDENTIFIED", codes)

    def test_invalid_preview_with_hash_mismatch_is_unknown(self):
        data = self.base()
        self.set_preview_status(data, "INVALID", [
            {"code": "OLD_PAYLOAD_ERROR", "severity": "ERROR"}
        ])
        data["official"]["validation_preview"]["payload_sha256"] = "b" * 64
        report = MODULE.diagnose(data)
        issue = next(row for row in report["findings"] if row["code"] == "OLD_PAYLOAD_ERROR")
        self.assertFalse(issue["applies_to_candidate"])
        self.assertEqual("UNKNOWN", report["candidate_preview_gate"])

    def test_invalid_preview_with_scope_mismatch_is_unknown(self):
        data = self.base()
        self.set_preview_status(data, "INVALID", [
            {"code": "OTHER_SKU_ERROR", "severity": "ERROR"}
        ])
        data["official"]["validation_preview"]["sku"] = "OTHER_SKU"
        report = MODULE.diagnose(data)
        self.assertEqual("UNKNOWN", report["candidate_preview_gate"])

    def test_invalid_preview_with_operation_mismatch_is_unknown(self):
        data = self.base()
        self.set_preview_status(data, "INVALID", [
            {"code": "OTHER_OPERATION_ERROR", "severity": "ERROR"}
        ])
        data["official"]["validation_preview"]["operation"] = "PATCH"
        report = MODULE.diagnose(data)
        self.assertEqual("UNKNOWN", report["candidate_preview_gate"])

    def test_valid_patch_requires_traceable_listing_snapshot(self):
        data = self.base()
        data["candidate"]["operation"] = "PATCH"
        data["candidate"]["touched_attributes"] = ["item_name"]
        data["official"]["validation_preview"]["operation"] = "PATCH"
        data["official"]["validation_preview"].pop("requirements")
        data["official"].pop("listing_snapshot")
        data["official"]["listing_issues"] = []
        self.refresh_preview_binding(data)
        report = MODULE.diagnose(data)
        self.assertEqual("PASS", report["candidate_preview_gate"])
        self.assertEqual("REVIEW", report["release_decision"])
        self.assertIn(
            "PATCH_REQUIRES_TRACEABLE_CURRENT_LISTING_SNAPSHOT", report["release_reasons"]
        )

    def test_put_preview_requirements_mismatch_is_unknown(self):
        data = self.base()
        data["official"]["validation_preview"]["requirements"] = "LISTING_OFFER_ONLY"
        report = MODULE.diagnose(data)
        self.assertEqual("UNKNOWN", report["candidate_preview_gate"])
        self.assertIn(
            "PREVIEW_REQUIREMENTS_MISMATCH", {row["code"] for row in report["findings"]}
        )

    def test_ptd_scope_mismatch_is_unknown(self):
        data = self.base()
        data["official"]["ptd"]["scope"]["marketplace_id"] = "OTHER_MARKETPLACE"
        report = MODULE.diagnose(data)
        self.assertEqual("UNKNOWN", report["current_listing_gate"])
        self.assertFalse(report["ptd_validation_coverage"]["scope_bound"])

    def test_mismatched_snapshot_error_does_not_block_current_scope(self):
        data = self.base()
        data["official"]["listing_snapshot"]["marketplace_id"] = "OTHER_MARKETPLACE"
        data["official"]["listing_snapshot"]["issues"] = [
            {"code": "OTHER_SCOPE_ERROR", "severity": "ERROR"}
        ]
        report = MODULE.diagnose(data)
        issue = next(row for row in report["findings"] if row["code"] == "OTHER_SCOPE_ERROR")
        self.assertFalse(issue["applies_to_current"])
        self.assertEqual("UNKNOWN", report["current_listing_gate"])

    def test_mismatched_ptd_violation_does_not_block_current_scope(self):
        data = self.base()
        data["content"]["title"] = "Too long"
        data["official"]["ptd"]["constraints"]["item_name"][0]["value"] = 1
        data["official"]["ptd"]["scope"]["marketplace_id"] = "OTHER_MARKETPLACE"
        report = MODULE.diagnose(data)
        issue = next(
            row for row in report["findings"] if row["code"] == "PTD_CONSTRAINT_VIOLATION"
        )
        self.assertFalse(issue["applies_to_current"])
        self.assertEqual("UNKNOWN", report["current_listing_gate"])

    def test_ptd_requirements_enforced_must_be_known_enum(self):
        data = self.base()
        data["official"]["ptd"]["scope"]["requirements_enforced"] = "MAYBE"
        report = MODULE.diagnose(data)
        self.assertIn("PTD_REQUIREMENTS_ENFORCED_INVALID", {
            row["code"] for row in report["findings"]
        })
        self.assertEqual("UNKNOWN", report["current_listing_gate"])

    def test_ptd_meta_schema_and_version_flags_are_required(self):
        data = self.base()
        for field in ("meta_schema_checksum", "latest", "release_candidate"):
            data["official"]["ptd"].pop(field)
        report = MODULE.diagnose(data)
        self.assertIn("PTD_TRACEABILITY_INCOMPLETE", {
            row["code"] for row in report["findings"]
        })
        self.assertEqual("UNKNOWN", report["current_listing_gate"])

    def test_ptd_traceability_is_required(self):
        data = self.base()
        for field in ("schema_checksum", "resolved_version", "fetched_at"):
            data["official"]["ptd"].pop(field)
        report = MODULE.diagnose(data)
        self.assertEqual("UNKNOWN", report["current_listing_gate"])
        self.assertEqual("INCOMPLETE", report["official_validation_completeness"])

    def test_preview_time_order_invalid_is_unknown(self):
        data = self.base()
        data["official"]["validation_preview"]["requested_at"] = "2026-01-01T00:00:05Z"
        report = MODULE.diagnose(data)
        self.assertEqual("UNKNOWN", report["candidate_preview_gate"])
        self.assertIn("PREVIEW_TIME_ORDER_INVALID", {row["code"] for row in report["findings"]})

    def test_expired_preview_is_not_evaluated(self):
        data = self.base()
        data["data_as_of"] = "2026-01-01T00:11:00Z"
        report = MODULE.diagnose(data)
        self.assertEqual("NOT_EVALUATED", report["candidate_preview_gate"])
        self.assertIn("PREVIEW_STALE", {row["code"] for row in report["findings"]})

    def test_image_boolean_strings_are_system_errors(self):
        data = self.base()
        data["content"]["images"][0]["watermark"] = "false"
        report = MODULE.diagnose(data)
        self.assertIn("IMAGE_METADATA_TYPE_INVALID", {row["code"] for row in report["findings"]})
        self.assertGreater(report["counts"][MODULE.SYSTEM_ERROR], 0)

    def test_image_dimension_strings_are_system_errors(self):
        data = self.base()
        data["content"]["images"][0]["width"] = "800"
        report = MODULE.diagnose(data)
        self.assertIn("IMAGE_METADATA_TYPE_INVALID", {
            row["code"] for row in report["findings"]
        })
        self.assertGreater(report["counts"][MODULE.SYSTEM_ERROR], 0)

    def test_partially_missing_image_dimensions_still_validate_provided_type(self):
        data = self.base()
        data["content"]["images"][0]["width"] = None
        data["content"]["images"][0]["height"] = "1200"
        report = MODULE.diagnose(data)
        self.assertIn("IMAGE_METADATA_TYPE_INVALID", {
            row["code"] for row in report["findings"]
        })

    def test_multiple_main_images_are_system_errors(self):
        data = self.base()
        data["content"]["images"].append({
            "is_main": True,
            "width": 1200,
            "height": 1200,
            "watermark": False,
            "white_background": True,
        })
        report = MODULE.diagnose(data)
        self.assertIn("MULTIPLE_MAIN_IMAGES", {row["code"] for row in report["findings"]})

    def test_official_error_and_system_error_have_distinct_exit_code(self):
        data = self.base()
        data["official"]["listing_snapshot"]["issues"] = [
            {"code": "KNOWN_ERROR", "severity": "ERROR"}
        ]
        data["official"]["ptd"] = "invalid"
        report = MODULE.diagnose(data)
        self.assertEqual(3, MODULE.exit_code(report))

    def test_put_offer_only_scope_is_partial(self):
        data = self.base()
        data["scope"]["requirements"] = "LISTING_OFFER_ONLY"
        data["candidate"]["requirements"] = "LISTING_OFFER_ONLY"
        data["official"]["validation_preview"]["requirements"] = "LISTING_OFFER_ONLY"
        data["official"]["ptd"]["scope"]["requirements"] = "LISTING_OFFER_ONLY"
        self.refresh_preview_binding(data)
        report = MODULE.diagnose(data)
        self.assertEqual("PASS", report["candidate_preview_gate"])
        self.assertEqual("PARTIAL", report["official_scope"]["coverage"])

    def test_lightweight_ptd_never_claims_full_schema_validation(self):
        report = MODULE.diagnose(self.base())
        self.assertEqual("LIGHTWEIGHT_SUBSET", report["ptd_validation_coverage"]["mode"])
        self.assertFalse(report["ptd_validation_coverage"]["full_schema_validation"])

    def test_attribute_aliases_evaluate_every_matching_amazon_element(self):
        data = self.base()
        data["attribute_aliases"] = {"item_highlight": "title_differentiation"}
        data["content"]["attributes"] = {
            "item_highlight": [
                {"value": "Short", "language_tag": "en_US", "marketplace_id": "MARKETPLACE_ID"},
                {"value": "Too long", "language_tag": "en_US", "marketplace_id": "MARKETPLACE_ID"},
                {"value": "Ignored for locale", "language_tag": "de_DE", "marketplace_id": "MARKETPLACE_ID"},
            ]
        }
        data["official"]["ptd"]["constraints"] = {
            "title_differentiation": [
                {"type": "MAX_LENGTH", "value": 5, "unit": "CODE_POINTS"}
            ]
        }
        report = MODULE.diagnose(data)
        violations = [
            row for row in report["findings"] if row["code"] == "PTD_CONSTRAINT_VIOLATION"
        ]
        self.assertEqual(1, len(violations))
        self.assertEqual(1, violations[0]["evidence"]["element_index"])
        self.assertEqual("item_highlight", violations[0]["evidence"]["resolved_attribute"])

    def test_attribute_alias_cycle_is_a_system_error(self):
        data = self.base()
        data["attribute_aliases"] = {"first": "second", "second": "first"}
        report = MODULE.diagnose(data)
        self.assertIn("ATTRIBUTE_ALIAS_CYCLE", {row["code"] for row in report["findings"]})
        self.assertGreater(report["counts"][MODULE.SYSTEM_ERROR], 0)

    def test_declared_alias_overrides_legacy_convenience_mapping(self):
        data = self.base()
        data["attribute_aliases"] = {"title": "custom_title_attribute"}
        data["content"]["title"] = "Too long"
        data["official"]["ptd"]["constraints"] = {
            "custom_title_attribute": [
                {"type": "MAX_LENGTH", "value": 3, "unit": "CODE_POINTS"}
            ]
        }
        report = MODULE.diagnose(data)
        violation = next(
            row for row in report["findings"] if row["code"] == "PTD_CONSTRAINT_VIOLATION"
        )
        self.assertEqual("title", violation["evidence"]["resolved_attribute"])

    def test_candidate_content_is_not_mixed_into_current_listing_gate(self):
        data = self.base()
        data["current_content"] = data.pop("content")
        data["candidate"]["content"] = {"title": "Candidate title is too long"}
        data["official"]["ptd"]["validation_target"] = "CANDIDATE"
        data["official"]["ptd"]["constraints"]["item_name"][0]["value"] = 5
        report = MODULE.diagnose(data)
        self.assertEqual("NO_KNOWN_OFFICIAL_ISSUES", report["current_listing_gate"])
        self.assertEqual("BLOCK", report["candidate_local_validation_gate"])
        self.assertEqual("BLOCK", report["release_decision"])
        self.assertEqual("EXPLICIT_CURRENT_AND_CANDIDATE", report["content_contract"]["mode"])

    def test_bound_full_schema_validation_can_enable_release_pass(self):
        data = self.base()
        self.enable_full_schema_validation(data)
        report = MODULE.diagnose(data)
        self.assertEqual("PASS", report["candidate_preview_gate"])
        self.assertEqual("PASS", report["candidate_local_validation_gate"])
        self.assertTrue(report["ptd_validation_coverage"]["full_schema_validation"])
        self.assertEqual("PASS", report["release_decision"])

    def test_not_enforced_ptd_cannot_enable_unattended_release(self):
        data = self.base()
        self.enable_full_schema_validation(data)
        data["official"]["ptd"]["scope"]["requirements_enforced"] = "NOT_ENFORCED"
        report = MODULE.diagnose(data)
        self.assertEqual("REVIEW", report["candidate_local_validation_gate"])
        self.assertEqual("REVIEW", report["release_decision"])
        self.assertIn("PTD_REQUIREMENTS_NOT_ENFORCED", {
            row["code"] for row in report["findings"]
        })

    def test_missing_candidate_content_does_not_pollute_current_gate(self):
        data = self.base()
        data["official"]["ptd"]["validation_target"] = "CANDIDATE"
        report = MODULE.diagnose(data)
        self.assertEqual("NO_KNOWN_OFFICIAL_ISSUES", report["current_listing_gate"])
        self.assertEqual("NOT_EVALUATED", report["candidate_local_validation_gate"])

    def test_invalid_candidate_content_does_not_pollute_current_gate(self):
        data = self.base()
        data["candidate"]["content"] = "invalid"
        report = MODULE.diagnose(data)
        self.assertEqual("NO_KNOWN_OFFICIAL_ISSUES", report["current_listing_gate"])
        self.assertEqual("UNKNOWN", report["candidate_preview_gate"])

    def test_boolean_full_schema_assertion_is_not_trusted(self):
        data = self.base()
        data["current_content"] = data.pop("content")
        data["candidate"]["content"] = {"title": "Valid title"}
        data["official"]["ptd"]["validation_target"] = "CANDIDATE"
        data["official"]["ptd"]["full_schema_validation"] = True
        report = MODULE.diagnose(data)
        self.assertIn("FULL_SCHEMA_VALIDATION_INVALID", {
            row["code"] for row in report["findings"]
        })
        self.assertEqual("UNKNOWN", report["candidate_local_validation_gate"])
        self.assertNotEqual("PASS", report["release_decision"])

    def test_report_locale_is_independent_from_listing_locale(self):
        data = self.base()
        data["scope"]["locale"] = "de_DE"
        data["official"]["ptd"]["scope"]["locale"] = "de_DE"
        data["report_locale"] = "zh-CN"
        report = MODULE.diagnose(data)
        self.assertEqual("de_DE", report["scope"]["locale"])
        self.assertEqual("zh-CN", report["report_locale"])


if __name__ == "__main__":
    unittest.main()
