# Amazon Listing Doctor

A repo-discoverable Codex Skill for evidence-first Amazon Listing diagnostics. It keeps Amazon official evidence, content-quality judgment, missing data, and system failures separate.

This public fork of [`buluslan/amazon-listing-doctor`](https://github.com/buluslan/amazon-listing-doctor) contains no company-specific code, endpoints, schemas, account identifiers, SKUs, ASINs, credentials, or runtime configuration.

Current version: **v1.2.0**. This release adds production evidence binding and a sanitized real-world replay. See [`CHANGELOG.md`](CHANGELOG.md).

## Three independent conclusions

| Layer | Output | Official submission effect |
|---|---|---|
| Official evidence | Current Listing gate, candidate preview gate, release decision, and validation completeness | Applies only within the bound official evidence scope |
| Content quality | Seven dimensions rated `STRONG / ADEQUATE / WEAK / NOT_EVALUATED` | Never changes the official gate |
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

v1.2.0 is suitable for human diagnostics, ERP-assisted gates, and automatically blocking a correctly bound Amazon `ERROR`. Mismatched old Preview errors, stale evidence, scope conflicts, and PATCH candidates without a current traceable snapshot fail closed instead of appearing to pass.

Unattended automatic release still requires a full Draft 2019-09 validator with Amazon vocabulary support, independent Preview rate limiting, an authorized submission workflow, and post-submission issue/status reconciliation in the integrating system. See the [official-source production research](docs/production-readiness-research.md) and [production integration guide](.agents/skills/amazon-listing-doctor/references/production-readiness.md).

A real read-only Listing exercise exposed a known Amazon ERROR while another structured view had not caught up. The public regression fixture preserves only the required behavior—`BLOCK + INCOMPLETE`. [`listing-practice-sanitized.json`](.agents/skills/amazon-listing-doctor/examples/listing-practice-sanitized.json) replaces every identity, content value, issue code, timestamp, and dimension and contains no source product data.

## Developer CLI

```bash
python scripts/diagnose_listing.py --file .agents/skills/amazon-listing-doctor/examples/listing-valid.json
```

The root command is a compatibility wrapper around the canonical Skill script. Both deterministic scripts use only the Python standard library, make no network calls, and perform no writes.

The local PTD engine executes only its supported length/item constraints and reports `ptd_validation_coverage=LIGHTWEIGHT_SUBSET`; it does not claim complete PTD Schema validation. Even with a bound, valid `VALIDATION_PREVIEW`, the bundled engine therefore keeps `release_decision=REVIEW`. Preview proves only that the candidate preview is valid, not that it was published or is ready for unattended release.

The quality branch follows [`quality-assessment.md`](.agents/skills/amazon-listing-doctor/references/quality-assessment.md) and is validated and merged by `scripts/merge_report.py` inside the Skill. Official input/output is defined in [`report-contract.md`](.agents/skills/amazon-listing-doctor/references/report-contract.md).

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
