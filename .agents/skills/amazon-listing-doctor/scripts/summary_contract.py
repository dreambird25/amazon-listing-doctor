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


def derive_evidence_stages(official_report: dict[str, Any]) -> dict[str, str]:
    """Describe evidence acquisition stages without changing canonical gates."""
    coverage = official_report.get("official_evidence_coverage")
    coverage = coverage if isinstance(coverage, dict) else {}

    snapshot_coverage = coverage.get("current_listing_snapshot")
    if snapshot_coverage == "COMPLETE":
        current_snapshot = "COMPLETE"
    elif snapshot_coverage == "INCOMPLETE":
        current_snapshot = "INCOMPLETE"
    else:
        current_snapshot = "UNKNOWN"

    current_findings = [
        row for row in official_report.get("findings", [])
        if isinstance(row, dict)
        and row.get("source") == "LISTINGS_ITEMS"
        and row.get("applies_to_current") is not False
    ]
    if any(row.get("status") == "OFFICIAL_ERROR" for row in current_findings):
        current_issues = "BLOCKERS_PRESENT"
    elif any(row.get("status") == "OFFICIAL_WARNING" for row in current_findings):
        current_issues = "REVIEW_PRESENT"
    elif any(row.get("status") == "SYSTEM_ERROR" for row in current_findings):
        current_issues = "EVIDENCE_ERROR"
    elif current_snapshot == "COMPLETE":
        current_issues = "NO_KNOWN_ISSUES"
    else:
        current_issues = "NOT_CONFIRMED"

    ptd_coverage = coverage.get("ptd_local_validation")
    if ptd_coverage == "FULL_JSON_SCHEMA":
        ptd_validation = "FULL_JSON_SCHEMA"
    elif ptd_coverage == "EVALUATED_SUBSET":
        ptd_validation = "EVALUATED_SUBSET"
    elif ptd_coverage == "INCOMPLETE":
        ptd_validation = "NOT_COMPLETED"
    else:
        ptd_validation = "UNKNOWN"

    contract = official_report.get("content_contract")
    candidate_present = contract.get("candidate_content_present") \
        if isinstance(contract, dict) else None
    if candidate_present is True:
        candidate_content = "PROVIDED"
    elif candidate_present is False:
        candidate_content = "NOT_PROVIDED"
    else:
        candidate_content = "UNKNOWN"

    def candidate_stage(gate: Any) -> str:
        if gate in {"PASS", "BLOCK", "REVIEW", "UNKNOWN"}:
            return str(gate)
        if gate == "NOT_EVALUATED":
            if candidate_content == "NOT_PROVIDED":
                return "NOT_APPLICABLE_NO_CANDIDATE_CONTENT"
            return "NOT_COMPLETED"
        return "UNKNOWN"

    preview_stage = candidate_stage(official_report.get("candidate_preview_gate"))
    if official_report.get("candidate_preview_gate") == "NOT_EVALUATED":
        preview_codes = {
            str(row.get("code") or "")
            for row in official_report.get("findings", [])
            if isinstance(row, dict) and row.get("source") == "VALIDATION_PREVIEW"
        }
        if preview_codes - {"VALIDATION_PREVIEW_NOT_RUN"}:
            preview_stage = "PROVIDED_NOT_USABLE"

    return {
        "current_snapshot": current_snapshot,
        "current_issues": current_issues,
        "ptd_local_validation": ptd_validation,
        "candidate_content": candidate_content,
        "candidate_local_validation": candidate_stage(
            official_report.get("candidate_local_validation_gate")
        ),
        "candidate_preview": preview_stage,
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


def official_action(
    reason: dict[str, Any] | None,
    official_report: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not reason:
        return None
    blocker = reason.get("status") == "OFFICIAL_ERROR"
    historical_issue_after_preview_pass = bool(
        blocker
        and isinstance(official_report, dict)
        and official_report.get("candidate_preview_gate") == "PASS"
        and "CURRENT_LISTING_HAS_HISTORICAL_BLOCKERS"
        in set(official_report.get("release_reasons") or [])
    )
    return {
        "source": "OFFICIAL_EVIDENCE",
        "priority": "HIGH" if blocker else "MEDIUM",
        "action_code": (
            "RECHECK_CURRENT_ISSUE_AFTER_PREVIEW_PASS"
            if historical_issue_after_preview_pass
            else "FIX_OFFICIAL_BLOCKER_AND_REVALIDATE"
            if blocker
            else "REVIEW_OFFICIAL_EVIDENCE"
        ),
        "completion_code": (
            "CURRENT_ISSUE_ABSENT_AFTER_RECHECK"
            if historical_issue_after_preview_pass
            else "OFFICIAL_BLOCKER_CLEARED"
            if blocker
            else "OFFICIAL_EVIDENCE_COMPLETED"
        ),
        "finding_code": reason.get("code"),
        "rewrite_is_advisory": False,
    }
