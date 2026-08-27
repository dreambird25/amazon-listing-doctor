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
        return {
            "current_listing_gate": "NO_KNOWN_OFFICIAL_ISSUES",
            "candidate_preview_gate": "PASS",
            "candidate_local_validation_gate": "PASS",
            "release_decision": "PASS",
            "official_validation_completeness": "COMPLETE",
            "findings": [{
                "status": "OFFICIAL_ERROR",
                "code": "PTD_CONSTRAINT_VIOLATION",
                "source": "PTD",
                "message": "Measured value violates the bound PTD constraint.",
            }],
        }

    def test_chinese_labels_do_not_claim_publication_success(self):
        localized = MODULE.localize_report(self.report(), "zh-CN")
        self.assertEqual("候选预检通过", localized["display"]["candidate_preview_gate"])
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
        markdown = MODULE.render_markdown(self.report(), "zh-CN")
        self.assertIn("当前 Listing", markdown)
        self.assertNotIn("Current Listing:", markdown)
        self.assertIn("PTD_CONSTRAINT_VIOLATION", markdown)
        self.assertIn("Amazon/引擎原始信息", markdown)
        self.assertIn("Measured value violates", markdown)


if __name__ == "__main__":
    unittest.main()
