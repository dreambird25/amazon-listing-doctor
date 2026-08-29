# Amazon Listing Doctor

A repo-discoverable Codex Skill for evidence-first Amazon Listing diagnostics. It keeps Amazon official evidence, content-quality judgment, missing data, and system failures separate.

This public fork of [`buluslan/amazon-listing-doctor`](https://github.com/buluslan/amazon-listing-doctor) contains no company-specific code, endpoints, schemas, account identifiers, SKUs, ASINs, credentials, or runtime configuration.

Current version: **v1.6.0**. Image-content ratings now require an observed visual description, unlabeled batch quality observation is supported, and core CLIs can write UTF-8 artifacts directly instead of relying on shell redirection. See [`CHANGELOG.md`](CHANGELOG.md).

## Three independent conclusions

| Layer | Output | Official submission effect |
|---|---|---|
| Official evidence | Current Listing gate, candidate preview gate, release decision, and validation completeness | Applies only within the bound official evidence scope |
| Content quality | Seven ratings plus a transparent internal 10-point score | Never changes the official gate |
| Business performance | `performance_verdict=NOT_EVALUATED` | Requires separate traffic, conversion, returns, and sales evidence |

The Skill does not produce official CDQ, A9, COSMO, or Rufus scores and does not predict indexing, ranking, traffic, or conversion.

## Use as a Codex Skill

```bash
git clone https://github.com/dreambird25/amazon-listing-doctor.git
cd amazon-listing-doctor
codex
```

Codex automatically discovers the repo-scoped Skill at:

```text
.agents/skills/amazon-listing-doctor/
```

Invoke it explicitly:

```text
$amazon-listing-doctor diagnose .agents/skills/amazon-listing-doctor/examples/listing-valid.json and separate official, quality, and untested conclusions
```

For a personal installation, run `$skill-installer` and ask it to install:

```text
https://github.com/dreambird25/amazon-listing-doctor/tree/main/.agents/skills/amazon-listing-doctor
```

See the [official OpenAI Build skills documentation](https://developers.openai.com/codex/skills) for discovery and invocation rules.

## Accepted sources and limits

- Normalized JSON can support official and quality assessment.
- Excel/CSV/Seller Central exports must first be mapped to the public contract.
- Pasted title, bullets, description, and image metadata support content-quality review while official gates remain `NOT_EVALUATED`.
- An ASIN or product URL alone cannot establish seller contribution, PTD scope, or candidate preview evidence.

The public version does not authenticate to Seller Central or call SP-API. A user, ERP, or converter supplies normalized evidence from files, Listings Items, Product Type Definitions, `VALIDATION_PREVIEW`, or another read-only source. See the [example fixtures](.agents/skills/amazon-listing-doctor/examples/README.md).

## Production status

v1.6.0 is suitable for human diagnostics, ERP-assisted gates, and automatically blocking a correctly bound Amazon `ERROR`. Mismatched old Preview errors, stale evidence, scope conflicts, and PATCH candidates without a current traceable snapshot fail closed instead of appearing to pass. User reports compare bound original evidence with an exact validated candidate when one exists, and explicitly mark the candidate as unavailable otherwise. Image URLs and technical metadata no longer masquerade as observed image content.

Unattended automatic release still requires a full Draft 2019-09 validator with Amazon vocabulary support, independent Preview rate limiting, an authorized submission workflow, and post-submission issue/status reconciliation in the integrating system. See the [official-source production research](docs/production-readiness-research.md) and [production integration guide](.agents/skills/amazon-listing-doctor/references/production-readiness.md).

A fixed-seed, read-only run of 30 private Listings validated official-gate behavior. v1.6.0 additionally ran an unlabeled quality observation over 100 private North American and European Listings: deterministic reports and semantic merges completed, and the run exposed a repeatable evidence gap where image locator/technical metadata existed without an actual visual observation. Unlabeled observation proves behavior and degradation boundaries, not human-reviewed correctness; a Quality Golden Set is still being built. No private record, identifier, per-item reference, product text, or raw response is stored here.

## Developer CLI

```bash
python scripts/diagnose_listing.py --file .agents/skills/amazon-listing-doctor/examples/listing-valid.json --output official-report.json
```

The root command is a compatibility wrapper around the canonical Skill script. The CLIs use only the Python standard library, make no network calls, and never write external systems or business data. They write a report file only when `--output` is explicitly supplied, always as UTF-8.

The deterministic CLI needs no OpenAI API key. When Codex performs the seven-dimension semantic assessment it uses the user's current Agent environment; no model credential is stored in this public repository. Other model integrations remain private adapter configuration.

The local PTD engine executes only supported length/item constraints and reports `LIGHTWEIGHT_SUBSET`. An adapter may supply a full-validator attestation bound to the Schema checksums, candidate payload hash, validator/version, and time; only that evidence can set `FULL_JSON_SCHEMA`. A bare boolean is rejected.

Unattended evidence also requires `requirementsEnforced=ENFORCED`; a valid external result against a `NOT_ENFORCED` Schema remains manual review.

```bash
python scripts/render_report.py --report official-report.json --lang zh-CN --format markdown --output user-report.md
python scripts/render_report.py --report merged-report.json --lang en --format markdown --view detailed --output audit-report.md
python scripts/evaluate_batch.py --file private-observation.jsonl --mode observation --output official-observation.json
python scripts/evaluate_batch.py --file private-quality-observation.jsonl --mode quality-observation --output quality-observation.json
python scripts/evaluate_batch.py --file private-golden-dataset.jsonl --mode golden-official
python scripts/evaluate_batch.py --file private-quality-golden.jsonl --mode golden-quality
```

The first command uses the concise default view; `--view detailed` renders the complete audit report and revalidates embedded quality fields for both Markdown and JSON, including a previously rendered Detailed JSON document. `scope.locale` controls Listing validation; `report_locale`/`--lang` controls display only. Candidate Preview `PASS` means “candidate preview passed,” never “published successfully.” `observation` aggregates official gates, while `quality-observation` aggregates bound quality assessments; neither requires labels. Golden modes fail when expected outcomes are absent. Batch output uses non-identifying row indexes unless a private HMAC key of at least 32 UTF-8 bytes is supplied; sample references and suggestion digests use separate HMAC domains.

The quality branch follows [`quality-assessment.md`](.agents/skills/amazon-listing-doctor/references/quality-assessment.md) and is validated and merged by `scripts/merge_report.py` inside the Skill. Official input/output is defined in [`report-contract.md`](.agents/skills/amazon-listing-doctor/references/report-contract.md).

The evaluated-dimension average maps `STRONG=10`, `ADEQUATE=7`, and `WEAK=3` and rounds to one decimal place. Seven evaluated dimensions return `FULL/structurally_comparable=true`; five or six return `PARTIAL`; fewer than five return `NOT_SCORED`. Two scores may be compared only when both are `FULL` and have the same `comparison_cohort_sha256`. Weak dimensions remain explicit even when the average is high. Recommendation priorities are rating-aware: WEAK allows HIGH/MEDIUM, ADEQUATE allows MEDIUM/LOW, STRONG allows at most LOW, and NOT_EVALUATED only allows evidence requests. It is an internal heuristic—not an Amazon score or performance prediction. Assessments bind the selected content context, locale, time, and official report hash and must satisfy the per-dimension Evidence Policy. Exact suggestions use every bound scalar fact exactly once and allow only spaces, comma, hyphens/dashes, slash, colon, and parentheses as literal separators; they still require applicable PTD and candidate Preview validation.

## Safety boundaries

- No real PATCH, feed submission, production write, or automatic publication.
- A preview passes only when mode, operation, Listing scope, candidate payload hash, request fingerprint, and evidence time match.
- `ACCEPTED` is a real-submission response, not a preview pass.
- Content-quality advice never changes the official gate.

## Verify

```bash
python -m unittest discover -s tests -v
python scripts/quick_validate.py
```

The fork retains the upstream MIT license and attribution. See [`LICENSE`](LICENSE).
