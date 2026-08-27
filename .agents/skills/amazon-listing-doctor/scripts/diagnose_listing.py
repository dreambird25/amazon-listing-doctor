#!/usr/bin/env python3
"""Classify Amazon Listing evidence without network calls or data writes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
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


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def request_fingerprint(scope: dict[str, Any], candidate: dict[str, Any]) -> str:
    material = {
        "marketplace_id": scope.get("marketplace_id"),
        "mode": "VALIDATION_PREVIEW",
        "operation": str(candidate.get("operation") or "").upper(),
        "payload_sha256": str(candidate.get("payload_sha256") or "").lower(),
        "product_type": scope.get("product_type"),
        "requirements": candidate.get("requirements"),
        "seller_id": scope.get("seller_id"),
        "sku": scope.get("sku"),
    }
    canonical = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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


def normalize_attribute_aliases(value: Any) -> tuple[dict[str, str], list[dict[str, Any]]]:
    if value is None:
        return {}, []
    if not isinstance(value, dict):
        return {}, [finding(
            SYSTEM_ERROR,
            "ATTRIBUTE_ALIASES_INVALID",
            "attribute_aliases must be an object mapping source names to PTD attribute names.",
            "INPUT",
        )]
    aliases: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for source, target in value.items():
        if not isinstance(source, str) or not source.strip() \
                or not isinstance(target, str) or not target.strip():
            rows.append(finding(
                SYSTEM_ERROR,
                "ATTRIBUTE_ALIAS_INVALID",
                "Each attribute alias must map a non-empty string to a non-empty string.",
                "INPUT",
                evidence={"source": source, "target": target},
            ))
            continue
        aliases[source.strip()] = target.strip()
    for source in aliases:
        visited: set[str] = set()
        name = source
        while name in aliases:
            if name in visited:
                rows.append(finding(
                    SYSTEM_ERROR,
                    "ATTRIBUTE_ALIAS_CYCLE",
                    "attribute_aliases contains a cycle and cannot be resolved safely.",
                    "INPUT",
                    evidence={"source": source},
                ))
                break
            visited.add(name)
            name = aliases[name]
    return aliases, rows


def canonical_attribute(attribute: Any, aliases: dict[str, str]) -> str:
    name = str(attribute or "")
    visited: set[str] = set()
    while name not in visited:
        visited.add(name)
        if name in aliases:
            name = aliases[name]
            continue
        mapped = CONTENT_ATTRIBUTE_MAP.get(name)
        if mapped and mapped != name:
            name = mapped
            continue
        break
    return name


def attribute_elements(
        content: dict[str, Any], attribute: str, aliases: dict[str, str],
        scope: dict[str, Any],
) -> tuple[list[dict[str, Any]], bool]:
    """Resolve all scope-matching Amazon attribute elements without first-item shortcuts."""
    attributes = content.get("attributes")
    if attributes is not None and not isinstance(attributes, dict):
        return [], False

    candidate_names: list[str] = [attribute]
    if attribute in aliases:
        candidate_names.append(aliases[attribute])
    candidate_names.extend(source for source, target in aliases.items() if target == attribute)
    candidate_names.extend(field for field, mapped in CONTENT_ATTRIBUTE_MAP.items() if mapped == attribute)
    canonical_requested = canonical_attribute(attribute, aliases)
    candidate_names.extend(
        name for name in (*aliases.keys(), *aliases.values(), *CONTENT_ATTRIBUTE_MAP.keys())
        if canonical_attribute(name, aliases) == canonical_requested
    )
    candidate_names = list(dict.fromkeys(candidate_names))

    raw: Any = None
    resolved_name: str | None = None
    for name in candidate_names:
        if isinstance(attributes, dict) and name in attributes:
            raw = attributes[name]
            resolved_name = name
            break
        if name in content:
            raw = content[name]
            resolved_name = name
            break
    if raw is None:
        return [], True

    values = raw if isinstance(raw, list) else [raw]
    elements: list[dict[str, Any]] = []
    target_marketplace = str(scope.get("marketplace_id") or "")
    target_locale = str(scope.get("locale") or "")
    for index, item in enumerate(values):
        if isinstance(item, dict) and "value" in item:
            element = {
                "value": item.get("value"),
                "marketplace_id": item.get("marketplace_id"),
                "language_tag": item.get("language_tag"),
                "index": index,
                "resolved_attribute": resolved_name,
            }
        else:
            element = {
                "value": item,
                "marketplace_id": None,
                "language_tag": None,
                "index": index,
                "resolved_attribute": resolved_name,
            }
        marketplace = str(element.get("marketplace_id") or "")
        language_tag = str(element.get("language_tag") or "")
        if marketplace and target_marketplace and marketplace != target_marketplace:
            continue
        if language_tag and target_locale and language_tag != target_locale:
            continue
        elements.append(element)
    return elements, True


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


def mark_unbound_official_findings(
        rows: list[dict[str, Any]], source: str, applicability_field: str
) -> None:
    for row in rows:
        if row["source"] == source and row["status"] in {OFFICIAL_ERROR, OFFICIAL_WARNING}:
            row[applicability_field] = False


def evaluate_listing_snapshot(
        scope: dict[str, Any], official: dict[str, Any], evaluation_time: datetime | None
) -> tuple[list[dict[str, Any]], bool, dict[str, Any]]:
    snapshot = official.get("listing_snapshot")
    legacy_issues = official.get("listing_issues")
    if snapshot is None:
        if legacy_issues is None:
            return [finding(
                NOT_EVALUATED,
                "LISTING_SNAPSHOT_MISSING",
                "A traceable Listings Items snapshot was not supplied.",
                "LISTINGS_ITEMS",
            )], False, {}
        if not isinstance(legacy_issues, list):
            return [finding(
                SYSTEM_ERROR,
                "LISTING_ISSUES_INVALID",
                "Legacy listing_issues evidence is not an array.",
                "LISTINGS_ITEMS",
            )], False, {"legacy": True}
        rows = [classify_official_issue(issue, "LISTINGS_ITEMS") for issue in legacy_issues]
        rows.append(finding(
            NOT_EVALUATED,
            "LISTING_SNAPSHOT_TRACEABILITY_MISSING",
            "Legacy listing_issues were classified, but identity, includedData, request, and time binding are missing.",
            "LISTINGS_ITEMS",
        ))
        return rows, False, {"legacy": True, "issue_count": len(legacy_issues)}

    if not isinstance(snapshot, dict):
        return [finding(
            SYSTEM_ERROR,
            "LISTING_SNAPSHOT_INVALID",
            "Listings Items snapshot evidence is not an object.",
            "LISTINGS_ITEMS",
        )], False, {}

    rows: list[dict[str, Any]] = []
    binding_valid = True
    required = (
        "seller_id", "marketplace_id", "sku", "request_id", "fetched_at",
        "expires_at", "included_data", "issues",
    )
    missing = [name for name in required if name not in snapshot or not is_provided(snapshot.get(name))]
    if isinstance(snapshot.get("issues"), list):
        missing = [name for name in missing if name != "issues"]
    if missing:
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "LISTING_SNAPSHOT_EVIDENCE_INCOMPLETE",
            "The Listings Items snapshot is missing required traceability fields.",
            "LISTINGS_ITEMS",
            evidence={"missing": missing},
        ))

    for field in ("seller_id", "marketplace_id", "sku"):
        if is_provided(snapshot.get(field)) and is_provided(scope.get(field)) \
                and str(snapshot.get(field)) != str(scope.get(field)):
            binding_valid = False
            rows.append(finding(
                SYSTEM_ERROR,
                "LISTING_SNAPSHOT_SCOPE_MISMATCH",
                f"Snapshot {field} does not match the diagnostic scope.",
                "LISTINGS_ITEMS",
                evidence={"field": field, "expected": scope.get(field), "actual": snapshot.get(field)},
            ))

    included_data = snapshot.get("included_data")
    if not isinstance(included_data, list) or not all(isinstance(item, str) for item in included_data):
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "LISTING_SNAPSHOT_INCLUDED_DATA_INVALID",
            "included_data must be an array of strings.",
            "LISTINGS_ITEMS",
        ))
    elif "issues" not in {item.lower() for item in included_data}:
        binding_valid = False
        rows.append(finding(
            NOT_EVALUATED,
            "LISTING_SNAPSHOT_ISSUES_NOT_INCLUDED",
            "The snapshot did not request issues, so an empty issue array is not a pass.",
            "LISTINGS_ITEMS",
        ))

    issues = snapshot.get("issues")
    if not isinstance(issues, list):
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "LISTING_SNAPSHOT_ISSUES_INVALID",
            "Snapshot issues are not an array.",
            "LISTINGS_ITEMS",
        ))
        issues = []
    else:
        rows.extend(classify_official_issue(issue, "LISTINGS_ITEMS") for issue in issues)

    fetched_at = parse_timestamp(snapshot.get("fetched_at"))
    expires_at = parse_timestamp(snapshot.get("expires_at"))
    if fetched_at is None or expires_at is None:
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "LISTING_SNAPSHOT_TIMESTAMP_INVALID",
            "Snapshot timestamps must be timezone-aware ISO-8601 values.",
            "LISTINGS_ITEMS",
        ))
    elif fetched_at > expires_at:
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "LISTING_SNAPSHOT_TIME_ORDER_INVALID",
            "Snapshot fetched_at is later than expires_at.",
            "LISTINGS_ITEMS",
        ))
    elif evaluation_time is None:
        binding_valid = False
    elif evaluation_time > expires_at:
        binding_valid = False
        rows.append(finding(
            NOT_EVALUATED,
            "LISTING_SNAPSHOT_STALE",
            "The Listings Items snapshot expired before this diagnostic run.",
            "LISTINGS_ITEMS",
            evidence={"expires_at": snapshot.get("expires_at")},
        ))

    if not binding_valid:
        mark_unbound_official_findings(rows, "LISTINGS_ITEMS", "applies_to_current")
    evaluated = binding_valid and not any(
        row["status"] in {NOT_EVALUATED, SYSTEM_ERROR} for row in rows
    )
    summary = {
        "request_id": snapshot.get("request_id"),
        "fetched_at": snapshot.get("fetched_at"),
        "expires_at": snapshot.get("expires_at"),
        "included_data": included_data if isinstance(included_data, list) else None,
        "issue_count": len(issues),
    }
    return rows, evaluated, summary


def ptd_coverage(status: str, supported: int = 0, unsupported: int = 0,
                 evaluated: int = 0, scope_bound: bool = False,
                 time_valid: bool = False, validation_target: str = "CURRENT",
                 full_schema_validation: bool = False) -> dict[str, Any]:
    return {
        "mode": "FULL_JSON_SCHEMA" if full_schema_validation else "LIGHTWEIGHT_SUBSET",
        "status": status,
        "validation_target": validation_target,
        "supported_constraint_count": supported,
        "unsupported_constraint_count": unsupported,
        "evaluated_constraint_count": evaluated,
        "scope_bound": scope_bound,
        "time_valid": time_valid,
        "full_schema_validation": full_schema_validation,
    }


def evaluate_full_schema_validation(
        proof: Any, ptd: dict[str, Any], candidate: dict[str, Any],
        evaluation_time: datetime | None,
) -> tuple[list[dict[str, Any]], bool]:
    if proof is None:
        return [finding(
            NOT_EVALUATED,
            "FULL_SCHEMA_VALIDATION_MISSING",
            "No bound external full-schema validation evidence was supplied for the candidate.",
            "PTD",
        )], False
    if not isinstance(proof, dict):
        return [finding(
            SYSTEM_ERROR,
            "FULL_SCHEMA_VALIDATION_INVALID",
            "full_schema_validation must be a traceable evidence object, not a boolean assertion.",
            "PTD",
        )], False

    required = (
        "complete", "valid", "validator", "validator_version", "schema_draft",
        "amazon_vocabulary", "schema_checksum", "meta_schema_checksum",
        "payload_sha256", "validated_at", "errors",
    )
    missing = [name for name in required if name not in proof]
    if missing:
        return [finding(
            SYSTEM_ERROR,
            "FULL_SCHEMA_VALIDATION_EVIDENCE_INCOMPLETE",
            "Full-schema validation evidence is missing required binding fields.",
            "PTD",
            evidence={"missing": missing},
        )], False

    rows: list[dict[str, Any]] = []
    binding_valid = True
    if proof.get("complete") is not True or not isinstance(proof.get("valid"), bool):
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "FULL_SCHEMA_VALIDATION_FLAGS_INVALID",
            "complete must be true and valid must be a boolean.",
            "PTD",
        ))
    if str(proof.get("schema_draft")) != "2019-09" or proof.get("amazon_vocabulary") is not True:
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "FULL_SCHEMA_VALIDATOR_CAPABILITY_MISMATCH",
            "The adapter must attest JSON Schema Draft 2019-09 and Amazon vocabulary support.",
            "PTD",
        ))
    for field in ("validator", "validator_version"):
        if not is_provided(proof.get(field)):
            binding_valid = False
    bindings = {
        "schema_checksum": ptd.get("schema_checksum"),
        "meta_schema_checksum": ptd.get("meta_schema_checksum"),
        "payload_sha256": candidate.get("payload_sha256"),
    }
    for field, expected in bindings.items():
        actual = proof.get(field)
        if not is_provided(expected) or str(actual).lower() != str(expected).lower():
            binding_valid = False
            rows.append(finding(
                SYSTEM_ERROR,
                "FULL_SCHEMA_VALIDATION_BINDING_MISMATCH",
                f"Full-schema validation {field} does not match its bound evidence.",
                "PTD",
                evidence={"field": field, "expected": expected, "actual": actual},
            ))
    errors = proof.get("errors")
    if not isinstance(errors, list):
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "FULL_SCHEMA_VALIDATION_ERRORS_INVALID",
            "Full-schema validation errors must be an array.",
            "PTD",
        ))
        errors = []

    validated_at = parse_timestamp(proof.get("validated_at"))
    created_at = parse_timestamp(candidate.get("created_at"))
    ptd_fetched_at = parse_timestamp(ptd.get("fetched_at"))
    if validated_at is None or created_at is None or ptd_fetched_at is None \
            or evaluation_time is None:
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "FULL_SCHEMA_VALIDATION_TIMESTAMP_INVALID",
            "Full-schema validation timestamps must be timezone-aware and fully bound.",
            "PTD",
        ))
    elif validated_at < max(created_at, ptd_fetched_at) or validated_at > evaluation_time:
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "FULL_SCHEMA_VALIDATION_TIME_ORDER_INVALID",
            "validated_at must follow the candidate and PTD fetch and not exceed data_as_of.",
            "PTD",
        ))

    if not binding_valid:
        return rows, False
    if proof.get("valid") is False or errors:
        rows.append(finding(
            OFFICIAL_ERROR,
            "FULL_SCHEMA_VALIDATION_FAILED",
            "The bound candidate failed full PTD JSON Schema validation.",
            "PTD",
            evidence={"error_count": len(errors), "validator": proof.get("validator")},
        ))
        return rows, False
    return rows, True


def evaluate_ptd(
        scope: dict[str, Any], content: dict[str, Any], ptd: Any,
        evaluation_time: datetime | None, aliases: dict[str, str] | None = None,
        validation_target: str = "CURRENT", candidate: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], bool, dict[str, Any]]:
    aliases = aliases or {}
    candidate = candidate or {}
    if ptd is None:
        return [finding(
            NOT_EVALUATED,
            "PTD_MISSING",
            "No Product Type Definition was supplied; local official-constraint checks were not run.",
            "PTD",
        )], False, ptd_coverage("NOT_EVALUATED", validation_target=validation_target)
    if not isinstance(ptd, dict):
        return [finding(
            SYSTEM_ERROR, "PTD_INVALID", "PTD data is not an object.", "PTD", evidence=ptd
        )], False, ptd_coverage("SYSTEM_ERROR", validation_target=validation_target)

    rows: list[dict[str, Any]] = []
    traceability_valid = True
    status = str(ptd.get("status") or "UNAVAILABLE").upper()
    if status == "UNAVAILABLE":
        return [finding(
            NOT_EVALUATED,
            "PTD_UNAVAILABLE",
            "The current PTD schema is unavailable; attribute limits were not inferred.",
            "PTD",
        )], False, ptd_coverage("NOT_EVALUATED", validation_target=validation_target)
    if status == "AVAILABLE":
        status = "FRESH"
    elif status == "STALE":
        status = "STALE_WITHIN_GRACE"
    if status not in {"FRESH", "STALE_WITHIN_GRACE"}:
        return [finding(
            SYSTEM_ERROR,
            "PTD_STATUS_UNKNOWN",
            "The PTD status is unknown and the schema cannot be used safely.",
            "PTD",
            evidence=status,
        )], False, ptd_coverage("SYSTEM_ERROR", validation_target=validation_target)
    if status == "STALE_WITHIN_GRACE":
        rows.append(finding(
            OFFICIAL_WARNING,
            "PTD_STALE_WITHIN_GRACE",
            "The last successful PTD schema is within its configured grace period; review refresh status before submission.",
            "PTD",
            evidence={"schema_checksum": ptd.get("schema_checksum")},
        ))

    ptd_scope = ptd.get("scope")
    scope_bound = True
    if not isinstance(ptd_scope, dict):
        scope_bound = False
        rows.append(finding(
            SYSTEM_ERROR,
            "PTD_SCOPE_MISSING",
            "PTD evidence must record the exact request scope.",
            "PTD",
        ))
        ptd_scope = {}
    required_ptd_scope = (
        "seller_id", "marketplace_id", "product_type", "product_type_version",
        "requirements", "requirements_enforced", "parentage_level", "locale",
    )
    missing_ptd_scope = [name for name in required_ptd_scope if not is_provided(ptd_scope.get(name))]
    if missing_ptd_scope:
        scope_bound = False
        rows.append(finding(
            SYSTEM_ERROR,
            "PTD_SCOPE_INCOMPLETE",
            "PTD request scope is incomplete.",
            "PTD",
            evidence={"missing": missing_ptd_scope},
        ))
    requirements_enforced = str(ptd_scope.get("requirements_enforced") or "").upper()
    if requirements_enforced and requirements_enforced not in {"ENFORCED", "NOT_ENFORCED"}:
        scope_bound = False
        rows.append(finding(
            SYSTEM_ERROR,
            "PTD_REQUIREMENTS_ENFORCED_INVALID",
            "PTD requirements_enforced must be ENFORCED or NOT_ENFORCED.",
            "PTD",
            evidence=requirements_enforced,
        ))
    elif validation_target == "CANDIDATE" and requirements_enforced == "NOT_ENFORCED":
        rows.append(finding(
            OFFICIAL_WARNING,
            "PTD_REQUIREMENTS_NOT_ENFORCED",
            "Candidate PTD evidence was retrieved with requirements_enforced=NOT_ENFORCED and cannot support unattended release.",
            "PTD",
        ))
    for field in ("seller_id", "marketplace_id", "product_type", "requirements", "parentage_level", "locale"):
        if is_provided(ptd_scope.get(field)) and is_provided(scope.get(field)) \
                and str(ptd_scope.get(field)) != str(scope.get(field)):
            scope_bound = False
            rows.append(finding(
                SYSTEM_ERROR,
                "PTD_SCOPE_MISMATCH",
                f"PTD {field} does not match the diagnostic scope.",
                "PTD",
                evidence={"field": field, "expected": scope.get(field), "actual": ptd_scope.get(field)},
            ))
    if is_provided(ptd_scope.get("product_type_version")) and is_provided(ptd.get("resolved_version")) \
            and str(ptd_scope.get("product_type_version")) != str(ptd.get("resolved_version")):
        scope_bound = False
        rows.append(finding(
            SYSTEM_ERROR,
            "PTD_VERSION_MISMATCH",
            "PTD scope version does not match resolved_version.",
            "PTD",
            evidence={
                "scope_version": ptd_scope.get("product_type_version"),
                "resolved_version": ptd.get("resolved_version"),
            },
        ))
    missing_traceability = [
        name for name in (
            "schema_checksum", "meta_schema_checksum", "resolved_version",
            "latest", "release_candidate", "fetched_at", "expires_at",
        )
        if not is_provided(ptd.get(name))
    ]
    if missing_traceability:
        traceability_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "PTD_TRACEABILITY_INCOMPLETE",
            "PTD evidence is missing version, checksum, or time metadata.",
            "PTD",
            evidence={"missing": missing_traceability},
        ))
    for field in ("latest", "release_candidate"):
        if field in ptd and not isinstance(ptd.get(field), bool):
            traceability_valid = False
            rows.append(finding(
                SYSTEM_ERROR,
                "PTD_VERSION_FLAG_INVALID",
                f"PTD {field} must be a boolean.",
                "PTD",
                evidence={"field": field},
            ))

    fetched_at = parse_timestamp(ptd.get("fetched_at"))
    expires_at = parse_timestamp(ptd.get("expires_at"))
    timestamps_valid = (
        fetched_at is not None and expires_at is not None and fetched_at <= expires_at
    )
    time_valid = timestamps_valid and evaluation_time is not None
    if not timestamps_valid:
        rows.append(finding(
            SYSTEM_ERROR,
            "PTD_TIMESTAMP_INVALID",
            "PTD fetched_at and expires_at must be ordered, timezone-aware ISO-8601 values.",
            "PTD",
        ))
    elif evaluation_time is None:
        rows.append(finding(
            NOT_EVALUATED,
            "PTD_FRESHNESS_NOT_EVALUATED",
            "data_as_of is required to determine whether the PTD evidence is current.",
            "PTD",
        ))
    elif status == "FRESH" and evaluation_time > expires_at:
        time_valid = False
        rows.append(finding(
            NOT_EVALUATED,
            "PTD_EXPIRED",
            "The PTD schema expired before this diagnostic run.",
            "PTD",
            evidence={"expires_at": ptd.get("expires_at")},
        ))
    elif status == "STALE_WITHIN_GRACE":
        grace_deadline = parse_timestamp(ptd.get("stale_grace_deadline"))
        if grace_deadline is None or evaluation_time is None or evaluation_time > grace_deadline:
            time_valid = False
            rows.append(finding(
                NOT_EVALUATED,
                "PTD_STALE_GRACE_INVALID",
                "Stale PTD evidence lacks a valid grace deadline for this diagnostic run.",
                "PTD",
            ))

    full_schema_validated = False
    if validation_target == "CANDIDATE":
        full_rows, full_schema_validated = evaluate_full_schema_validation(
            ptd.get("full_schema_validation"), ptd, candidate, evaluation_time
        )
        rows.extend(full_rows)
        full_schema_validated = (
            full_schema_validated and scope_bound and traceability_valid and time_valid
        )
        if full_schema_validated:
            return rows, True, ptd_coverage(
                "FULLY_EVALUATED",
                scope_bound=scope_bound,
                time_valid=time_valid,
                validation_target=validation_target,
                full_schema_validation=True,
            )

    constraints = ptd.get("constraints")
    if not isinstance(constraints, dict) or not constraints:
        if not full_schema_validated:
            rows.append(finding(
                NOT_EVALUATED,
                "PTD_CONSTRAINTS_MISSING",
                "The PTD input contains no executable constraints.",
                "PTD",
            ))
        if not (scope_bound and traceability_valid and time_valid):
            mark_unbound_official_findings(
                rows, "PTD",
                "applies_to_candidate" if validation_target == "CANDIDATE"
                else "applies_to_current",
            )
        evaluated = full_schema_validated and scope_bound and traceability_valid and time_valid
        return rows, evaluated, ptd_coverage(
            "FULLY_EVALUATED" if full_schema_validated else "NOT_EVALUATED",
            scope_bound=scope_bound,
            time_valid=time_valid,
            validation_target=validation_target,
            full_schema_validation=full_schema_validated,
        )

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
        elements, attributes_valid = attribute_elements(content, attribute, aliases, scope)
        if not attributes_valid:
            rows.append(finding(
                SYSTEM_ERROR,
                "CONTENT_ATTRIBUTES_INVALID",
                "content.attributes must be an object when supplied.",
                "PTD",
                attribute,
            ))
            continue
        if not elements:
            rows.append(finding(
                NOT_EVALUATED,
                "ATTRIBUTE_VALUE_MISSING",
                "No value matching the diagnostic marketplace and locale was found for this attribute.",
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
            measured_elements = [{"value": [element.get("value") for element in elements]}] \
                if unit == "ITEMS" else elements
            for element in measured_elements:
                value = element.get("value")
                actual = measure(value, unit)
                if actual is None:
                    rows.append(finding(
                        SYSTEM_ERROR,
                        "PTD_VALUE_TYPE_MISMATCH",
                        "The attribute value type does not match the PTD measurement unit.",
                        "PTD",
                        attribute,
                        {
                            "rule": rule,
                            "value_type": type(value).__name__,
                            "element_index": element.get("index"),
                        },
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
                            "element_index": element.get("index"),
                            "language_tag": element.get("language_tag"),
                            "marketplace_id": element.get("marketplace_id"),
                            "resolved_attribute": element.get("resolved_attribute"),
                            "schema_checksum": ptd.get("schema_checksum"),
                            "resolved_version": ptd.get("resolved_version"),
                        },
                    ))
    binding_valid = scope_bound and traceability_valid and time_valid
    if not binding_valid:
        mark_unbound_official_findings(
            rows, "PTD",
            "applies_to_candidate" if validation_target == "CANDIDATE"
            else "applies_to_current",
        )
    ptd_complete = binding_valid and not any(
        row["status"] in {NOT_EVALUATED, SYSTEM_ERROR} for row in rows
    )
    if full_schema_validated:
        coverage_status = "FULLY_EVALUATED"
    else:
        coverage_status = "EVALUATED_SUBSET" if ptd_complete else "PARTIALLY_EVALUATED"
    return rows, ptd_complete, ptd_coverage(
        coverage_status,
        supported=supported_count,
        unsupported=unsupported_count,
        evaluated=evaluated_count,
        scope_bound=scope_bound,
        time_valid=time_valid,
        validation_target=validation_target,
        full_schema_validation=full_schema_validated,
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
    main_count = 0
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
        is_main_value = image.get("is_main")
        if is_main_value is not None and not isinstance(is_main_value, bool):
            rows.append(finding(
                SYSTEM_ERROR,
                "IMAGE_METADATA_TYPE_INVALID",
                "is_main must be true, false, or null.",
                "HEURISTIC",
                evidence={"index": index, "field": "is_main"},
            ))
        is_main = is_main_value is True
        if is_main:
            main_count += 1
        main_identified = main_identified or is_main
        width, height = image.get("width"), image.get("height")
        label = "main image" if is_main else f"image {index + 1}"
        dimensions_missing = width is None or height is None
        dimensions_type_valid = all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in (width, height)
            if value is not None
        )
        if not dimensions_type_valid:
            rows.append(finding(
                SYSTEM_ERROR,
                "IMAGE_METADATA_TYPE_INVALID",
                "width and height must be positive integers or null.",
                "HEURISTIC",
                evidence={"index": index, "field": "width/height"},
            ))
        elif dimensions_missing:
            rows.append(finding(
                NOT_EVALUATED,
                "IMAGE_DIMENSIONS_MISSING",
                f"The {label} has no valid dimensions; resolution and aspect ratio were not evaluated.",
                "HEURISTIC",
                evidence={"index": index, "url": image.get("url")},
            ))
        elif width <= 0 or height <= 0:
            rows.append(finding(
                SYSTEM_ERROR,
                "IMAGE_DIMENSIONS_INVALID",
                "width and height must be positive when provided.",
                "HEURISTIC",
                evidence={"index": index, "width": width, "height": height},
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

        watermark = image.get("watermark")
        if watermark is not None and not isinstance(watermark, bool):
            rows.append(finding(
                SYSTEM_ERROR,
                "IMAGE_METADATA_TYPE_INVALID",
                "watermark must be true, false, or null.",
                "HEURISTIC",
                evidence={"index": index, "field": "watermark"},
            ))
        elif watermark is None:
            rows.append(finding(
                NOT_EVALUATED,
                "IMAGE_WATERMARK_UNKNOWN",
                f"The {label}'s watermark status is unknown.",
                "HEURISTIC",
                evidence={"index": index, "url": image.get("url")},
            ))
        elif watermark is True:
            rows.append(finding(
                HEURISTIC_ADVICE,
                "IMAGE_WATERMARK_PRESENT",
                f"A watermark was detected on the {label}; use an Amazon issue or current category rule for compliance classification.",
                "HEURISTIC",
                evidence={"index": index, "url": image.get("url")},
            ))

        if is_main:
            white_background = image.get("white_background")
            if white_background is not None and not isinstance(white_background, bool):
                rows.append(finding(
                    SYSTEM_ERROR,
                    "IMAGE_METADATA_TYPE_INVALID",
                    "white_background must be true, false, or null.",
                    "HEURISTIC",
                    evidence={"index": index, "field": "white_background"},
                ))
            elif white_background is None:
                rows.append(finding(
                    NOT_EVALUATED,
                    "MAIN_IMAGE_BACKGROUND_UNKNOWN",
                    "The main image background was not verified.",
                    "HEURISTIC",
                    evidence={"index": index, "url": image.get("url")},
                ))
            elif white_background is False:
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
    elif main_count > 1:
        rows.append(finding(
            SYSTEM_ERROR,
            "MULTIPLE_MAIN_IMAGES",
            "More than one image is marked as the main image.",
            "HEURISTIC",
            evidence={"main_image_count": main_count},
        ))
    return rows


def evaluate_validation_preview(
        scope: dict[str, Any], candidate: Any, preview: Any,
        evaluation_time: datetime | None, ptd_fetched_at: datetime | None,
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

    required_candidate = (
        "operation", "requirements", "parentage_level", "payload_sha256", "created_at",
    )
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
        "attribute_aliases": candidate.get("attribute_aliases") or {},
        "created_at": candidate.get("created_at"),
        "request_fingerprint_sha256": request_fingerprint(scope, candidate),
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
            or not all(isinstance(item, str) and bool(item.strip()) for item in touched_attributes)
    ):
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "PATCH_TOUCHED_ATTRIBUTES_MISSING",
            "A PATCH candidate must list the attributes it touches.",
            "VALIDATION_PREVIEW",
        ))
    elif touched_attributes is not None and (
            not isinstance(touched_attributes, list)
            or not all(isinstance(item, str) and bool(item.strip()) for item in touched_attributes)
    ):
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "TOUCHED_ATTRIBUTES_INVALID",
            "touched_attributes must contain only non-empty strings.",
            "VALIDATION_PREVIEW",
        ))

    required_preview = (
        "mode", "operation", "payload_sha256", "seller_id", "marketplace_id",
        "sku", "product_type", "request_id", "submission_id", "requested_at",
        "responded_at", "expires_at", "request_fingerprint_sha256", "http_status",
        "status", "issues",
    )
    if operation == "PUT":
        required_preview += ("requirements",)
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

    if operation == "PUT" and is_provided(preview.get("requirements")):
        if str(preview.get("requirements")) != str(candidate.get("requirements")) \
                or str(preview.get("requirements")) != str(scope.get("requirements")):
            binding_valid = False
            rows.append(finding(
                SYSTEM_ERROR,
                "PREVIEW_REQUIREMENTS_MISMATCH",
                "PUT preview requirements do not match the candidate and diagnostic scope.",
                "VALIDATION_PREVIEW",
                evidence={
                    "scope": scope.get("requirements"),
                    "candidate": candidate.get("requirements"),
                    "preview": preview.get("requirements"),
                },
            ))

    expected_fingerprint = request_fingerprint(scope, candidate)
    preview_fingerprint = preview.get("request_fingerprint_sha256")
    if is_provided(preview_fingerprint) and (
            not SHA256_PATTERN.fullmatch(str(preview_fingerprint))
            or str(preview_fingerprint).lower() != expected_fingerprint
    ):
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "PREVIEW_REQUEST_FINGERPRINT_MISMATCH",
            "Preview request fingerprint does not match the bound candidate request.",
            "VALIDATION_PREVIEW",
            evidence={"expected": expected_fingerprint, "actual": preview_fingerprint},
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

    candidate_created_at = parse_timestamp(candidate.get("created_at"))
    requested_at = parse_timestamp(preview.get("requested_at"))
    responded_at = parse_timestamp(preview.get("responded_at"))
    expires_at = parse_timestamp(preview.get("expires_at"))
    if None in {candidate_created_at, requested_at, responded_at, expires_at}:
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "PREVIEW_TIMESTAMP_INVALID",
            "Candidate and preview timestamps must be timezone-aware ISO-8601 values.",
            "VALIDATION_PREVIEW",
        ))
    elif not (candidate_created_at <= requested_at <= responded_at <= expires_at):
        binding_valid = False
        rows.append(finding(
            SYSTEM_ERROR,
            "PREVIEW_TIME_ORDER_INVALID",
            "Expected candidate.created_at <= requested_at <= responded_at <= expires_at.",
            "VALIDATION_PREVIEW",
        ))
    elif evaluation_time is None:
        binding_valid = False
        rows.append(finding(
            NOT_EVALUATED,
            "PREVIEW_FRESHNESS_NOT_EVALUATED",
            "data_as_of is required to determine whether the Preview is still current.",
            "VALIDATION_PREVIEW",
        ))
    elif evaluation_time > expires_at:
        binding_valid = False
        rows.append(finding(
            NOT_EVALUATED,
            "PREVIEW_STALE",
            "The bound preview expired before this diagnostic run.",
            "VALIDATION_PREVIEW",
            evidence={"expires_at": preview.get("expires_at")},
        ))
    if requested_at is not None and ptd_fetched_at is not None and requested_at < ptd_fetched_at:
        binding_valid = False
        rows.append(finding(
            NOT_EVALUATED,
            "PREVIEW_PREDATES_PTD",
            "The preview predates the PTD evidence used in this report and must be rerun.",
            "VALIDATION_PREVIEW",
            evidence={"preview_requested_at": preview.get("requested_at")},
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

    if not binding_valid:
        for row in rows:
            if row["source"] == "VALIDATION_PREVIEW" and row["status"] in {
                OFFICIAL_ERROR, OFFICIAL_WARNING
            }:
                row["applies_to_candidate"] = False

    preview_passed = preview_status == "VALID" and binding_valid and not any(
        row["status"] in {OFFICIAL_ERROR, SYSTEM_ERROR}
        and row.get("applies_to_candidate", True)
        for row in rows
    )
    return rows, preview_passed, normalized_candidate


def calculate_gate(rows: list[dict[str, Any]], sources: set[str], evaluated: bool,
                   pass_value: str = "PASS", applicability_field: str | None = None) -> str:
    relevant = [
        row for row in rows
        if row["source"] in sources
        and not (applicability_field and row.get(applicability_field) is False)
    ]
    if any(row["status"] == OFFICIAL_ERROR for row in relevant):
        return "BLOCK"
    if any(row["status"] == SYSTEM_ERROR for row in relevant):
        return "UNKNOWN"
    if any(row["status"] == OFFICIAL_WARNING for row in relevant):
        return "REVIEW"
    if any(row["status"] == NOT_EVALUATED for row in relevant):
        return "NOT_EVALUATED"
    return pass_value if evaluated else "NOT_EVALUATED"


def decide_release(current_gate: str, candidate_gate: str, candidate_local_gate: str,
                   candidate: dict[str, Any],
                   rows: list[dict[str, Any]],
                   listing_snapshot_evaluated: bool,
                   full_schema_validated: bool) -> tuple[str, list[str]]:
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

    if candidate_local_gate == "BLOCK":
        return "BLOCK", ["CANDIDATE_FULL_SCHEMA_VALIDATION_FAILED"]
    if candidate_local_gate == "UNKNOWN":
        return "UNKNOWN", ["CANDIDATE_LOCAL_VALIDATION_UNKNOWN"]
    if candidate_local_gate == "REVIEW":
        if current_gate == "BLOCK":
            return "BLOCK", ["CURRENT_BLOCKER_AND_CANDIDATE_LOCAL_REVIEW"]
        return "REVIEW", ["CANDIDATE_LOCAL_VALIDATION_REQUIRES_REVIEW"]
    operation = str(candidate.get("operation") or "").upper()
    if operation == "PATCH" and not listing_snapshot_evaluated:
        return "REVIEW", ["PATCH_REQUIRES_TRACEABLE_CURRENT_LISTING_SNAPSHOT"]
    if current_gate == "UNKNOWN":
        return "UNKNOWN", ["CURRENT_LISTING_EVIDENCE_UNKNOWN"]
    if current_gate == "BLOCK":
        if any(row["status"] == SYSTEM_ERROR and row["source"] in OFFICIAL_SOURCES for row in rows):
            return "BLOCK", ["CURRENT_BLOCKER_AND_OFFICIAL_VALIDATION_INCOMPLETE"]
        if operation == "PATCH":
            aliases = candidate.get("attribute_aliases") or {}
            touched = {
                canonical_attribute(value, aliases)
                for value in candidate.get("touched_attributes") or []
            }
            uncovered = {
                canonical_attribute(row.get("attribute") or "<unknown>", aliases)
                for row in rows
                if row["status"] == OFFICIAL_ERROR
                and row["source"] in {"LISTINGS_ITEMS", "PTD"}
                and canonical_attribute(row.get("attribute") or "<unknown>", aliases) not in touched
            }
            if uncovered:
                return "REVIEW", ["PATCH_DOES_NOT_COVER_CURRENT_BLOCKERS"]
        return "REVIEW", ["CURRENT_LISTING_HAS_HISTORICAL_BLOCKERS"]
    if current_gate == "REVIEW":
        return "REVIEW", ["CURRENT_LISTING_REQUIRES_REVIEW"]
    if operation == "PATCH" and current_gate == "NOT_EVALUATED":
        return "REVIEW", ["PATCH_DOES_NOT_ESTABLISH_FULL_LISTING_STATE"]
    if not full_schema_validated:
        return "REVIEW", ["FULL_PTD_SCHEMA_VALIDATION_REQUIRED"]
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
    legacy_content = data.get("content") or {}
    current_content = data.get("current_content") \
        if "current_content" in data else legacy_content
    candidate_input = data.get("candidate")
    candidate_content = candidate_input.get("content") \
        if isinstance(candidate_input, dict) and "content" in candidate_input else None
    official = data.get("official") or {}
    if not isinstance(scope, dict) or not isinstance(current_content, dict) \
            or not isinstance(official, dict):
        return finalize({}, {}, {}, [finding(
            SYSTEM_ERROR,
            "INPUT_SECTIONS_INVALID",
            "scope, current_content/content, and official must be JSON objects.",
            "INPUT",
        )], False, False)

    rows: list[dict[str, Any]] = []
    aliases, alias_rows = normalize_attribute_aliases(data.get("attribute_aliases"))
    rows.extend(alias_rows)
    if isinstance(candidate_input, dict):
        candidate_input = dict(candidate_input)
        candidate_input["attribute_aliases"] = aliases
    if candidate_content is not None and not isinstance(candidate_content, dict):
        invalid_content = finding(
            SYSTEM_ERROR,
            "CANDIDATE_CONTENT_INVALID",
            "candidate.content must be an object when supplied.",
            "INPUT",
        )
        invalid_content["applies_to_current"] = False
        invalid_content["applies_to_candidate"] = True
        rows.append(invalid_content)
        candidate_content = {}

    content_contract_mode = "LEGACY_SHARED_CONTENT"
    evaluation_content = current_content
    validation_target = "CURRENT"
    if isinstance(candidate_content, dict):
        content_contract_mode = "EXPLICIT_CURRENT_AND_CANDIDATE"
        evaluation_content = candidate_content
        validation_target = "CANDIDATE"

    ptd_input = official.get("ptd")
    if isinstance(ptd_input, dict) and is_provided(ptd_input.get("validation_target")):
        requested_target = str(ptd_input.get("validation_target")).upper()
        if requested_target not in {"CURRENT", "CANDIDATE"}:
            rows.append(finding(
                SYSTEM_ERROR,
                "PTD_VALIDATION_TARGET_INVALID",
                "PTD validation_target must be CURRENT or CANDIDATE.",
                "PTD",
                evidence=requested_target,
            ))
        elif requested_target == "CANDIDATE" and not isinstance(candidate_content, dict):
            missing_candidate = finding(
                NOT_EVALUATED,
                "CANDIDATE_CONTENT_MISSING",
                "Candidate PTD validation requires an explicit candidate.content object.",
                "PTD",
            )
            missing_candidate["applies_to_current"] = False
            missing_candidate["applies_to_candidate"] = True
            rows.append(missing_candidate)
            validation_target = "CANDIDATE"
            evaluation_content = {}
        else:
            validation_target = requested_target
            evaluation_content = candidate_content if requested_target == "CANDIDATE" \
                else current_content
    data_as_of = data.get("data_as_of")
    evaluation_time = parse_timestamp(data_as_of)
    if data_as_of is None:
        rows.append(finding(
            NOT_EVALUATED,
            "EVALUATION_TIME_MISSING",
            "data_as_of is required to evaluate evidence freshness.",
            "INPUT",
        ))
    elif evaluation_time is None:
        rows.append(finding(
            SYSTEM_ERROR,
            "EVALUATION_TIME_INVALID",
            "data_as_of must be a timezone-aware ISO-8601 timestamp.",
            "INPUT",
            evidence=data_as_of,
        ))
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
        key: "PROVIDED" if is_provided(evaluation_content.get(key)) else "MISSING"
        for key in ("title", "item_highlight", "bullets", "description", "backend_search_terms", "images")
    }
    if isinstance(evaluation_content.get("attributes"), dict):
        coverage["attributes"] = "PROVIDED"

    snapshot_rows, listing_snapshot_evaluated, listing_snapshot = evaluate_listing_snapshot(
        scope, official, evaluation_time
    )
    rows.extend(snapshot_rows)

    ptd_rows, ptd_evaluated, ptd_validation_coverage = evaluate_ptd(
        scope, evaluation_content, ptd_input, evaluation_time, aliases,
        validation_target, candidate_input if isinstance(candidate_input, dict) else {},
    )
    for row in ptd_rows:
        row.setdefault("applies_to_current", validation_target == "CURRENT")
        row.setdefault("applies_to_candidate", validation_target == "CANDIDATE")
    rows.extend(ptd_rows)

    ptd_fetched_at = parse_timestamp(ptd_input.get("fetched_at")) if isinstance(ptd_input, dict) else None
    preview_rows, preview_passed, candidate = evaluate_validation_preview(
        scope, candidate_input, official.get("validation_preview"),
        evaluation_time, ptd_fetched_at,
    )
    rows.extend(preview_rows)

    image_rows = evaluate_images(evaluation_content)
    for row in image_rows:
        row["content_target"] = validation_target
    rows.extend(image_rows)
    report = finalize(
        scope,
        coverage,
        candidate,
        rows,
        listing_snapshot_evaluated or (ptd_evaluated and validation_target == "CURRENT"),
        preview_passed,
        listing_snapshot_evaluated,
        ptd_evaluated and validation_target == "CURRENT",
        bool(ptd_validation_coverage.get("full_schema_validation")),
        ptd_evaluated and validation_target == "CANDIDATE",
    )
    report["data_as_of"] = data_as_of
    report["listing_snapshot"] = listing_snapshot
    report["ptd_validation_coverage"] = ptd_validation_coverage
    report["report_locale"] = str(data.get("report_locale") or "en")
    report["content_contract"] = {
        "mode": content_contract_mode,
        "evaluated_target": validation_target,
        "current_content_present": bool(current_content),
        "candidate_content_present": isinstance(candidate_content, dict),
        "attribute_alias_count": len(aliases),
    }
    preview = official.get("validation_preview")
    report["validation_preview"] = {
        key: preview.get(key)
        for key in (
            "ran", "mode", "operation", "payload_sha256", "seller_id", "marketplace_id",
            "sku", "product_type", "requirements", "request_fingerprint_sha256",
            "request_id", "submission_id", "requested_at", "responded_at", "expires_at",
            "http_status", "status",
        )
        if isinstance(preview, dict) and key in preview
    }
    return report


def finalize(scope: dict[str, Any], coverage: dict[str, Any], candidate: dict[str, Any],
             rows: list[dict[str, Any]], current_evaluated: bool,
             preview_passed: bool, listing_snapshot_evaluated: bool = False,
             ptd_evaluated: bool = False,
             full_schema_validated: bool = False,
             candidate_local_evaluated: bool = False) -> dict[str, Any]:
    counts = Counter(row["status"] for row in rows)
    current_gate = calculate_gate(
        rows,
        {"INPUT", "LISTINGS_ITEMS", "PTD"},
        current_evaluated,
        pass_value="NO_KNOWN_OFFICIAL_ISSUES",
        applicability_field="applies_to_current",
    )
    candidate_gate = calculate_gate(
        rows,
        {"INPUT", "VALIDATION_PREVIEW"},
        preview_passed,
        pass_value="PASS",
        applicability_field="applies_to_candidate",
    )
    candidate_local_gate = calculate_gate(
        rows,
        {"PTD"},
        candidate_local_evaluated or full_schema_validated,
        pass_value="PASS",
        applicability_field="applies_to_candidate",
    )
    release_decision, release_reasons = decide_release(
        current_gate, candidate_gate, candidate_local_gate, candidate, rows,
        listing_snapshot_evaluated,
        full_schema_validated,
    )
    official_incomplete = any(
        row["status"] in {NOT_EVALUATED, SYSTEM_ERROR} and row["source"] in OFFICIAL_SOURCES
        for row in rows
    ) or not full_schema_validated
    operation = str(candidate.get("operation") or "").upper() or None
    requirements = str(candidate.get("requirements") or "").upper() or None
    official_coverage = "FULL" if operation == "PUT" and requirements == "LISTING" \
        else "PARTIAL" if operation in {"PUT", "PATCH"} else "UNKNOWN"
    return {
        "scope": scope,
        "candidate": candidate,
        "current_listing_gate": current_gate,
        "candidate_preview_gate": candidate_gate,
        "candidate_local_validation_gate": candidate_local_gate,
        "release_decision": release_decision,
        "release_reasons": release_reasons,
        # Compatibility field retained for 1.0.x consumers.
        "gate": "PASS_OFFICIAL_CHECKS" if release_decision == "PASS" else release_decision,
        "official_scope": {
            "operation": operation,
            "requirements": requirements,
            "coverage": official_coverage,
            "touched_attributes": candidate.get("touched_attributes") if operation == "PATCH" else None,
        },
        "official_validation_completeness": "INCOMPLETE" if official_incomplete else "COMPLETE",
        "official_evidence_coverage": {
            "current_listing_snapshot": "COMPLETE" if listing_snapshot_evaluated else "INCOMPLETE",
            "candidate_preview": "COMPLETE" if preview_passed else "INCOMPLETE",
            "ptd_local_validation": "FULL_JSON_SCHEMA" if full_schema_validated
            else "EVALUATED_SUBSET" if ptd_evaluated else "INCOMPLETE",
        },
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


def exit_code(report: dict[str, Any]) -> int:
    has_official_error = bool(report["counts"][OFFICIAL_ERROR])
    has_system_error = bool(report["counts"][SYSTEM_ERROR])
    if has_official_error and has_system_error:
        return 3
    if has_official_error:
        return 1
    if has_system_error:
        return 2
    return 0


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
    return exit_code(report)


if __name__ == "__main__":
    sys.exit(main())
