#!/usr/bin/env python3
"""Evaluate a private Golden Dataset and emit aggregate, identifier-safe results."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from diagnose_listing import diagnose
from merge_report import merge_report


GATE_FIELDS = (
    "current_listing_gate",
    "candidate_preview_gate",
    "candidate_local_validation_gate",
    "release_decision",
    "official_validation_completeness",
)
QUALITY_EXPECTED_FIELDS = (
    "quality_verdict",
    "score_status",
    "comparable",
    "weak_dimensions",
    "primary_reason_dimension",
    "primary_action_dimension",
    "suggested_value_allowed",
)


def safe_sample_ref(value: Any) -> str:
    return hashlib.sha256(str(value or "anonymous").encode("utf-8")).hexdigest()[:12]


def load_samples(path: Path) -> list[Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    value = json.loads(text)
    if not isinstance(value, list):
        raise ValueError("batch JSON must be an array")
    return value


def quality_snapshot(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("executive_summary") or {}
    score = summary.get("evaluated_dimension_average") or {}
    reason = summary.get("primary_reason") or {}
    action = summary.get("primary_action") or {}
    return {
        "quality_verdict": report.get("quality_verdict"),
        "score_status": score.get("status"),
        "score_value": score.get("value"),
        "comparable": score.get("comparable"),
        "weak_dimensions": score.get("weak_dimensions") or [],
        "primary_reason_dimension": reason.get("dimension"),
        "primary_action_dimension": action.get("dimension"),
        "suggested_value_allowed": bool(action.get("suggested_value")),
    }


def quality_differences(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    differences = {
        field: {"expected": expected[field], "actual": actual.get(field)}
        for field in QUALITY_EXPECTED_FIELDS
        if field in expected and expected[field] != actual.get(field)
    }
    if "score_range" in expected:
        score_range = expected["score_range"]
        value = actual.get("score_value")
        valid_range = isinstance(score_range, list) and len(score_range) == 2 \
            and all(isinstance(item, (int, float)) for item in score_range)
        if not valid_range or not isinstance(value, (int, float)) \
                or not score_range[0] <= value <= score_range[1]:
            differences["score_range"] = {"expected": score_range, "actual": value}
    return differences


def evaluate_samples(
        samples: list[Any], mode: str = "official-gates",
) -> tuple[dict[str, Any], bool]:
    distributions = {field: Counter() for field in GATE_FIELDS}
    mismatches: list[dict[str, Any]] = []
    malformed = 0
    deterministic = True
    quality_distributions = {
        "quality_verdict": Counter(),
        "score_status": Counter(),
        "comparable": Counter(),
        "weak_dimension_count": Counter(),
    }
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict) or not isinstance(sample.get("input"), dict):
            malformed += 1
            continue
        report = diagnose(sample["input"])
        deterministic = deterministic and report == diagnose(sample["input"])
        if mode == "quality-summary":
            assessment = sample.get("assessment")
            merged, valid_merge = merge_report(report, assessment)
            rerun, rerun_valid = merge_report(report, assessment)
            deterministic = deterministic and valid_merge == rerun_valid and merged == rerun
            if not valid_merge:
                mismatches.append({
                    "sample_ref": safe_sample_ref(sample.get("sample_id", index)),
                    "differences": {"merge_status": {
                        "expected": "OK",
                        "actual": merged.get("merge_status"),
                    }},
                })
                continue
            actual_quality = quality_snapshot(merged)
            quality_distributions["quality_verdict"][str(actual_quality["quality_verdict"])] += 1
            quality_distributions["score_status"][str(actual_quality["score_status"])] += 1
            quality_distributions["comparable"][str(actual_quality["comparable"])] += 1
            quality_distributions["weak_dimension_count"][
                str(len(actual_quality["weak_dimensions"]))
            ] += 1
            expected_quality = sample.get("expected_quality") or {}
            if not isinstance(expected_quality, dict):
                malformed += 1
                continue
            differences = quality_differences(expected_quality, actual_quality)
            if differences:
                mismatches.append({
                    "sample_ref": safe_sample_ref(sample.get("sample_id", index)),
                    "differences": differences,
                })
            continue
        for field in GATE_FIELDS:
            distributions[field][str(report.get(field) or "MISSING")] += 1
        expected = sample.get("expected") or {}
        if not isinstance(expected, dict):
            malformed += 1
            continue
        differences = {
            field: {"expected": expected[field], "actual": report.get(field)}
            for field in GATE_FIELDS
            if field in expected and expected[field] != report.get(field)
        }
        if differences:
            mismatches.append({
                "sample_ref": safe_sample_ref(sample.get("sample_id", index)),
                "differences": differences,
            })
    result = {
        "sample_count": len(samples),
        "evaluated_count": len(samples) - malformed,
        "malformed_count": malformed,
        "deterministic_rerun": deterministic,
        "gate_distributions": {
            field: dict(sorted(counter.items())) for field, counter in distributions.items()
        },
        "quality_distributions": {
            field: dict(sorted(counter.items()))
            for field, counter in quality_distributions.items()
        } if mode == "quality-summary" else {},
        "mode": mode,
        "expectation_mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "privacy": "No input content or raw sample identifiers are emitted.",
    }
    return result, malformed == 0 and not mismatches and deterministic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate private Listing Golden Dataset samples")
    parser.add_argument("--file", type=Path, required=True, help="Private JSON/JSONL sample file")
    parser.add_argument(
        "--mode", choices=("official-gates", "quality-summary"), default="official-gates"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result, valid = evaluate_samples(load_samples(args.file), args.mode)
    except Exception as exc:
        result = {"batch_status": "SYSTEM_ERROR", "error": f"{type(exc).__name__}: {exc}"}
        valid = False
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if valid else 2


if __name__ == "__main__":
    sys.exit(main())
