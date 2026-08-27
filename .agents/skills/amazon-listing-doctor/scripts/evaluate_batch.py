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


GATE_FIELDS = (
    "current_listing_gate",
    "candidate_preview_gate",
    "candidate_local_validation_gate",
    "release_decision",
    "official_validation_completeness",
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


def evaluate_samples(samples: list[Any]) -> tuple[dict[str, Any], bool]:
    distributions = {field: Counter() for field in GATE_FIELDS}
    mismatches: list[dict[str, Any]] = []
    malformed = 0
    deterministic = True
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict) or not isinstance(sample.get("input"), dict):
            malformed += 1
            continue
        report = diagnose(sample["input"])
        deterministic = deterministic and report == diagnose(sample["input"])
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
        "expectation_mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "privacy": "No input content or raw sample identifiers are emitted.",
    }
    return result, malformed == 0 and not mismatches and deterministic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate private Listing Golden Dataset samples")
    parser.add_argument("--file", type=Path, required=True, help="Private JSON/JSONL sample file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result, valid = evaluate_samples(load_samples(args.file))
    except Exception as exc:
        result = {"batch_status": "SYSTEM_ERROR", "error": f"{type(exc).__name__}: {exc}"}
        valid = False
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if valid else 2


if __name__ == "__main__":
    sys.exit(main())
