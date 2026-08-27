#!/usr/bin/env python3
"""Classify Amazon Listing evidence without network calls or data writes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


OFFICIAL_ERROR = "OFFICIAL_ERROR"
OFFICIAL_WARNING = "OFFICIAL_WARNING"
HEURISTIC_ADVICE = "HEURISTIC_ADVICE"
NOT_EVALUATED = "NOT_EVALUATED"
SYSTEM_ERROR = "SYSTEM_ERROR"
ALL_STATES = (
    OFFICIAL_ERROR,
    OFFICIAL_WARNING,
    HEURISTIC_ADVICE,
    NOT_EVALUATED,
    SYSTEM_ERROR,
)

CONTENT_ATTRIBUTE_MAP = {
    "title": "item_name",
    "item_highlight": "item_highlight",
    "backend_search_terms": "generic_keyword",
    "bullets": "bullet_point",
}
OFFICIAL_SOURCES = {"INPUT", "LISTINGS_ITEMS", "PTD", "VALIDATION_PREVIEW"}
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def finding(status: str, code: str, message: str, source: str,
            attribute: str | None = None, evidence: Any = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "status": status,
        "code": code,
        "message": message,
        "source": source,
    }
    if attribute:
        row["attribute"] = attribute
    if evidence is not None:
        row["evidence"] = evidence
    return row


def is_provided(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def content_value(content: dict[str, Any], attribute: str) -> Any:
    for field, mapped in CONTENT_ATTRIBUTE_MAP.items():
        if mapped == attribute:
            return content.get(field)
    return content.get(attribute)


def measure(value: Any, unit: str) -> int | None:
    if unit == "ITEMS":
        return len(value) if isinstance(value, list) else None
    if not isinstance(value, str):
        return None
    if unit == "CODE_POINTS":
        return len(value)
    if unit == "UTF8_BYTES":
        return len(value.encode("utf-8"))
    return None


def classify_official_issue(issue: Any, source: str) -> dict[str, Any]:
    if not isinstance(issue, dict):
        return finding(
            SYSTEM_ERROR,
            "OFFICIAL_ISSUE_INVALID",
            "The official issue is not an object and could not be parsed.",
            source,
            evidence=issue,
        )
    severity = str(issue.get("severity") or "").upper()
    if severity == "ERROR":
        status = OFFICIAL_ERROR
    elif severity in {"WARNING", "INFO"}:
        # Keep the five-state contract while preserving Amazon's severity in evidence.
        status = OFFICIAL_WARNING
    else:
        return finding(
            SYSTEM_ERROR,
            "OFFICIAL_SEVERITY_UNKNOWN",
            "The official issue severity is missing or unknown; it cannot be treated as a pass.",
            source,
            evidence=issue,
        )
    attributes = issue.get("attributeNames") or issue.get("attribute_names") or []
    attribute = attributes[0] if isinstance(attributes, list) and attributes else None
    return finding(
        status,
        str(issue.get("code") or "AMAZON_ISSUE"),
        str(issue.get("message") or "Amazon returned a Listing issue."),
        source,
        attribute,
        issue,
    )


def ptd_coverage(status: str, supported: int = 0, unsupported: int = 0,
                 evaluated: int = 0) -> dict[str, Any]:
    return {
        "mode": "LIGHTWEIGHT_SUBSET",
        "status": status,
        "supported_constraint_count": supported,
        "unsupported_constraint_count": unsupported,
        "evaluated_constraint_count": evaluated,
        "full_schema_validation": False,
    }


def evaluate_ptd(
        content: dict[str, Any], ptd: Any
) -> tuple[list[dict[str, Any]], bool, dict[str, Any]]:
    if ptd is None:
        return [finding(
            NOT_EVALUATED,
            "PTD_MISSING",
            "No Product Type Definition was supplied; local official-constraint checks were not run.",
            "PTD",
        )], False, ptd_coverage("NOT_EVALUATED")
    if not isinstance(ptd, dict):
        return [finding(
            SYSTEM_ERROR, "PTD_INVALID", "PTD data is not an object.", "PTD", evidence=ptd
        )], False, ptd_coverage("SYSTEM_ERROR")

    rows: list[dict[str, Any]] = []
    status = str(ptd.get("status") or "UNAVAILABLE").upper()
    if status == "UNAVAILABLE":
        return [finding(
            NOT_EVALUATED,
            "PTD_UNAVAILABLE",
            "The current PTD schema is unavailable; attribute limits were not inferred.",
            "PTD",
        )], False, ptd_coverage("NOT_EVALUATED")
    if status not in {"FRESH", "STALE_WITHIN_GRACE"}:
        return [finding(
            SYSTEM_ERROR,
            "PTD_STATUS_UNKNOWN",
            "The PTD status is unknown and the schema cannot be used safely.",
            "PTD",
            evidence=status,
        )], False, ptd_coverage("SYSTEM_ERROR")
    if status == "STALE_WITHIN_GRACE":
        rows.append(finding(
            OFFICIAL_WARNING,
            "PTD_STALE_WITHIN_GRACE",
            "The last successful PTD schema is within its configured grace period; review refresh status before submission.",
            "PTD",
            evidence={"schema_checksum": ptd.get("schema_checksum")},
        ))

    constraints = ptd.get("constraints")
    if not isinstance(constraints, dict) or not constraints:
        rows.append(finding(
            NOT_EVALUATED,
            "PTD_CONSTRAINTS_MISSING",
            "The PTD input contains no executable constraints.",
            "PTD",
        ))
        return rows, False, ptd_coverage("NOT_EVALUATED")

    supported_types = {"MAX_LENGTH", "MIN_LENGTH", "MAX_ITEMS", "MIN_ITEMS"}
    supported_units = {"CODE_POINTS", "UTF8_BYTES", "ITEMS"}
    supported_count = 0
    unsupported_count = 0
    evaluated_count = 0
    for attribute, rules in constraints.items():
        attribute = str(attribute)
        if not isinstance(rules, list):
            rows.append(finding(
                SYSTEM_ERROR,
                "PTD_RULES_INVALID",
                "PTD constraints for this attribute are not an array.",
                "PTD",
                attribute,
                rules,
            ))
            continue
        value = content_value(content, attribute)
        if not is_provided(value):
            rows.append(finding(
                NOT_EVALUATED,
                "ATTRIBUTE_VALUE_MISSING",
                "The current attribute value is missing, so PTD constraints could not be evaluated.",
                "PTD",
                attribute,
            ))
            continue
        for rule in rules:
            if not isinstance(rule, dict):
                rows.append(finding(
                    SYSTEM_ERROR,
                    "PTD_RULE_INVALID",
                    "A PTD constraint is not an object.",
                    "PTD",
                    attribute,
                    rule,
                ))
                continue
            rule_type = str(rule.get("type") or "").upper()
            unit = str(rule.get("unit") or "").upper()
            limit = rule.get("value")
            if rule_type not in supported_types or unit not in supported_units or not isinstance(limit, int):
                unsupported_count += 1
                rows.append(finding(
                    NOT_EVALUATED,
                    "PTD_CONSTRAINT_UNSUPPORTED",
                    "This PTD constraint or measurement unit is unsupported; no assumption was made.",
                    "PTD",
                    attribute,
                    rule,
                ))
                continue
            supported_count += 1
            actual = measure(value, unit)
            if actual is None:
                rows.append(finding(
                    SYSTEM_ERROR,
                    "PTD_VALUE_TYPE_MISMATCH",
                    "The attribute value type does not match the PTD measurement unit.",
                    "PTD",
                    attribute,
                    {"rule": rule, "value_type": type(value).__name__},
                ))
                continue
            evaluated_count += 1
            violated = (
                rule_type in {"MAX_LENGTH", "MAX_ITEMS"} and actual > limit
            ) or (
                rule_type in {"MIN_LENGTH", "MIN_ITEMS"} and actual < limit
            )
            if violated:
                rows.append(finding(
                    OFFICIAL_ERROR,
                    "PTD_CONSTRAINT_VIOLATION",
                    f"Measured value {actual} violates PTD {rule_type}={limit} ({unit}).",
                    "PTD",
                    attribute,
                    {
                        "actual": actual,
                        "limit": limit,
                        "unit": unit,
                        "schema_checksum": ptd.get("schema_checksum"),
                        "resolved_version": ptd.get("resolved_version"),
                    },
                ))
    ptd_complete = not any(row["status"] in {NOT_EVALUATED, SYSTEM_ERROR} for row in rows)
    coverage_status = "EVALUATED_SUBSET" if ptd_complete else "PARTIALLY_EVALUATED"
    return rows, ptd_complete, ptd_coverage(
        coverage_status,
        supported=supported_count,
        unsupported=unsupported_count,
        evaluated=evaluated_count,
    )


def evaluate_images(content: dict[str, Any]) -> list[dict[str, Any]]:
    images = content.get("images")
    if not is_provided(images):
        return [finding(
            NOT_EVALUATED,
            "IMAGES_MISSING",
            "No image set was supplied; image quality was not evaluated.",
            "HEURISTIC",
        )]
    if not isinstance(images, list):
        return [finding(SYSTEM_ERROR, "IMAGES_INVALID", "The image set is not an array.", "HEURISTIC")]

    rows: list[dict[str, Any]] = []
    main_identified = False
    for index, image in enumerate(images):
        if not isinstance(image, dict):
            rows.append(finding(
                SYSTEM_ERROR,
                "IMAGE_INVALID",
                "Image metadata is not an object.",
                "HEURISTIC",
                evidence={"index": index},
            ))
            continue
        is_main = image.get("is_main") is True
        main_identified = main_identified or is_main
        width, height = image.get("width"), image.get("height")
        label = "main image" if is_main else f"image {index + 1}"
        if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
            rows.append(finding(
                NOT_EVALUATED,
                "IMAGE_DIMENSIONS_MISSING",
                f"The {label} has no valid dimensions; resolution and aspect ratio were not evaluated.",
                "HEURISTIC",
                evidence={"index": index, "url": image.get("url")},
            ))
        else:
            longest = max(width, height)
            if longest < 500:
                rows.append(finding(
                    HEURISTIC_ADVICE,
                    "IMAGE_VERY_SMALL",
                    f"The {label}'s longest side is {longest}px; verify current category requirements and consider a higher-resolution image.",
                    "HEURISTIC",
                    evidence={"index": index, "width": width, "height": height},
                ))
            elif longest < 1000:
                rows.append(finding(
                    HEURISTIC_ADVICE,
                    "IMAGE_ZOOM_QUALITY",
                    f"The {label}'s longest side is {longest}px; consider at least 1000px for a better zoom experience.",
                    "HEURISTIC",
                    evidence={"index": index, "width": width, "height": height},
                ))
            if width != height:
                rows.append(finding(
                    HEURISTIC_ADVICE,
                    "IMAGE_NOT_SQUARE",
                    f"The {label} is not square. This is layout advice, not a universal official violation.",
                    "HEURISTIC",
                    evidence={"index": index, "width": width, "height": height},
                ))

        if image.get("watermark") is None:
            rows.append(finding(
                NOT_EVALUATED,
                "IMAGE_WATERMARK_UNKNOWN",
                f"The {label}'s watermark status is unknown.",
                "HEURISTIC",
                evidence={"index": index, "url": image.get("url")},
            ))
        elif image.get("watermark") is True:
            rows.append(finding(
                HEURISTIC_ADVICE,
                "IMAGE_WATERMARK_PRESENT",
                f"A watermark was detected on the {label}; use an Amazon issue or current category rule for compliance classification.",
                "HEURISTIC",
                evidence={"index": index, "url": image.get("url")},
            ))

        if is_main:
            if image.get("white_background") is None:
                rows.append(finding(
                    NOT_EVALUATED,
                    "MAIN_IMAGE_BACKGROUND_UNKNOWN",
                    "The main image background was not verified.",
                    "HEURISTIC",
                    evidence={"index": index, "url": image.get("url")},
                ))
            elif image.get("white_background") is False:
                rows.append(finding(
                    HEURISTIC_ADVICE,
                    "MAIN_IMAGE_NOT_WHITE",
                    "The main image was not confirmed as white-background compliant; verify against an Amazon issue or current category rule.",
                    "HEURISTIC",
                    evidence={"index": index, "url": image.get("url")},
                ))
    if not main_identified:
        rows.append(finding(
            NOT_EVALUATED,
            "MAIN_IMAGE_NOT_IDENTIFIED",
            "Images were supplied, but none was identified as the main image; main-image checks were not run.",
            "HEURISTIC",
        ))
    return rows


def evaluate_validation_preview(
        scope: dict[str, Any], candidate: Any, preview: Any
) -> tuple[list[dict[str, Any]], bool, dict[str, Any]]:
    """Return findings, pass state, and normalized candidate scope."""
    if preview is not None and not isinstance(preview, dict):
        return [finding(
            SYSTEM_ERROR,
            "VALIDATION_PREVIEW_INVALID",
            "VALIDATION_PREVIEW evidence is not an object.",
            "VALIDATION_PREVIEW",
            evidence=preview,
        )], False, {}
    if not isinstance(preview, dict) or preview.get("ran") is not True:
        return [finding(
            NOT_EVALUATED,
            "VALIDATION_PREVIEW_NOT_RUN",
            "Listings Items VALIDATION_PREVIEW was not completed.",
            "VALIDATION_PREVIEW",
        )], False, {}

    rows: list[dict[str, Any]] = []
    binding_valid = True

    required_scope = (
        "seller_id", "marketplace_id", "sku", "product_type",
        "requirements", "parentage_level", "locale",
    )
    missing_scope = [name for name in required_scope if not is_provided(scope.get(name))]
    if missing_scope:
        binding_valid = False
        rows.append(finding(
            NOT_EVALUATED,
            "VALIDATION_PREVIEW_SCOPE_INCOMPLETE",
            "The official preview scope is incomplete and cannot support a candidate pass.",
            "VALIDATION_PREVIEW",
            evidence={"missing": missing_scope},
        ))

    if not isinstance(candidate, dict):
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "CANDIDATE_EVIDENCE_MISSING",
            "A completed preview must be paired with a candidate evidence object.",
            "VALIDATION_PREVIEW",
        ))
        candidate = {}

    required_candidate = ("operation", "requirements", "parentage_level", "payload_sha256")
    missing_candidate = [name for name in required_candidate if not is_provided(candidate.get(name))]
    if missing_candidate:
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "CANDIDATE_EVIDENCE_INCOMPLETE",
            "Candidate evidence is missing fields required to bind the preview result.",
            "VALIDATION_PREVIEW",
            evidence={"missing": missing_candidate},
        ))

    operation = str(candidate.get("operation") or "").upper()
    normalized_candidate = {
        "operation": operation or None,
        "requirements": candidate.get("requirements"),
        "parentage_level": candidate.get("parentage_level"),
        "payload_sha256": candidate.get("payload_sha256"),
        "touched_attributes": candidate.get("touched_attributes"),
        "created_at": candidate.get("created_at"),
    }
    if operation and operation not in {"PUT", "PATCH"}:
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "CANDIDATE_OPERATION_INVALID",
            "Candidate operation must be PUT or PATCH.",
            "VALIDATION_PREVIEW",
            evidence=operation,
        ))

    payload_sha256 = candidate.get("payload_sha256")
    if is_provided(payload_sha256) and not SHA256_PATTERN.fullmatch(str(payload_sha256)):
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "CANDIDATE_PAYLOAD_HASH_INVALID",
            "Candidate payload_sha256 must be a 64-character hexadecimal SHA-256 digest.",
            "VALIDATION_PREVIEW",
        ))

    for field in ("requirements", "parentage_level"):
        if is_provided(candidate.get(field)) and is_provided(scope.get(field)) \
                and str(candidate.get(field)) != str(scope.get(field)):
            binding_valid = False
            rows.append(finding(
                SYSTEM_ERROR,
                "CANDIDATE_SCOPE_MISMATCH",
                f"Candidate {field} does not match the diagnostic scope.",
                "VALIDATION_PREVIEW",
                evidence={"field": field, "expected": scope.get(field), "actual": candidate.get(field)},
            ))

    touched_attributes = candidate.get("touched_attributes")
    if operation == "PATCH" and (
            not isinstance(touched_attributes, list)
            or not touched_attributes
            or not all(is_provided(item) for item in touched_attributes)
    ):
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "PATCH_TOUCHED_ATTRIBUTES_MISSING",
            "A PATCH candidate must list the attributes it touches.",
            "VALIDATION_PREVIEW",
        ))
    elif touched_attributes is not None and not isinstance(touched_attributes, list):
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "TOUCHED_ATTRIBUTES_INVALID",
            "touched_attributes must be an array when provided.",
            "VALIDATION_PREVIEW",
        ))

    required_preview = (
        "mode", "operation", "payload_sha256", "seller_id", "marketplace_id",
        "sku", "product_type", "request_id", "submission_id", "requested_at",
        "responded_at", "http_status", "status", "issues",
    )
    missing_preview = [name for name in required_preview if name not in preview or not is_provided(preview.get(name))]
    # An empty issue array is valid evidence, unlike empty strings and nulls.
    if "issues" in preview and isinstance(preview.get("issues"), list):
        missing_preview = [name for name in missing_preview if name != "issues"]
    if missing_preview:
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "VALIDATION_PREVIEW_EVIDENCE_INCOMPLETE",
            "The completed preview is missing required traceability fields.",
            "VALIDATION_PREVIEW",
            evidence={"missing": missing_preview},
        ))

    issues = preview.get("issues")
    if "issues" in preview and not isinstance(issues, list):
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "VALIDATION_PREVIEW_ISSUES_INVALID",
            "VALIDATION_PREVIEW issues are not an array.",
            "VALIDATION_PREVIEW",
        ))
    elif isinstance(issues, list):
        rows.extend(classify_official_issue(issue, "VALIDATION_PREVIEW") for issue in issues)

    mode = str(preview.get("mode") or "").upper()
    if mode and mode != "VALIDATION_PREVIEW":
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "PREVIEW_MODE_MISMATCH",
            "The response is not explicitly bound to mode=VALIDATION_PREVIEW.",
            "VALIDATION_PREVIEW",
            evidence={"mode": preview.get("mode")},
        ))

    preview_operation = str(preview.get("operation") or "").upper()
    if preview_operation and operation and preview_operation != operation:
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "PREVIEW_OPERATION_MISMATCH",
            "Preview operation does not match the candidate operation.",
            "VALIDATION_PREVIEW",
            evidence={"candidate": operation, "preview": preview_operation},
        ))

    preview_hash = preview.get("payload_sha256")
    if is_provided(preview_hash) and is_provided(payload_sha256) \
            and str(preview_hash).lower() != str(payload_sha256).lower():
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "PREVIEW_PAYLOAD_MISMATCH",
            "Preview payload_sha256 does not match the current candidate payload.",
            "VALIDATION_PREVIEW",
            evidence={"candidate": payload_sha256, "preview": preview_hash},
        ))

    for field in ("seller_id", "marketplace_id", "sku", "product_type"):
        if is_provided(preview.get(field)) and is_provided(scope.get(field)) \
                and str(preview.get(field)) != str(scope.get(field)):
            binding_valid = False
            rows.append(finding(
                SYSTEM_ERROR,
                "PREVIEW_SCOPE_MISMATCH",
                f"Preview {field} does not match the diagnostic scope.",
                "VALIDATION_PREVIEW",
                evidence={"field": field, "expected": scope.get(field), "actual": preview.get(field)},
            ))

    http_status = preview.get("http_status")
    if http_status is not None and (not isinstance(http_status, int) or not 200 <= http_status < 300):
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "VALIDATION_PREVIEW_HTTP_STATUS_INVALID",
            "Preview HTTP status is not a successful 2xx response.",
            "VALIDATION_PREVIEW",
            evidence=http_status,
        ))

    preview_status = str(preview.get("status") or "").upper()
    if preview_status == "INVALID":
        if not any(row["status"] == OFFICIAL_ERROR and row["source"] == "VALIDATION_PREVIEW"
                   for row in rows):
            rows.append(finding(
                OFFICIAL_ERROR,
                "VALIDATION_PREVIEW_INVALID",
                "Amazon preview status is INVALID but no parseable ERROR issue was returned.",
                "VALIDATION_PREVIEW",
                evidence={"submission_id": preview.get("submission_id")},
            ))
    elif preview_status == "ACCEPTED":
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "PREVIEW_MODE_MISMATCH",
            "ACCEPTED belongs to a real submission response, not a VALIDATION_PREVIEW pass.",
            "VALIDATION_PREVIEW",
            evidence={"status": preview_status, "submission_id": preview.get("submission_id")},
        ))
    elif preview_status != "VALID":
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "VALIDATION_PREVIEW_STATUS_UNKNOWN",
            "VALIDATION_PREVIEW status is missing or unknown.",
            "VALIDATION_PREVIEW",
            evidence=preview_status,
        ))

    preview_passed = preview_status == "VALID" and binding_valid and not any(
        row["status"] in {OFFICIAL_ERROR, SYSTEM_ERROR} for row in rows
    )
    return rows, preview_passed, normalized_candidate


def calculate_gate(rows: list[dict[str, Any]], sources: set[str], evaluated: bool,
                   pass_value: str = "PASS") -> str:
    relevant = [row for row in rows if row["source"] in sources]
    if any(row["status"] == OFFICIAL_ERROR for row in relevant):
        return "BLOCK"
    if any(row["status"] == SYSTEM_ERROR for row in relevant):
        return "UNKNOWN"
    if any(row["status"] == OFFICIAL_WARNING for row in relevant):
        return "REVIEW"
    return pass_value if evaluated else "NOT_EVALUATED"


def decide_release(current_gate: str, candidate_gate: str, candidate: dict[str, Any],
                   rows: list[dict[str, Any]]) -> tuple[str, list[str]]:
    if candidate_gate == "BLOCK":
        return "BLOCK", ["CANDIDATE_PREVIEW_BLOCKED"]
    if candidate_gate == "UNKNOWN":
        if current_gate == "BLOCK":
            return "BLOCK", ["CURRENT_BLOCKER_AND_CANDIDATE_UNKNOWN"]
        return "UNKNOWN", ["CANDIDATE_PREVIEW_UNKNOWN"]
    if candidate_gate == "NOT_EVALUATED":
        if current_gate == "BLOCK":
            return "BLOCK", ["CURRENT_BLOCKER_WITHOUT_VALID_CANDIDATE_PREVIEW"]
        return "NOT_EVALUATED", ["CANDIDATE_PREVIEW_NOT_EVALUATED"]
    if candidate_gate == "REVIEW":
        if current_gate == "BLOCK":
            return "BLOCK", ["CURRENT_BLOCKER_AND_CANDIDATE_REQUIRES_REVIEW"]
        return "REVIEW", ["CANDIDATE_PREVIEW_REQUIRES_REVIEW"]

    operation = str(candidate.get("operation") or "").upper()
    if current_gate == "UNKNOWN":
        return "UNKNOWN", ["CURRENT_LISTING_EVIDENCE_UNKNOWN"]
    if current_gate == "BLOCK":
        if any(row["status"] == SYSTEM_ERROR and row["source"] in OFFICIAL_SOURCES for row in rows):
            return "BLOCK", ["CURRENT_BLOCKER_AND_OFFICIAL_VALIDATION_INCOMPLETE"]
        if operation == "PATCH":
            touched = {str(value) for value in candidate.get("touched_attributes") or []}
            uncovered = {
                str(row.get("attribute") or "<unknown>")
                for row in rows
                if row["status"] == OFFICIAL_ERROR
                and row["source"] in {"LISTINGS_ITEMS", "PTD"}
                and str(row.get("attribute") or "<unknown>") not in touched
            }
            if uncovered:
                return "REVIEW", ["PATCH_DOES_NOT_COVER_CURRENT_BLOCKERS"]
        return "REVIEW", ["CURRENT_LISTING_HAS_HISTORICAL_BLOCKERS"]
    if current_gate == "REVIEW":
        return "REVIEW", ["CURRENT_LISTING_REQUIRES_REVIEW"]
    if operation == "PATCH" and current_gate == "NOT_EVALUATED":
        return "REVIEW", ["PATCH_DOES_NOT_ESTABLISH_FULL_LISTING_STATE"]

    return "PASS", ["BOUND_CANDIDATE_PREVIEW_VALID"]


def diagnose(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return finalize({}, {}, {}, [finding(
            SYSTEM_ERROR,
            "INPUT_INVALID",
            "The input root must be a JSON object.",
            "INPUT",
            evidence=data,
        )], False, False)

    scope = data.get("scope") or {}
    content = data.get("content") or {}
    official = data.get("official") or {}
    if not isinstance(scope, dict) or not isinstance(content, dict) or not isinstance(official, dict):
        return finalize({}, {}, {}, [finding(
            SYSTEM_ERROR,
            "INPUT_SECTIONS_INVALID",
            "scope, content, and official must be JSON objects.",
            "INPUT",
        )], False, False)

    rows: list[dict[str, Any]] = []
    missing_identity = [name for name in ("seller_id", "marketplace_id", "sku")
                        if not is_provided(scope.get(name))]
    if missing_identity:
        rows.append(finding(
            NOT_EVALUATED,
            "LISTING_IDENTITY_INCOMPLETE",
            "Seller Listing identity is incomplete and cannot be reliably tied to official evidence.",
            "INPUT",
            evidence={"missing": missing_identity},
        ))

    coverage = {
        key: "PROVIDED" if is_provided(content.get(key)) else "MISSING"
        for key in ("title", "item_highlight", "bullets", "description", "backend_search_terms", "images")
    }

    listing_issues = official.get("listing_issues")
    listing_issues_evaluated = False
    if listing_issues is None:
        rows.append(finding(
            NOT_EVALUATED,
            "LISTING_ISSUES_MISSING",
            "Current Listings Items issues were not supplied.",
            "LISTINGS_ITEMS",
        ))
    elif not isinstance(listing_issues, list):
        rows.append(finding(
            SYSTEM_ERROR,
            "LISTING_ISSUES_INVALID",
            "Listings Items issues are not an array.",
            "LISTINGS_ITEMS",
        ))
    else:
        listing_issues_evaluated = True
        rows.extend(classify_official_issue(issue, "LISTINGS_ITEMS") for issue in listing_issues)

    preview_rows, preview_passed, candidate = evaluate_validation_preview(
        scope, data.get("candidate"), official.get("validation_preview")
    )
    rows.extend(preview_rows)

    ptd_rows, ptd_evaluated, ptd_validation_coverage = evaluate_ptd(content, official.get("ptd"))
    rows.extend(ptd_rows)
    rows.extend(evaluate_images(content))
    report = finalize(
        scope,
        coverage,
        candidate,
        rows,
        listing_issues_evaluated or ptd_evaluated,
        preview_passed,
    )
    report["data_as_of"] = data.get("data_as_of")
    report["ptd_validation_coverage"] = ptd_validation_coverage
    preview = official.get("validation_preview")
    report["validation_preview"] = {
        key: preview.get(key)
        for key in (
            "ran", "mode", "operation", "payload_sha256", "seller_id", "marketplace_id",
            "sku", "product_type", "request_id", "submission_id", "requested_at",
            "responded_at", "http_status", "status",
        )
        if isinstance(preview, dict) and key in preview
    }
    return report


def finalize(scope: dict[str, Any], coverage: dict[str, Any], candidate: dict[str, Any],
             rows: list[dict[str, Any]], current_evaluated: bool,
             preview_passed: bool) -> dict[str, Any]:
    counts = Counter(row["status"] for row in rows)
    current_gate = calculate_gate(
        rows,
        {"LISTINGS_ITEMS", "PTD"},
        current_evaluated,
        pass_value="NO_KNOWN_OFFICIAL_ISSUES",
    )
    candidate_gate = calculate_gate(
        rows,
        {"VALIDATION_PREVIEW"},
        preview_passed,
        pass_value="PASS",
    )
    release_decision, release_reasons = decide_release(current_gate, candidate_gate, candidate, rows)
    official_incomplete = any(
        row["status"] in {NOT_EVALUATED, SYSTEM_ERROR} and row["source"] in OFFICIAL_SOURCES
        for row in rows
    )
    operation = str(candidate.get("operation") or "").upper() or None
    return {
        "scope": scope,
        "candidate": candidate,
        "current_listing_gate": current_gate,
        "candidate_preview_gate": candidate_gate,
        "release_decision": release_decision,
        "release_reasons": release_reasons,
        # Compatibility field retained for 1.0.x consumers.
        "gate": "PASS_OFFICIAL_CHECKS" if release_decision == "PASS" else release_decision,
        "official_scope": {
            "operation": operation,
            "coverage": "FULL" if operation == "PUT" else "PARTIAL" if operation == "PATCH" else "UNKNOWN",
            "touched_attributes": candidate.get("touched_attributes") if operation == "PATCH" else None,
        },
        "official_validation_completeness": "INCOMPLETE" if official_incomplete else "COMPLETE",
        "coverage": coverage,
        "counts": {state: counts.get(state, 0) for state in ALL_STATES},
        "findings": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify Amazon Listing diagnostic evidence")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=Path, help="Input JSON file")
    group.add_argument("--data", help="Inline JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        raw = args.file.read_text(encoding="utf-8") if args.file else args.data
        report = diagnose(json.loads(raw))
    except Exception as exc:
        report = finalize({}, {}, {}, [finding(
            SYSTEM_ERROR,
            "INPUT_READ_ERROR",
            f"Could not read or parse input: {type(exc).__name__}: {exc}",
            "INPUT",
        )], False, False)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["counts"][SYSTEM_ERROR]:
        return 2
    if report["counts"][OFFICIAL_ERROR]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
