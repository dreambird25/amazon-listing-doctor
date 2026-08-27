import ast
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents" / "skills" / "amazon-listing-doctor" / "scripts" / "render_report.py"
DIAGNOSE = ROOT / ".agents" / "skills" / "amazon-listing-doctor" / "scripts" / "diagnose_listing.py"
SPEC = importlib.util.spec_from_file_location("render_report", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
sys.path.insert(0, str(SCRIPT.parent))
from quality_contract import build_quality_context, official_report_sha256, sha256_json
from merge_report import merge_report


class RenderReportTest(unittest.TestCase):

    def report(self):
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
            "data_as_of": "2026-01-01T00:00:00Z",
            "quality_contexts": {
                "CURRENT": build_quality_context("CURRENT", scope, content),
            },
            "findings": [{
                "status": "OFFICIAL_ERROR",
                "code": "PTD_CONSTRAINT_VIOLATION",
                "source": "PTD",
                "applies_to_candidate": True,
                "message": "Measured value violates the bound PTD constraint.",
            }],
        }
        report["official_report_sha256"] = official_report_sha256(report)
        dimension_names = (
            "content_completeness",
            "clarity_and_readability",
            "intent_coverage",
            "buyer_question_coverage",
            "image_information_coverage",
            "cross_field_consistency",
            "localization_quality",
        )
        def evidence(path, value):
            return {"field_path": path, "quote_or_value": value, "value_sha256": sha256_json(value)}

        dimension_evidence = {
            "content_completeness": [
                evidence("$.current_content.title", "Example Brand Bottle"),
                evidence("$.current_content.bullets[0]", "Leak-resistant lid for daily use."),
            ],
            "clarity_and_readability": [evidence("$.current_content.title", "Example Brand Bottle")],
            "intent_coverage": [evidence(
                "$.current_content.description", "A reusable bottle for commuting and workouts."
            )],
            "buyer_question_coverage": [evidence(
                "$.current_content.bullets[0]", "Leak-resistant lid for daily use."
            )],
            "image_information_coverage": [evidence(
                "$.current_content.images[0].url", "https://example.invalid/main.jpg"
            )],
            "cross_field_consistency": [
                evidence("$.current_content.title", "Example Brand Bottle"),
                evidence("$.current_content.attributes.capacity[0].value", 24),
            ],
            "localization_quality": [evidence("$.current_content.title", "Example Brand Bottle")],
        }
        dimensions = {
            name: {
                "rating": "STRONG",
                "rationale": "The supplied content supports this dimension.",
                "evidence": dimension_evidence[name],
                "missing_evidence": [],
            }
            for name in dimension_names
        }
        dimensions["clarity_and_readability"].update({
            "rating": "WEAK",
            "rationale": "标题没有清楚表达已经验证的容量信息。",
        })
        dimensions["image_information_coverage"].update({
            "rating": "WEAK",
            "rationale": "只提供了一张图片。",
        })
        assessment = {
            "assessment_version": "1.3",
            "assessment_model": "test-model",
            "prompt_version": "quality-v1.4.0",
            "assessed_at": "2026-01-01T00:00:00Z",
            "assessment_target": "CURRENT",
            "assessment_locale": "en_US",
            "evidence_policy_version": "1.0",
            "scope_fingerprint_sha256": report["quality_contexts"]["CURRENT"]["scope_fingerprint_sha256"],
            "content_sha256": report["quality_contexts"]["CURRENT"]["content_sha256"],
            "official_report_sha256": official_report_sha256(report),
            "evidence_manifest_sha256": report["quality_contexts"]["CURRENT"]["evidence_manifest_sha256"],
            "dimensions": dimensions,
            "recommendations": [{
                "priority": "HIGH",
                "dimension": "clarity_and_readability",
                "attribute": "item_name",
                "current_problem": "标题缺少容量。",
                "action": "重写标题并保留已验证事实。",
                "completion_criterion": "新标题通过 PTD 与候选预检。",
                "fact_bindings": [
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
                ],
                "suggested_template": [
                    {"type": "BOUND_FACT", "binding_id": "product_name"},
                    {"type": "LITERAL", "value": ", "},
                    {"type": "BOUND_FACT", "binding_id": "capacity"},
                    {"type": "LITERAL", "value": " "},
                    {"type": "BOUND_FACT", "binding_id": "capacity_unit"},
                ],
            }],
            "limitations": ["No business performance metrics were supplied."],
        }
        capacity_evidence = {
            "field_path": "$.current_content.attributes.capacity[0].value",
            "quote_or_value": 24,
            "value_sha256": sha256_json(24),
        }
        assessment["dimensions"]["clarity_and_readability"]["evidence"].append(capacity_evidence)
        assessment["dimensions"]["clarity_and_readability"]["evidence"].append({
            "field_path": "$.current_content.attributes.capacity[0].unit",
            "quote_or_value": "oz",
            "value_sha256": sha256_json("oz"),
        })
        merged, valid = merge_report(report, assessment)
        self.assertTrue(valid)
        return merged

    def test_chinese_labels_do_not_claim_publication_success(self):
        localized = MODULE.localize_report(self.report(), "zh-CN")
        self.assertEqual("候选预检通过", localized["display"]["candidate_preview_gate"])
        self.assertEqual("候选本地校验通过", localized["display"]["candidate_local_validation_gate"])
        self.assertNotIn("发布成功", json.dumps(localized, ensure_ascii=False))
        self.assertEqual(
            "属性违反 PTD 约束", localized["findings"][0]["message_display"]
        )
        self.assertEqual(
            "Measured value violates the bound PTD constraint.",
            localized["findings"][0]["message_original"],
        )

    def test_all_static_engine_codes_have_chinese_titles(self):
        tree = ast.parse(DIAGNOSE.read_text(encoding="utf-8"))
        codes = {
            node.args[1].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "finding"
            and len(node.args) > 1
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        }
        messages = MODULE.load_messages("zh-CN")
        self.assertEqual(set(), codes - set(messages["code_titles"]))

    def test_markdown_keeps_stable_codes_and_original_message(self):
        markdown = MODULE.render_markdown(self.report(), "zh-CN", "detailed")
        self.assertIn("当前 Listing", markdown)
        self.assertNotIn("Current Listing:", markdown)
        self.assertIn("PTD_CONSTRAINT_VIOLATION", markdown)
        self.assertIn("Amazon/引擎原始信息", markdown)
        self.assertIn("Measured value violates", markdown)
        self.assertIn("七维内容质量明细", markdown)
        self.assertIn("建议与证据", markdown)
        self.assertIn("限制与未评估项", markdown)
        self.assertIn("质量评估追踪", markdown)
        self.assertIn("薄弱 (`WEAK`)", markdown)
        self.assertIn("已绑定事实", markdown)
        self.assertIn("$.current_content.attributes.capacity[0].value", markdown)

    def test_default_markdown_is_concise_operational_summary(self):
        markdown = MODULE.render_markdown(self.report(), "zh-CN")
        self.assertIn("Amazon Listing 质检结论", markdown)
        self.assertIn("ASIN_PLACEHOLDER", markdown)
        self.assertIn("MARKETPLACE_ID", markdown)
        self.assertIn("SELLER_SKU", markdown)
        self.assertIn("8.0 / 10", markdown)
        self.assertIn("完整七维评分", markdown)
        self.assertIn("七维结构完整: 是", markdown)
        self.assertIn("非 Amazon 官方评分", markdown)
        self.assertIn("官方验证完整度", markdown)
        self.assertIn("(`COMPLETE`)", markdown)
        self.assertIn("标题没有清楚表达", markdown)
        self.assertIn("仅使用已绑定的 Listing 事实", markdown)
        self.assertIn("Example Brand Bottle, 24 oz", markdown)
        self.assertNotIn("PTD_CONSTRAINT_VIOLATION", markdown)

    def test_official_only_report_is_not_scored(self):
        report = self.report()
        report.pop("executive_summary")
        report.pop("semantic_assessment")
        report.pop("merge_status")
        report.pop("quality_verdict")
        concise = MODULE.concise_report(report, "zh-CN")
        self.assertEqual("NOT_SCORED", concise["summary"]["quality_score"]["status"])
        self.assertEqual("未评分", concise["display"]["quality_score"])

    def test_renderer_rederives_instead_of_trusting_embedded_summary(self):
        report = self.report()
        report["executive_summary"]["quality_score"]["value"] = 10.0
        report["executive_summary"]["primary_action"]["suggested_value"] = "Unsupported claim"
        markdown = MODULE.render_markdown(report, "zh-CN")
        self.assertIn("8.0 / 10", markdown)
        self.assertNotIn("Unsupported claim", markdown)

    def test_invalid_assessment_cannot_inject_quality_verdict(self):
        report = self.report()
        report["semantic_assessment"] = {}
        report["quality_verdict"] = "STRONG"
        concise = MODULE.concise_report(report, "zh-CN")
        self.assertEqual("NOT_EVALUATED", concise["summary"]["quality_verdict"])
        self.assertEqual("NOT_SCORED", concise["summary"]["quality_score"]["status"])

    def test_detailed_json_rederives_summary_and_removes_invalid_quality(self):
        report = self.report()
        report["executive_summary"]["quality_score"]["value"] = 10.0
        report["executive_summary"]["primary_action"]["suggested_value"] = "Unsupported claim"
        detailed = MODULE.validated_detailed_report(report, "zh-CN")
        self.assertEqual("VALIDATED", detailed["quality_render_status"])
        self.assertEqual(8.0, detailed["executive_summary"]["quality_score"]["value"])
        self.assertNotIn("Unsupported claim", json.dumps(detailed, ensure_ascii=False))

        report["quality_verdict"] = "STRONG"
        report["quality_dimensions"] = {"clarity_and_readability": "STRONG"}
        report["quality_evidence_policy"] = {"passed": False}
        report["quality_assessment_trace"] = {"assessment_model": "forged"}
        report["performance_verdict"] = "STRONG"
        detailed = MODULE.validated_detailed_report(report, "zh-CN")
        self.assertEqual("NEEDS_IMPROVEMENT", detailed["quality_verdict"])
        self.assertEqual("WEAK", detailed["quality_dimensions"]["clarity_and_readability"])
        self.assertTrue(detailed["quality_evidence_policy"]["passed"])
        self.assertEqual("test-model", detailed["quality_assessment_trace"]["assessment_model"])
        self.assertEqual("NOT_EVALUATED", detailed["performance_verdict"])

        report["semantic_assessment"] = {}
        detailed = MODULE.validated_detailed_report(report, "zh-CN")
        self.assertEqual("INVALID_ASSESSMENT", detailed["quality_render_status"])
        self.assertNotIn("semantic_assessment", detailed)
        self.assertEqual("NOT_EVALUATED", detailed["quality_verdict"])

    def test_detailed_json_can_be_revalidated_after_display_fields_are_added(self):
        report = self.report()
        expected_hash = report["official_report_sha256"]
        first = MODULE.validated_detailed_report(report, "zh-CN")
        self.assertEqual("VALIDATED", first["quality_render_status"])
        first["report_locale"] = "zh-CN"
        second = MODULE.validated_detailed_report(first, "en")
        self.assertEqual("VALIDATED", second["quality_render_status"])
        self.assertEqual(expected_hash, second["official_report_sha256"])
        self.assertEqual(
            first["executive_summary"]["quality_score"],
            second["executive_summary"]["quality_score"],
        )

    def test_official_blocker_is_the_primary_concise_action(self):
        report = self.report()
        report["release_decision"] = "BLOCK"
        report["official_validation_completeness"] = "INCOMPLETE"
        report["executive_summary"]["primary_reason"] = {
            "source": "OFFICIAL_EVIDENCE",
            "status": "OFFICIAL_ERROR",
            "code": "PTD_CONSTRAINT_VIOLATION",
            "text": "Measured value violates the bound PTD constraint.",
        }
        report["executive_summary"]["primary_action"] = {
            "source": "OFFICIAL_EVIDENCE",
            "action_code": "FIX_OFFICIAL_BLOCKER_AND_REVALIDATE",
            "completion_code": "OFFICIAL_BLOCKER_CLEARED",
        }
        markdown = MODULE.render_markdown(report, "zh-CN")
        self.assertIn("属性违反 PTD 约束", markdown)
        self.assertIn("先修复上述 Amazon 官方错误", markdown)
        self.assertNotIn("标题没有清楚表达", markdown)


if __name__ == "__main__":
    unittest.main()
