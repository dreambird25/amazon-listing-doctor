#!/usr/bin/env python3
"""Evaluate private observation or Golden Datasets without exposing identifiers."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
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
    "structurally_comparable",
    "comparison_cohort_sha256",
    "weak_dimensions",
    "primary_reason_dimension",
    "primary_reason_source",
    "primary_reason_code",
    "primary_reason_finding_source",
    "primary_action_dimension",
    "primary_action_code",
    "official_reason_status",
    "official_reason_code",
    "official_reason_finding_source",
    "official_action_code",
    "suggested_value_allowed",
    "suggested_value_hmac_sha256",
    "fact_binding_count",
    "unbound_fact_count",
)
MODE_ALIASES = {
    "official-gates": "golden-official",
    "quality-summary": "golden-quality",
}
MODES = ("observation", "golden-official", "golden-quality", *MODE_ALIASES)
MIN_HMAC_KEY_BYTES = 32
SAMPLE_REF_HMAC_DOMAIN = b"amazon-listing-doctor/sample-reference/v1\0"
SUGGESTED_VALUE_HMAC_DOMAIN = b"amazon-listing-doctor/suggested-value/v1\0"


def private_hmac(value: Any, key: str, domain: bytes) -> str:
    key_bytes = key.encode("utf-8")
    if len(key_bytes) < MIN_HMAC_KEY_BYTES:
        raise ValueError(f"private HMAC key must be at least {MIN_HMAC_KEY_BYTES} UTF-8 bytes")
    message = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hmac.new(key_bytes, domain + message, hashlib.sha256).hexdigest()


def sample_ref(value: Any, index: int, key: str | None) -> str:
    if not key:
        return f"sample-{index + 1:06d}"
    material = value if value is not None else {"row_index": index}
    return private_hmac(material, key, SAMPLE_REF_HMAC_DOMAIN)[:16]


def load_samples(path: Path) -> list[Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    value = json.loads(text)
    if not isinstance(value, list):
        raise ValueError("batch JSON must be an array")
    return value


def quality_snapshot(
        report: dict[str, Any], private_digest_key: str | None = None,
) -> dict[str, Any]:
    summary = report.get("executive_summary") or {}
    score = summary.get("evaluated_dimension_average") or {}
    reason = summary.get("quality_primary_reason") or summary.get("primary_reason") or {}
    action = summary.get("quality_primary_action") or summary.get("primary_action") or {}
    official_reason = summary.get("official_primary_reason") or {}
    official_primary_action = summary.get("official_primary_action") or {}
    suggested_value = action.get("suggested_value")
    fact_bindings = action.get("fact_bindings") or []
    return {
        "quality_verdict": report.get("quality_verdict"),
        "score_status": score.get("status"),
        "score_value": score.get("value"),
        "structurally_comparable": score.get("structurally_comparable"),
        "comparison_cohort_sha256": score.get("comparison_cohort_sha256"),
        "weak_dimensions": score.get("weak_dimensions") or [],
        "primary_reason_dimension": reason.get("dimension"),
        "primary_reason_source": reason.get("source"),
        "primary_reason_code": reason.get("code"),
        "primary_reason_finding_source": reason.get("finding_source"),
        "primary_action_dimension": action.get("dimension"),
        "primary_action_code": action.get("action_code"),
        "official_reason_status": official_reason.get("status"),
        "official_reason_code": official_reason.get("code"),
        "official_reason_finding_source": official_reason.get("finding_source"),
        "official_action_code": official_primary_action.get("action_code"),
        "suggested_value_allowed": bool(suggested_value),
        "suggested_value_hmac_sha256": (
            private_hmac(suggested_value, private_digest_key, SUGGESTED_VALUE_HMAC_DOMAIN)
            if suggested_value and private_digest_key else None
        ),
        "fact_binding_count": len(fact_bindings),
        "unbound_fact_count": 0,
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


def valid_expected_fields(expected: Any, allowed: tuple[str, ...], extras: set[str]) -> bool:
    supported = set(allowed) | extras
    return isinstance(expected, dict) and bool(set(expected) & supported) \
        and set(expected) <= supported


def evaluate_samples(
        samples: list[Any], mode: str = "golden-official", sample_ref_key: str | None = None,
) -> tuple[dict[str, Any], bool]:
    normalized_mode = MODE_ALIASES.get(mode, mode)
    if normalized_mode not in {"observation", "golden-official", "golden-quality"}:
        raise ValueError(f"unsupported mode: {mode}")
    if sample_ref_key:
        private_hmac("key-validation", sample_ref_key, SAMPLE_REF_HMAC_DOMAIN)
    distributions = {field: Counter() for field in GATE_FIELDS}
    mismatches: list[dict[str, Any]] = []
    malformed = 0
    deterministic = True
    quality_distributions = {
        "quality_verdict": Counter(),
        "score_status": Counter(),
        "structurally_comparable": Counter(),
        "weak_dimension_count": Counter(),
    }
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict) or not isinstance(sample.get("input"), dict):
            malformed += 1
            continue
        reference = sample_ref(sample.get("sample_id"), index, sample_ref_key)
        report = diagnose(sample["input"])
        deterministic = deterministic and report == diagnose(sample["input"])
        for field in GATE_FIELDS:
            distributions[field][str(report.get(field) or "MISSING")] += 1

        if normalized_mode == "observation":
            continue
        if normalized_mode == "golden-quality":
            expected_quality = sample.get("expected_quality")
            if not valid_expected_fields(
                    expected_quality, QUALITY_EXPECTED_FIELDS, {"score_range"}
            ):
                malformed += 1
                continue
            assessment = sample.get("assessment")
            merged, valid_merge = merge_report(report, assessment)
            rerun, rerun_valid = merge_report(report, assessment)
            deterministic = deterministic and valid_merge == rerun_valid and merged == rerun
            if not valid_merge:
                mismatches.append({
                    "sample_ref": reference,
                    "differences": {"merge_status": {
                        "expected": "OK",
                        "actual": merged.get("merge_status"),
                    }},
                })
                continue
            actual_quality = quality_snapshot(merged, sample_ref_key)
            quality_distributions["quality_verdict"][str(actual_quality["quality_verdict"])] += 1
            quality_distributions["score_status"][str(actual_quality["score_status"])] += 1
            quality_distributions["structurally_comparable"][
                str(actual_quality["structurally_comparable"])
            ] += 1
            quality_distributions["weak_dimension_count"][
                str(len(actual_quality["weak_dimensions"]))
            ] += 1
            differences = quality_differences(expected_quality, actual_quality)
            if differences:
                mismatches.append({"sample_ref": reference, "differences": differences})
            continue

        expected = sample.get("expected")
        if not valid_expected_fields(expected, GATE_FIELDS, set()):
            malformed += 1
            continue
        differences = {
            field: {"expected": expected[field], "actual": report.get(field)}
            for field in GATE_FIELDS
            if field in expected and expected[field] != report.get(field)
        }
        if differences:
            mismatches.append({"sample_ref": reference, "differences": differences})

    result = {
        "sample_count": len(samples),
        "dataset_status": "EVALUATED" if samples else "EMPTY",
        "evaluated_count": len(samples) - malformed,
        "malformed_count": malformed,
        "deterministic_rerun": deterministic,
        "gate_distributions": {
            field: dict(sorted(counter.items())) for field, counter in distributions.items()
        },
        "quality_distributions": {
            field: dict(sorted(counter.items()))
            for field, counter in quality_distributions.items()
        } if normalized_mode == "golden-quality" else {},
        "mode": normalized_mode,
        "expectation_mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "sample_reference_method": "HMAC_SHA256" if sample_ref_key else "NON_IDENTIFYING_INDEX",
        "private_value_digest_method": "HMAC_SHA256" if sample_ref_key else "DISABLED",
        "hmac_domain_separation": "V1" if sample_ref_key else "DISABLED",
        "privacy": "No input content or raw sample identifiers are emitted.",
    }
    return result, bool(samples) and malformed == 0 and not mismatches and deterministic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate private Listing datasets")
    parser.add_argument("--file", type=Path, required=True, help="Private JSON/JSONL sample file")
    parser.add_argument("--mode", choices=MODES, default="golden-official")
    parser.add_argument(
        "--sample-ref-key-env",
        default="LISTING_DOCTOR_SAMPLE_REF_KEY",
        help="Environment variable containing an optional private HMAC key",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        key = os.environ.get(args.sample_ref_key_env)
        result, valid = evaluate_samples(load_samples(args.file), args.mode, key)
    except Exception as exc:
        result = {"batch_status": "SYSTEM_ERROR", "error": f"{type(exc).__name__}: {exc}"}
        valid = False
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if valid else 2


if __name__ == "__main__":
    sys.exit(main())
