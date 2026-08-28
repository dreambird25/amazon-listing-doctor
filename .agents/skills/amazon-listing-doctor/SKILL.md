---
name: amazon-listing-doctor
description: "Diagnose Amazon seller Listings from JSON, Excel/CSV exports, or pasted content by separating official SP-API evidence, content-quality assessment, missing data, and system failures. Use for current Listing audits, candidate preflight, and reviewable optimization reports; not for performance predictions or real submissions."
license: MIT
metadata:
  category: ecommerce/amazon
  version: 1.5.2
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
2. Normalize the supplied source into the public JSON contract. Keep `current_content` and `candidate.content` separate. Preserve every Amazon attribute array element with its `language_tag` and `marketplace_id`; when a source uses a non-PTD name such as `item_highlight`, declare it in `attribute_aliases` instead of hard-coding a guess. Read [the input and report contract](references/report-contract.md) when transforming JSON, tables, exports, or API responses. For an external system integration, also read [the vendor-neutral adapter guide](references/erp-integration.md).
3. Resolve the Skill directory containing this `SKILL.md`, resolve user files to absolute paths, change to the Skill directory, and run its deterministic engine:

   ```bash
   python scripts/diagnose_listing.py --file listing.json
   ```

   This step is complete when the report contains separate `current_listing_gate`, `candidate_preview_gate`, `candidate_local_validation_gate`, `release_decision`, `official_validation_completeness`, `official_evidence_coverage`, and `ptd_validation_coverage` fields. Treat `ptd_validation_coverage.mode=LIGHTWEIGHT_SUBSET` as an explicit limit, never as complete PTD Schema validation. An external full validator may enable `FULL_JSON_SCHEMA` only through the bound evidence contract in [the production readiness guide](references/production-readiness.md); a bare boolean is invalid. Exit codes are `0` for no official/system error, `1` for an official error only, `2` for a system error only, and `3` when both exist.
4. When the user asks whether the content is good, or requests optimization advice, read [the quality assessment contract](references/quality-assessment.md). Assess every defined dimension with direct Listing evidence or mark it `NOT_EVALUATED`, then merge it with the deterministic report:

   ```bash
   python scripts/merge_report.py \
     --official-report official-report.json \
     --semantic-assessment semantic-assessment.json
   ```

   This step is complete when the assessment uses `assessment_version=1.3`, selects `CURRENT` or `CANDIDATE`, binds the scope/content/official-report/evidence-manifest hashes emitted by the deterministic engine, matches the Listing locale and evidence time, includes all seven dimensions, satisfies the dimension-specific Evidence Policy, and the merge script returns `merge_status=OK`. Use the script-derived verdict and `executive_summary.evaluated_dimension_average`; do not invent or override a score. Five or six evaluated dimensions produce `PARTIAL`. Seven produce structurally complete `FULL`, but two scores are comparable only when both are `FULL` and have the same `comparison_cohort_sha256`. The score is an internal heuristic, never an Amazon score or performance prediction.
5. Render in the user's language. `scope.locale` controls Listing evidence; `report_locale` controls display and must never change validation. The default concise user view shows localized conclusions only; do not expose stable status/error codes or Amazon's original foreign-language message there. Preserve those machine fields in the separate detailed audit view. For Chinese Markdown:

   ```bash
   python scripts/render_report.py --report merged-report.json --lang zh-CN --format markdown
   ```

   The default view contains two explicit sections: content quality and Amazon official-evidence status. Content score, verdict, reason, action, and optional suggested value come only from the quality lane. Missing, stale, or untraceable official evidence stays in the official section and must not be described as incomplete Listing content. An applicable `OFFICIAL_ERROR` remains an operational blocker and is always shown in the official section. Use `--view detailed` when the user asks for findings or audit evidence:

   ```bash
   python scripts/render_report.py --report merged-report.json --lang zh-CN --format markdown --view detailed
   ```

   Detailed Markdown and JSON must revalidate the embedded assessment before exposing quality fields, including when Detailed JSON is rendered again. They include the concise conclusion, official findings, all seven quality dimensions, Evidence Policy result, recommendations, limitations, fact bindings, and assessment trace. Write rationales and recommendations in `report_locale`. Recommendation priority must match the target rating: WEAK allows HIGH/MEDIUM, ADEQUATE allows MEDIUM/LOW, STRONG allows only LOW, and NOT_EVALUATED allows only `recommendation_type=EVIDENCE_REQUEST`. An exact suggested value is optional and can contain each manifest-bound scalar fact exactly once; literal separators are limited to spaces, comma, hyphens/dashes, slash, colon, and parentheses. Units and every other product fact require their own binding. It remains advisory and must be rechecked against PTD and a bound candidate Preview. `PASS` means the current evidence conditions are met; never label it “published successfully.”
6. For private practice or semantic analysis, the authorized parent environment must collect and normalize complete Listing evidence before any model assessment. When the runtime supports sub-agents, run semantic assessment in a fresh, short-context sub-agent by default; otherwise use a separate clean process or isolated context phase. Give that worker only one private normalized file plus this public Skill's resources. Do not pass credentials, private API topology, database access, raw response archives, or unrelated parent history. The worker must not discover or fetch data itself. A side-effect-free Listings Items/Catalog Items GET adapter may supply the parent with evidence; synchronization, cache refresh with persistence, Preview, PUT, PATCH, feed, and submission endpoints are outside this step. A local development adapter may call the integrating project's loopback dev API when it is bound to a development profile and development database; production access is disabled unless the user separately authorizes it. Keep the full private identity and raw evidence outside the repository. Use `scripts/evaluate_batch.py` with an explicit intent. `--mode observation` collects aggregate distributions without expected labels. `--mode golden-official` requires at least one expected official gate per sample. `--mode golden-quality` requires at least one expected concise-quality outcome per sample. Use a private `LISTING_DOCTOR_SAMPLE_REF_KEY` of at least 32 UTF-8 bytes when stable cross-run sample references are needed; sample references and suggestion digests use separate HMAC domains. Otherwise output uses non-identifying row indexes. Never add raw private Listing records to this repository; commit only synthetic fixtures and non-identifying aggregate conclusions. Read [the private practice guide](references/private-golden-dataset.md) before sampling production-like data.

## Evidence interpretation

Read [the evidence model](references/evidence-model.md) when classifying official findings.

- Amazon `ERROR`, traceable PTD violations, and a bound full-schema validation failure are `OFFICIAL_ERROR`.
- Amazon `WARNING` and `INFO` are `OFFICIAL_WARNING`; preserve the original severity.
- Content-quality observations are `HEURISTIC_ADVICE` and never change the official gate.
- Missing inputs are `NOT_EVALUATED`; malformed or mismatched evidence is `SYSTEM_ERROR`.
- Only a fresh, fully bound `mode=VALIDATION_PREVIEW` response with status `VALID` can pass the same candidate payload. Bind scope, operation, Payload SHA-256, request fingerprint, and ordered timestamps. `ACCEPTED` is a real-submission response mismatch.
- A Preview ERROR whose scope, operation, or fingerprint does not match the candidate remains visible but has `applies_to_candidate=false`; it cannot block that candidate.
- A PATCH preview cannot produce release `PASS` without a traceable current Listings Items snapshot.
- An external full validator must support JSON Schema Draft 2019-09 plus Amazon's PTD vocabulary and bind validator version, Schema checksums, candidate Payload SHA-256, and timestamp. The Skill validates this attestation; it does not implement or certify the external validator.

For production integration or an automatic release decision, read [the production readiness guide](references/production-readiness.md). A valid Preview is low-throughput evidence, not a substitute for full local PTD Schema validation or post-submission verification.

## Boundaries

Diagnosis is read-only. A real PATCH, feed submission, production write, or automatic content rewrite requires a separate user-authorized workflow. The public Skill does not authenticate to SP-API; users or adapters supply normalized evidence.

Quality ratings describe the supplied content, not Amazon indexing, ranking, traffic, conversion, or Rufus recommendation probability. `performance_verdict` remains `NOT_EVALUATED` in this Skill.
