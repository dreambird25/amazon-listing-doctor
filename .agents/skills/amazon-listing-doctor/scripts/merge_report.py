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
