#!/usr/bin/env python3
"""Validate and merge semantic Listing quality assessment with an official report."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parent))
from quality_contract import official_report_sha256, sha256_json, valid_sha256
from summary_contract import official_action, primary_official_finding


DIMENSIONS = (
    "content_completeness",
    "clarity_and_readability",
    "intent_coverage",
    "buyer_question_coverage",
    "image_information_coverage",
    "cross_field_consistency",
    "localization_quality",
)
RATINGS = {"STRONG", "ADEQUATE", "WEAK", "NOT_EVALUATED"}
PRIORITIES = {"HIGH", "MEDIUM", "LOW"}
PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
RATING_POINTS = {"STRONG": 10.0, "ADEQUATE": 7.0, "WEAK": 3.0}
MIN_SCORED_DIMENSIONS = 5
SCORE_RUBRIC_VERSION = "1.1"
OFFICIAL_REPORT_FIELDS = {
    "current_listing_gate",
    "candidate_preview_gate",
    "candidate_local_validation_gate",
    "release_decision",
    "official_validation_completeness",
    "official_evidence_coverage",
    "ptd_validation_coverage",
    "counts",
    "findings",
    "quality_contexts",
}


def nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def timezone_aware_timestamp(value: Any) -> bool:
    if not nonempty_text(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def scalar_value(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def validate_assessment(
        assessment: Any, official_report: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(assessment, dict):
        return ["semantic assessment must be a JSON object"]
    if assessment.get("assessment_version") != "1.2":
        errors.append("assessment_version must be 1.2")
    for field in ("assessment_model", "prompt_version"):
        if not nonempty_text(assessment.get(field)):
            errors.append(f"{field} is required")
    if not timezone_aware_timestamp(assessment.get("assessed_at")):
        errors.append("assessed_at must be a timezone-aware ISO-8601 timestamp")

    target = str(assessment.get("assessment_target") or "").upper()
    if target not in {"CURRENT", "CANDIDATE"}:
        errors.append("assessment_target must be CURRENT or CANDIDATE")
    for field in (
        "scope_fingerprint_sha256",
        "content_sha256",
        "official_report_sha256",
        "evidence_manifest_sha256",
    ):
        if not valid_sha256(assessment.get(field)):
            errors.append(f"{field} must be a lowercase SHA-256 digest")

    manifest_by_path: dict[str, str] = {}
    if isinstance(official_report, dict) and target in {"CURRENT", "CANDIDATE"}:
        computed_report_hash = official_report_sha256(official_report)
        declared_report_hash = official_report.get("official_report_sha256")
        if declared_report_hash is not None and declared_report_hash != computed_report_hash:
            errors.append("official_report_sha256 field does not match the supplied official report")
        contexts = official_report.get("quality_contexts")
        context = contexts.get(target) if isinstance(contexts, dict) else None
        if not isinstance(context, dict):
            errors.append(f"quality context for {target} is missing from the official report")
        else:
            for field in (
                "scope_fingerprint_sha256", "content_sha256", "evidence_manifest_sha256",
            ):
                if assessment.get(field) != context.get(field):
                    errors.append(f"{field} does not match the official report quality context")
            manifest = context.get("evidence_manifest")
            if not isinstance(manifest, list):
                errors.append("official report evidence_manifest must be an array")
            else:
                manifest_by_path = {
                    str(item.get("field_path")): str(item.get("value_sha256"))
                    for item in manifest if isinstance(item, dict)
                    and nonempty_text(item.get("field_path"))
                    and valid_sha256(item.get("value_sha256"))
                }
        if assessment.get("official_report_sha256") != computed_report_hash:
            errors.append("official_report_sha256 does not match the supplied official report")

    dimensions = assessment.get("dimensions")
    if not isinstance(dimensions, dict):
        return errors + ["dimensions must be a JSON object"]
    missing = [name for name in DIMENSIONS if name not in dimensions]
    unknown = sorted(str(name) for name in dimensions if name not in DIMENSIONS)
    if missing:
        errors.append(f"missing dimensions: {', '.join(missing)}")
    if unknown:
        errors.append(f"unknown dimensions: {', '.join(unknown)}")

    for name in DIMENSIONS:
        row = dimensions.get(name)
        if not isinstance(row, dict):
            if name in dimensions:
                errors.append(f"{name} must be a JSON object")
            continue
        rating = row.get("rating")
        if rating not in RATINGS:
            errors.append(f"{name}.rating must be one of {', '.join(sorted(RATINGS))}")
            continue
        evidence = row.get("evidence")
        missing_evidence = row.get("missing_evidence")
        if not isinstance(evidence, list):
            errors.append(f"{name}.evidence must be an array")
            evidence = []
        if not isinstance(missing_evidence, list):
            errors.append(f"{name}.missing_evidence must be an array")
            missing_evidence = []
        if rating == "NOT_EVALUATED":
            if not any(nonempty_text(item) for item in missing_evidence):
                errors.append(f"{name} requires missing_evidence when NOT_EVALUATED")
        else:
            if not nonempty_text(row.get("rationale")):
                errors.append(f"{name}.rationale is required for an evaluated rating")
            valid_evidence = all(
                isinstance(item, dict)
                and nonempty_text(item.get("field_path"))
                and scalar_value(item.get("quote_or_value"))
                and valid_sha256(item.get("value_sha256"))
                and item.get("value_sha256") == sha256_json(item.get("quote_or_value"))
                and (
                    not manifest_by_path
                    or manifest_by_path.get(item.get("field_path")) == item.get("value_sha256")
                )
                for item in evidence
            )
            if not evidence or not valid_evidence:
                errors.append(
                    f"{name} requires manifest-bound evidence with field_path, "
                    "quote_or_value, and value_sha256"
                )

    assessed_evidence = {
        (item["field_path"].strip(), item["value_sha256"].lower())
        for name in DIMENSIONS
        for item in (
            dimensions.get(name, {}).get("evidence", [])
            if isinstance(dimensions.get(name), dict) else []
        )
        if isinstance(item, dict)
        and nonempty_text(item.get("field_path"))
        and valid_sha256(item.get("value_sha256"))
    }

    recommendations = assessment.get("recommendations", [])
    if not isinstance(recommendations, list):
        errors.append("recommendations must be an array")
    else:
        for index, recommendation in enumerate(recommendations):
            prefix = f"recommendations[{index}]"
            if not isinstance(recommendation, dict):
                errors.append(f"{prefix} must be a JSON object")
                continue
            if recommendation.get("priority") not in PRIORITIES:
                errors.append(f"{prefix}.priority must be HIGH, MEDIUM, or LOW")
            if recommendation.get("dimension") not in DIMENSIONS:
                errors.append(f"{prefix}.dimension is invalid")
            for field in ("action", "completion_criterion"):
                if not nonempty_text(recommendation.get(field)):
                    errors.append(f"{prefix}.{field} is required")
            for field in ("attribute", "current_problem", "suggested_value"):
                if field in recommendation and not nonempty_text(recommendation.get(field)):
                    errors.append(f"{prefix}.{field} must be a non-empty string when supplied")
            if "suggested_value" in recommendation:
                dimension = recommendation.get("dimension")
                dimension_row = dimensions.get(dimension) if dimension in DIMENSIONS else None
                if isinstance(dimension_row, dict) and dimension_row.get("rating") == "NOT_EVALUATED":
                    errors.append(f"{prefix}.suggested_value cannot target a NOT_EVALUATED dimension")
                if not nonempty_text(recommendation.get("attribute")):
                    errors.append(f"{prefix}.attribute is required with suggested_value")
                if not nonempty_text(recommendation.get("current_problem")):
                    errors.append(f"{prefix}.current_problem is required with suggested_value")
                source_evidence = recommendation.get("source_evidence")
                valid_source_evidence = isinstance(source_evidence, list) and bool(source_evidence) \
                    and all(
                        isinstance(item, dict)
                        and nonempty_text(item.get("field_path"))
                        and scalar_value(item.get("quote_or_value"))
                        and valid_sha256(item.get("value_sha256"))
                        and item.get("value_sha256") == sha256_json(item.get("quote_or_value"))
                        for item in source_evidence
                    )
                if not valid_source_evidence:
                    errors.append(
                        f"{prefix}.source_evidence with field_path, quote_or_value, and value_sha256 "
                        "is required with suggested_value"
                    )
                elif any(
                    (item["field_path"].strip(), item["value_sha256"].lower())
                    not in assessed_evidence
                    for item in source_evidence
                ):
                    errors.append(
                        f"{prefix}.source_evidence must match evidence from an evaluated dimension"
                    )
                fact_bindings = recommendation.get("fact_bindings")
                valid_fact_bindings = isinstance(fact_bindings, list) and bool(fact_bindings) \
                    and all(
                        isinstance(item, dict)
                        and nonempty_text(item.get("fact"))
                        and nonempty_text(item.get("source_path"))
                        and valid_sha256(item.get("source_value_sha256"))
                        and item.get("source_value_sha256") == sha256_json(item.get("fact"))
                        and (
                            item["source_path"].strip(), item["source_value_sha256"].lower()
                        ) in assessed_evidence
                        and item["fact"].casefold() in recommendation["suggested_value"].casefold()
                        for item in fact_bindings
                    )
                if not valid_fact_bindings:
                    errors.append(
                        f"{prefix}.fact_bindings must bind every suggested fact to assessed evidence"
                    )

    limitations = assessment.get("limitations", [])
    if not isinstance(limitations, list) or not all(nonempty_text(item) for item in limitations):
        errors.append("limitations must be an array of non-empty strings")
    return errors


def derive_quality(dimensions: dict[str, Any]) -> tuple[str, str]:
    ratings = [dimensions[name]["rating"] for name in DIMENSIONS]
    evaluated = [rating for rating in ratings if rating != "NOT_EVALUATED"]
    if not evaluated:
        return "NOT_EVALUATED", "NONE"
    completeness = "COMPLETE" if len(evaluated) == len(DIMENSIONS) else "PARTIAL"
    if "WEAK" in evaluated:
        return "NEEDS_IMPROVEMENT", completeness
    if len(evaluated) < len(DIMENSIONS):
        return "PARTIALLY_EVALUATED", completeness
    if all(rating == "STRONG" for rating in evaluated):
        return "STRONG", completeness
    return "ADEQUATE", completeness


def derive_quality_score(dimensions: dict[str, Any]) -> dict[str, Any]:
    evaluated_rows = [
        (name, dimensions[name]["rating"])
        for name in DIMENSIONS
        if dimensions[name]["rating"] != "NOT_EVALUATED"
    ]
    evaluated = [rating for _, rating in evaluated_rows]
    dimension_mask = [name for name, _ in evaluated_rows]
    weak_dimensions = [name for name, rating in evaluated_rows if rating == "WEAK"]
    status = (
        "FULL" if len(evaluated) == len(DIMENSIONS)
        else "PARTIAL" if len(evaluated) >= MIN_SCORED_DIMENSIONS
        else "NOT_SCORED"
    )
    result: dict[str, Any] = {
        "status": status,
        "value": None,
        "raw_evaluated_average": None,
        "scale": 10,
        "type": "INTERNAL_HEURISTIC",
        "official": False,
        "comparable": status == "FULL",
        "evaluated_dimensions": len(evaluated),
        "total_dimensions": len(DIMENSIONS),
        "minimum_dimensions_required": MIN_SCORED_DIMENSIONS,
        "dimension_mask": dimension_mask,
        "weak_dimensions": weak_dimensions,
        "rubric_version": SCORE_RUBRIC_VERSION,
        "rating_points": dict(RATING_POINTS),
    }
    if len(evaluated) >= MIN_SCORED_DIMENSIONS:
        average = round(sum(RATING_POINTS[rating] for rating in evaluated) / len(evaluated), 1)
        result["value"] = average
        result["raw_evaluated_average"] = average
    else:
        result["not_scored_reason"] = "Insufficient evaluated quality dimensions."
    return result


def primary_quality_reason(dimensions: dict[str, Any]) -> dict[str, Any] | None:
    for target_rating in ("WEAK", "ADEQUATE", "STRONG"):
        for name in DIMENSIONS:
            row = dimensions[name]
            if row["rating"] == target_rating:
                return {
                    "dimension": name,
                    "rating": target_rating,
                    "text": row["rationale"],
                }
    return None


def primary_recommendation(
        recommendations: list[dict[str, Any]], reason: dict[str, Any] | None,
) -> dict[str, Any] | None:
    ordered = sorted(
        enumerate(recommendations),
        key=lambda item: (
            PRIORITY_ORDER[item[1]["priority"]],
            0 if reason and item[1].get("dimension") == reason.get("dimension") else 1,
            item[0],
        ),
    )
    if not ordered:
        return None
    recommendation = copy.deepcopy(ordered[0][1])
    recommendation["rewrite_is_advisory"] = "suggested_value" in recommendation
    return recommendation


def build_executive_summary(
        official_report: dict[str, Any], assessment: dict[str, Any], verdict: str,
) -> dict[str, Any]:
    scope = official_report.get("scope") if isinstance(official_report.get("scope"), dict) else {}
    quality_reason = primary_quality_reason(assessment["dimensions"])
    quality_action = primary_recommendation(assessment.get("recommendations") or [], quality_reason)
    official_reason = primary_official_finding(official_report)
    score = derive_quality_score(assessment["dimensions"])
    summary = {
        "summary_version": "1.1",
        "identity": {
            "marketplace_id": scope.get("marketplace_id"),
            "seller_sku": scope.get("sku"),
            "asin": scope.get("asin"),
        },
        "official": {
            "current_listing_gate": official_report["current_listing_gate"],
            "candidate_preview_gate": official_report["candidate_preview_gate"],
            "candidate_local_validation_gate": official_report["candidate_local_validation_gate"],
            "release_decision": official_report["release_decision"],
            "validation_completeness": official_report["official_validation_completeness"],
        },
        "quality_verdict": verdict,
        "evaluated_dimension_average": score,
        "primary_reason": official_reason or quality_reason,
        "primary_action": official_action(official_reason) or quality_action,
        "quality_primary_reason": quality_reason,
        "quality_primary_action": quality_action,
        "performance_verdict": "NOT_EVALUATED",
        "disclaimer": "Internal content-quality summary; not an Amazon official score or performance prediction.",
    }
    summary["quality_score"] = copy.deepcopy(score)
    return summary


def merge_report(official_report: Any, assessment: Any) -> tuple[dict[str, Any], bool]:
    errors: list[str] = []
    if not isinstance(official_report, dict):
        errors.append("official report must be a JSON object")
    else:
        missing_report_fields = sorted(OFFICIAL_REPORT_FIELDS - set(official_report))
        if missing_report_fields:
            errors.append(f"official report is missing fields: {', '.join(missing_report_fields)}")
    errors.extend(validate_assessment(assessment, official_report if isinstance(official_report, dict) else None))
    if errors:
        return {"merge_status": "SYSTEM_ERROR", "errors": errors}, False

    result = copy.deepcopy(official_report)
    verdict, completeness = derive_quality(assessment["dimensions"])
    result.update({
        "merge_status": "OK",
        "quality_verdict": verdict,
        "quality_dimensions": {
            name: assessment["dimensions"][name]["rating"]
            for name in DIMENSIONS
        },
        "quality_evidence_completeness": completeness,
        "semantic_assessment": assessment,
        "quality_assessment_trace": {
            "assessment_version": assessment["assessment_version"],
            "assessment_model": assessment["assessment_model"],
            "prompt_version": assessment["prompt_version"],
            "assessed_at": assessment["assessed_at"],
            "assessment_target": assessment["assessment_target"],
            "scope_fingerprint_sha256": assessment["scope_fingerprint_sha256"],
            "content_sha256": assessment["content_sha256"],
            "official_report_sha256": assessment["official_report_sha256"],
            "evidence_manifest_sha256": assessment["evidence_manifest_sha256"],
        },
        "performance_verdict": "NOT_EVALUATED",
    })
    result["executive_summary"] = build_executive_summary(result, assessment, verdict)
    return result, True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge Listing official and content-quality reports")
    parser.add_argument("--official-report", type=Path, required=True)
    parser.add_argument("--semantic-assessment", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        official_report = json.loads(args.official_report.read_text(encoding="utf-8"))
        assessment = json.loads(args.semantic_assessment.read_text(encoding="utf-8"))
        result, valid = merge_report(official_report, assessment)
    except Exception as exc:
        result = {
            "merge_status": "SYSTEM_ERROR",
            "errors": [f"could not read input: {type(exc).__name__}: {exc}"],
        }
        valid = False
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if valid else 2


if __name__ == "__main__":
    sys.exit(main())
