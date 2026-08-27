# Content Quality Assessment Contract

Use this contract only for the quality branch. It is internal, evidence-based advice and does not affect Amazon official gates.

## Ratings

- `STRONG`: the supplied content addresses the dimension clearly and consistently with direct evidence.
- `ADEQUATE`: the essential information is present, with limited gaps that do not obscure the main buyer decision.
- `WEAK`: a material gap, ambiguity, repetition, or contradiction is visible in the supplied content.
- `NOT_EVALUATED`: the source lacks enough evidence to judge the dimension.

## Dimensions

| Dimension | Judge from supplied evidence |
|---|---|
| `content_completeness` | Required/current attributes, title, bullets, description, images, variation and other supplied modules |
| `clarity_and_readability` | Specific wording, repetition, keyword stuffing, grammar and information order |
| `intent_coverage` | Use case, audience, goal and constraints explicitly supported by content |
| `buyer_question_coverage` | Compatibility, size/specification, use, limitations, durability and value questions |
| `image_information_coverage` | Main image identification plus supplied dimensions, feature, use, packaging and variation views |
| `cross_field_consistency` | Agreement among title, attributes, bullets, description, images and variation data |
| `localization_quality` | Locale, language, units and marketplace-appropriate expression |

## Assessment JSON

Supply all seven dimensions. An evaluated dimension requires a concise rationale and at least one direct evidence reference. A `NOT_EVALUATED` dimension requires at least one `missing_evidence` item.

```json
{
  "assessment_version": "1.1",
  "assessment_model": "MODEL_IDENTIFIER",
  "prompt_version": "quality-v1.3",
  "assessed_at": "2026-01-01T00:00:00Z",
  "dimensions": {
    "content_completeness": {
      "rating": "ADEQUATE",
      "rationale": "The core content fields are present, but no variation evidence was supplied.",
      "evidence": [{"field": "bullets", "quote_or_value": "Five supplied bullet points"}],
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
    "completion_criterion": "Parentage and variation attributes are present in the normalized input."
  }],
  "limitations": ["No business performance metrics were supplied."]
}
```

The abbreviated example above shows field shape; the actual object must contain every dimension from the table.

## Derived result

`scripts/merge_report.py` validates the assessment and derives:

- `NEEDS_IMPROVEMENT` when any evaluated dimension is `WEAK`.
- `STRONG` when all seven dimensions are evaluated and all are `STRONG`.
- `ADEQUATE` when all seven are evaluated, none is `WEAK`, and at least one is `ADEQUATE`.
- `PARTIALLY_EVALUATED` when one to six dimensions are evaluated and none is `WEAK`.
- `NOT_EVALUATED` when no dimension is evaluated.

The script also emits `quality_evidence_completeness` as `COMPLETE`, `PARTIAL`, or `NONE`, preserves the four trace fields under `quality_assessment_trace`, and always emits `performance_verdict=NOT_EVALUATED`. `assessed_at` must be a timezone-aware ISO-8601 timestamp. Record the actual model identifier and prompt contract version so a changed evaluator can be detected in Golden Dataset regression.

## Evidence discipline

Quote only supplied Listing content or metadata. General product knowledge, competitor pages, reviews, and assumed buyer preferences are not evidence unless the user explicitly supplies them and the report labels their source. Keep recommendations tied to a rated dimension and include a checkable completion criterion.

For multilingual content, apply [the localization calibration guide](localization-calibration.md). Do not downgrade correct marketplace language merely because its sentence structure, word length, punctuation, or units differ from English.
