---
name: amazon-listing-doctor
description: "Diagnose Amazon seller Listings from JSON, Excel/CSV exports, or pasted content by separating official SP-API evidence, content-quality assessment, missing data, and system failures. Use for current Listing audits, candidate preflight, and reviewable optimization reports; not for performance predictions or real submissions."
license: MIT
metadata:
  category: ecommerce/amazon
  version: 1.2.0
  upstream: buluslan/amazon-listing-doctor
---

# Amazon Listing Doctor

Produce two independent conclusions: whether supplied official evidence identifies a submission problem, and whether the supplied content communicates the product well. Keep performance outcomes unassessed unless the user separately provides business metrics.

## Choose the evidence lane

- **Candidate preflight**: a specific PUT/PATCH payload and its `VALIDATION_PREVIEW` evidence are available. Bind them before reporting a pass.
- **Current Listing audit**: Listings Items issues or a current PTD validation result are available without a candidate preview. Report the current state without implying a future payload will pass.
- **Content-only review**: only pasted content, a file, or a table is available. Run quality assessment and mark official checks `NOT_EVALUATED`.

Use `seller_id + marketplace_id + Seller SKU` as the seller Listing identity. ASIN is optional catalog context, not a substitute for Seller SKU.

## Diagnose

1. Establish the evidence lane, identity, product type, requirements, parentage level, locale, source, and timezone-aware `data_as_of`. This step is complete when every unavailable scope field is explicit rather than silently defaulted.
2. Normalize the supplied source into the public JSON contract. Read [the input and report contract](references/report-contract.md) when transforming JSON, tables, exports, or API responses. For an external system integration, also read [the vendor-neutral adapter guide](references/erp-integration.md).
3. Resolve the Skill directory containing this `SKILL.md`, resolve user files to absolute paths, change to the Skill directory, and run its deterministic engine:

   ```bash
   python scripts/diagnose_listing.py --file listing.json
   ```

   This step is complete when the report contains separate `current_listing_gate`, `candidate_preview_gate`, `release_decision`, `official_validation_completeness`, `official_evidence_coverage`, and `ptd_validation_coverage` fields. Treat `ptd_validation_coverage.mode=LIGHTWEIGHT_SUBSET` as an explicit limit, never as complete PTD Schema validation; the bundled engine must keep `release_decision=REVIEW` even when a bound Preview passes. Exit codes are `0` for no official/system error, `1` for an official error only, `2` for a system error only, and `3` when both exist.
4. When the user asks whether the content is good, or requests optimization advice, read [the quality assessment contract](references/quality-assessment.md). Assess every defined dimension with direct Listing evidence or mark it `NOT_EVALUATED`, then merge it with the deterministic report:

   ```bash
   python scripts/merge_report.py \
     --official-report official-report.json \
     --semantic-assessment semantic-assessment.json
   ```

   This step is complete when all seven dimensions are present, every evaluated rating cites evidence, and the merge script returns `merge_status=OK`. Use the script-derived verdict; do not invent a score or manually override it.
5. Render [the report template](assets/report-template.md). Lead with official blockers, official completeness, quality verdict, and at most three actions. Include completion criteria, recheck method, and untested areas.

## Evidence interpretation

Read [the evidence model](references/evidence-model.md) when classifying official findings.

- Amazon `ERROR` and traceable PTD violations are `OFFICIAL_ERROR`.
- Amazon `WARNING` and `INFO` are `OFFICIAL_WARNING`; preserve the original severity.
- Content-quality observations are `HEURISTIC_ADVICE` and never change the official gate.
- Missing inputs are `NOT_EVALUATED`; malformed or mismatched evidence is `SYSTEM_ERROR`.
- Only a fresh, fully bound `mode=VALIDATION_PREVIEW` response with status `VALID` can pass the same candidate payload. Bind scope, operation, Payload SHA-256, request fingerprint, and ordered timestamps. `ACCEPTED` is a real-submission response mismatch.
- A Preview ERROR whose scope, operation, or fingerprint does not match the candidate remains visible but has `applies_to_candidate=false`; it cannot block that candidate.
- A PATCH preview cannot produce release `PASS` without a traceable current Listings Items snapshot.

For production integration or an automatic release decision, read [the production readiness guide](references/production-readiness.md). A valid Preview is low-throughput evidence, not a substitute for full local PTD Schema validation or post-submission verification.

## Boundaries

Diagnosis is read-only. A real PATCH, feed submission, production write, or automatic content rewrite requires a separate user-authorized workflow. The public Skill does not authenticate to SP-API; users or adapters supply normalized evidence.

Quality ratings describe the supplied content, not Amazon indexing, ranking, traffic, conversion, or Rufus recommendation probability. `performance_verdict` remains `NOT_EVALUATED` in this Skill.
