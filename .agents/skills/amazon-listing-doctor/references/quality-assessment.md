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
- `assessment_locale`, exactly matching `scope.locale`;
- `evidence_policy_version=1.0`;
- `scope_fingerprint_sha256`;
- `content_sha256`;
- `evidence_manifest_sha256`;
- `official_report_sha256`, emitted by the deterministic official report before quality fields are merged.

Every evaluated dimension must cite a scalar value from the selected context's `evidence_manifest`. The citation includes the exact `field_path`, the supplied `quote_or_value`, and its canonical JSON `value_sha256`. `merge_report.py` recomputes the value hash and requires the path/hash pair to exist in the manifest. A self-declared quote is not evidence.

```json
{
  "assessment_version": "1.3",
  "assessment_model": "MODEL_IDENTIFIER",
  "prompt_version": "quality-v1.5.1",
  "assessed_at": "2026-01-01T00:00:00Z",
  "assessment_target": "CURRENT",
  "assessment_locale": "en_US",
  "evidence_policy_version": "1.0",
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

The abbreviated example shows field shape; the actual object must contain all seven dimensions. An evaluated dimension requires a rationale and manifest-bound evidence. `NOT_EVALUATED` requires non-empty `missing_evidence` and an empty `evidence` array. `STRONG` requires an empty `missing_evidence` array. `assessed_at` must include a timezone and cannot predate the official report's `data_as_of`.

## Dimension-specific Evidence Policy 1.0

Matching any manifest path is not enough. Each evaluated dimension must meet its own minimum evidence shape:

| Dimension | Minimum bound evidence |
|---|---|
| `content_completeness` | `STRONG/ADEQUATE`: at least two content modules; `WEAK`: at least one module plus explicit missing evidence |
| `clarity_and_readability` | a textual title, item highlight, bullet, description, attribute, or backend-term value |
| `intent_coverage` | visible Listing text or a visible structured attribute; backend terms alone are insufficient |
| `buyer_question_coverage` | visible Listing text or a structured attribute |
| `image_information_coverage` | at least one `images[...]` path |
| `cross_field_consistency` | evidence from at least two top-level content modules |
| `localization_quality` | visible text and `assessment_locale == scope.locale` |

Evidence must support the specific defect named in the rationale, not merely identify the field. A claim about a replacement character, mojibake, control character, encoding artifact, debug stack, exception trace, or log residue must bind text that actually contains the suspicious character or technical sequence. A normal title or bullet is not evidence for one of these claims. Keep code-point or byte-length validation separate from readability: passing a declared length limit neither proves nor disproves an independent text-quality defect.

For `localization_quality`, perform a basic language and marketplace review whenever the assessor can understand the scoped language. Lack of a separate native human reviewer is a limitation for publication-grade review, not missing Listing evidence and not by itself a reason for `NOT_EVALUATED`. Use `NOT_EVALUATED` only when the assessor genuinely lacks language capability or the bound Listing lacks enough scoped visible text; state which of those is missing.

`quality_evidence_policy` records each rule code and the non-sensitive module names used. A failed policy makes the merge fail; it is not downgraded to a warning.

## Derived verdict and evaluated-dimension average

`merge_report.py` derives the verdict independently of the numeric display aid:

- any evaluated `WEAK` produces `NEEDS_IMPROVEMENT`;
- seven `STRONG` ratings produce `STRONG`;
- seven evaluated ratings without `WEAK` otherwise produce `ADEQUATE`;
- an incomplete set without `WEAK` produces `PARTIALLY_EVALUATED`;
- no evaluated dimension produces `NOT_EVALUATED`.

`executive_summary.evaluated_dimension_average` uses `STRONG=10`, `ADEQUATE=7`, and `WEAK=3`, rounded to one decimal place. Its status is:

- `FULL`: all seven dimensions evaluated; `structurally_comparable=true`;
- `PARTIAL`: five or six evaluated; the value is shown but `structurally_comparable=false`;
- `NOT_SCORED`: fewer than five evaluated; no numeric value.

The result also exposes `dimension_mask`, `weak_dimensions`, `comparison_rule`, and `comparison_cohort_sha256`. `FULL` only means that one report has all seven dimensions. Two score values may be compared only when both are `FULL` and their cohort hashes match. The cohort binds assessment model, prompt, assessment contract, score rubric, Evidence Policy, target, Marketplace, Product Type, requirements, parentage, and locale. The legacy `comparable` field remains `false` because a single report cannot prove a pairwise comparison condition.

A high average never hides a weak dimension or changes the verdict. `quality_score` remains a compatibility alias for the same object. The rubric is `1.1`, is marked `INTERNAL_HEURISTIC` and `official=false`, and does not predict indexing, ranking, traffic, conversion, or sales.

## Recommendation constraints

Recommendation priority is bound to the target dimension rating:

- `WEAK`: `HIGH` or `MEDIUM`;
- `ADEQUATE`: `MEDIUM` or `LOW`;
- `STRONG`: optional `LOW` only;
- `NOT_EVALUATED`: only `recommendation_type=EVIDENCE_REQUEST`, with no exact rewrite.

This prevents a high-priority recommendation for a strong dimension from hiding a real weak dimension. An evidence request asks for the missing input needed to assess the dimension; it does not claim how the Listing should be rewritten.

## Exact suggested values

An exact suggestion additionally requires:

- `attribute` and `current_problem`;
- `fact_bindings`, each containing a unique `binding_id`, typed scalar `source_value`, exact `source_path`, and canonical `source_value_sha256` already cited by an evaluated dimension;
- a non-empty `suggested_template` made only of `BOUND_FACT` references and `LITERAL` segments;
- every binding must be used exactly once;
- every literal must be non-empty and use only space, comma, ASCII hyphen, en/em dash, slash, colon, or parentheses; CommonMark thematic-break forms made from three or more ASCII hyphens (including spaced forms), controls, line breaks, tabs, emoji, trademark symbols, check marks, stars, and an unbound percent sign are rejected;
- `completion_criterion`.

The renderer converts the bound scalar value itself; free `rendered_fact` text is forbidden. Therefore a value and its unit require two bindings. An optional input `suggested_value` must exactly equal the deterministic template output; the merged report derives it again rather than trusting it.

```json
{
  "priority": "HIGH",
  "dimension": "clarity_and_readability",
  "attribute": "item_name",
  "current_problem": "The title omits the verified capacity.",
  "action": "Build the suggestion from verified values.",
  "fact_bindings": [
    {
      "binding_id": "capacity",
      "source_path": "$.current_content.attributes.capacity[0].value",
      "source_value": 24,
      "source_value_sha256": "VALUE_SHA256"
    },
    {
      "binding_id": "unit",
      "source_path": "$.current_content.attributes.capacity[0].unit",
      "source_value": "oz",
      "source_value_sha256": "UNIT_SHA256"
    }
  ],
  "suggested_template": [
    {"type": "BOUND_FACT", "binding_id": "capacity"},
    {"type": "LITERAL", "value": " "},
    {"type": "BOUND_FACT", "binding_id": "unit"}
  ],
  "completion_criterion": "The candidate passes the applicable PTD and Preview."
}
```

The target dimension cannot be `NOT_EVALUATED`. Exact rewrites remain advisory and must pass the applicable PTD and a bound candidate `VALIDATION_PREVIEW`.

The concise default action does not repeat free model prose. `merge_report.py` maps the selected recommendation dimension to a stable `action_code` and a generic `completion_code`, which the renderer localizes. The original `action` and `completion_criterion` remain visible only in the detailed audit view. This keeps unbound product claims out of the default operational instruction while preserving review traceability.

## Separate content and official-evidence summaries

`executive_summary.content_quality` contains the quality verdict, evidence completeness, score, reason, and action. `executive_summary.official_evidence` contains official validation completeness, coverage, reason, and action. The compatibility fields `quality_primary_reason` / `quality_primary_action` and `official_primary_reason` / `official_primary_action` mirror those lanes.

For a merged quality report, missing, stale, or untraceable official evidence never replaces the content-quality reason. An applicable `OFFICIAL_ERROR` may remain the compatibility `primary_reason` because it blocks the operational workflow, but the renderer still displays both lanes. If no quality dimension was evaluated, the official reason remains the only available primary reason.

## Evidence discipline

Quote only the selected bound Listing context. General product knowledge, competitor pages, reviews, and assumed buyer preferences are not evidence. Keep recommendations tied to rated dimensions; choose the highest priority action before using dimension match as a tie-breaker. For multilingual content, apply [the localization calibration guide](localization-calibration.md).
