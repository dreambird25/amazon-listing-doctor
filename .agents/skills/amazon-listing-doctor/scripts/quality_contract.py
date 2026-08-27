#!/usr/bin/env python3
"""Deterministic hashes and evidence manifests for semantic quality binding."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SCOPE_FIELDS = (
    "seller_id",
    "marketplace_id",
    "sku",
    "product_type",
    "requirements",
    "parentage_level",
    "locale",
)
MERGE_ONLY_FIELDS = {
    "official_report_sha256",
    "merge_status",
    "quality_verdict",
    "quality_dimensions",
    "quality_evidence_completeness",
    "semantic_assessment",
    "quality_assessment_trace",
    "performance_verdict",
    "executive_summary",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_PATTERN.fullmatch(value))


def scope_fingerprint(scope: dict[str, Any]) -> str:
    return sha256_json({field: scope.get(field) for field in SCOPE_FIELDS})


def path_for_key(base: str, key: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        return f"{base}.{key}"
    return f"{base}[{json.dumps(key, ensure_ascii=False)}]"


def manifest_entries(value: Any, base_path: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []

    def visit(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key in sorted(node):
                visit(node[key], path_for_key(path, str(key)))
        elif isinstance(node, list):
            for index, item in enumerate(node):
                visit(item, f"{path}[{index}]")
        else:
            entries.append({
                "field_path": path,
                "value_sha256": sha256_json(node),
                "value_type": (
                    "null" if node is None else "boolean" if isinstance(node, bool)
                    else "number" if isinstance(node, (int, float)) else "string"
                ),
            })

    visit(value, base_path)
    return entries


def build_quality_context(
        target: str, scope: dict[str, Any], content: dict[str, Any],
) -> dict[str, Any]:
    root = "$.candidate.content" if target == "CANDIDATE" else "$.current_content"
    entries = manifest_entries(content, root)
    return {
        "context_version": "1.0",
        "assessment_target": target,
        "scope_fingerprint_sha256": scope_fingerprint(scope),
        "content_sha256": sha256_json(content),
        "evidence_manifest_sha256": sha256_json(entries),
        "evidence_manifest": entries,
    }


def official_report_material(report: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in report.items() if key not in MERGE_ONLY_FIELDS}


def official_report_sha256(report: dict[str, Any]) -> str:
    return sha256_json(official_report_material(report))
