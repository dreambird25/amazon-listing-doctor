#!/usr/bin/env python3
"""Validate and merge semantic Listing quality assessment with an official report."""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parent))
from quality_contract import (
    comparison_cohort_sha256,
    official_report_sha256,
    scope_fingerprint,
    sha256_json,
    valid_sha256,
)
from quality_policy import EVIDENCE_POLICY_VERSION, evaluate_evidence_policy
from summary_contract import official_action, primary_official_finding


DIMENSIONS = (
    "content_completeness",
    "clarity_and_readability",
    "intent_coverage",
    "buyer_question_coverage",
    "image_information_coverage",
    "cross_field_consistency",
    "localization_quality",
)
RATINGS = {"STRONG", "ADEQUATE", "WEAK", "NOT_EVALUATED"}
EVIDENCE_BASES = {"OBSERVED_CONTENT", "OBSERVED_ABSENCE", "EVIDENCE_GAP"}
PRIORITIES = {"HIGH", "MEDIUM", "LOW"}
PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
RECOMMENDATION_TYPES = {"IMPROVEMENT", "EVIDENCE_REQUEST"}
PRIORITIES_BY_RATING = {
    "WEAK": {"HIGH", "MEDIUM"},
    "ADEQUATE": {"MEDIUM", "LOW"},
    "STRONG": {"LOW"},
    "NOT_EVALUATED": PRIORITIES,
}
ALLOWED_LITERAL_CHARACTERS = frozenset(" ,-–—/:()")
ENCODING_CLAIM_MARKERS = (
    "replacement character",
    "encoding artifact",
    "encoding issue",
    "mojibake",
    "unicode replacement",
    "u+fffd",
    "control character",
    "non-printable character",
    "异常替换字符",
    "替换字符",
    "编码痕迹",
    "编码异常",
    "乱码",
    "控制字符",
    "不可见字符",
)
SUSPICIOUS_TEXT_MARKERS = (
    "\ufffd",
    "ï¿½",
    "Ã©",
    "Ã¨",
    "Ãª",
    "Ã«",
    "Ã¤",
    "Ã¶",
    "Ã¼",
    "ÃŸ",
    "Ã±",
    "Ã¡",
    "Ã£",
    "Ã³",
    "Ãº",
    "Â©",
    "Â®",
    "Â°",
    "â€",
    "â€™",
    "â€œ",
    "ðŸ",
)
NATIVE_REVIEWER_MARKERS = (
    "native reviewer",
    "native-language reviewer",
    "mother tongue reviewer",
    "native speaker review",
    "母语级审校",
    "母语审校",
    "母语审核",
    "muttersprach",
)
TECHNICAL_ARTIFACT_CLAIM_MARKERS = (
    "traceback",
    "debug stack",
    "stack trace",
    "exception trace",
    "exception stack",
    "debug log",
    "log residue",
    "debug residue",
    "调试堆栈",
    "异常堆栈",
    "异常跟踪",
    "异常追踪",
    "堆栈残留",
    "日志残留",
    "调试信息",
    "调试文本",
)
MISSING_CONTENT_CLAIM_MARKERS = (
    "missing bullet",
    "missing bullets",
    "missing description",
    "missing content",
    "lacks bullet",
    "lacks description",
    "only a title",
    "only the title",
    "content was not provided",
    "bullets were not provided",
    "description was not provided",
    "缺少亮点",
    "缺少要点",
    "缺少描述",
    "缺少搜索词",
    "缺少产品属性",
    "只有一个标题",
    "只有标题",
    "未提供要点",
    "未提供描述",
    "未返回要点",
    "未返回描述",
)
QUALITY_ACTION_CODES = {
    "content_completeness": "COMPLETE_MISSING_CONTENT_EVIDENCE",
    "clarity_and_readability": "IMPROVE_CLARITY_WITH_BOUND_FACTS",
    "intent_coverage": "COVER_VERIFIED_USE_INTENT",
    "buyer_question_coverage": "ANSWER_BUYER_QUESTIONS_WITH_EVIDENCE",
    "image_information_coverage": "ADD_MISSING_IMAGE_INFORMATION",
    "cross_field_consistency": "RESOLVE_CROSS_FIELD_INCONSISTENCY",
    "localization_quality": "REVIEW_LOCALIZATION_FOR_SCOPE",
}
QUALITY_COMPLETION_CODE = "REASSESS_QUALITY_DIMENSION_WITH_BOUND_EVIDENCE"
RATING_POINTS = {"STRONG": 10.0, "ADEQUATE": 7.0, "WEAK": 3.0}
MIN_SCORED_DIMENSIONS = 5
SCORE_RUBRIC_VERSION = "1.1"
OFFICIAL_REPORT_FIELDS = {
    "current_listing_gate",
    "candidate_preview_gate",
    "candidate_local_validation_gate",
    "release_decision",
    "official_validation_completeness",
    "official_evidence_coverage",
    "ptd_validation_coverage",
    "counts",
    "findings",
    "quality_contexts",
    "scope",
    "release_reasons",
    "official_report_sha256",
    "data_as_of",
}


def nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def timezone_aware_timestamp(value: Any) -> bool:
    if not nonempty_text(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def parse_timestamp(value: Any) -> datetime | None:
    if not nonempty_text(value):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def scalar_value(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, bool)) \
        or isinstance(value, float) and math.isfinite(value)


def marker_is_negated(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 80):start]
    clause = re.split(
        r"[.!?;,，。！？；\n]|\b(?:but|however|yet)\b|(?:但是|但|然而|不过)",
        prefix,
        flags=re.IGNORECASE,
    )[-1]
    suffix = text[end:end + 50]
    affirmative_double_negative = re.search(
        r"\bnot\s+free\s+of\b[^.!?;,\n]{0,32}$",
        clause,
    ) or re.search(
        r"(?:并非|不是)没有[^，。！？；\n]{0,20}$",
        clause,
    )
    if affirmative_double_negative:
        return False
    english_before = re.search(
        r"(?:\b(?:no|not(?!\s+only)|without|none|never|neither|nor)\b"
        r"|\bfree\s+of\b)[^.!?;\n]{0,48}$",
        clause,
    )
    chinese_before = re.search(
        r"(?:未发现|未见|没有|不存在|不含|无)[^。！？；\n]{0,24}$",
        clause,
    )
    english_after = re.match(
        r"^[^.!?;\n]{0,28}\b(?:is|are|was|were|does|do)?\s*"
        r"(?:not present|absent|not found|not detected)\b",
        suffix,
    )
    chinese_after = re.match(
        r"^[^。！？；\n]{0,20}(?:不存在|未发现|未出现|没有|不含)",
        suffix,
    )
    return bool(english_before or chinese_before or english_after or chinese_after)


def text_asserts_marked_defect(value: Any, markers: tuple[str, ...]) -> bool:
    if not nonempty_text(value):
        return False
    lowered = value.casefold()
    for marker in markers:
        normalized = marker.casefold()
        start = lowered.find(normalized)
        while start >= 0:
            end = start + len(normalized)
            if not marker_is_negated(lowered, start, end):
                return True
            start = lowered.find(normalized, end)
    return False


def text_claims_missing_content(value: Any) -> bool:
    return text_asserts_marked_defect(value, MISSING_CONTENT_CLAIM_MARKERS)


def text_claims_encoding_defect(value: Any) -> bool:
    return text_asserts_marked_defect(value, ENCODING_CLAIM_MARKERS)


def suspicious_bound_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if any(marker in value for marker in SUSPICIOUS_TEXT_MARKERS):
        return True
    return any(ord(char) < 32 and char not in "\n\r" for char in value)


def text_claims_technical_artifact(value: Any) -> bool:
    return text_asserts_marked_defect(value, TECHNICAL_ARTIFACT_CLAIM_MARKERS)


def suspicious_technical_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    patterns = (
        r"traceback\s*\(most recent call last\)",
        r"exception in thread",
        r"(?:^|\n)\s*at\s+[\w.$]+\([^\n)]*:\d+\)",
        r"\b(?:java\.lang|org\.springframework)\.",
        r"\[(?:debug|error|warn|trace)\]",
    )
    return any(re.search(pattern, value, re.IGNORECASE) for pattern in patterns)


def missing_evidence_requests_native_reviewer(values: Any) -> bool:
    if not isinstance(values, list):
        return False
    text = " ".join(item for item in values if isinstance(item, str)).casefold()
    return any(marker.casefold() in text for marker in NATIVE_REVIEWER_MARKERS) \
        or bool(re.search(r"\bnative\b.{0,40}\breviewer\b", text))


def render_bound_value(value: Any) -> str | None:
    if value is None or not scalar_value(value):
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def safe_template_literal(value: Any) -> bool:
    if not isinstance(value, str) or not value \
            or not all(char in ALLOWED_LITERAL_CHARACTERS for char in value):
        return False
    compact = value.replace(" ", "")
    return not (len(compact) >= 3 and set(compact) == {"-"})


def render_suggested_template(recommendation: dict[str, Any]) -> str | None:
    bindings = recommendation.get("fact_bindings")
    template = recommendation.get("suggested_template")
    if not isinstance(bindings, list) or not isinstance(template, list):
        return None
    binding_ids = [
        item.get("binding_id") for item in bindings
        if isinstance(item, dict) and nonempty_text(item.get("binding_id"))
    ]
    if len(binding_ids) != len(bindings) or len(binding_ids) != len(set(binding_ids)):
        return None
    rendered_by_id = {
        item["binding_id"]: render_bound_value(item.get("source_value"))
        for item in bindings
    }
    parts: list[str] = []
    referenced_ids: set[str] = set()
    for segment in template:
        if not isinstance(segment, dict):
            return None
        segment_type = segment.get("type")
        if segment_type == "BOUND_FACT":
            binding_id = segment.get("binding_id")
            if binding_id not in rendered_by_id or binding_id in referenced_ids:
                return None
            value = rendered_by_id[binding_id]
            if not nonempty_text(value):
                return None
            referenced_ids.add(binding_id)
            parts.append(value)
        elif segment_type == "LITERAL" and safe_template_literal(segment.get("value")):
            parts.append(segment["value"])
        else:
            return None
    if referenced_ids != set(binding_ids):
        return None
    result = "".join(parts)
    return result if result.strip() else None


def validate_assessment(
        assessment: Any, official_report: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(assessment, dict):
        return ["semantic assessment must be a JSON object"]
    if assessment.get("assessment_version") != "1.4":
        errors.append("assessment_version must be 1.4")
    for field in ("assessment_model", "prompt_version"):
        if not nonempty_text(assessment.get(field)):
            errors.append(f"{field} is required")
    if not timezone_aware_timestamp(assessment.get("assessed_at")):
        errors.append("assessed_at must be a timezone-aware ISO-8601 timestamp")
    if not nonempty_text(assessment.get("assessment_locale")):
        errors.append("assessment_locale is required")

    target = str(assessment.get("assessment_target") or "").upper()
    if target not in {"CURRENT", "CANDIDATE"}:
        errors.append("assessment_target must be CURRENT or CANDIDATE")
    for field in (
        "scope_fingerprint_sha256",
        "content_sha256",
        "official_report_sha256",
        "evidence_manifest_sha256",
    ):
        if not valid_sha256(assessment.get(field)):
            errors.append(f"{field} must be a lowercase SHA-256 digest")

    manifest_by_path: dict[str, str] = {}
    if isinstance(official_report, dict) and target in {"CURRENT", "CANDIDATE"}:
        computed_report_hash = official_report_sha256(official_report)
        declared_report_hash = official_report.get("official_report_sha256")
        if declared_report_hash is not None and declared_report_hash != computed_report_hash:
            errors.append("official_report_sha256 field does not match the supplied official report")
        contexts = official_report.get("quality_contexts")
        context = contexts.get(target) if isinstance(contexts, dict) else None
        if not isinstance(context, dict):
            errors.append(f"quality context for {target} is missing from the official report")
        else:
            scope = official_report.get("scope")
            scope = scope if isinstance(scope, dict) else {}
            if context.get("context_version") != "1.1" \
                    or context.get("assessment_target") != target:
                errors.append(f"quality context for {target} has invalid metadata")
            if context.get("scope_fingerprint_sha256") != scope_fingerprint(scope):
                errors.append(f"quality context for {target} does not match report scope")
            for field in (
                "scope_fingerprint_sha256", "content_sha256", "evidence_manifest_sha256",
            ):
                if assessment.get(field) != context.get(field):
                    errors.append(f"{field} does not match the official report quality context")
            manifest = context.get("evidence_manifest")
            if not isinstance(manifest, list):
                errors.append("official report evidence_manifest must be an array")
            else:
                manifest_paths = [
                    item.get("field_path") for item in manifest if isinstance(item, dict)
                ]
                valid_manifest = all(
                    isinstance(item, dict)
                    and nonempty_text(item.get("field_path"))
                    and valid_sha256(item.get("value_sha256"))
                    and item.get("value_type") in {"null", "boolean", "number", "string"}
                    for item in manifest
                ) and len(manifest_paths) == len(set(manifest_paths))
                if not valid_manifest or context.get("evidence_manifest_sha256") != sha256_json(manifest):
                    errors.append("official report evidence_manifest integrity check failed")
                manifest_by_path = {
                    str(item.get("field_path")): str(item.get("value_sha256"))
                    for item in manifest if isinstance(item, dict)
                    and nonempty_text(item.get("field_path"))
                    and valid_sha256(item.get("value_sha256"))
                }
        if assessment.get("official_report_sha256") != computed_report_hash:
            errors.append("official_report_sha256 does not match the supplied official report")
        scope = official_report.get("scope")
        scope = scope if isinstance(scope, dict) else {}
        if not timezone_aware_timestamp(official_report.get("data_as_of")):
            errors.append("official report data_as_of must be a timezone-aware ISO-8601 timestamp")
        if assessment.get("assessment_locale") != scope.get("locale"):
            errors.append("assessment_locale does not match the official report scope locale")
        assessed_at = parse_timestamp(assessment.get("assessed_at"))
        data_as_of = parse_timestamp(official_report.get("data_as_of"))
        if assessed_at and data_as_of and assessed_at < data_as_of:
            errors.append("assessed_at must not predate official report data_as_of")

    dimensions = assessment.get("dimensions")
    if not isinstance(dimensions, dict):
        return errors + ["dimensions must be a JSON object"]
    missing = [name for name in DIMENSIONS if name not in dimensions]
    unknown = sorted(str(name) for name in dimensions if name not in DIMENSIONS)
    if missing:
        errors.append(f"missing dimensions: {', '.join(missing)}")
    if unknown:
        errors.append(f"unknown dimensions: {', '.join(unknown)}")

    for name in DIMENSIONS:
        row = dimensions.get(name)
        if not isinstance(row, dict):
            if name in dimensions:
                errors.append(f"{name} must be a JSON object")
            continue
        rating = row.get("rating")
        if rating not in RATINGS:
            errors.append(f"{name}.rating must be one of {', '.join(sorted(RATINGS))}")
            continue
        evidence_basis = row.get("evidence_basis")
        if evidence_basis not in EVIDENCE_BASES:
            errors.append(
                f"{name}.evidence_basis must be one of {', '.join(sorted(EVIDENCE_BASES))}"
            )
        evidence = row.get("evidence")
        missing_evidence = row.get("missing_evidence")
        if not isinstance(evidence, list):
            errors.append(f"{name}.evidence must be an array")
            evidence = []
        if not isinstance(missing_evidence, list):
            errors.append(f"{name}.missing_evidence must be an array")
            missing_evidence = []
        valid_evidence = all(
            isinstance(item, dict)
            and nonempty_text(item.get("field_path"))
            and scalar_value(item.get("quote_or_value"))
            and valid_sha256(item.get("value_sha256"))
            and item.get("value_sha256") == sha256_json(item.get("quote_or_value"))
            and (
                not manifest_by_path
                or manifest_by_path.get(item.get("field_path")) == item.get("value_sha256")
            )
            for item in evidence
        )
        if evidence and not valid_evidence:
            errors.append(
                f"{name} evidence must be manifest-bound with field_path, "
                "quote_or_value, and value_sha256"
            )
        if rating == "NOT_EVALUATED":
            if evidence_basis != "EVIDENCE_GAP":
                errors.append(f"{name}.evidence_basis must be EVIDENCE_GAP when NOT_EVALUATED")
            if evidence:
                errors.append(f"{name}.evidence must be empty when NOT_EVALUATED")
            if not any(nonempty_text(item) for item in missing_evidence):
                errors.append(f"{name} requires missing_evidence when NOT_EVALUATED")
            if name == "localization_quality" \
                    and missing_evidence_requests_native_reviewer(missing_evidence):
                errors.append(
                    "localization_quality native reviewer absence is not missing Listing evidence"
                )
        else:
            if evidence_basis not in {"OBSERVED_CONTENT", "OBSERVED_ABSENCE"}:
                errors.append(
                    f"{name}.evidence_basis must be observed evidence when evaluated"
                )
            if not nonempty_text(row.get("rationale")):
                errors.append(f"{name}.rationale is required for an evaluated rating")
            if not evidence or not valid_evidence:
                errors.append(
                    f"{name} requires manifest-bound evidence with field_path, "
                    "quote_or_value, and value_sha256"
                )
            if rating == "STRONG" and missing_evidence:
                errors.append(f"{name}.missing_evidence must be empty when STRONG")
            if text_claims_missing_content(row.get("rationale")) \
                    and evidence_basis != "OBSERVED_ABSENCE":
                errors.append(
                    f"{name} missing-content claim requires OBSERVED_ABSENCE evidence"
                )
            if name == "clarity_and_readability" \
                    and text_claims_encoding_defect(row.get("rationale")) \
                    and not any(
                        suspicious_bound_text(item.get("quote_or_value"))
                        for item in evidence if isinstance(item, dict)
                    ):
                errors.append(
                    "clarity_and_readability encoding defect claim requires suspicious bound text"
                )
            if name == "clarity_and_readability" \
                    and text_claims_technical_artifact(row.get("rationale")) \
                    and not any(
                        suspicious_technical_text(item.get("quote_or_value"))
                        for item in evidence if isinstance(item, dict)
                    ):
                errors.append(
                    "clarity_and_readability technical artifact claim requires suspicious bound text"
                )

    assessed_evidence = {
        (item["field_path"].strip(), item["value_sha256"].lower())
        for name in DIMENSIONS
        for item in (
            dimensions.get(name, {}).get("evidence", [])
            if isinstance(dimensions.get(name), dict) else []
        )
        if dimensions.get(name, {}).get("rating") != "NOT_EVALUATED"
        if isinstance(item, dict)
        and nonempty_text(item.get("field_path"))
        and valid_sha256(item.get("value_sha256"))
    }

    recommendations = assessment.get("recommendations", [])
    if not isinstance(recommendations, list):
        errors.append("recommendations must be an array")
    else:
        for index, recommendation in enumerate(recommendations):
            prefix = f"recommendations[{index}]"
            if not isinstance(recommendation, dict):
                errors.append(f"{prefix} must be a JSON object")
                continue
            priority = recommendation.get("priority")
            if priority not in PRIORITIES:
                errors.append(f"{prefix}.priority must be HIGH, MEDIUM, or LOW")
            dimension = recommendation.get("dimension")
            if dimension not in DIMENSIONS:
                errors.append(f"{prefix}.dimension is invalid")
                dimension_row = None
            else:
                dimension_row = dimensions.get(dimension)
                rating = dimension_row.get("rating") if isinstance(dimension_row, dict) else None
                if priority in PRIORITIES and rating in PRIORITIES_BY_RATING \
                        and priority not in PRIORITIES_BY_RATING[rating]:
                    allowed = ", ".join(sorted(PRIORITIES_BY_RATING[rating]))
                    errors.append(
                        f"{prefix}.priority {priority} is invalid for {rating}; allowed: {allowed}"
                    )
            recommendation_type = recommendation.get("recommendation_type")
            if recommendation_type is not None and recommendation_type not in RECOMMENDATION_TYPES:
                errors.append(
                    f"{prefix}.recommendation_type must be IMPROVEMENT or EVIDENCE_REQUEST"
                )
            if isinstance(dimension_row, dict) \
                    and dimension_row.get("rating") == "NOT_EVALUATED" \
                    and recommendation_type != "EVIDENCE_REQUEST":
                errors.append(
                    f"{prefix} targeting NOT_EVALUATED must be an EVIDENCE_REQUEST"
                )
            for field in ("action", "completion_criterion"):
                if not nonempty_text(recommendation.get(field)):
                    errors.append(f"{prefix}.{field} is required")
            for field in ("attribute", "current_problem", "suggested_value"):
                if field in recommendation and not nonempty_text(recommendation.get(field)):
                    errors.append(f"{prefix}.{field} must be a non-empty string when supplied")
            has_exact_suggestion = "suggested_template" in recommendation \
                or "fact_bindings" in recommendation or "suggested_value" in recommendation
            if has_exact_suggestion:
                if isinstance(dimension_row, dict) and dimension_row.get("rating") == "NOT_EVALUATED":
                    errors.append(f"{prefix}.suggested_template cannot target a NOT_EVALUATED dimension")
                if not nonempty_text(recommendation.get("attribute")):
                    errors.append(f"{prefix}.attribute is required with suggested_template")
                if not nonempty_text(recommendation.get("current_problem")):
                    errors.append(f"{prefix}.current_problem is required with suggested_template")
                fact_bindings = recommendation.get("fact_bindings")
                valid_fact_bindings = isinstance(fact_bindings, list) and bool(fact_bindings)
                binding_ids: list[str] = []
                fact_keys: list[tuple[str, str]] = []
                if valid_fact_bindings:
                    valid_fact_bindings = all(
                        isinstance(item, dict)
                        and nonempty_text(item.get("binding_id"))
                        and nonempty_text(item.get("source_path"))
                        and scalar_value(item.get("source_value"))
                        and item.get("source_value") is not None
                        and valid_sha256(item.get("source_value_sha256"))
                        and item.get("source_value_sha256") == sha256_json(item.get("source_value"))
                        and (
                            item["source_path"].strip(), item["source_value_sha256"].lower()
                        ) in assessed_evidence
                        and "rendered_fact" not in item
                        for item in fact_bindings
                    )
                    binding_ids = [
                        item.get("binding_id") for item in fact_bindings if isinstance(item, dict)
                    ]
                    fact_keys = [
                        (item.get("source_path", "").strip(), item.get("source_value_sha256", "").lower())
                        for item in fact_bindings if isinstance(item, dict)
                    ]
                    valid_fact_bindings = valid_fact_bindings \
                        and len(binding_ids) == len(set(binding_ids)) \
                        and len(fact_keys) == len(set(fact_keys))
                if not valid_fact_bindings:
                    errors.append(
                        f"{prefix}.fact_bindings must contain unique typed facts bound to assessed evidence"
                    )
                template = recommendation.get("suggested_template")
                valid_template = isinstance(template, list) and bool(template)
                referenced_ids: list[str] = []
                if valid_template:
                    for segment in template:
                        if not isinstance(segment, dict):
                            valid_template = False
                            continue
                        if segment.get("type") == "BOUND_FACT" \
                                and nonempty_text(segment.get("binding_id")):
                            referenced_ids.append(segment["binding_id"])
                        elif segment.get("type") == "LITERAL" \
                                and safe_template_literal(segment.get("value")):
                            continue
                        else:
                            valid_template = False
                    valid_template = valid_template \
                        and len(referenced_ids) == len(binding_ids) \
                        and len(referenced_ids) == len(set(referenced_ids)) \
                        and set(referenced_ids) == set(binding_ids) \
                        and render_suggested_template(recommendation) is not None
                if not valid_template:
                    errors.append(
                        f"{prefix}.suggested_template must use every bound fact exactly once and "
                        "only allowlisted separator literals"
                    )
                rendered = render_suggested_template(recommendation)
                if "suggested_value" in recommendation \
                        and recommendation.get("suggested_value") != rendered:
                    errors.append(f"{prefix}.suggested_value must equal the deterministic template output")

    limitations = assessment.get("limitations", [])
    if not isinstance(limitations, list) or not all(nonempty_text(item) for item in limitations):
        errors.append("limitations must be an array of non-empty strings")
    if isinstance(official_report, dict):
        _, policy_errors = evaluate_evidence_policy(assessment, official_report)
        errors.extend(policy_errors)
    return errors


def derive_quality(dimensions: dict[str, Any]) -> tuple[str, str]:
    ratings = [dimensions[name]["rating"] for name in DIMENSIONS]
    evaluated = [rating for rating in ratings if rating != "NOT_EVALUATED"]
    if not evaluated:
        return "NOT_EVALUATED", "NONE"
    completeness = "COMPLETE" if len(evaluated) == len(DIMENSIONS) else "PARTIAL"
    if "WEAK" in evaluated:
        return "NEEDS_IMPROVEMENT", completeness
    if len(evaluated) < len(DIMENSIONS):
        return "PARTIALLY_EVALUATED", completeness
    if all(rating == "STRONG" for rating in evaluated):
        return "STRONG", completeness
    return "ADEQUATE", completeness


def assessment_content_evidence(
        official_report: dict[str, Any], assessment: dict[str, Any],
) -> dict[str, Any]:
    contexts = official_report.get("quality_contexts")
    target = str(assessment.get("assessment_target") or "").upper()
    context = contexts.get(target) \
        if isinstance(contexts, dict) else None
    evidence = context.get("content_evidence") if isinstance(context, dict) else None
    return copy.deepcopy(evidence) if isinstance(evidence, dict) else {}


def combined_quality_completeness(
        dimension_completeness: str, content_evidence: dict[str, Any],
) -> str:
    return "COMPLETE" if dimension_completeness == "COMPLETE" \
        and content_evidence.get("coverage") == "COMPLETE" else "PARTIAL"


def derive_quality_score(
        dimensions: dict[str, Any], assessment: dict[str, Any],
        scope: dict[str, Any] | None = None,
        content_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evaluated_rows = [
        (name, dimensions[name]["rating"])
        for name in DIMENSIONS
        if dimensions[name]["rating"] != "NOT_EVALUATED"
    ]
    evaluated = [rating for _, rating in evaluated_rows]
    dimension_mask = [name for name, _ in evaluated_rows]
    weak_dimensions = [name for name, rating in evaluated_rows if rating == "WEAK"]
    content_evidence = content_evidence or {}
    source_complete = content_evidence.get("coverage") == "COMPLETE"
    status = (
        "FULL" if len(evaluated) == len(DIMENSIONS) and source_complete
        else "PARTIAL" if len(evaluated) >= MIN_SCORED_DIMENSIONS
        else "NOT_SCORED"
    )
    result: dict[str, Any] = {
        "status": status,
        "value": None,
        "raw_evaluated_average": None,
        "scale": 10,
        "type": "INTERNAL_HEURISTIC",
        "official": False,
        "comparable": False,
        "structurally_comparable": status == "FULL",
        "comparison_rule": "BOTH_FULL_AND_SAME_COMPARISON_COHORT",
        "comparison_cohort_sha256": comparison_cohort_sha256(
            assessment, SCORE_RUBRIC_VERSION, EVIDENCE_POLICY_VERSION, scope,
            content_evidence,
        ),
        "content_source_type": content_evidence.get("source_type"),
        "content_scope": content_evidence.get("content_scope"),
        "content_coverage": content_evidence.get("coverage"),
        "evaluated_dimensions": len(evaluated),
        "total_dimensions": len(DIMENSIONS),
        "minimum_dimensions_required": MIN_SCORED_DIMENSIONS,
        "dimension_mask": dimension_mask,
        "weak_dimensions": weak_dimensions,
        "rubric_version": SCORE_RUBRIC_VERSION,
        "rating_points": dict(RATING_POINTS),
    }
    if len(evaluated) >= MIN_SCORED_DIMENSIONS:
        average = round(sum(RATING_POINTS[rating] for rating in evaluated) / len(evaluated), 1)
        result["value"] = average
        result["raw_evaluated_average"] = average
    else:
        result["not_scored_reason"] = "Insufficient evaluated quality dimensions."
    return result


def primary_quality_reason(dimensions: dict[str, Any]) -> dict[str, Any] | None:
    for target_rating in ("WEAK", "ADEQUATE", "STRONG"):
        for name in DIMENSIONS:
            row = dimensions[name]
            if row["rating"] == target_rating:
                return {
                    "dimension": name,
                    "rating": target_rating,
                    "text": row["rationale"],
                }
    return None


def primary_recommendation(
        recommendations: list[dict[str, Any]], reason: dict[str, Any] | None,
) -> dict[str, Any] | None:
    ordered = sorted(
        enumerate(recommendations),
        key=lambda item: (
            PRIORITY_ORDER[item[1]["priority"]],
            0 if reason and item[1].get("dimension") == reason.get("dimension") else 1,
            item[0],
        ),
    )
    if not ordered:
        return None
    recommendation = copy.deepcopy(ordered[0][1])
    recommendation["action_code"] = QUALITY_ACTION_CODES[recommendation["dimension"]]
    recommendation["completion_code"] = QUALITY_COMPLETION_CODE
    rendered = render_suggested_template(recommendation)
    if rendered is not None:
        recommendation["suggested_value"] = rendered
    recommendation["rewrite_is_advisory"] = rendered is not None
    return recommendation


def build_executive_summary(
        official_report: dict[str, Any], assessment: dict[str, Any], verdict: str,
) -> dict[str, Any]:
    scope = official_report.get("scope") if isinstance(official_report.get("scope"), dict) else {}
    quality_reason = primary_quality_reason(assessment["dimensions"])
    quality_action = primary_recommendation(assessment.get("recommendations") or [], quality_reason)
    official_reason = primary_official_finding(official_report)
    official_primary_action = official_action(official_reason, official_report)
    content_evidence = assessment_content_evidence(official_report, assessment)
    score = derive_quality_score(
        assessment["dimensions"], assessment, scope, content_evidence
    )
    _, dimension_completeness = derive_quality(assessment["dimensions"])
    quality_completeness = combined_quality_completeness(
        dimension_completeness, content_evidence
    )
    official_blocker = bool(
        official_reason and official_reason.get("status") == "OFFICIAL_ERROR"
    )
    operational_reason = official_reason if official_blocker else quality_reason or official_reason
    operational_action = (
        official_primary_action if official_blocker else quality_action or official_primary_action
    )
    summary = {
        "summary_version": "1.2",
        "identity": {
            "marketplace_id": scope.get("marketplace_id"),
            "seller_sku": scope.get("sku"),
            "asin": scope.get("asin"),
        },
        "official": {
            "current_listing_gate": official_report["current_listing_gate"],
            "candidate_preview_gate": official_report["candidate_preview_gate"],
            "candidate_local_validation_gate": official_report["candidate_local_validation_gate"],
            "release_decision": official_report["release_decision"],
            "validation_completeness": official_report["official_validation_completeness"],
        },
        "quality_verdict": verdict,
        "content_evidence": content_evidence,
        "evaluated_dimension_average": score,
        "primary_reason": operational_reason,
        "primary_action": operational_action,
        "quality_primary_reason": quality_reason,
        "quality_primary_action": quality_action,
        "official_primary_reason": official_reason,
        "official_primary_action": official_primary_action,
        "content_quality": {
            "verdict": verdict,
            "evidence_completeness": quality_completeness,
            "content_evidence": copy.deepcopy(content_evidence),
            "evaluated_dimension_average": copy.deepcopy(score),
            "primary_reason": copy.deepcopy(quality_reason),
            "primary_action": copy.deepcopy(quality_action),
        },
        "official_evidence": {
            "validation_completeness": official_report["official_validation_completeness"],
            "coverage": copy.deepcopy(official_report.get("official_evidence_coverage") or {}),
            "primary_reason": copy.deepcopy(official_reason),
            "primary_action": copy.deepcopy(official_primary_action),
        },
        "performance_verdict": "NOT_EVALUATED",
        "disclaimer": "Internal content-quality summary; not an Amazon official score or performance prediction.",
    }
    summary["quality_score"] = copy.deepcopy(score)
    return summary


def merge_report(official_report: Any, assessment: Any) -> tuple[dict[str, Any], bool]:
    errors: list[str] = []
    if not isinstance(official_report, dict):
        errors.append("official report must be a JSON object")
    else:
        missing_report_fields = sorted(OFFICIAL_REPORT_FIELDS - set(official_report))
        if missing_report_fields:
            errors.append(f"official report is missing fields: {', '.join(missing_report_fields)}")
    errors.extend(validate_assessment(assessment, official_report if isinstance(official_report, dict) else None))
    if errors:
        return {"merge_status": "SYSTEM_ERROR", "errors": errors}, False

    result = copy.deepcopy(official_report)
    verdict, dimension_completeness = derive_quality(assessment["dimensions"])
    content_evidence = assessment_content_evidence(official_report, assessment)
    completeness = combined_quality_completeness(
        dimension_completeness, content_evidence
    )
    evidence_policy, _ = evaluate_evidence_policy(assessment, official_report)
    result.update({
        "merge_status": "OK",
        "quality_verdict": verdict,
        "quality_dimensions": {
            name: assessment["dimensions"][name]["rating"]
            for name in DIMENSIONS
        },
        "quality_evidence_completeness": completeness,
        "quality_content_evidence": content_evidence,
        "quality_evidence_policy": evidence_policy,
        "semantic_assessment": assessment,
        "quality_assessment_trace": {
            "assessment_version": assessment["assessment_version"],
            "assessment_model": assessment["assessment_model"],
            "prompt_version": assessment["prompt_version"],
            "assessed_at": assessment["assessed_at"],
            "assessment_target": assessment["assessment_target"],
            "assessment_locale": assessment["assessment_locale"],
            "evidence_policy_version": assessment["evidence_policy_version"],
            "scope_fingerprint_sha256": assessment["scope_fingerprint_sha256"],
            "content_sha256": assessment["content_sha256"],
            "official_report_sha256": assessment["official_report_sha256"],
            "evidence_manifest_sha256": assessment["evidence_manifest_sha256"],
        },
        "performance_verdict": "NOT_EVALUATED",
    })
    result["executive_summary"] = build_executive_summary(result, assessment, verdict)
    return result, True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge Listing official and content-quality reports")
    parser.add_argument("--official-report", type=Path, required=True)
    parser.add_argument("--semantic-assessment", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        official_report = json.loads(args.official_report.read_text(encoding="utf-8"))
        assessment = json.loads(args.semantic_assessment.read_text(encoding="utf-8"))
        result, valid = merge_report(official_report, assessment)
    except Exception as exc:
        result = {
            "merge_status": "SYSTEM_ERROR",
            "errors": [f"could not read input: {type(exc).__name__}: {exc}"],
        }
        valid = False
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if valid else 2


if __name__ == "__main__":
    sys.exit(main())
