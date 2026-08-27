#!/usr/bin/env python3
"""Render a stable diagnostic report with a separate display locale."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_LOCALES = {"en", "zh-CN"}


def load_messages(locale: str) -> dict[str, Any]:
    selected = locale if locale in SUPPORTED_LOCALES else "en"
    return json.loads((ROOT / "i18n" / f"{selected}.json").read_text(encoding="utf-8"))


def label(messages: dict[str, Any], group: str, value: Any) -> str:
    stable = str(value or "")
    return str(messages.get(group, {}).get(stable) or stable)


def localize_report(report: Any, locale: str) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise ValueError("report must be a JSON object")
    messages = load_messages(locale)
    result = copy.deepcopy(report)
    result["display_locale"] = locale if locale in SUPPORTED_LOCALES else "en"
    result["display"] = {
        "current_listing_gate": label(messages, "gate_labels", report.get("current_listing_gate")),
        "candidate_preview_gate": label(messages, "gate_labels", report.get("candidate_preview_gate")),
        "candidate_local_validation_gate": label(
            messages, "gate_labels", report.get("candidate_local_validation_gate")
        ),
        "release_decision": label(messages, "release_labels", report.get("release_decision")),
        "official_validation_completeness": (
            "完整" if locale == "zh-CN" and report.get("official_validation_completeness") == "COMPLETE"
            else "不完整" if locale == "zh-CN" else str(report.get("official_validation_completeness") or "")
        ),
    }
    code_titles = messages.get("code_titles", {})
    for row in result.get("findings", []):
        if not isinstance(row, dict):
            continue
        original = str(row.get("message") or "")
        code = str(row.get("code") or "")
        if locale == "zh-CN":
            title = str(code_titles.get(code) or "Amazon 官方返回的问题")
        else:
            title = original or code
        row["status_label"] = label(messages, "status_labels", row.get("status"))
        row["title_display"] = title
        row["message_original"] = original
        row["message_display"] = title if locale == "zh-CN" else original
    return result


def render_markdown(report: dict[str, Any], locale: str) -> str:
    localized = localize_report(report, locale)
    messages = load_messages(locale)
    headings = messages["headings"]
    fields = messages["fields"]
    display = localized["display"]
    lines = [
        f"# {headings['title']}",
        "",
        f"## {headings['summary']}",
        "",
        f"- {fields['current_listing']}: {display['current_listing_gate']} (`{report.get('current_listing_gate')}`)",
        f"- {fields['candidate_preview']}: {display['candidate_preview_gate']} (`{report.get('candidate_preview_gate')}`)",
        f"- {fields['candidate_local_validation']}: {display['candidate_local_validation_gate']} "
        f"(`{report.get('candidate_local_validation_gate')}`)",
        f"- {fields['release_decision']}: {display['release_decision']} (`{report.get('release_decision')}`)",
        f"- {fields['official_validation_completeness']}: {display['official_validation_completeness']} "
        f"(`{report.get('official_validation_completeness')}`)",
        "",
        f"## {headings['findings']}",
        "",
    ]
    findings = localized.get("findings") or []
    if not findings:
        lines.append(f"- {fields['none']}")
    for row in findings:
        lines.extend([
            f"- **{row.get('status_label')} · {row.get('title_display')}** "
            f"(`{row.get('code')}` / `{row.get('source')}`)",
            f"  - {headings['original_message']}: {row.get('message_original')}",
        ])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a localized Amazon Listing report")
    parser.add_argument("--report", type=Path, required=True, help="Diagnostic report JSON")
    parser.add_argument("--lang", choices=sorted(SUPPORTED_LOCALES), help="Display locale")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        locale = args.lang or str(report.get("report_locale") or "en")
        output = localize_report(report, locale) if args.format == "json" \
            else render_markdown(report, locale)
        print(json.dumps(output, ensure_ascii=False, indent=2) if isinstance(output, dict) else output)
        return 0
    except Exception as exc:
        print(json.dumps({
            "render_status": "SYSTEM_ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        }, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    sys.exit(main())
