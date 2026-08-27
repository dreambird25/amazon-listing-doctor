---
name: amazon-listing-doctor
description: "Diagnose Amazon Listing content with evidence from Listings Items issues, Product Type Definitions, and VALIDATION_PREVIEW while keeping internal optimization advice, missing data, and system failures separate. Use for Listing audits, content checks, pre-submission validation, and diagnostic reports; not for ranking predictions or automatic Listing submission."
license: MIT
metadata:
  category: ecommerce/amazon
  version: 1.0.0
  upstream: buluslan/amazon-listing-doctor
---

# Amazon Listing Doctor

Turn Listing data into explainable, reviewable findings and actions. Diagnosis is read-only by default and never implies permission to modify an ERP, database, or Amazon Listing.

This fork retains the upstream ideas of input normalization, data coverage, semantic coverage, and action lists. It does not present CDQ/A9/COSMO/Alexa heuristics as Amazon scores.

## Identify the Listing

Prefer `seller + marketplace + Seller SKU`. ASIN identifies a catalog product, not a seller's Listing contribution. Record product type, locale, source, and data timestamp.

- For pasted text, tables, or JSON, normalize to [the report contract](references/report-contract.md).
- For an ERP integration, read [the public integration guide](references/erp-integration.md).

Continue with available data when fields are missing, but mark affected checks `NOT_EVALUATED`. Never insert default pass values.

## Five Evidence States

Read [the evidence model](references/evidence-model.md) when classifying findings:

- `OFFICIAL_ERROR`: Amazon ERROR/INVALID, or a deterministic violation of a current traceable PTD constraint.
- `OFFICIAL_WARNING`: Amazon WARNING or official evidence requiring human review.
- `HEURISTIC_ADVICE`: deterministic or semantic optimization advice; never blocks submission.
- `NOT_EVALUATED`: missing content, image metadata, schema, permissions, or data freshness.
- `SYSTEM_ERROR`: API, parsing, or checker failure; never treat it as a pass.

Do not output an “Amazon official CDQ score,” “A9 index score,” “COSMO score,” or “Rufus/Alexa recommendation probability.” Summarize counts, coverage, and evidence sources instead.

## Workflow

1. Normalize seller Listing data. Catalog merged values may be supporting context but must not replace seller-contributed attributes.
2. Prefer current Listings Items attributes/issues and the applicable PTD. Use `VALIDATION_PREVIEW` only when a candidate payload needs official pre-submission validation; it calls Amazon but does not persist the payload.
3. Run the deterministic classifier:

   ```bash
   python scripts/diagnose_listing.py --file listing.json
   ```

   Exit codes: `0` no official error/system failure; `1` official error; `2` system failure.
4. Optionally add semantic advice for intent coverage (`use_case`, `audience`, `goal`, `constraint`) and buyer-question coverage (compatibility, specifications, use, durability, and value concerns). Cite Listing evidence; do not invent product facts from common sense, reviews, or competitors.
5. Render [the report template](assets/report-template.md). Include identity, data timestamp, official findings, internal advice, missing evidence, and actions with completion and recheck criteria.

## Safety Boundaries

- Diagnosis does not authorize a real PATCH, feed submission, production database write, or automatic rewrite.
- A passing `VALIDATION_PREVIEW` is not a persisted Amazon acceptance. `ACCEPTED` is not proof that an issue is resolved; verify against a later complete Listing snapshot.
- PTD and Listing requirements change. Do not turn fixed title lengths, bullet counts, or static category lists into universal official rules.
- Only `OFFICIAL_ERROR` blocks the same candidate payload. `HEURISTIC_ADVICE` remains advisory.
- If official preview was not run, state that official pre-submission validation is incomplete.

Lead with the outcome: official blockers, completeness of official validation, and the three most important actions. Then show evidence, gaps, and recheck criteria.
