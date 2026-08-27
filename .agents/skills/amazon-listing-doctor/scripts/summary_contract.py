#!/usr/bin/env python3
"""Shared priority rules for concise Listing summaries."""

from __future__ import annotations

from typing import Any


def primary_official_finding(official_report: dict[str, Any]) -> dict[str, Any] | None:
    release_decision = official_report.get("release_decision")
    status_order = {
        "BLOCK": ("OFFICIAL_ERROR", "SYSTEM_ERROR"),
        "UNKNOWN": ("SYSTEM_ERROR", "OFFICIAL_ERROR"),
        "REVIEW": ("OFFICIAL_WARNING", "SYSTEM_ERROR", "NOT_EVALUATED"),
        "NOT_EVALUATED": ("NOT_EVALUATED", "SYSTEM_ERROR"),
    }.get(release_decision, ())
    findings = []
    for row in official_report.get("findings", []):
        if not isinstance(row, dict):
            continue
        applicability = [
            row[key]
            for key in ("applies_to_current", "applies_to_candidate")
            if key in row
        ]
        if applicability and not any(value is True for value in applicability):
            continue
        findings.append(row)
    for status in status_order:
        finding = next((row for row in findings if row.get("status") == status), None)
        if finding:
            return {
                "source": "OFFICIAL_EVIDENCE",
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
