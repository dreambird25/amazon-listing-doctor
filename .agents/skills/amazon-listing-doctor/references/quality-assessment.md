# Content Quality Assessment Contract

Use this contract only for the quality branch. It is internal, evidence-based advice and never changes Amazon official gates.

## Ratings and dimensions

- `STRONG`: the supplied content addresses the dimension clearly and consistently.
- `ADEQUATE`: essential information is present, with limited gaps.
- `WEAK`: a material gap, ambiguity, repetition, or contradiction is visible.
- `NOT_EVALUATED`: the bound source lacks enough evidence.

The seven required dimensions are `content_completeness`, `clarity_and_readability`, `intent_coverage`, `buyer_question_coverage`, `image_information_coverage`, `cross_field_consistency`, and `localization_quality`.

## Bind the assessment before judging content

Run `diagnose_listing.py` first. Select exactly one `quality_contexts.CURRENT` or `quality_contexts.CANDIDATE` target, then copy these bindings into the assessment:

- `assessment_target`;
- `scope_fingerprint_sha256`;
- `content_sha256`;
- `evidence_manifest_sha256`;
- `official_report_sha256`, emitted by the deterministic official report before quality fields are merged.

Every evaluated dimension must cite a scalar value from the selected context's `evidence_manifest`. The citation includes the exact `field_path`, the supplied `quote_or_value`, and its canonical JSON `value_sha256`. `merge_report.py` recomputes the value hash and requires the path/hash pair to exist in the manifest. A self-declared quote is not evidence.

```json
{
  "assessment_version": "1.2",
  "assessment_model": "MODEL_IDENTIFIER",
  "prompt_version": "quality-v1.3.2",
  "assessed_at": "2026-01-01T00:00:00Z",
  "assessment_target": "CURRENT",
  "scope_fingerprint_sha256": "SCOPE_SHA256",
  "content_sha256": "CONTENT_SHA256",
  "official_report_sha256": "REPORT_SHA256",
  "evidence_manifest_sha256": "MANIFEST_SHA256",
  "dimensions": {
    "content_completeness": {
      "rating": "ADEQUATE",
      "rationale": "Core content is present, but variation evidence is absent.",
      "evidence": [{
        "field_path": "$.current_content.title",
        "quote_or_value": "Synthetic example title",
        "value_sha256": "VALUE_SHA256"
      }],
      "missing_evidence": ["variation data"]
    },
    "clarity_and_readability": {
      "rating": "NOT_EVALUATED",
      "rationale": "",
      "evidence": [],
      "missing_evidence": ["localized title and bullets"]
    }
  },
  "recommendations": [{
    "priority": "MEDIUM",
    "dimension": "content_completeness",
    "action": "Provide variation relationship data.",
    "completion_criterion": "Parentage and variation attributes are present."
  }],
  "limitations": ["No business performance metrics were supplied."]
}
```

The abbreviated example shows field shape; the actual object must contain all seven dimensions. An evaluated dimension requires a rationale and manifest-bound evidence. `NOT_EVALUATED` requires `missing_evidence`. `assessed_at` must include a timezone.

## Derived verdict and evaluated-dimension average

`merge_report.py` derives the verdict independently of the numeric display aid:

- any evaluated `WEAK` produces `NEEDS_IMPROVEMENT`;
- seven `STRONG` ratings produce `STRONG`;
- seven evaluated ratings without `WEAK` otherwise produce `ADEQUATE`;
- an incomplete set without `WEAK` produces `PARTIALLY_EVALUATED`;
- no evaluated dimension produces `NOT_EVALUATED`.

`executive_summary.evaluated_dimension_average` uses `STRONG=10`, `ADEQUATE=7`, and `WEAK=3`, rounded to one decimal place. Its status is:

- `FULL`: all seven dimensions evaluated; `comparable=true`;
- `PARTIAL`: five or six evaluated; the value is shown but `comparable=false`;
- `NOT_SCORED`: fewer than five evaluated; no numeric value.

The result also exposes `dimension_mask` and `weak_dimensions`. A high average never hides a weak dimension or changes the verdict. `quality_score` remains a compatibility alias for the same object. The rubric is `1.1`, is marked `INTERNAL_HEURISTIC` and `official=false`, and does not predict indexing, ranking, traffic, conversion, or sales.

## Exact suggested values

An exact `suggested_value` additionally requires:

- `attribute` and `current_problem`;
- `source_evidence` entries with manifest-bound `field_path`, `quote_or_value`, and `value_sha256` already cited by an evaluated dimension;
- `fact_bindings`, each containing a literal `fact`, its `source_path`, and `source_value_sha256`;
- every bound fact must occur in the suggested value;
- `completion_criterion`.

The target dimension cannot be `NOT_EVALUATED`. Exact rewrites remain advisory and must pass the applicable PTD and a bound candidate `VALIDATION_PREVIEW`.

## Evidence discipline

Quote only the selected bound Listing context. General product knowledge, competitor pages, reviews, and assumed buyer preferences are not evidence. Keep recommendations tied to rated dimensions; choose the highest priority action before using dimension match as a tie-breaker. For multilingual content, apply [the localization calibration guide](localization-calibration.md).
