#!/usr/bin/env python3
"""Dimension-specific minimum evidence policy for semantic quality ratings."""

from __future__ import annotations

import re
from typing import Any


EVIDENCE_POLICY_VERSION = "1.2"
EVIDENCE_BASES = {"OBSERVED_CONTENT", "OBSERVED_ABSENCE", "EVIDENCE_GAP"}
VISIBLE_TEXT_MODULES = {"title", "item_highlight", "bullets", "description", "attributes"}
TEXT_MODULES = VISIBLE_TEXT_MODULES | {"backend_search_terms"}
CONTENT_PATH = re.compile(r"^\$\.(?:current_content|candidate\.content)\.([^.[\]]+)")
IMAGE_VISUAL_OBSERVATION_PATH = re.compile(
    r"^\$\.(?:current_content|candidate\.content)\.images\[\d+\]\.visual_observation$"
)


def content_module(path: Any) -> str | None:
    if not isinstance(path, str):
        return None
    matched = CONTENT_PATH.match(path)
    return matched.group(1) if matched else None


def meaningful_scalar(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def evaluate_evidence_policy(
        assessment: dict[str, Any], official_report: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Return non-sensitive policy evidence plus validation errors."""
    errors: list[str] = []
    if assessment.get("evidence_policy_version") != EVIDENCE_POLICY_VERSION:
        errors.append(f"evidence_policy_version must be {EVIDENCE_POLICY_VERSION}")

    target = str(assessment.get("assessment_target") or "").upper()
    contexts = official_report.get("quality_contexts")
    context = contexts.get(target) if isinstance(contexts, dict) else None
    manifest = context.get("evidence_manifest") if isinstance(context, dict) else []
    metadata = {
        item.get("field_path"): item
        for item in manifest
        if isinstance(item, dict) and isinstance(item.get("field_path"), str)
    }
    content_evidence = context.get("content_evidence") if isinstance(context, dict) else {}
    content_evidence = content_evidence if isinstance(content_evidence, dict) else {}
    content_coverage = content_evidence.get("coverage")
    missing_field_semantics = content_evidence.get("missing_field_semantics")
    dimensions = assessment.get("dimensions")
    dimensions = dimensions if isinstance(dimensions, dict) else {}
    scope = official_report.get("scope")
    scope = scope if isinstance(scope, dict) else {}
    locale_matches = assessment.get("assessment_locale") == scope.get("locale")

    results: dict[str, Any] = {}
    for name, row in dimensions.items():
        if not isinstance(row, dict):
            continue
        rating = row.get("rating")
        evidence_basis = row.get("evidence_basis")
        evidence = row.get("evidence") if isinstance(row.get("evidence"), list) else []
        bound_items = [
            item for item in evidence
            if isinstance(item, dict) and isinstance(item.get("field_path"), str)
            and meaningful_scalar(item.get("quote_or_value"))
        ]
        paths = [item["field_path"] for item in bound_items]
        modules = sorted({module for path in paths if (module := content_module(path))})
        string_paths = [
            path for path in paths
            if isinstance(metadata.get(path), dict)
            and metadata[path].get("value_type") == "string"
        ]
        string_modules = {content_module(path) for path in string_paths}
        passed = True
        rule_code = "DIRECT_BOUND_EVIDENCE"
        if rating == "NOT_EVALUATED":
            passed = evidence_basis == "EVIDENCE_GAP"
            rule_code = "NOT_EVALUATED_WITH_MISSING_EVIDENCE"
        elif name == "content_completeness":
            minimum = 1 if rating == "WEAK" else 2
            passed = len(modules) >= minimum
            if rating == "WEAK":
                passed = passed and bool(row.get("missing_evidence"))
            rule_code = "CONTENT_MODULE_COVERAGE"
        elif name == "clarity_and_readability":
            passed = bool(string_modules & TEXT_MODULES)
            rule_code = "TEXTUAL_CONTENT_REQUIRED"
        elif name == "intent_coverage":
            passed = bool(string_modules & VISIBLE_TEXT_MODULES)
            rule_code = "VISIBLE_TEXT_REQUIRED"
        elif name == "buyer_question_coverage":
            passed = bool(string_modules & VISIBLE_TEXT_MODULES) or "attributes" in modules
            rule_code = "BUYER_DECISION_CONTENT_REQUIRED"
        elif name == "image_information_coverage":
            passed = any(IMAGE_VISUAL_OBSERVATION_PATH.fullmatch(path) for path in string_paths)
            rule_code = "OBSERVED_IMAGE_CONTENT_REQUIRED"
        elif name == "cross_field_consistency":
            passed = len(modules) >= 2
            rule_code = "TWO_CONTENT_MODULES_REQUIRED"
        elif name == "localization_quality":
            passed = locale_matches and bool(string_modules & VISIBLE_TEXT_MODULES)
            rule_code = "BOUND_LOCALE_TEXT_REQUIRED"

        if evidence_basis not in EVIDENCE_BASES:
            passed = False
        elif rating != "NOT_EVALUATED" and evidence_basis == "EVIDENCE_GAP":
            passed = False
        elif rating == "NOT_EVALUATED" and evidence_basis != "EVIDENCE_GAP":
            passed = False
        elif evidence_basis == "OBSERVED_ABSENCE" and not (
                content_coverage == "COMPLETE"
                and missing_field_semantics == "OBSERVED_ABSENT"
        ):
            passed = False

        results[name] = {
            "passed": passed,
            "rule_code": rule_code,
            "evidence_modules": modules,
            "evidence_basis": evidence_basis,
        }
        if not passed:
            errors.append(f"{name} does not satisfy evidence policy {rule_code}")

    return {
        "version": EVIDENCE_POLICY_VERSION,
        "passed": not errors,
        "dimensions": results,
    }, errors
