import ast
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents" / "skills" / "amazon-listing-doctor" / "scripts" / "render_report.py"
DIAGNOSE = ROOT / ".agents" / "skills" / "amazon-listing-doctor" / "scripts" / "diagnose_listing.py"
SPEC = importlib.util.spec_from_file_location("render_report", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RenderReportTest(unittest.TestCase):

    def report(self):
        report = {
            "scope": {"asin": "ASIN_PLACEHOLDER"},
            "current_listing_gate": "NO_KNOWN_OFFICIAL_ISSUES",
            "candidate_preview_gate": "PASS",
            "candidate_local_validation_gate": "PASS",
            "release_decision": "PASS",
            "official_validation_completeness": "COMPLETE",
            "executive_summary": {
                "summary_version": "1.0",
                "asin": "ASIN_PLACEHOLDER",
                "official": {
                    "current_listing_gate": "NO_KNOWN_OFFICIAL_ISSUES",
                    "candidate_preview_gate": "PASS",
                    "candidate_local_validation_gate": "PASS",
                    "release_decision": "PASS",
                    "validation_completeness": "COMPLETE"
                },
                "quality_verdict": "NEEDS_IMPROVEMENT",
                "quality_score": {
                    "status": "SCORED",
                    "value": 8.0,
                    "scale": 10,
                    "type": "INTERNAL_HEURISTIC",
                    "official": False,
                    "evaluated_dimensions": 6,
                    "total_dimensions": 7,
                    "minimum_dimensions_required": 5,
                    "rubric_version": "1.0"
                },
                "primary_reason": {
                    "dimension": "clarity_and_readability",
                    "rating": "WEAK",
                    "text": "标题没有清楚表达已经验证的容量信息。"
                },
                "primary_action": {
                    "priority": "HIGH",
                    "dimension": "clarity_and_readability",
                    "attribute": "item_name",
                    "current_problem": "标题缺少容量。",
                    "action": "重写标题并保留已验证事实。",
                    "suggested_value": "Example Brand Bottle, 24 oz",
                    "completion_criterion": "新标题通过 PTD 与候选预检。",
                    "source_evidence": [{"field": "capacity", "quote_or_value": "24 oz"}],
                    "rewrite_is_advisory": True
                },
                "performance_verdict": "NOT_EVALUATED",
                "disclaimer": "Internal content-quality summary; not an Amazon official score."
            },
            "findings": [{
                "status": "OFFICIAL_ERROR",
                "code": "PTD_CONSTRAINT_VIOLATION",
                "source": "PTD",
                "message": "Measured value violates the bound PTD constraint.",
            }],
        }
        dimension_names = (
            "content_completeness",
            "clarity_and_readability",
            "intent_coverage",
            "buyer_question_coverage",
            "image_information_coverage",
            "cross_field_consistency",
            "localization_quality",
        )
        dimensions = {
            name: {
                "rating": "STRONG",
                "rationale": "The supplied content supports this dimension.",
                "evidence": [{"field": "title", "quote_or_value": "Example title, 24 oz"}],
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
            "assessment_version": "1.1",
            "assessment_model": "test-model",
            "prompt_version": "quality-v1.3.1",
            "assessed_at": "2026-01-01T00:00:00Z",
            "dimensions": dimensions,
            "recommendations": [{
                "priority": "HIGH",
                "dimension": "clarity_and_readability",
                "attribute": "item_name",
                "current_problem": "标题缺少容量。",
                "action": "重写标题并保留已验证事实。",
                "suggested_value": "Example Brand Bottle, 24 oz",
                "completion_criterion": "新标题通过 PTD 与候选预检。",
                "source_evidence": [{"field": "title", "quote_or_value": "Example title, 24 oz"}],
            }],
            "limitations": ["No business performance metrics were supplied."],
        }
        report["merge_status"] = "OK"
        report["quality_verdict"] = "NEEDS_IMPROVEMENT"
        report["semantic_assessment"] = assessment
        report["executive_summary"] = MODULE.build_executive_summary(
            report, assessment, "NEEDS_IMPROVEMENT"
        )
        return report

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

    def test_default_markdown_is_concise_operational_summary(self):
        markdown = MODULE.render_markdown(self.report(), "zh-CN")
        self.assertIn("Amazon Listing 质检结论", markdown)
        self.assertIn("ASIN_PLACEHOLDER", markdown)
        self.assertIn("8.0 / 10", markdown)
        self.assertIn("非 Amazon 官方评分", markdown)
        self.assertIn("官方验证完整度", markdown)
        self.assertIn("(`COMPLETE`)", markdown)
        self.assertIn("标题没有清楚表达", markdown)
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
