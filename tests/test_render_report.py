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
            "images": [{
                "url": "https://example.invalid/main.jpg",
                "is_main": True,
                "visual_observation": "A single bottle is visible on a plain background.",
            }],
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
                "CURRENT": build_quality_context("CURRENT", scope, content, {
                    "source_type": "STOREFRONT_OBSERVATION",
                    "content_scope": "BUYER_VISIBLE",
                    "coverage": "COMPLETE",
                    "missing_field_semantics": "OBSERVED_ABSENT",
                }),
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
                "$.current_content.images[0].visual_observation",
                "A single bottle is visible on a plain background.",
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
                "evidence_basis": "OBSERVED_CONTENT",
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
            "assessment_version": "1.4",
            "assessment_model": "test-model",
            "prompt_version": "quality-v1.4.0",
            "assessed_at": "2026-01-01T00:00:00Z",
            "assessment_target": "CURRENT",
            "assessment_locale": "en_US",
            "evidence_policy_version": "1.2",
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

    def test_concise_report_names_buyer_visible_content_scope(self):
        markdown = MODULE.render_concise_markdown(self.report(), "zh-CN")
        self.assertIn("内容证据范围: 买家前台可见内容", markdown)
        self.assertIn("内容证据覆盖: 本次目标范围已完整采集", markdown)
        self.assertIn("| 目标字段 | 原始值 | 候选值 |", markdown)
        self.assertIn("Example Brand Bottle", markdown)
        self.assertIn("Example Brand Bottle, 24 oz", markdown)

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
        self.assertIn("当前问题快照", markdown)
        self.assertNotIn("Current Listing:", markdown)
        self.assertIn("PTD_CONSTRAINT_VIOLATION", markdown)
        self.assertIn("Amazon/引擎原始信息", markdown)
        self.assertIn("Measured value violates", markdown)
        self.assertIn("七维内容质量明细", markdown)
        self.assertIn("建议与证据", markdown)
        self.assertIn("限制与未评估项", markdown)
        self.assertIn("质量评估追踪", markdown)
        self.assertIn("| 状态 | 问题标题 | 稳定代码 | 证据来源 | Amazon/引擎原始信息 |", markdown)
        self.assertIn("| 维度 | 评级 | 理由 | 证据 | 证据政策 | 缺失证据 |", markdown)
        self.assertIn("| 优先级 | 维度 | 目标字段 | 原始值 | 候选值 |", markdown)
        self.assertIn("候选值事实绑定", markdown)
        self.assertIn("$.current_content.attributes.capacity[0].value", markdown)

    def test_missing_exact_candidate_is_explicit(self):
        report = self.report()
        report["semantic_assessment"]["recommendations"] = []
        report["official_report_sha256"] = official_report_sha256(report)
        report["semantic_assessment"]["official_report_sha256"] = report[
            "official_report_sha256"
        ]
        markdown = MODULE.render_markdown(report, "zh-CN")
        self.assertIn("本轮未生成候选值", markdown)
        self.assertNotIn("需先补证据或人工确认", markdown)

    def test_chinese_concise_report_replaces_foreign_language_quality_reason(self):
        report = self.report()
        report["semantic_assessment"]["dimensions"]["clarity_and_readability"][
            "rationale"
        ] = "The title is difficult to scan."

        markdown = MODULE.render_markdown(report, "zh-CN")

        self.assertIn("所评估标题、要点或描述的表达影响快速理解与阅读。", markdown)
        self.assertNotIn("The title is difficult to scan.", markdown)

    def test_chinese_concise_report_rejects_token_chinese_prefix_on_english_reason(self):
        report = self.report()
        report["semantic_assessment"]["dimensions"]["clarity_and_readability"][
            "rationale"
        ] = "标题: The title is difficult to scan and repeats many English phrases."

        markdown = MODULE.render_markdown(report, "zh-CN")

        self.assertIn("所评估标题、要点或描述的表达影响快速理解与阅读。", markdown)
        self.assertNotIn("The title is difficult to scan", markdown)

    def test_official_stage_table_separates_snapshot_from_missing_ptd_and_preview(self):
        report = self.report()
        report["current_listing_gate"] = "NOT_EVALUATED"
        report["candidate_preview_gate"] = "NOT_EVALUATED"
        report["candidate_local_validation_gate"] = "NOT_EVALUATED"
        report["release_decision"] = "NOT_EVALUATED"
        report["release_reasons"] = ["CANDIDATE_PREVIEW_NOT_EVALUATED"]
        report["official_validation_completeness"] = "INCOMPLETE"
        report["official_evidence_coverage"] = {
            "current_listing_snapshot": "COMPLETE",
            "ptd_local_validation": "INCOMPLETE",
            "candidate_preview": "INCOMPLETE",
        }
        report["listing_snapshot"] = {
            "request_id": "REQUEST_ID",
            "fetched_at": "2026-01-01T00:00:00Z",
            "expires_at": "2026-01-01T00:10:00Z",
            "included_data": ["summaries", "attributes", "issues"],
            "issue_count": 0,
        }
        report["content_contract"] = {
            "candidate_content_present": False,
        }
        report["findings"] = [
            {
                "status": "NOT_EVALUATED",
                "code": "PTD_MISSING",
                "source": "PTD",
                "applies_to_current": True,
                "message": "PTD evidence was not supplied.",
            },
            {
                "status": "NOT_EVALUATED",
                "code": "VALIDATION_PREVIEW_NOT_RUN",
                "source": "VALIDATION_PREVIEW",
                "applies_to_candidate": True,
                "message": "Validation Preview was not run.",
            },
        ]
        report["official_report_sha256"] = official_report_sha256(report)
        report["semantic_assessment"]["official_report_sha256"] = report[
            "official_report_sha256"
        ]

        markdown = MODULE.render_markdown(report, "zh-CN")

        self.assertIn("| 当前问题快照 | 已获取 |", markdown)
        self.assertIn("| 当前快照问题 | 未发现已知问题 |", markdown)
        self.assertIn("| PTD 本地校验 | 本轮未完成 |", markdown)
        self.assertIn("| 候选内容 | 未提供可评估内容 |", markdown)
        self.assertIn("| 候选本地校验 | 未执行（无候选内容） |", markdown)
        self.assertIn("| 候选官方预检 | 未执行（无候选内容） |", markdown)
        self.assertIn("不代表当前问题快照未获取", markdown)
        self.assertNotIn("当前 Listing: 未评估", markdown)

    def test_official_stage_table_names_full_schema_validation(self):
        report = self.report()
        report["official_evidence_coverage"] = {
            "current_listing_snapshot": "COMPLETE",
            "ptd_local_validation": "FULL_JSON_SCHEMA",
            "candidate_preview": "COMPLETE",
        }
        report["official_report_sha256"] = official_report_sha256(report)
        report["semantic_assessment"]["official_report_sha256"] = report[
            "official_report_sha256"
        ]

        markdown = MODULE.render_markdown(report, "zh-CN")

        self.assertIn("| PTD 本地校验 | 已完成完整 Schema 校验 |", markdown)

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
        self.assertIn("内容质量", markdown)
        self.assertIn("Amazon 官方证据状态", markdown)
        self.assertIn("官方证据完整性", markdown)
        self.assertIn("| 官方证据完整性 | 已完成 |", markdown)
        self.assertIn("标题没有清楚表达", markdown)
        self.assertIn("仅使用已绑定的 Listing 事实", markdown)
        self.assertIn("Example Brand Bottle, 24 oz", markdown)
        self.assertNotIn("PTD_CONSTRAINT_VIOLATION", markdown)

    def test_chinese_concise_markdown_hides_machine_status_codes(self):
        markdown = MODULE.render_markdown(self.report(), "zh-CN")
        for machine_value in (
            "NEEDS_IMPROVEMENT", "FULL", "NO_KNOWN_OFFICIAL_ISSUES",
            "PASS", "COMPLETE", "PTD_CONSTRAINT_VIOLATION",
        ):
            self.assertNotIn(f"`{machine_value}`", markdown)
        self.assertIn("内容质量结论: 需要优化", markdown)
        self.assertIn("评分覆盖状态: 完整七维评分", markdown)
        self.assertIn("| 当前快照问题 | 尚未确认 |", markdown)

    def test_official_gap_is_separate_from_content_quality(self):
        report = self.report()
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
        report["semantic_assessment"]["official_report_sha256"] = report[
            "official_report_sha256"
        ]

        markdown = MODULE.render_markdown(report, "zh-CN")

        self.assertIn("内容质量原因", markdown)
        self.assertIn("标题没有清楚表达", markdown)
        self.assertIn("官方状态原因", markdown)
        self.assertIn("当前 Listing 可追溯快照缺失", markdown)
        self.assertIn("不代表 Listing 内容不完整", markdown)

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
        self.assertNotIn("quality_content_evidence", detailed)
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
        report["release_reasons"] = ["CANDIDATE_FULL_SCHEMA_VALIDATION_FAILED"]
        report["official_validation_completeness"] = "INCOMPLETE"
        report["findings"] = [{
            "status": "OFFICIAL_ERROR",
            "code": "PTD_CONSTRAINT_VIOLATION",
            "source": "PTD",
            "applies_to_candidate": True,
            "message": "Measured value violates the bound PTD constraint.",
        }]
        report["official_report_sha256"] = official_report_sha256(report)
        report["semantic_assessment"]["official_report_sha256"] = report[
            "official_report_sha256"
        ]
        markdown = MODULE.render_markdown(report, "zh-CN")
        self.assertIn("属性违反 PTD 约束", markdown)
        self.assertIn("先修复上述 Amazon 官方错误", markdown)
        self.assertIn("标题没有清楚表达", markdown)

    def test_preview_pass_with_historical_current_issue_requests_recheck(self):
        report = self.report()
        report["current_listing_gate"] = "BLOCK"
        report["candidate_preview_gate"] = "PASS"
        report["candidate_local_validation_gate"] = "PASS"
        report["release_decision"] = "REVIEW"
        report["release_reasons"] = ["CURRENT_LISTING_HAS_HISTORICAL_BLOCKERS"]
        report["findings"] = [{
            "status": "OFFICIAL_ERROR",
            "code": "OFFICIAL_ISSUE",
            "source": "LISTINGS_ITEMS",
            "applies_to_current": True,
            "applies_to_candidate": False,
            "message": "The current Listing still returns the historical issue.",
        }]
        report["official_report_sha256"] = official_report_sha256(report)
        report["semantic_assessment"]["official_report_sha256"] = report[
            "official_report_sha256"
        ]
        markdown = MODULE.render_markdown(report, "zh-CN")
        self.assertIn("| 候选官方预检 | 已通过 |", markdown)
        self.assertIn("无需仅因这个历史问题继续修改已通过该预检的候选字段", markdown)
        self.assertIn("其他候选校验仍需单独处理", markdown)
        self.assertIn("重新获取当前 Listing 问题", markdown)
        self.assertNotIn("先修复上述 Amazon 官方错误", markdown)


if __name__ == "__main__":
    unittest.main()
