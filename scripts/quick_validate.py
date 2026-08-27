#!/usr/bin/env python3
"""Fast repository validation using only the Python standard library."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "amazon-listing-doctor"
REQUIRED = (
    "README.md",
    "README_EN.md",
    "CHANGELOG.md",
    "LICENSE",
    "scripts/diagnose_listing.py",
    "scripts/compliance_report.py",
    ".agents/skills/amazon-listing-doctor/SKILL.md",
    ".agents/skills/amazon-listing-doctor/agents/openai.yaml",
    ".agents/skills/amazon-listing-doctor/assets/report-template.md",
    ".agents/skills/amazon-listing-doctor/references/evidence-model.md",
    ".agents/skills/amazon-listing-doctor/references/erp-integration.md",
    ".agents/skills/amazon-listing-doctor/references/quality-assessment.md",
    ".agents/skills/amazon-listing-doctor/references/report-contract.md",
    ".agents/skills/amazon-listing-doctor/scripts/diagnose_listing.py",
    ".agents/skills/amazon-listing-doctor/scripts/merge_report.py",
    ".agents/skills/amazon-listing-doctor/examples/listing-valid.json",
    ".agents/skills/amazon-listing-doctor/examples/listing-blocked.json",
    ".agents/skills/amazon-listing-doctor/examples/listing-incomplete.json",
    ".agents/skills/amazon-listing-doctor/examples/semantic-assessment.json",
)


def fail(message: str) -> None:
    raise AssertionError(message)


def validate_files() -> None:
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    if missing:
        fail(f"Missing required files: {', '.join(missing)}")


def validate_skill() -> None:
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        fail("SKILL.md frontmatter is missing or malformed")
    frontmatter = text.split("---", 2)[1]
    if not re.search(r"(?m)^name:\s+amazon-listing-doctor\s*$", frontmatter):
        fail("SKILL.md name is invalid")
    if not re.search(r"(?m)^description:\s+.+$", frontmatter):
        fail("SKILL.md description is missing")
    if not re.search(r"(?m)^\s+version:\s+1\.1\.0\s*$", frontmatter):
        fail("SKILL.md version is not 1.1.0")
    if (ROOT / "SKILL.md").exists():
        fail("Root SKILL.md would duplicate the repo-scoped skill")


def validate_public_boundary() -> None:
    forbidden = (
        re.compile(r"https?://(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+)", re.I),
        re.compile(r"(?i)(?:password|secret|token|api[_-]?key)\s*[:=]\s*['\"][^'\"]{8,}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    )
    candidates = [path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts]
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in forbidden:
            if pattern.search(text):
                fail(f"Potential private or secret content in {path.relative_to(ROOT)}")


def validate_tests() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT,
        check=False,
    )
    if result.returncode:
        fail("Unit tests failed")


def main() -> int:
    try:
        validate_files()
        validate_skill()
        validate_public_boundary()
        validate_tests()
    except AssertionError as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1
    print("Validation passed: structure, public boundary, and unit tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
