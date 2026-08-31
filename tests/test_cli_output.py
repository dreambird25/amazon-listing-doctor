import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "amazon-listing-doctor"
EXAMPLES = SKILL / "examples"


class CliOutputTest(unittest.TestCase):

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[bytes]:
        result = subprocess.run(
            [sys.executable, *arguments], capture_output=True, check=False
        )
        self.assertEqual(0, result.returncode, result.stderr.decode("utf-8", errors="replace"))
        self.assertEqual(b"", result.stdout)
        return result

    def assert_utf8_without_bom(self, path: Path):
        raw = path.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        return raw.decode("utf-8")

    def test_core_clis_write_explicit_utf8_artifacts(self):
        listing = EXAMPLES / "listing-valid.json"
        assessment = EXAMPLES / "semantic-assessment.json"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            official = target / "official.json"
            merged = target / "merged.json"
            markdown = target / "report-zh-CN.md"
            batch_input = target / "quality-observation.json"
            batch_output = target / "quality-observation-result.json"

            self.run_cli(
                str(ROOT / "scripts" / "diagnose_listing.py"),
                "--file", str(listing), "--output", str(official),
            )
            self.run_cli(
                str(SKILL / "scripts" / "merge_report.py"),
                "--official-report", str(official),
                "--semantic-assessment", str(assessment),
                "--output", str(merged),
            )
            self.run_cli(
                str(ROOT / "scripts" / "render_report.py"),
                "--report", str(merged),
                "--format", "markdown", "--output", str(markdown),
            )

            batch_input.write_text(json.dumps([{
                "sample_id": "SYNTHETIC_SAMPLE",
                "input": json.loads(listing.read_text(encoding="utf-8")),
                "assessment": json.loads(assessment.read_text(encoding="utf-8")),
            }], ensure_ascii=False), encoding="utf-8")
            self.run_cli(
                str(ROOT / "scripts" / "evaluate_batch.py"),
                "--file", str(batch_input), "--mode", "quality-observation",
                "--output", str(batch_output),
            )

            self.assertEqual("OK", json.loads(
                self.assert_utf8_without_bom(merged)
            )["merge_status"])
            self.assertIn("内容质量", self.assert_utf8_without_bom(markdown))
            self.assertEqual("quality-observation", json.loads(
                self.assert_utf8_without_bom(batch_output)
            )["mode"])
            self.assert_utf8_without_bom(official)


if __name__ == "__main__":
    unittest.main()
