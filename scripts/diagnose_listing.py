#!/usr/bin/env python3
"""Classify Amazon Listing evidence without network calls or data writes."""

from __future__ import annotations

import argparse
import json
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
    elif severity == "WARNING":
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


def evaluate_ptd(content: dict[str, Any], ptd: Any) -> list[dict[str, Any]]:
    if ptd is None:
        return [finding(
            NOT_EVALUATED,
            "PTD_MISSING",
            "No Product Type Definition was supplied; local official-constraint checks were not run.",
            "PTD",
        )]
    if not isinstance(ptd, dict):
        return [finding(SYSTEM_ERROR, "PTD_INVALID", "PTD data is not an object.", "PTD", evidence=ptd)]

    rows: list[dict[str, Any]] = []
    status = str(ptd.get("status") or "UNAVAILABLE").upper()
    if status == "UNAVAILABLE":
        return [finding(
            NOT_EVALUATED,
            "PTD_UNAVAILABLE",
            "The current PTD schema is unavailable; attribute limits were not inferred.",
            "PTD",
        )]
    if status not in {"FRESH", "STALE_WITHIN_GRACE"}:
        return [finding(
            SYSTEM_ERROR,
            "PTD_STATUS_UNKNOWN",
            "The PTD status is unknown and the schema cannot be used safely.",
            "PTD",
            evidence=status,
        )]
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
        return rows

    supported_types = {"MAX_LENGTH", "MIN_LENGTH", "MAX_ITEMS", "MIN_ITEMS"}
    supported_units = {"CODE_POINTS", "UTF8_BYTES", "ITEMS"}
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
                rows.append(finding(
                    NOT_EVALUATED,
                    "PTD_CONSTRAINT_UNSUPPORTED",
                    "This PTD constraint or measurement unit is unsupported; no assumption was made.",
                    "PTD",
                    attribute,
                    rule,
                ))
                continue
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
    return rows


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
        width, height = image.get("width"), image.get("height")
        label = "main image" if image.get("is_main") else f"image {index + 1}"
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

        if image.get("is_main"):
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
    return rows


def diagnose(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return finalize({}, {}, [finding(
            SYSTEM_ERROR,
            "INPUT_INVALID",
            "The input root must be a JSON object.",
            "INPUT",
            evidence=data,
        )], False)

    scope = data.get("scope") or {}
    content = data.get("content") or {}
    official = data.get("official") or {}
    if not isinstance(scope, dict) or not isinstance(content, dict) or not isinstance(official, dict):
        return finalize({}, {}, [finding(
            SYSTEM_ERROR,
            "INPUT_SECTIONS_INVALID",
            "scope, content, and official must be JSON objects.",
            "INPUT",
        )], False)

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
        rows.extend(classify_official_issue(issue, "LISTINGS_ITEMS") for issue in listing_issues)

    preview = official.get("validation_preview")
    preview_ran = isinstance(preview, dict) and preview.get("ran") is True
    preview_passed = False
    if not preview_ran:
        rows.append(finding(
            NOT_EVALUATED,
            "VALIDATION_PREVIEW_NOT_RUN",
            "Listings Items VALIDATION_PREVIEW was not completed.",
            "VALIDATION_PREVIEW",
        ))
    elif not isinstance(preview.get("issues", []), list):
        rows.append(finding(
            SYSTEM_ERROR,
            "VALIDATION_PREVIEW_ISSUES_INVALID",
            "VALIDATION_PREVIEW issues are not an array.",
            "VALIDATION_PREVIEW",
        ))
    else:
        rows.extend(classify_official_issue(issue, "VALIDATION_PREVIEW")
                    for issue in preview.get("issues", []))
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
        elif preview_status in {"VALID", "ACCEPTED"}:
            preview_passed = True
        else:
            rows.append(finding(
                SYSTEM_ERROR,
                "VALIDATION_PREVIEW_STATUS_UNKNOWN",
                "VALIDATION_PREVIEW status is missing or unknown.",
                "VALIDATION_PREVIEW",
                evidence=preview_status,
            ))

    rows.extend(evaluate_ptd(content, official.get("ptd")))
    rows.extend(evaluate_images(content))
    report = finalize(scope, coverage, rows, preview_passed)
    report["data_as_of"] = data.get("data_as_of")
    return report


def finalize(scope: dict[str, Any], coverage: dict[str, Any], rows: list[dict[str, Any]],
             preview_passed: bool) -> dict[str, Any]:
    counts = Counter(row["status"] for row in rows)
    official_sources = {"INPUT", "LISTINGS_ITEMS", "PTD", "VALIDATION_PREVIEW"}
    official_system_error = any(
        row["status"] == SYSTEM_ERROR and row["source"] in official_sources
        for row in rows
    )
    if official_system_error:
        gate = "UNKNOWN"
    elif counts[OFFICIAL_ERROR]:
        gate = "BLOCK"
    elif counts[OFFICIAL_WARNING]:
        gate = "REVIEW"
    elif preview_passed:
        gate = "PASS_OFFICIAL_CHECKS"
    else:
        gate = "NOT_EVALUATED"
    return {
        "scope": scope,
        "gate": gate,
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
        report = finalize({}, {}, [finding(
            SYSTEM_ERROR,
            "INPUT_READ_ERROR",
            f"Could not read or parse input: {type(exc).__name__}: {exc}",
            "INPUT",
        )], False)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["counts"][SYSTEM_ERROR]:
        return 2
    if report["counts"][OFFICIAL_ERROR]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
