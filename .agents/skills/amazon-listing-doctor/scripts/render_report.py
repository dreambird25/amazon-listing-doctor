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
from merge_report import (
    build_executive_summary,
    derive_quality,
    render_suggested_template,
    validate_assessment,
)
from quality_policy import evaluate_evidence_policy
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
    result = {
        "summary_version": "1.1",
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
        "quality_verdict": "NOT_EVALUATED",
        "evaluated_dimension_average": {
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
        },
        "primary_reason": official_reason,
        "primary_action": official_action(official_reason),
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
                if score.get("status") in {"FULL", "PARTIAL"} else messages["fields"]["not_scored"]
            ),
            "score_status": label(messages, "score_status_labels", score.get("status")),
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
    score = summary.get("evaluated_dimension_average") or {}
    reason = summary.get("primary_reason") or {}
    action = summary.get("primary_action") or {}
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
        f"- {fields['current_listing']}: {display['current_listing_gate']} "
        f"(`{report.get('current_listing_gate')}`)",
    ]
    if report.get("release_decision") != "PASS" \
            or report.get("candidate_preview_gate") != "PASS" \
            or report.get("candidate_local_validation_gate") != "PASS":
        lines.extend([
            f"- {fields['candidate_preview']}: {display['candidate_preview_gate']} "
            f"(`{report.get('candidate_preview_gate')}`)",
            f"- {fields['candidate_local_validation']}: {display['candidate_local_validation_gate']} "
            f"(`{report.get('candidate_local_validation_gate')}`)",
        ])
    lines.extend([
        f"- {fields['release_decision']}: {display['release_decision']} "
        f"(`{report.get('release_decision')}`)",
        f"- {fields['official_validation_completeness']}: "
        f"{display['official_validation_completeness']} "
        f"(`{report.get('official_validation_completeness')}`)",
        f"- {fields['evaluated_dimension_average']}: {display['quality_score']}"
        f"（{display['score_disclaimer']}）" if locale == "zh-CN" else
        f"- {fields['evaluated_dimension_average']}: {display['quality_score']} "
        f"({display['score_disclaimer']})",
        f"- {fields['score_status']}: {display['score_status']} (`{score.get('status')}`)",
        f"- {fields['dimensions']}: {score.get('evaluated_dimensions', 0)} / "
        f"{score.get('total_dimensions', 7)}",
        f"- {fields['weak_dimensions']}: {weak_display}",
        f"- {fields['structurally_comparable']}: "
        f"{fields['yes'] if score.get('structurally_comparable') else fields['no']}",
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
    ])
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
    lines = [render_concise_markdown(report, locale).rstrip(), "", f"## {headings['official_findings']}", ""]
    findings = localized.get("findings") or []
    if not findings:
        lines.append(f"- {fields['none']}")
    for row in findings:
        lines.extend([
            f"- **{row.get('status_label')} · {row.get('title_display')}** "
            f"(`{row.get('code')}` / `{row.get('source')}`)",
            f"  - {headings['original_message']}: {row.get('message_original')}",
        ])

    assessment = report.get("semantic_assessment")
    assessment_errors = validate_assessment(assessment, report)
    if not assessment_errors:
        policy, _ = evaluate_evidence_policy(assessment, report)
        policy_dimensions = policy["dimensions"]
        lines.extend(["", f"## {headings['quality_dimensions']}", ""])
        for name, row in assessment["dimensions"].items():
            dimension_label = label(messages, "dimension_labels", name)
            lines.append(
                f"- **{dimension_label}** (`{name}`): "
                f"{label(messages, 'quality_labels', row.get('rating'))} (`{row.get('rating')}`)"
            )
            if row.get("rationale"):
                lines.append(f"  - {fields['rationale']}: {row['rationale']}")
            policy = policy_dimensions.get(name) if isinstance(policy_dimensions, dict) else None
            if isinstance(policy, dict):
                lines.append(
                    f"  - {fields['evidence_policy']}: `{policy.get('rule_code')}` "
                    f"({'PASS' if policy.get('passed') else 'FAIL'})"
                )
            for evidence in row.get("evidence") or []:
                lines.append(
                    f"  - {fields['evidence']}: `{evidence.get('field_path')}` = "
                    f"{evidence.get('quote_or_value')}"
                )
            if row.get("missing_evidence"):
                lines.append(
                    f"  - {fields['missing_evidence']}: "
                    + "; ".join(str(item) for item in row["missing_evidence"])
                )

        lines.extend(["", f"## {headings['recommendations']}", ""])
        recommendations = assessment.get("recommendations") or []
        if not recommendations:
            lines.append(f"- {fields['none']}")
        for recommendation in recommendations:
            suggested_value = render_suggested_template(recommendation)
            lines.append(
                f"- **{recommendation.get('priority')} · "
                f"{label(messages, 'dimension_labels', recommendation.get('dimension'))}**: "
                f"{recommendation.get('action')}"
            )
            if recommendation.get("attribute"):
                lines.append(f"  - {fields['attribute']}: `{recommendation['attribute']}`")
            if recommendation.get("current_problem"):
                lines.append(f"  - {fields['current_problem']}: {recommendation['current_problem']}")
            for binding in recommendation.get("fact_bindings") or []:
                lines.append(
                    f"  - {fields['bound_fact']}: `{binding.get('binding_id')}` = "
                    f"{binding.get('source_value')} ← `{binding.get('source_path')}` "
                    f"(`{binding.get('source_value_sha256')}`)"
                )
            if suggested_value:
                lines.append(
                    f"  - {fields['suggested_value']}: {suggested_value}"
                )
            lines.append(
                f"  - {fields['completion_criterion']}: "
                f"{recommendation.get('completion_criterion')}"
            )

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
            "quality_evidence_policy", "quality_assessment_trace",
        ):
            result.pop(field, None)
        result["quality_verdict"] = "NOT_EVALUATED"
        result["quality_render_status"] = "INVALID_ASSESSMENT"
        result["quality_render_errors"] = errors
    else:
        verdict, completeness = derive_quality(assessment["dimensions"])
        policy, _ = evaluate_evidence_policy(assessment, report)
        result["quality_verdict"] = verdict
        result["quality_dimensions"] = {
            name: row["rating"] for name, row in assessment["dimensions"].items()
        }
        result["quality_evidence_completeness"] = completeness
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        locale = args.lang or str(report.get("report_locale") or "en")
        output = (
            concise_report(report, locale) if args.format == "json" and args.view == "concise"
            else validated_detailed_report(report, locale) if args.format == "json"
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
