#!/usr/bin/env python3
"""Shared priority rules for concise Listing summaries."""

from __future__ import annotations

from typing import Any


OFFICIAL_SUMMARY_SOURCES = {"INPUT", "LISTINGS_ITEMS", "PTD", "VALIDATION_PREVIEW"}
CURRENT_BLOCKER_REASONS = {
    "CURRENT_BLOCKER_AND_CANDIDATE_UNKNOWN",
    "CURRENT_BLOCKER_WITHOUT_VALID_CANDIDATE_PREVIEW",
    "CURRENT_BLOCKER_AND_CANDIDATE_REQUIRES_REVIEW",
    "CURRENT_BLOCKER_AND_CANDIDATE_LOCAL_REVIEW",
    "CURRENT_BLOCKER_AND_OFFICIAL_VALIDATION_INCOMPLETE",
    "PATCH_DOES_NOT_COVER_CURRENT_BLOCKERS",
    "CURRENT_LISTING_HAS_HISTORICAL_BLOCKERS",
    "PATCH_REQUIRES_TRACEABLE_CURRENT_LISTING_SNAPSHOT",
    "CURRENT_LISTING_EVIDENCE_UNKNOWN",
    "CURRENT_LISTING_REQUIRES_REVIEW",
    "PATCH_DOES_NOT_ESTABLISH_FULL_LISTING_STATE",
}
PREVIEW_REASONS = {
    "CANDIDATE_PREVIEW_BLOCKED",
    "CANDIDATE_PREVIEW_UNKNOWN",
    "CANDIDATE_PREVIEW_NOT_EVALUATED",
    "CANDIDATE_PREVIEW_REQUIRES_REVIEW",
}
LOCAL_VALIDATION_REASONS = {
    "CANDIDATE_FULL_SCHEMA_VALIDATION_FAILED",
    "CANDIDATE_LOCAL_VALIDATION_UNKNOWN",
    "CANDIDATE_LOCAL_VALIDATION_REQUIRES_REVIEW",
    "FULL_PTD_SCHEMA_VALIDATION_REQUIRED",
}


def primary_official_finding(official_report: dict[str, Any]) -> dict[str, Any] | None:
    release_decision = official_report.get("release_decision")
    status_order = {
        "BLOCK": ("OFFICIAL_ERROR", "SYSTEM_ERROR", "OFFICIAL_WARNING", "NOT_EVALUATED"),
        "UNKNOWN": ("SYSTEM_ERROR", "OFFICIAL_ERROR", "NOT_EVALUATED", "OFFICIAL_WARNING"),
        "REVIEW": ("OFFICIAL_ERROR", "OFFICIAL_WARNING", "SYSTEM_ERROR", "NOT_EVALUATED"),
        "NOT_EVALUATED": ("NOT_EVALUATED", "SYSTEM_ERROR", "OFFICIAL_ERROR", "OFFICIAL_WARNING"),
    }.get(release_decision, ())
    findings = []
    for row in official_report.get("findings", []):
        if not isinstance(row, dict) or row.get("source") not in OFFICIAL_SUMMARY_SOURCES:
            continue
        applicability = [
            row[key]
            for key in ("applies_to_current", "applies_to_candidate")
            if key in row
        ]
        if applicability and not any(value is True for value in applicability):
            continue
        findings.append(row)

    reasons = set(official_report.get("release_reasons") or [])
    if reasons & CURRENT_BLOCKER_REASONS:
        preferred = [row for row in findings if row.get("applies_to_current") is True]
    elif reasons & PREVIEW_REASONS:
        preferred = [row for row in findings if row.get("source") == "VALIDATION_PREVIEW"]
    elif reasons & LOCAL_VALIDATION_REASONS:
        preferred = [
            row for row in findings
            if row.get("source") == "PTD" and row.get("applies_to_candidate") is True
        ]
    else:
        preferred = findings

    search_groups = [preferred]
    if preferred is not findings:
        search_groups.append(findings)
    for group in search_groups:
        for status in status_order:
            finding = next((row for row in group if row.get("status") == status), None)
            if finding:
                return {
                    "source": "OFFICIAL_EVIDENCE",
                    "finding_source": finding.get("source"),
                    "status": status,
                    "code": finding.get("code"),
                    "attribute": finding.get("attribute"),
                    "text": finding.get("message") or finding.get("code") or status,
                }
    return None


def official_action(reason: dict[str, Any] | None) -> dict[str, Any] | None:
    if not reason:
        return None
    blocker = reason.get("status") == "OFFICIAL_ERROR"
    return {
        "source": "OFFICIAL_EVIDENCE",
        "priority": "HIGH" if blocker else "MEDIUM",
        "action_code": (
            "FIX_OFFICIAL_BLOCKER_AND_REVALIDATE"
            if blocker else "REVIEW_OFFICIAL_EVIDENCE"
        ),
        "completion_code": (
            "OFFICIAL_BLOCKER_CLEARED"
            if blocker else "OFFICIAL_EVIDENCE_COMPLETED"
        ),
        "finding_code": reason.get("code"),
        "rewrite_is_advisory": False,
    }
