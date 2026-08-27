#!/usr/bin/env python3
"""Render a stable diagnostic report with a separate display locale."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parent))
from merge_report import build_executive_summary, derive_quality, validate_assessment
from summary_contract import official_action, primary_official_finding


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
            messages, "local_gate_labels", report.get("candidate_local_validation_gate")
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


def fallback_executive_summary(report: dict[str, Any]) -> dict[str, Any]:
    scope = report.get("scope") if isinstance(report.get("scope"), dict) else {}
    official_reason = primary_official_finding(report)
    return {
        "summary_version": "1.0",
        "asin": scope.get("asin"),
        "official": {
            "current_listing_gate": report.get("current_listing_gate"),
            "candidate_preview_gate": report.get("candidate_preview_gate"),
            "candidate_local_validation_gate": report.get("candidate_local_validation_gate"),
            "release_decision": report.get("release_decision"),
            "validation_completeness": report.get("official_validation_completeness"),
        },
        "quality_verdict": "NOT_EVALUATED",
        "quality_score": {
            "status": "NOT_SCORED",
            "value": None,
            "scale": 10,
            "type": "INTERNAL_HEURISTIC",
            "official": False,
            "evaluated_dimensions": 0,
            "total_dimensions": 7,
            "minimum_dimensions_required": 5,
            "rubric_version": "1.0",
            "not_scored_reason": "No validated semantic quality assessment was merged.",
        },
        "primary_reason": official_reason,
        "primary_action": official_action(official_reason),
        "performance_verdict": "NOT_EVALUATED",
        "disclaimer": "Internal content-quality summary; not an Amazon official score or performance prediction.",
    }


def validated_executive_summary(report: dict[str, Any]) -> dict[str, Any]:
    assessment = report.get("semantic_assessment")
    if report.get("merge_status") != "OK" or validate_assessment(assessment):
        return fallback_executive_summary(report)
    verdict, _ = derive_quality(assessment["dimensions"])
    if report.get("quality_verdict") != verdict:
        return fallback_executive_summary(report)
    return build_executive_summary(report, assessment, verdict)


def concise_report(report: dict[str, Any], locale: str) -> dict[str, Any]:
    localized = localize_report(report, locale)
    summary = validated_executive_summary(report)
    messages = load_messages(locale)
    score = summary.get("quality_score") or {}
    reason = summary.get("primary_reason") or {}
    action = summary.get("primary_action") or {}
    reason_text = str(reason.get("text") or messages["fields"]["no_reason"])
    if reason.get("source") == "OFFICIAL_EVIDENCE" and locale == "zh-CN":
        reason_text = str(
            messages.get("code_titles", {}).get(str(reason.get("code") or "")) or reason_text
        )
    return {
        "display_locale": localized["display_locale"],
        "summary": summary,
        "display": {
            **localized["display"],
            "quality_verdict": label(messages, "quality_labels", summary.get("quality_verdict")),
            "quality_score": (
                f"{score.get('value')} / {score.get('scale')}"
                if score.get("status") == "SCORED" else messages["fields"]["not_scored"]
            ),
            "score_disclaimer": messages["fields"]["score_disclaimer"],
            "primary_reason": reason_text,
            "primary_action": (
                label(messages, "action_codes", action.get("action_code"))
                if action.get("action_code") else action.get("action")
            ) or messages["fields"]["no_action"],
            "completion_criterion": (
                label(messages, "completion_codes", action.get("completion_code"))
                if action.get("completion_code") else action.get("completion_criterion")
            ),
        },
    }


def render_concise_markdown(report: dict[str, Any], locale: str) -> str:
    view = concise_report(report, locale)
    summary = view["summary"]
    display = view["display"]
    messages = load_messages(locale)
    headings = messages["headings"]
    fields = messages["fields"]
    score = summary.get("quality_score") or {}
    reason = summary.get("primary_reason") or {}
    action = summary.get("primary_action") or {}
    asin = summary.get("asin") or "-"
    lines = [
        f"# {headings['concise_title']}",
        "",
        f"- {fields['asin']}: `{asin}`",
        f"- {fields['current_listing']}: {display['current_listing_gate']} "
        f"(`{report.get('current_listing_gate')}`)",
        f"- {fields['release_decision']}: {display['release_decision']} "
        f"(`{report.get('release_decision')}`)",
        f"- {fields['official_validation_completeness']}: "
        f"{display['official_validation_completeness']} "
        f"(`{report.get('official_validation_completeness')}`)",
        f"- {fields['quality_score']}: {display['quality_score']}（{display['score_disclaimer']}）"
        if locale == "zh-CN" else
        f"- {fields['quality_score']}: {display['quality_score']} ({display['score_disclaimer']})",
        f"- {fields['dimensions']}: {score.get('evaluated_dimensions', 0)} / "
        f"{score.get('total_dimensions', 7)}",
        f"- {fields['quality_verdict']}: {display['quality_verdict']} "
        f"(`{summary.get('quality_verdict')}`)",
        "",
        f"## {fields['primary_reason']}",
        "",
        str(display["primary_reason"]),
        "",
        f"## {fields['primary_action']}",
        "",
        str(display["primary_action"]),
    ]
    if action.get("suggested_value"):
        suggested_label = (
            f"{fields['suggested_value']}：" if locale == "zh-CN"
            else f"{fields['suggested_value']}:"
        )
        lines.extend(["", suggested_label, "", f"> {action['suggested_value']}"])
    if display.get("completion_criterion"):
        lines.extend(["", f"- {fields['completion_criterion']}: {display['completion_criterion']}"])
    return "\n".join(lines) + "\n"


def render_detailed_markdown(report: dict[str, Any], locale: str) -> str:
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


def render_markdown(report: dict[str, Any], locale: str, view: str = "concise") -> str:
    return render_concise_markdown(report, locale) if view == "concise" \
        else render_detailed_markdown(report, locale)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a localized Amazon Listing report")
    parser.add_argument("--report", type=Path, required=True, help="Diagnostic report JSON")
    parser.add_argument("--lang", choices=sorted(SUPPORTED_LOCALES), help="Display locale")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--view", choices=("concise", "detailed"), default="concise")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        locale = args.lang or str(report.get("report_locale") or "en")
        output = (
            concise_report(report, locale) if args.format == "json" and args.view == "concise"
            else localize_report(report, locale) if args.format == "json"
            else render_markdown(report, locale, args.view)
        )
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
