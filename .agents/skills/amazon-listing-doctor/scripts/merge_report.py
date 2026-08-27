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
SCORE_RUBRIC_VERSION = "1.0"
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


def validate_assessment(assessment: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(assessment, dict):
        return ["semantic assessment must be a JSON object"]
    if assessment.get("assessment_version") != "1.1":
        errors.append("assessment_version must be 1.1")
    for field in ("assessment_model", "prompt_version"):
        if not nonempty_text(assessment.get(field)):
            errors.append(f"{field} is required")
    if not timezone_aware_timestamp(assessment.get("assessed_at")):
        errors.append("assessed_at must be a timezone-aware ISO-8601 timestamp")

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
                and nonempty_text(item.get("field"))
                and nonempty_text(item.get("quote_or_value"))
                for item in evidence
            )
            if not evidence or not valid_evidence:
                errors.append(f"{name} requires evidence with field and quote_or_value")

    assessed_evidence = {
        (item["field"].strip(), item["quote_or_value"].strip())
        for name in DIMENSIONS
        for item in (
            dimensions.get(name, {}).get("evidence", [])
            if isinstance(dimensions.get(name), dict) else []
        )
        if isinstance(item, dict)
        and nonempty_text(item.get("field"))
        and nonempty_text(item.get("quote_or_value"))
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
                        and nonempty_text(item.get("field"))
                        and nonempty_text(item.get("quote_or_value"))
                        for item in source_evidence
                    )
                if not valid_source_evidence:
                    errors.append(
                        f"{prefix}.source_evidence with field and quote_or_value "
                        "is required with suggested_value"
                    )
                elif any(
                    (item["field"].strip(), item["quote_or_value"].strip())
                    not in assessed_evidence
                    for item in source_evidence
                ):
                    errors.append(
                        f"{prefix}.source_evidence must match evidence from an evaluated dimension"
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
    evaluated = [
        dimensions[name]["rating"]
        for name in DIMENSIONS
        if dimensions[name]["rating"] != "NOT_EVALUATED"
    ]
    result: dict[str, Any] = {
        "status": "SCORED" if len(evaluated) >= MIN_SCORED_DIMENSIONS else "NOT_SCORED",
        "value": None,
        "scale": 10,
        "type": "INTERNAL_HEURISTIC",
        "official": False,
        "evaluated_dimensions": len(evaluated),
        "total_dimensions": len(DIMENSIONS),
        "minimum_dimensions_required": MIN_SCORED_DIMENSIONS,
        "rubric_version": SCORE_RUBRIC_VERSION,
        "rating_points": dict(RATING_POINTS),
    }
    if len(evaluated) >= MIN_SCORED_DIMENSIONS:
        result["value"] = round(sum(RATING_POINTS[rating] for rating in evaluated) / len(evaluated), 1)
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
            0 if reason and item[1].get("dimension") == reason.get("dimension") else 1,
            PRIORITY_ORDER[item[1]["priority"]],
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
    return {
        "summary_version": "1.0",
        "asin": scope.get("asin"),
        "official": {
            "current_listing_gate": official_report["current_listing_gate"],
            "candidate_preview_gate": official_report["candidate_preview_gate"],
            "candidate_local_validation_gate": official_report["candidate_local_validation_gate"],
            "release_decision": official_report["release_decision"],
            "validation_completeness": official_report["official_validation_completeness"],
        },
        "quality_verdict": verdict,
        "quality_score": derive_quality_score(assessment["dimensions"]),
        "primary_reason": official_reason or quality_reason,
        "primary_action": official_action(official_reason) or quality_action,
        "quality_primary_reason": quality_reason,
        "quality_primary_action": quality_action,
        "performance_verdict": "NOT_EVALUATED",
        "disclaimer": "Internal content-quality summary; not an Amazon official score or performance prediction.",
    }


def merge_report(official_report: Any, assessment: Any) -> tuple[dict[str, Any], bool]:
    errors: list[str] = []
    if not isinstance(official_report, dict):
        errors.append("official report must be a JSON object")
    else:
        missing_report_fields = sorted(OFFICIAL_REPORT_FIELDS - set(official_report))
        if missing_report_fields:
            errors.append(f"official report is missing fields: {', '.join(missing_report_fields)}")
    errors.extend(validate_assessment(assessment))
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
