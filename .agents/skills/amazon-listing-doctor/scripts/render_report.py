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
from cli_output import emit_utf8
from merge_report import (
    assessment_content_evidence,
    build_executive_summary,
    combined_quality_completeness,
    derive_quality,
    render_suggested_template,
    validate_assessment,
)
from quality_policy import evaluate_evidence_policy
from summary_contract import (
    derive_evidence_stages,
    official_action,
    primary_official_finding,
)


ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_LOCALES = {"en", "zh-CN"}


def load_messages(locale: str) -> dict[str, Any]:
    selected = locale if locale in SUPPORTED_LOCALES else "en"
    return json.loads((ROOT / "i18n" / f"{selected}.json").read_text(encoding="utf-8"))


def label(messages: dict[str, Any], group: str, value: Any) -> str:
    stable = str(value or "")
    return str(messages.get(group, {}).get(stable) or stable)


def markdown_cell(value: Any) -> str:
    """Render one value inside a compact Markdown table cell."""
    if value is None or value == "":
        return "-"
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) \
        else str(value)
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")
    )


def is_chinese_conclusion(value: Any) -> bool:
    text = str(value or "")
    han_count = sum("\u3400" <= char <= "\u9fff" for char in text)
    latin_count = sum(char.isascii() and char.isalpha() for char in text)
    return han_count >= 6 and han_count / max(han_count + latin_count, 1) >= 0.2


def evidence_values(
        rows: Any, *, include_paths: bool = False,
) -> str:
    rendered = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        value = markdown_cell(row.get("quote_or_value", row.get("value")))
        path = markdown_cell(row.get("field_path"))
        rendered.append(f"`{path}` = {value}" if include_paths and path != "-" else value)
    return "<br>".join(rendered) or "-"


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
        "official_validation_completeness": label(
            messages,
            "validation_completeness_labels",
            report.get("official_validation_completeness"),
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
    official_primary_action = official_action(official_reason, report)
    current_context = (report.get("quality_contexts") or {}).get("CURRENT") \
        if isinstance(report.get("quality_contexts"), dict) else {}
    content_evidence = current_context.get("content_evidence") \
        if isinstance(current_context, dict) else {}
    content_evidence = copy.deepcopy(content_evidence) \
        if isinstance(content_evidence, dict) else {}
    score = {
        "status": "NOT_SCORED",
        "value": None,
        "raw_evaluated_average": None,
        "scale": 10,
        "type": "INTERNAL_HEURISTIC",
        "official": False,
        "comparable": False,
        "structurally_comparable": False,
        "comparison_rule": "BOTH_FULL_AND_SAME_COMPARISON_COHORT",
        "comparison_cohort_sha256": None,
        "evaluated_dimensions": 0,
        "total_dimensions": 7,
        "minimum_dimensions_required": 5,
        "dimension_mask": [],
        "weak_dimensions": [],
        "rubric_version": "1.1",
        "not_scored_reason": "No validated semantic quality assessment was merged.",
        "content_scope": content_evidence.get("content_scope"),
        "content_coverage": content_evidence.get("coverage"),
    }
    result = {
        "summary_version": "1.4",
        "identity": {
            "marketplace_id": scope.get("marketplace_id"),
            "seller_sku": scope.get("sku"),
            "asin": scope.get("asin"),
        },
        "official": {
            "current_listing_gate": report.get("current_listing_gate"),
            "candidate_preview_gate": report.get("candidate_preview_gate"),
            "candidate_local_validation_gate": report.get("candidate_local_validation_gate"),
            "release_decision": report.get("release_decision"),
            "validation_completeness": report.get("official_validation_completeness"),
        },
        "evidence_stages": derive_evidence_stages(report),
        "quality_verdict": "NOT_EVALUATED",
        "content_evidence": content_evidence,
        "evaluated_dimension_average": score,
        "primary_reason": official_reason,
        "primary_action": official_primary_action,
        "quality_primary_reason": None,
        "quality_primary_action": None,
        "change_preview": {
            "dimension": None,
            "attribute": None,
            "original_values": [],
            "candidate_value": None,
            "candidate_available": False,
        },
        "official_primary_reason": official_reason,
        "official_primary_action": official_primary_action,
        "content_quality": {
            "verdict": "NOT_EVALUATED",
            "evidence_completeness": "NOT_EVALUATED",
            "content_evidence": copy.deepcopy(content_evidence),
            "evaluated_dimension_average": copy.deepcopy(score),
            "primary_reason": None,
            "primary_action": None,
            "change_preview": {
                "dimension": None,
                "attribute": None,
                "original_values": [],
                "candidate_value": None,
                "candidate_available": False,
            },
        },
        "official_evidence": {
            "validation_completeness": report.get("official_validation_completeness"),
            "coverage": copy.deepcopy(report.get("official_evidence_coverage") or {}),
            "primary_reason": copy.deepcopy(official_reason),
            "primary_action": copy.deepcopy(official_primary_action),
        },
        "performance_verdict": "NOT_EVALUATED",
        "disclaimer": "Internal content-quality summary; not an Amazon official score or performance prediction.",
    }
    result["quality_score"] = copy.deepcopy(result["evaluated_dimension_average"])
    return result


def validated_executive_summary(report: dict[str, Any]) -> dict[str, Any]:
    assessment = report.get("semantic_assessment")
    if report.get("merge_status") != "OK" or validate_assessment(assessment, report):
        return fallback_executive_summary(report)
    verdict, _ = derive_quality(assessment["dimensions"])
    return build_executive_summary(report, assessment, verdict)


def concise_report(report: dict[str, Any], locale: str) -> dict[str, Any]:
    localized = localize_report(report, locale)
    summary = validated_executive_summary(report)
    messages = load_messages(locale)
    score = summary.get("evaluated_dimension_average") or {}
    content_evidence = summary.get("content_evidence") or {}
    reason = summary.get("primary_reason") or {}
    action = summary.get("primary_action") or {}
    quality_reason = summary.get("quality_primary_reason") or {}
    quality_action = summary.get("quality_primary_action") or {}
    official_reason = summary.get("official_primary_reason") or {}
    official_primary_action = summary.get("official_primary_action") or {}
    change_preview = summary.get("change_preview") or {}
    evidence_stages = summary.get("evidence_stages") or derive_evidence_stages(report)

    def reason_text(value: dict[str, Any], fallback: str) -> str:
        result = str(value.get("text") or fallback)
        if value.get("source") == "OFFICIAL_EVIDENCE" and locale == "zh-CN":
            result = str(
                messages.get("code_titles", {}).get(str(value.get("code") or "")) or result
            )
        elif locale == "zh-CN" and value.get("dimension") and not is_chinese_conclusion(result):
            fallback_group = "quality_reason_fallbacks" \
                if value.get("rating") == "WEAK" else "quality_rating_reason_fallbacks"
            fallback_key = value.get("dimension") \
                if value.get("rating") == "WEAK" else value.get("rating")
            result = str(
                messages.get(fallback_group, {}).get(str(fallback_key or ""))
                or messages["fields"]["no_reason"]
            )
        return result

    def action_text(value: dict[str, Any], fallback: str) -> str:
        return str(
            label(messages, "action_codes", value.get("action_code"))
            if value.get("action_code") else value.get("action") or fallback
        )

    return {
        "display_locale": localized["display_locale"],
        "summary": summary,
        "display": {
            **localized["display"],
            "quality_verdict": label(messages, "quality_labels", summary.get("quality_verdict")),
            "quality_score": (
                f"{score.get('value')} / {score.get('scale')}"
                if score.get("status") in {"FULL", "PARTIAL"} else messages["fields"]["not_scored"]
            ),
            "score_status": label(messages, "score_status_labels", score.get("status")),
            "score_disclaimer": messages["fields"]["score_disclaimer"],
            "content_scope": label(
                messages, "content_scope_labels", content_evidence.get("content_scope")
            ),
            "content_coverage": label(
                messages, "content_coverage_labels", content_evidence.get("coverage")
            ),
            "primary_reason": reason_text(reason, messages["fields"]["no_reason"]),
            "primary_action": action_text(action, messages["fields"]["no_action"]),
            "content_primary_reason": reason_text(
                quality_reason, messages["fields"]["no_reason"]
            ),
            "content_primary_action": action_text(
                quality_action, messages["fields"]["no_action"]
            ),
            "official_primary_reason": reason_text(
                official_reason, messages["fields"]["no_official_reason"]
            ),
            "official_primary_action": action_text(
                official_primary_action, messages["fields"]["no_official_action"]
            ),
            "completion_criterion": (
                label(messages, "completion_codes", quality_action.get("completion_code"))
                if quality_action.get("completion_code")
                else quality_action.get("completion_criterion")
            ),
            "candidate_value": (
                change_preview.get("candidate_value")
                if change_preview.get("candidate_available")
                else messages["fields"]["candidate_not_generated"]
            ),
            "evidence_stages": {
                key: label(messages, "evidence_stage_labels", value)
                for key, value in evidence_stages.items()
            },
        },
    }


def render_concise_markdown(report: dict[str, Any], locale: str) -> str:
    view = concise_report(report, locale)
    summary = view["summary"]
    display = view["display"]
    messages = load_messages(locale)
    headings = messages["headings"]
    fields = messages["fields"]
    score = summary.get("evaluated_dimension_average") or {}
    quality_action = summary.get("quality_primary_action") or {}
    official_reason = summary.get("official_primary_reason") or {}
    official_primary_action = summary.get("official_primary_action") or {}
    change_preview = summary.get("change_preview") or {}
    evidence_stages = display.get("evidence_stages") or {}
    identity = summary.get("identity") or {}
    weak_dimensions = score.get("weak_dimensions") or []
    weak_display = ", ".join(
        label(messages, "dimension_labels", name) for name in weak_dimensions
    ) or fields["none"]
    lines = [
        f"# {headings['concise_title']}",
        "",
        f"- {fields['marketplace']}: `{identity.get('marketplace_id') or '-'}`",
        f"- {fields['seller_sku']}: `{identity.get('seller_sku') or '-'}`",
        f"- {fields['asin']}: `{identity.get('asin') or '-'}`",
        "",
        f"## {headings['content_quality']}",
        "",
        f"- {fields['content_evidence_scope']}: {display['content_scope']}",
        f"- {fields['content_evidence_coverage']}: {display['content_coverage']}",
        f"- {fields['evaluated_dimension_average']}: {display['quality_score']}"
        f"（{display['score_disclaimer']}）" if locale == "zh-CN" else
        f"- {fields['evaluated_dimension_average']}: {display['quality_score']} "
        f"({display['score_disclaimer']})",
        f"- {fields['score_status']}: {display['score_status']}",
        f"- {fields['dimensions']}: {score.get('evaluated_dimensions', 0)} / "
        f"{score.get('total_dimensions', 7)}",
        f"- {fields['weak_dimensions']}: {weak_display}",
        f"- {fields['structurally_comparable']}: "
        f"{fields['yes'] if score.get('structurally_comparable') else fields['no']}",
        f"- {fields['quality_verdict']}: {display['quality_verdict']}",
        "",
        f"### {fields['content_primary_reason']}",
        "",
        str(display["content_primary_reason"]),
        "",
        f"### {fields['content_primary_action']}",
        "",
        str(display["content_primary_action"]),
        "",
        f"### {headings['change_preview']}",
        "",
        f"| {fields['target_field']} | {fields['original_value']} | {fields['candidate_value']} |",
        "|---|---|---|",
        f"| {markdown_cell(change_preview.get('attribute') or label(messages, 'dimension_labels', change_preview.get('dimension')))} "
        f"| {evidence_values(change_preview.get('original_values'))} "
        f"| {markdown_cell(display['candidate_value'])} |",
    ]
    quality_completion = display.get("completion_criterion")
    if quality_completion:
        lines.extend(["", f"- {fields['completion_criterion']}: {quality_completion}"])

    lines.extend([
        "",
        f"## {headings['official_evidence']}",
        "",
        f"| {fields['evidence_stage']} | {fields['status']} |",
        "|---|---|",
        f"| {fields['current_snapshot']} | {evidence_stages.get('current_snapshot', fields['unknown'])} |",
        f"| {fields['current_snapshot_issues']} | {evidence_stages.get('current_issues', fields['unknown'])} |",
        f"| {fields['ptd_local_validation']} | {evidence_stages.get('ptd_local_validation', fields['unknown'])} |",
        f"| {fields['candidate_content']} | {evidence_stages.get('candidate_content', fields['unknown'])} |",
        f"| {fields['candidate_local_validation']} | {evidence_stages.get('candidate_local_validation', fields['unknown'])} |",
        f"| {fields['candidate_preview']} | {evidence_stages.get('candidate_preview', fields['unknown'])} |",
        f"| {fields['release_decision']} | {display['release_decision']} |",
        f"| {fields['official_validation_completeness']} | {display['official_validation_completeness']} |",
    ])
    if report.get("official_validation_completeness") != "COMPLETE":
        lines.extend(["", f"> {fields['official_incomplete_note']}"])
    if official_reason:
        lines.extend([
            "",
            f"### {fields['official_primary_reason']}",
            "",
            str(display["official_primary_reason"]),
        ])
    if official_primary_action:
        lines.extend([
            "",
            f"### {fields['official_primary_action']}",
            "",
            str(display["official_primary_action"]),
        ])
        completion = (
            label(messages, "completion_codes", official_primary_action.get("completion_code"))
            if official_primary_action.get("completion_code")
            else official_primary_action.get("completion_criterion")
        )
        if completion:
            lines.extend(["", f"- {fields['completion_criterion']}: {completion}"])
    return "\n".join(lines) + "\n"


def render_detailed_markdown(report: dict[str, Any], locale: str) -> str:
    localized = localize_report(report, locale)
    messages = load_messages(locale)
    headings = messages["headings"]
    fields = messages["fields"]
    lines = [
        render_concise_markdown(report, locale).rstrip(),
        "", f"## {headings['official_findings']}", "",
        f"| {fields['status']} | {fields['finding_title']} | {fields['code']} | "
        f"{fields['source']} | {headings['original_message']} |",
        "|---|---|---|---|---|",
    ]
    findings = localized.get("findings") or []
    if not findings:
        lines.append(f"| {fields['none']} | - | - | - | - |")
    for row in findings:
        lines.append(
            f"| {markdown_cell(row.get('status_label'))} "
            f"| {markdown_cell(row.get('title_display'))} "
            f"| `{markdown_cell(row.get('code'))}` "
            f"| `{markdown_cell(row.get('source'))}` "
            f"| {markdown_cell(row.get('message_original'))} |"
        )

    assessment = report.get("semantic_assessment")
    assessment_errors = validate_assessment(assessment, report)
    if not assessment_errors:
        policy, _ = evaluate_evidence_policy(assessment, report)
        policy_dimensions = policy["dimensions"]
        lines.extend([
            "", f"## {headings['quality_dimensions']}", "",
            f"| {fields['dimension']} | {fields['rating']} | {fields['rationale']} | "
            f"{fields['evidence']} | {fields['evidence_policy']} | {fields['missing_evidence']} |",
            "|---|---|---|---|---|---|",
        ])
        for name, row in assessment["dimensions"].items():
            dimension_label = label(messages, "dimension_labels", name)
            dimension_policy = policy_dimensions.get(name) \
                if isinstance(policy_dimensions, dict) else None
            policy_text = "-"
            if isinstance(dimension_policy, dict):
                policy_text = (
                    f"`{markdown_cell(dimension_policy.get('rule_code'))}` / "
                    f"{'PASS' if dimension_policy.get('passed') else 'FAIL'}"
                )
            lines.append(
                f"| {markdown_cell(dimension_label)} "
                f"| {markdown_cell(label(messages, 'quality_labels', row.get('rating')))} "
                f"| {markdown_cell(row.get('rationale'))} "
                f"| {evidence_values(row.get('evidence'), include_paths=True)} "
                f"| {policy_text} "
                f"| {markdown_cell('; '.join(str(item) for item in row.get('missing_evidence') or []))} |"
            )

        lines.extend([
            "", f"## {headings['recommendations']}", "",
            f"| {fields['priority']} | {fields['dimension']} | {fields['target_field']} | "
            f"{fields['original_value']} | {fields['candidate_value']} | "
            f"{fields['primary_action']} | {fields['completion_criterion']} |",
            "|---|---|---|---|---|---|---|",
        ])
        recommendations = assessment.get("recommendations") or []
        if not recommendations:
            lines.append(f"| - | - | - | - | {fields['candidate_not_generated']} | {fields['none']} | - |")
        for recommendation in recommendations:
            suggested_value = render_suggested_template(recommendation)
            dimension = (assessment.get("dimensions") or {}).get(
                recommendation.get("dimension")
            ) or {}
            original = evidence_values(dimension.get("evidence"), include_paths=True)
            candidate = suggested_value or fields["candidate_not_generated"]
            lines.append(
                f"| {markdown_cell(recommendation.get('priority'))} "
                f"| {markdown_cell(label(messages, 'dimension_labels', recommendation.get('dimension')))} "
                f"| {markdown_cell(recommendation.get('attribute'))} "
                f"| {original} "
                f"| {markdown_cell(candidate)} "
                f"| {markdown_cell(recommendation.get('action'))} "
                f"| {markdown_cell(recommendation.get('completion_criterion'))} |"
            )

        bindings = [
            (recommendation, binding)
            for recommendation in recommendations
            for binding in recommendation.get("fact_bindings") or []
        ]
        if bindings:
            lines.extend(["", f"### {headings['fact_bindings']}", ""])
            lines.extend([
                f"- `{binding.get('binding_id')}` = {binding.get('source_value')} "
                f"← `{binding.get('source_path')}` (`{binding.get('source_value_sha256')}`)"
                for _, binding in bindings
            ])

        lines.extend(["", f"## {headings['limitations']}", ""])
        limitations = assessment.get("limitations") or []
        lines.extend(f"- {item}" for item in limitations or [fields["none"]])

        lines.extend(["", f"## {headings['quality_trace']}", ""])
        for key in (
            "assessment_version", "assessment_model", "prompt_version", "assessed_at",
            "assessment_target", "assessment_locale", "evidence_policy_version",
            "scope_fingerprint_sha256", "content_sha256",
            "official_report_sha256", "evidence_manifest_sha256",
        ):
            lines.append(f"- `{key}`: `{assessment.get(key)}`")
    else:
        lines.extend(["", f"## {headings['limitations']}", ""])
        lines.append("- Quality assessment was not rendered because its binding is invalid.")
    return "\n".join(lines) + "\n"


def validated_detailed_report(report: dict[str, Any], locale: str) -> dict[str, Any]:
    result = localize_report(report, locale)
    assessment = report.get("semantic_assessment")
    errors = validate_assessment(assessment, report)
    summary = validated_executive_summary(report)
    result["executive_summary"] = summary
    if errors:
        for field in (
            "semantic_assessment", "quality_dimensions", "quality_evidence_completeness",
            "quality_content_evidence", "quality_evidence_policy", "quality_assessment_trace",
        ):
            result.pop(field, None)
        result["quality_verdict"] = "NOT_EVALUATED"
        result["quality_render_status"] = "INVALID_ASSESSMENT"
        result["quality_render_errors"] = errors
    else:
        verdict, dimension_completeness = derive_quality(assessment["dimensions"])
        content_evidence = assessment_content_evidence(report, assessment)
        completeness = combined_quality_completeness(
            dimension_completeness, content_evidence
        )
        policy, _ = evaluate_evidence_policy(assessment, report)
        result["quality_verdict"] = verdict
        result["quality_dimensions"] = {
            name: row["rating"] for name, row in assessment["dimensions"].items()
        }
        result["quality_evidence_completeness"] = completeness
        result["quality_content_evidence"] = content_evidence
        result["quality_evidence_policy"] = policy
        result["quality_assessment_trace"] = {
            key: assessment[key] for key in (
                "assessment_version", "assessment_model", "prompt_version", "assessed_at",
                "assessment_target", "assessment_locale", "evidence_policy_version",
                "scope_fingerprint_sha256", "content_sha256", "official_report_sha256",
                "evidence_manifest_sha256",
            )
        }
        result["performance_verdict"] = "NOT_EVALUATED"
        result["quality_render_status"] = "VALIDATED"
    return result


def render_markdown(report: dict[str, Any], locale: str, view: str = "concise") -> str:
    return render_concise_markdown(report, locale) if view == "concise" \
        else render_detailed_markdown(report, locale)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a localized Amazon Listing report")
    parser.add_argument("--report", type=Path, required=True, help="Diagnostic report JSON")
    parser.add_argument("--lang", choices=sorted(SUPPORTED_LOCALES), help="Display locale")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--view", choices=("concise", "detailed"), default="concise")
    parser.add_argument("--output", type=Path, help="Write the UTF-8 report to this file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        locale = args.lang or str(report.get("report_locale") or "zh-CN")
        output = (
            concise_report(report, locale) if args.format == "json" and args.view == "concise"
            else validated_detailed_report(report, locale) if args.format == "json"
            else render_markdown(report, locale, args.view)
        )
        emit_utf8(
            json.dumps(output, ensure_ascii=False, indent=2)
            if isinstance(output, dict) else output,
            args.output,
        )
        return 0
    except Exception as exc:
        emit_utf8(json.dumps({
            "render_status": "SYSTEM_ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        }, ensure_ascii=False, indent=2), args.output)
        return 2


if __name__ == "__main__":
    sys.exit(main())
