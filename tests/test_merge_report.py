import importlib.util
import json
import sys
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
sys.path.insert(0, str(SCRIPT.parent))
from quality_contract import (
    build_quality_context,
    official_report_sha256,
    scope_fingerprint,
    sha256_json,
)


class MergeReportTest(unittest.TestCase):

    def official_report(self):
        scope = {
            "seller_id": "SELLER_ID",
            "marketplace_id": "MARKETPLACE_ID",
            "sku": "SELLER_SKU",
            "asin": "ASIN_PLACEHOLDER",
            "product_type": "PRODUCT_TYPE",
            "requirements": "LISTING",
            "parentage_level": "CHILD",
            "locale": "en_US",
        }
        content = {
            "title": "Example Brand Bottle",
            "bullets": ["Leak-resistant lid for daily use."],
            "description": "A reusable bottle for commuting and workouts.",
            "images": [{"url": "https://example.invalid/main.jpg", "is_main": True}],
            "attributes": {"capacity": [{"value": 24, "unit": "oz"}]},
        }
        report = {
            "scope": scope,
            "current_listing_gate": "NO_KNOWN_OFFICIAL_ISSUES",
            "candidate_preview_gate": "PASS",
            "candidate_local_validation_gate": "PASS",
            "release_decision": "PASS",
            "release_reasons": ["BOUND_CANDIDATE_PREVIEW_VALID"],
            "official_validation_completeness": "COMPLETE",
            "official_evidence_coverage": {},
            "ptd_validation_coverage": {},
            "counts": {},
            "findings": [],
            "data_as_of": "2026-01-01T00:00:00Z",
            "quality_contexts": {
                "CURRENT": build_quality_context("CURRENT", scope, content, {
                    "source_type": "STOREFRONT_OBSERVATION",
                    "content_scope": "BUYER_VISIBLE",
                    "coverage": "COMPLETE",
                    "missing_field_semantics": "OBSERVED_ABSENT",
                }),
            },
        }
        report["official_report_sha256"] = official_report_sha256(report)
        return report

    def assessment(self, rating="STRONG", report=None):
        report = report or self.official_report()
        report["official_report_sha256"] = official_report_sha256(report)
        context = report["quality_contexts"]["CURRENT"]
        def evidence(path, value):
            return {"field_path": path, "quote_or_value": value, "value_sha256": sha256_json(value)}

        dimension_evidence = {
            "content_completeness": [
                evidence("$.current_content.title", "Example Brand Bottle"),
                evidence("$.current_content.bullets[0]", "Leak-resistant lid for daily use."),
            ],
            "clarity_and_readability": [
                evidence("$.current_content.title", "Example Brand Bottle"),
            ],
            "intent_coverage": [
                evidence(
                    "$.current_content.description",
                    "A reusable bottle for commuting and workouts.",
                ),
            ],
            "buyer_question_coverage": [
                evidence("$.current_content.bullets[0]", "Leak-resistant lid for daily use."),
            ],
            "image_information_coverage": [
                evidence("$.current_content.images[0].url", "https://example.invalid/main.jpg"),
            ],
            "cross_field_consistency": [
                evidence("$.current_content.title", "Example Brand Bottle"),
                evidence("$.current_content.attributes.capacity[0].value", 24),
            ],
            "localization_quality": [
                evidence("$.current_content.title", "Example Brand Bottle"),
            ],
        }
        return {
            "assessment_version": "1.4",
            "assessment_model": "test-model",
            "prompt_version": "quality-v1.4.0",
            "assessed_at": "2026-01-01T00:00:00Z",
            "assessment_target": "CURRENT",
            "assessment_locale": "en_US",
            "evidence_policy_version": "1.1",
            "scope_fingerprint_sha256": context["scope_fingerprint_sha256"],
            "content_sha256": context["content_sha256"],
            "official_report_sha256": official_report_sha256(report),
            "evidence_manifest_sha256": context["evidence_manifest_sha256"],
            "dimensions": {
                name: {
                    "rating": rating,
                    "evidence_basis": "OBSERVED_CONTENT",
                    "rationale": "Direct evidence supports this rating.",
                    "evidence": dimension_evidence[name],
                    "missing_evidence": ["additional content module"] if rating == "WEAK"
                    and name == "content_completeness" else [],
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
        self.assertTrue(merged["quality_evidence_policy"]["passed"])
        self.assertEqual("1.1", merged["quality_evidence_policy"]["version"])
        self.assertEqual("NOT_EVALUATED", merged["performance_verdict"])
        self.assertEqual("PASS", merged["release_decision"])
        self.assertEqual(10.0, merged["executive_summary"]["quality_score"]["value"])
        self.assertEqual("FULL", merged["executive_summary"]["quality_score"]["status"])
        self.assertFalse(merged["executive_summary"]["quality_score"]["comparable"])
        self.assertTrue(merged["executive_summary"]["quality_score"]["structurally_comparable"])
        self.assertEqual(64, len(
            merged["executive_summary"]["quality_score"]["comparison_cohort_sha256"]
        ))
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
            "evidence_basis": "EVIDENCE_GAP",
            "rationale": "",
            "evidence": [],
            "missing_evidence": ["locale-specific content"],
        })
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertTrue(valid)
        self.assertEqual("PARTIALLY_EVALUATED", merged["quality_verdict"])
        self.assertEqual("PARTIAL", merged["quality_evidence_completeness"])
        score = merged["executive_summary"]["quality_score"]
        self.assertEqual("PARTIAL", score["status"])
        self.assertFalse(score["comparable"])
        self.assertFalse(score["structurally_comparable"])
        self.assertNotIn("localization_quality", score["dimension_mask"])

    def test_evaluated_rating_requires_direct_evidence(self):
        assessment = self.assessment()
        assessment["dimensions"]["content_completeness"]["evidence"] = []
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertEqual("SYSTEM_ERROR", merged["merge_status"])
        self.assertTrue(any("content_completeness requires manifest-bound evidence" in error for error in merged["errors"]))

    def test_encoding_defect_claim_requires_suspicious_bound_text(self):
        assessment = self.assessment("ADEQUATE")
        assessment["dimensions"]["clarity_and_readability"].update({
            "rating": "WEAK",
            "rationale": "The visible bullet contains a replacement character or encoding artifact.",
        })
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertEqual("SYSTEM_ERROR", merged["merge_status"])
        self.assertTrue(any(
            "encoding defect claim requires suspicious bound text" in error
            for error in merged["errors"]
        ))

    def test_missing_content_claim_requires_observed_absence_basis(self):
        assessment = self.assessment("ADEQUATE")
        assessment["dimensions"]["content_completeness"].update({
            "rating": "WEAK",
            "evidence_basis": "OBSERVED_CONTENT",
            "rationale": "当前来源只有标题，缺少要点和描述。",
            "missing_evidence": ["bullets", "description"],
        })
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any(
            "missing-content claim requires OBSERVED_ABSENCE evidence" in error
            for error in merged["errors"]
        ))

    def test_observed_absence_requires_complete_source_coverage(self):
        report = self.official_report()
        report["quality_contexts"]["CURRENT"]["content_evidence"].update({
            "source_type": "LISTINGS_ITEMS",
            "content_scope": "SELLER_CONTRIBUTION",
            "coverage": "PARTIAL",
            "missing_field_semantics": "UNKNOWN",
        })
        report["official_report_sha256"] = official_report_sha256(report)
        assessment = self.assessment("ADEQUATE", report=report)
        assessment["dimensions"]["content_completeness"].update({
            "rating": "WEAK",
            "evidence_basis": "OBSERVED_ABSENCE",
            "rationale": "The supplied source is missing bullets and description.",
            "missing_evidence": ["bullets", "description"],
        })
        merged, valid = MODULE.merge_report(report, assessment)
        self.assertFalse(valid)
        self.assertTrue(any(
            "content_completeness does not satisfy evidence policy" in error
            for error in merged["errors"]
        ))

    def test_summary_exposes_buyer_visible_content_scope(self):
        merged, valid = MODULE.merge_report(self.official_report(), self.assessment())
        self.assertTrue(valid)
        evidence = merged["executive_summary"]["content_evidence"]
        self.assertEqual("BUYER_VISIBLE", evidence["content_scope"])
        self.assertEqual("COMPLETE", evidence["coverage"])

    def test_negated_defect_statements_do_not_require_suspicious_text(self):
        rationales = (
            "No replacement character or encoding issue is present.",
            "The text contains no debug log or stack trace residue.",
            "The title is free of encoding issues.",
            "未发现乱码或替换字符。",
        )
        for rationale in rationales:
            with self.subTest(rationale=rationale):
                assessment = self.assessment("STRONG")
                assessment["dimensions"]["clarity_and_readability"]["rationale"] = rationale
                merged, valid = MODULE.merge_report(self.official_report(), assessment)
                self.assertTrue(valid, merged.get("errors"))

    def test_negation_scope_does_not_hide_affirmative_defect_claim(self):
        rationales = (
            "No title issue, but an encoding issue exists in the bullet.",
            "标题无问题，但要点有乱码。",
            "The bullet is not free of encoding issues.",
        )
        for rationale in rationales:
            with self.subTest(rationale=rationale):
                assessment = self.assessment("ADEQUATE")
                assessment["dimensions"]["clarity_and_readability"].update({
                    "rating": "WEAK",
                    "rationale": rationale,
                })
                merged, valid = MODULE.merge_report(self.official_report(), assessment)
                self.assertFalse(valid)
                self.assertEqual("SYSTEM_ERROR", merged["merge_status"])

    def test_legitimate_multilingual_characters_are_not_mojibake(self):
        self.assertFalse(MODULE.suspicious_bound_text("SÃO TOMÉ – ÂNGULO"))

    def test_common_mojibake_and_tab_are_detected(self):
        self.assertTrue(MODULE.suspicious_bound_text("SÃ£o"))
        self.assertTrue(MODULE.suspicious_bound_text("visible\ttext"))

    def test_documented_defect_claims_require_matching_bound_evidence(self):
        rationales = (
            "The bullet contains a control character.",
            "The bullet contains an exception trace.",
        )
        for rationale in rationales:
            with self.subTest(rationale=rationale):
                assessment = self.assessment("ADEQUATE")
                assessment["dimensions"]["clarity_and_readability"].update({
                    "rating": "WEAK",
                    "rationale": rationale,
                })
                merged, valid = MODULE.merge_report(self.official_report(), assessment)
                self.assertFalse(valid)
                self.assertEqual("SYSTEM_ERROR", merged["merge_status"])

    def test_native_reviewer_absence_is_not_missing_listing_evidence(self):
        assessment = self.assessment("ADEQUATE")
        assessment["dimensions"]["localization_quality"] = {
            "rating": "NOT_EVALUATED",
            "evidence_basis": "EVIDENCE_GAP",
            "rationale": "",
            "evidence": [],
            "missing_evidence": ["A native German reviewer is unavailable."],
        }
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertEqual("SYSTEM_ERROR", merged["merge_status"])
        self.assertTrue(any(
            "native reviewer absence is not missing Listing evidence" in error
            for error in merged["errors"]
        ))

    def test_encoding_defect_claim_accepts_actual_replacement_character(self):
        report = self.official_report()
        report["quality_contexts"]["CURRENT"] = build_quality_context(
            "CURRENT", report["scope"], {
                "title": "Example Brand Bottle",
                "bullets": ["Leak-resistant lid \ufffd for daily use."],
                "description": "A reusable bottle for commuting and workouts.",
                "images": [{"url": "https://example.invalid/main.jpg", "is_main": True}],
                "attributes": {"capacity": [{"value": 24, "unit": "oz"}]},
            },
        )
        report["official_report_sha256"] = official_report_sha256(report)
        assessment = self.assessment("ADEQUATE", report=report)
        for name in MODULE.DIMENSIONS:
            if name != "clarity_and_readability":
                assessment["dimensions"][name] = {
                    "rating": "NOT_EVALUATED",
                    "evidence_basis": "EVIDENCE_GAP",
                    "rationale": "",
                    "evidence": [],
                    "missing_evidence": ["not needed for this focused test"],
                }
        value = "Leak-resistant lid \ufffd for daily use."
        assessment["dimensions"]["clarity_and_readability"] = {
            "rating": "WEAK",
            "evidence_basis": "OBSERVED_CONTENT",
            "rationale": "The visible bullet contains a replacement character.",
            "evidence": [{
                "field_path": "$.current_content.bullets[0]",
                "quote_or_value": value,
                "value_sha256": sha256_json(value),
            }],
            "missing_evidence": [],
        }
        merged, valid = MODULE.merge_report(report, assessment)
        self.assertTrue(valid, merged.get("errors"))

    def test_debug_artifact_claim_requires_technical_artifact_evidence(self):
        assessment = self.assessment("ADEQUATE")
        assessment["dimensions"]["clarity_and_readability"].update({
            "rating": "WEAK",
            "rationale": "The fifth bullet contains a debug stack trace residue.",
        })
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertEqual("SYSTEM_ERROR", merged["merge_status"])
        self.assertTrue(any(
            "technical artifact claim requires suspicious bound text" in error
            for error in merged["errors"]
        ))

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

    def test_assessment_locale_and_time_bind_to_report(self):
        report = self.official_report()
        assessment = self.assessment(report=report)
        assessment["assessment_locale"] = "de_DE"
        merged, valid = MODULE.merge_report(report, assessment)
        self.assertFalse(valid)
        self.assertTrue(any("assessment_locale does not match" in error for error in merged["errors"]))

        report = self.official_report()
        report["data_as_of"] = "2026-01-01T00:00:01Z"
        assessment = self.assessment(report=report)
        merged, valid = MODULE.merge_report(report, assessment)
        self.assertFalse(valid)
        self.assertTrue(any("must not predate" in error for error in merged["errors"]))

        report = self.official_report()
        report["data_as_of"] = "not-a-time"
        assessment = self.assessment(report=report)
        merged, valid = MODULE.merge_report(report, assessment)
        self.assertFalse(valid)
        self.assertTrue(any("official report data_as_of" in error for error in merged["errors"]))

    def test_dimension_evidence_policy_rejects_wrong_paths(self):
        assessment = self.assessment()
        assessment["dimensions"]["image_information_coverage"]["evidence"] = [
            assessment["dimensions"]["clarity_and_readability"]["evidence"][0]
        ]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("IMAGE_PATH_REQUIRED" in error for error in merged["errors"]))

        assessment = self.assessment()
        assessment["dimensions"]["cross_field_consistency"]["evidence"] = [
            assessment["dimensions"]["clarity_and_readability"]["evidence"][0]
        ]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("TWO_CONTENT_MODULES_REQUIRED" in error for error in merged["errors"]))

        report = self.official_report()
        content = {"title": "", "bullets": ["Leak-resistant lid for daily use."]}
        report["quality_contexts"]["CURRENT"] = build_quality_context(
            "CURRENT", report["scope"], content
        )
        assessment = self.assessment(report=report)
        assessment["dimensions"]["clarity_and_readability"]["evidence"] = [{
            "field_path": "$.current_content.title",
            "quote_or_value": "",
            "value_sha256": sha256_json(""),
        }]
        merged, valid = MODULE.merge_report(report, assessment)
        self.assertFalse(valid)
        self.assertTrue(any("TEXTUAL_CONTENT_REQUIRED" in error for error in merged["errors"]))

    def test_fewer_than_five_dimensions_is_not_scored(self):
        assessment = self.assessment("ADEQUATE")
        for name in MODULE.DIMENSIONS[4:]:
            assessment["dimensions"][name] = {
                "rating": "NOT_EVALUATED",
                "evidence_basis": "EVIDENCE_GAP",
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

    def test_suggested_rewrite_requires_typed_template_bindings(self):
        assessment = self.assessment("ADEQUATE")
        assessment["recommendations"] = [{
            "priority": "MEDIUM",
            "dimension": "clarity_and_readability",
            "attribute": "item_name",
            "current_problem": "The title omits a verified capacity.",
            "action": "Rewrite the title using supplied facts.",
            "suggested_value": "Example Brand Bottle, 24 oz",
            "completion_criterion": "The title passes PTD and Preview.",
        }]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("fact_bindings" in error for error in merged["errors"]))

        assessment["dimensions"]["clarity_and_readability"]["evidence"].append({
            "field_path": "$.current_content.attributes.capacity[0].value",
            "quote_or_value": 24,
            "value_sha256": sha256_json(24),
        })
        assessment["dimensions"]["clarity_and_readability"]["evidence"].append({
            "field_path": "$.current_content.attributes.capacity[0].unit",
            "quote_or_value": "oz",
            "value_sha256": sha256_json("oz"),
        })
        assessment["recommendations"][0]["fact_bindings"] = [
            {
                "binding_id": "product_name",
                "source_path": "$.current_content.title",
                "source_value": "Example Brand Bottle",
                "source_value_sha256": sha256_json("Example Brand Bottle"),
            },
            {
                "binding_id": "capacity",
                "source_path": "$.current_content.attributes.capacity[0].value",
                "source_value": 24,
                "source_value_sha256": sha256_json(24),
            },
            {
                "binding_id": "capacity_unit",
                "source_path": "$.current_content.attributes.capacity[0].unit",
                "source_value": "oz",
                "source_value_sha256": sha256_json("oz"),
            },
        ]
        assessment["recommendations"][0]["suggested_template"] = [
            {"type": "BOUND_FACT", "binding_id": "product_name"},
            {"type": "LITERAL", "value": ", "},
            {"type": "BOUND_FACT", "binding_id": "capacity"},
            {"type": "LITERAL", "value": " "},
            {"type": "BOUND_FACT", "binding_id": "capacity_unit"},
        ]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertTrue(valid)
        action = merged["executive_summary"]["primary_action"]
        self.assertEqual("Example Brand Bottle, 24 oz", action["suggested_value"])
        self.assertTrue(action["rewrite_is_advisory"])
        preview = merged["executive_summary"]["change_preview"]
        self.assertEqual("item_name", preview["attribute"])
        self.assertTrue(preview["candidate_available"])
        self.assertEqual("Example Brand Bottle, 24 oz", preview["candidate_value"])
        self.assertTrue(any(
            row["field_path"] == "$.current_content.title"
            and row["value"] == "Example Brand Bottle"
            for row in preview["original_values"]
        ))

    def test_suggested_rewrite_rejects_unverified_source_value(self):
        assessment = self.assessment("ADEQUATE")
        assessment["recommendations"] = [{
            "priority": "MEDIUM",
            "dimension": "clarity_and_readability",
            "attribute": "item_name",
            "current_problem": "The title omits a verified capacity.",
            "action": "Rewrite the title using supplied facts.",
            "suggested_value": "Example Brand Bottle, 48 oz",
            "fact_bindings": [{
                "binding_id": "capacity",
                "source_path": "$.current_content.attributes.capacity[0].value",
                "source_value": 48,
                "source_value_sha256": sha256_json(48),
            }],
            "suggested_template": [
                {"type": "BOUND_FACT", "binding_id": "capacity"},
            ],
            "completion_criterion": "The title passes PTD and Preview.",
        }]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("bound to assessed evidence" in error for error in merged["errors"]))

    def test_suggested_template_rejects_unbound_literal_claims(self):
        assessment = self.assessment("ADEQUATE")
        assessment["recommendations"] = [{
            "priority": "MEDIUM",
            "dimension": "clarity_and_readability",
            "attribute": "item_name",
            "current_problem": "The title needs a verified capacity.",
            "action": "Build a title from verified facts.",
            "fact_bindings": [{
                "binding_id": "capacity",
                "source_path": "$.current_content.attributes.capacity[0].value",
                "source_value": 24,
                "source_value_sha256": sha256_json(24),
            }],
            "suggested_template": [
                {"type": "LITERAL", "value": "BPA-Free "},
                {"type": "BOUND_FACT", "binding_id": "capacity"},
            ],
            "completion_criterion": "The title passes review.",
        }]
        assessment["dimensions"]["clarity_and_readability"]["evidence"].append({
            "field_path": "$.current_content.attributes.capacity[0].value",
            "quote_or_value": 24,
            "value_sha256": sha256_json(24),
        })
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("allowlisted separator literals" in error for error in merged["errors"]))

    def test_suggested_template_rejects_free_rendered_fact(self):
        assessment = self.assessment("ADEQUATE")
        assessment["recommendations"] = [{
            "priority": "MEDIUM",
            "dimension": "clarity_and_readability",
            "attribute": "item_name",
            "current_problem": "The title needs a verified capacity.",
            "action": "Build a title from verified facts.",
            "fact_bindings": [{
                "binding_id": "capacity",
                "source_path": "$.current_content.attributes.capacity[0].value",
                "source_value": 24,
                "source_value_sha256": sha256_json(24),
                "rendered_fact": "BPA-Free",
            }],
            "suggested_template": [
                {"type": "BOUND_FACT", "binding_id": "capacity"},
            ],
            "completion_criterion": "The title passes review.",
        }]
        assessment["dimensions"]["clarity_and_readability"]["evidence"].append({
            "field_path": "$.current_content.attributes.capacity[0].value",
            "quote_or_value": 24,
            "value_sha256": sha256_json(24),
        })
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("typed facts" in error for error in merged["errors"]))

    def test_suggested_rewrite_cannot_target_unassessed_dimension(self):
        assessment = self.assessment("ADEQUATE")
        assessment["dimensions"]["clarity_and_readability"] = {
            "rating": "NOT_EVALUATED",
            "evidence_basis": "EVIDENCE_GAP",
            "rationale": "",
            "evidence": [],
            "missing_evidence": ["localized title"],
        }
        assessment["recommendations"] = [{
            "priority": "MEDIUM",
            "dimension": "clarity_and_readability",
            "attribute": "item_name",
            "current_problem": "The title was not supplied.",
            "action": "Rewrite the title.",
            "suggested_value": "Example Brand Bottle, 24 oz",
            "fact_bindings": [{
                "binding_id": "capacity",
                "source_path": "$.current_content.attributes.capacity[0].value",
                "source_value": 24,
                "source_value_sha256": sha256_json(24),
            }],
            "suggested_template": [
                {"type": "BOUND_FACT", "binding_id": "capacity"},
            ],
            "completion_criterion": "A localized title is supplied.",
        }]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("NOT_EVALUATED" in error for error in merged["errors"]))

    def test_unassessed_evidence_cannot_supply_a_fact_binding(self):
        assessment = self.assessment("ADEQUATE")
        assessment["dimensions"]["localization_quality"] = {
            "rating": "NOT_EVALUATED",
            "evidence_basis": "EVIDENCE_GAP",
            "rationale": "",
            "evidence": [{
                "field_path": "$.current_content.attributes.capacity[0].unit",
                "quote_or_value": "oz",
                "value_sha256": sha256_json("oz"),
            }],
            "missing_evidence": ["localized review"],
        }
        assessment["recommendations"] = [{
            "priority": "MEDIUM",
            "dimension": "clarity_and_readability",
            "attribute": "item_name",
            "current_problem": "The title needs a verified capacity.",
            "action": "Build a title from verified facts.",
            "fact_bindings": [{
                "binding_id": "capacity_unit",
                "source_path": "$.current_content.attributes.capacity[0].unit",
                "source_value": "oz",
                "source_value_sha256": sha256_json("oz"),
            }],
            "suggested_template": [
                {"type": "BOUND_FACT", "binding_id": "capacity_unit"},
            ],
            "completion_criterion": "The title passes review.",
        }]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("bound to assessed evidence" in error for error in merged["errors"]))

    def test_summary_does_not_change_official_gates(self):
        report = self.official_report()
        report["release_decision"] = "BLOCK"
        report["release_reasons"] = ["CANDIDATE_FULL_SCHEMA_VALIDATION_FAILED"]
        report["findings"] = [{
            "status": "OFFICIAL_ERROR",
            "code": "PTD_CONSTRAINT_VIOLATION",
            "source": "PTD",
            "applies_to_candidate": True,
            "message": "The candidate violates a bound constraint.",
        }]
        merged, valid = MODULE.merge_report(report, self.assessment(report=report))
        self.assertTrue(valid)
        self.assertEqual("BLOCK", merged["release_decision"])
        self.assertEqual("BLOCK", merged["executive_summary"]["official"]["release_decision"])
        self.assertEqual("OFFICIAL_EVIDENCE", merged["executive_summary"]["primary_reason"]["source"])
        self.assertEqual(
            "FIX_OFFICIAL_BLOCKER_AND_REVALIDATE",
            merged["executive_summary"]["primary_action"]["action_code"],
        )

    def test_official_evidence_gap_does_not_hide_content_quality_reason(self):
        report = self.official_report()
        report["current_listing_gate"] = "NOT_EVALUATED"
        report["candidate_preview_gate"] = "NOT_EVALUATED"
        report["candidate_local_validation_gate"] = "NOT_EVALUATED"
        report["release_decision"] = "NOT_EVALUATED"
        report["release_reasons"] = ["CANDIDATE_PREVIEW_NOT_EVALUATED"]
        report["official_validation_completeness"] = "INCOMPLETE"
        report["findings"] = [{
            "status": "NOT_EVALUATED",
            "code": "LISTING_SNAPSHOT_MISSING",
            "source": "LISTINGS_ITEMS",
            "applies_to_current": True,
            "message": "A traceable current Listing snapshot was not supplied.",
        }]
        report["official_report_sha256"] = official_report_sha256(report)
        assessment = self.assessment("ADEQUATE", report)
        assessment["dimensions"]["clarity_and_readability"].update({
            "rating": "WEAK",
            "rationale": "The supplied title is difficult to scan.",
        })

        merged, valid = MODULE.merge_report(report, assessment)

        self.assertTrue(valid)
        summary = merged["executive_summary"]
        self.assertEqual("1.3", summary["summary_version"])
        self.assertEqual(
            "clarity_and_readability", summary["primary_reason"]["dimension"]
        )
        self.assertEqual(
            "clarity_and_readability",
            summary["content_quality"]["primary_reason"]["dimension"],
        )
        self.assertEqual(
            "LISTING_SNAPSHOT_MISSING",
            summary["official_evidence"]["primary_reason"]["code"],
        )
        self.assertEqual(
            "INCOMPLETE", summary["official_evidence"]["validation_completeness"]
        )

    def test_nonapplicable_official_finding_is_not_primary(self):
        report = self.official_report()
        report["release_decision"] = "BLOCK"
        report["release_reasons"] = ["CANDIDATE_FULL_SCHEMA_VALIDATION_FAILED"]
        report["findings"] = [
            {
                "status": "OFFICIAL_ERROR",
                "code": "STALE_FOREIGN_ERROR",
                "message": "This error belongs to another candidate.",
                "source": "PTD",
                "applies_to_candidate": False,
            },
            {
                "status": "OFFICIAL_ERROR",
                "code": "PTD_CONSTRAINT_VIOLATION",
                "message": "The current candidate violates a constraint.",
                "source": "PTD",
                "applies_to_candidate": True,
            },
        ]
        merged, valid = MODULE.merge_report(report, self.assessment(report=report))
        self.assertTrue(valid)
        self.assertEqual(
            "PTD_CONSTRAINT_VIOLATION",
            merged["executive_summary"]["primary_reason"]["code"],
        )

    def test_assessment_must_bind_to_official_context_and_report(self):
        report = self.official_report()
        assessment = self.assessment(report=report)
        assessment["content_sha256"] = "0" * 64
        merged, valid = MODULE.merge_report(report, assessment)
        self.assertFalse(valid)
        self.assertTrue(any("content_sha256 does not match" in error for error in merged["errors"]))

        assessment = self.assessment(report=report)
        assessment["official_report_sha256"] = "0" * 64
        merged, valid = MODULE.merge_report(report, assessment)
        self.assertFalse(valid)
        self.assertTrue(any("official_report_sha256 does not match" in error for error in merged["errors"]))

        assessment = self.assessment(report=report)
        report["official_report_sha256"] = "0" * 64
        merged, valid = MODULE.merge_report(report, assessment)
        self.assertFalse(valid)
        self.assertTrue(any("field does not match" in error for error in merged["errors"]))

    def test_official_hash_ignores_display_fields_but_detects_canonical_changes(self):
        report = self.official_report()
        report["findings"] = [{
            "status": "OFFICIAL_WARNING",
            "code": "SYNTHETIC_WARNING",
            "message": "Synthetic canonical message.",
            "source": "PTD",
            "applies_to_candidate": True,
        }]
        report["official_scope"] = {"operation": "PATCH", "coverage": "PARTIAL"}
        report["listing_snapshot"] = {"request_id": "SYNTHETIC_REQUEST"}
        report["validation_preview"] = {"request_id": "SYNTHETIC_PREVIEW"}
        expected = official_report_sha256(report)
        decorated = json.loads(json.dumps(report))
        decorated["report_locale"] = "zh-CN"
        decorated["display"] = {"release_decision": "展示值"}
        decorated["quality_render_status"] = "VALIDATED"
        decorated["findings"][0].update({
            "status_label": "官方警告",
            "title_display": "展示标题",
            "message_original": "Synthetic canonical message.",
            "message_display": "展示消息",
        })
        self.assertEqual(expected, official_report_sha256(decorated))

        decorated["findings"][0]["message"] = "Changed canonical message."
        self.assertNotEqual(expected, official_report_sha256(decorated))

        for field, key in (
            ("official_scope", "coverage"),
            ("listing_snapshot", "request_id"),
            ("validation_preview", "request_id"),
        ):
            with self.subTest(field=field):
                changed = json.loads(json.dumps(report))
                changed[field][key] = "CHANGED_CANONICAL_VALUE"
                self.assertNotEqual(expected, official_report_sha256(changed))

        report = self.official_report()
        report["quality_contexts"]["CURRENT"]["evidence_manifest"][0]["value_type"] = "other"
        assessment = self.assessment(report=report)
        merged, valid = MODULE.merge_report(report, assessment)
        self.assertFalse(valid)
        self.assertTrue(any("manifest integrity" in error for error in merged["errors"]))

    def test_assessment_evidence_must_match_manifest_path_and_value(self):
        report = self.official_report()
        assessment = self.assessment(report=report)
        evidence = assessment["dimensions"]["content_completeness"]["evidence"][0]
        evidence["quote_or_value"] = "Fabricated title"
        evidence["value_sha256"] = sha256_json("Fabricated title")
        merged, valid = MODULE.merge_report(report, assessment)
        self.assertFalse(valid)
        self.assertTrue(any("manifest-bound evidence" in error for error in merged["errors"]))

    def test_full_score_keeps_weak_dimension_visible(self):
        assessment = self.assessment("STRONG")
        assessment["dimensions"]["localization_quality"]["rating"] = "WEAK"
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertTrue(valid)
        score = merged["executive_summary"]["evaluated_dimension_average"]
        self.assertEqual("FULL", score["status"])
        self.assertEqual(9.0, score["value"])
        self.assertFalse(score["comparable"])
        self.assertTrue(score["structurally_comparable"])
        self.assertEqual(["localization_quality"], score["weak_dimensions"])
        self.assertEqual("NEEDS_IMPROVEMENT", merged["quality_verdict"])

    def test_five_dimension_average_is_partial_and_not_comparable(self):
        assessment = self.assessment("STRONG")
        for name in MODULE.DIMENSIONS[-2:]:
            assessment["dimensions"][name] = {
                "rating": "NOT_EVALUATED",
                "evidence_basis": "EVIDENCE_GAP",
                "rationale": "",
                "evidence": [],
                "missing_evidence": ["required evidence"],
            }
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertTrue(valid)
        score = merged["executive_summary"]["evaluated_dimension_average"]
        self.assertEqual("PARTIAL", score["status"])
        self.assertEqual(10.0, score["value"])
        self.assertFalse(score["comparable"])
        self.assertFalse(score["structurally_comparable"])
        self.assertEqual(5, len(score["dimension_mask"]))

    def test_comparison_cohort_changes_with_model_or_locale_contract(self):
        report = self.official_report()
        first, valid = MODULE.merge_report(report, self.assessment(report=report))
        self.assertTrue(valid)
        second_assessment = self.assessment(report=report)
        second_assessment["assessment_model"] = "different-model"
        second, valid = MODULE.merge_report(report, second_assessment)
        self.assertTrue(valid)
        first_cohort = first["executive_summary"]["quality_score"]["comparison_cohort_sha256"]
        second_cohort = second["executive_summary"]["quality_score"]["comparison_cohort_sha256"]
        self.assertNotEqual(first_cohort, second_cohort)

        other_scope = self.official_report()
        other_scope["scope"]["product_type"] = "OTHER_PRODUCT_TYPE"
        other_scope["quality_contexts"]["CURRENT"]["scope_fingerprint_sha256"] = \
            scope_fingerprint(other_scope["scope"])
        other_assessment = self.assessment(report=other_scope)
        third, valid = MODULE.merge_report(other_scope, other_assessment)
        self.assertTrue(valid)
        third_cohort = third["executive_summary"]["quality_score"]["comparison_cohort_sha256"]
        self.assertNotEqual(first_cohort, third_cohort)

    def test_recommendation_priority_must_match_dimension_rating(self):
        assessment = self.assessment("ADEQUATE")
        assessment["dimensions"]["clarity_and_readability"]["rating"] = "WEAK"
        assessment["recommendations"] = [{
            "priority": "LOW",
            "dimension": "clarity_and_readability",
            "action": "Low priority action.",
            "completion_criterion": "Low action complete.",
        }]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("invalid for WEAK" in error for error in merged["errors"]))

        assessment["recommendations"][0]["priority"] = "HIGH"
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertTrue(valid)
        self.assertEqual("Low priority action.", merged["executive_summary"]["primary_action"]["action"])

    def test_strong_dimension_allows_only_low_priority_recommendation(self):
        assessment = self.assessment("STRONG")
        assessment["recommendations"] = [{
            "priority": "MEDIUM",
            "dimension": "clarity_and_readability",
            "action": "Optional polish.",
            "completion_criterion": "The optional review is complete.",
        }]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("invalid for STRONG" in error for error in merged["errors"]))

    def test_not_evaluated_recommendation_must_request_evidence(self):
        assessment = self.assessment("ADEQUATE")
        assessment["dimensions"]["localization_quality"] = {
            "rating": "NOT_EVALUATED",
            "evidence_basis": "EVIDENCE_GAP",
            "rationale": "",
            "evidence": [],
            "missing_evidence": ["localized review"],
        }
        assessment["recommendations"] = [{
            "priority": "HIGH",
            "dimension": "localization_quality",
            "action": "Provide a locale-qualified review.",
            "completion_criterion": "A qualified reviewer supplies the missing evidence.",
        }]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("must be an EVIDENCE_REQUEST" in error for error in merged["errors"]))

        assessment["recommendations"][0]["recommendation_type"] = "EVIDENCE_REQUEST"
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertTrue(valid)

    def test_not_evaluated_has_no_evidence_and_strong_has_no_missing_evidence(self):
        assessment = self.assessment("ADEQUATE")
        assessment["dimensions"]["localization_quality"] = {
            "rating": "NOT_EVALUATED",
            "evidence_basis": "EVIDENCE_GAP",
            "rationale": "",
            "evidence": [{
                "field_path": "$.current_content.title",
                "quote_or_value": "Example Brand Bottle",
                "value_sha256": sha256_json("Example Brand Bottle"),
            }],
            "missing_evidence": ["localized review"],
        }
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("evidence must be empty when NOT_EVALUATED" in error for error in merged["errors"]))

        assessment = self.assessment("STRONG")
        assessment["dimensions"]["clarity_and_readability"]["missing_evidence"] = ["more evidence"]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("missing_evidence must be empty when STRONG" in error for error in merged["errors"]))

    def test_suggested_template_rejects_unsafe_literals_and_reused_bindings(self):
        assessment = self.assessment("WEAK")
        recommendation = {
            "priority": "HIGH",
            "dimension": "clarity_and_readability",
            "attribute": "item_name",
            "current_problem": "The title needs review.",
            "action": "Build a title from bound facts.",
            "fact_bindings": [{
                "binding_id": "title",
                "source_path": "$.current_content.title",
                "source_value": "Example Brand Bottle",
                "source_value_sha256": sha256_json("Example Brand Bottle"),
            }],
            "completion_criterion": "The candidate passes PTD and Preview.",
        }
        assessment["recommendations"] = [recommendation]
        for literal in ("\n", "\t", "™", "®", "✓", "🔥", "%", "---", "- - -"):
            with self.subTest(literal=literal):
                recommendation["suggested_template"] = [
                    {"type": "BOUND_FACT", "binding_id": "title"},
                    {"type": "LITERAL", "value": literal},
                ]
                merged, valid = MODULE.merge_report(self.official_report(), assessment)
                self.assertFalse(valid)
                self.assertTrue(any("allowlisted separator literals" in error for error in merged["errors"]))

        self.assertTrue(MODULE.safe_template_literal("--"))

        recommendation["suggested_template"] = [
            {"type": "BOUND_FACT", "binding_id": "title"},
            {"type": "LITERAL", "value": " - "},
            {"type": "BOUND_FACT", "binding_id": "title"},
        ]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("exactly once" in error for error in merged["errors"]))

        recommendation["fact_bindings"] = [
            recommendation["fact_bindings"][0],
            {
                "binding_id": "same_title_under_another_id",
                "source_path": "$.current_content.title",
                "source_value": "Example Brand Bottle",
                "source_value_sha256": sha256_json("Example Brand Bottle"),
            },
        ]
        recommendation["suggested_template"] = [
            {"type": "BOUND_FACT", "binding_id": "title"},
            {"type": "LITERAL", "value": " - "},
            {"type": "BOUND_FACT", "binding_id": "same_title_under_another_id"},
        ]
        merged, valid = MODULE.merge_report(self.official_report(), assessment)
        self.assertFalse(valid)
        self.assertTrue(any("unique typed facts" in error for error in merged["errors"]))

    def test_review_prefers_current_official_error_and_preserves_source(self):
        report = self.official_report()
        report["release_decision"] = "REVIEW"
        report["release_reasons"] = ["CURRENT_LISTING_HAS_HISTORICAL_BLOCKERS"]
        report["findings"] = [
            {
                "status": "OFFICIAL_WARNING",
                "code": "PREVIEW_WARNING",
                "source": "VALIDATION_PREVIEW",
                "applies_to_candidate": True,
                "message": "Candidate warning.",
            },
            {
                "status": "OFFICIAL_ERROR",
                "code": "CURRENT_ERROR",
                "source": "LISTINGS_ITEMS",
                "applies_to_current": True,
                "message": "Current listing error.",
            },
        ]
        merged, valid = MODULE.merge_report(report, self.assessment(report=report))
        self.assertTrue(valid)
        reason = merged["executive_summary"]["primary_reason"]
        self.assertEqual("CURRENT_ERROR", reason["code"])
        self.assertEqual("LISTINGS_ITEMS", reason["finding_source"])

    def test_nonofficial_source_cannot_be_selected_as_official_summary(self):
        report = self.official_report()
        report["release_decision"] = "REVIEW"
        report["release_reasons"] = ["CANDIDATE_FULL_SCHEMA_VALIDATION_FAILED"]
        report["findings"] = [
            {
                "status": "SYSTEM_ERROR",
                "code": "MODEL_FAILURE",
                "source": "HEURISTIC",
                "applies_to_candidate": True,
                "message": "Nonofficial evaluator failed.",
            },
            {
                "status": "NOT_EVALUATED",
                "code": "PTD_REQUIRED",
                "source": "PTD",
                "applies_to_candidate": True,
                "message": "Full PTD validation is required.",
            },
        ]
        merged, valid = MODULE.merge_report(report, self.assessment(report=report))
        self.assertTrue(valid)
        summary = merged["executive_summary"]
        self.assertEqual("content_completeness", summary["primary_reason"]["dimension"])
        reason = summary["official_evidence"]["primary_reason"]
        self.assertEqual("PTD_REQUIRED", reason["code"])
        self.assertEqual("PTD", reason["finding_source"])


if __name__ == "__main__":
    unittest.main()
