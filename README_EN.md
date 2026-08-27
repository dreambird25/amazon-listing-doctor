# Amazon Listing Doctor — Evidence-first Edition

This public fork of [`buluslan/amazon-listing-doctor`](https://github.com/buluslan/amazon-listing-doctor) keeps structured input, data coverage, field checks, semantic coverage, and action lists while replacing unofficial aggregate scores with traceable evidence states.

It contains no company-specific source code, endpoints, schemas, account identifiers, SKUs, ASINs, or runtime configuration. It is intended as a public reference for ERP and operations integrations.

Current version: **v1.0.1**. This release fixes candidate-preview evidence binding and gate semantics; see [`CHANGELOG.md`](CHANGELOG.md).

## Evidence states

| State | Meaning | Submission gate |
|---|---|---|
| `OFFICIAL_ERROR` | Amazon ERROR/INVALID or a deterministic current-PTD violation | Block same candidate |
| `OFFICIAL_WARNING` | Amazon WARNING or official evidence requiring review | Review |
| `HEURISTIC_ADVICE` | Content, image, intent, or buyer-question advice | Never blocks |
| `NOT_EVALUATED` | Missing data, schema, permissions, or metadata | Unknown |
| `SYSTEM_ERROR` | API, parsing, or checker failure | Gate unknown |

The report keeps three conclusions separate: `current_listing_gate`, `candidate_preview_gate`, and `release_decision`. `official_validation_completeness` independently records whether the official evidence chain is complete, so a known ERROR is never hidden by an unrelated system failure.

The authoritative path is Listings Items attributes/issues → current Product Type Definition → deterministic local validation → Listings Items `VALIDATION_PREVIEW`. Heuristics are appended after official evidence.

Amazon documentation:

- [Retrieve a Product Type Definition](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/retrieve-a-product-type-definition)
- [Manage Product Listings with SP-API](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/manage-product-listings-guide)
- [SP-API release notes for `VALIDATION_PREVIEW`](https://developer-docs.amazon.com/sp-api/docs/sp-api-release-notes)

## Data sources

Input can come from multiple channels; a direct SP-API connection is not required:

- JSON files or pasted structured content.
- Excel, CSV, Seller Central exports, or similar tabular files.
- Amazon SP-API Listings Items, Product Type Definitions, and `VALIDATION_PREVIEW` responses.
- ERP systems, data warehouses, read-only database views, or other internal/third-party APIs.

A converter, ERP adapter, or Agent must normalize each source into the common JSON contract before diagnosis. The current script reads JSON directly and does not parse `.xlsx`; Excel and CSV inputs must first be converted or mapped.

The channel does not determine the evidence level. Only traceable Amazon issues, PTD schemas, and `VALIDATION_PREVIEW` results are official evidence. Files, manual input, and third-party data can still support content checks but cannot automatically prove an Amazon pass.

## Run

```bash
python scripts/diagnose_listing.py --file listing.json
```

The checker uses only the Python standard library, makes no network calls, and performs no writes. See [`references/report-contract.md`](references/report-contract.md) for the data contract and [`references/erp-integration.md`](references/erp-integration.md) for a vendor-neutral adapter design for SP-API, Excel, and other systems.

A passing candidate preview requires `mode=VALIDATION_PREVIEW`, matching PUT/PATCH operation and Listing scope, a matching SHA-256 digest of the exact candidate payload, and complete request/response traceability. Amazon status `ACCEPTED` belongs to a real submission response and is not treated as a preview pass.

## Breaking changes from upstream 0.4.x

The former scoring scripts, static category rules, third-party fetcher, and aggregate score report were removed. `scripts/compliance_report.py` remains as a compatibility entry point but emits the five-state evidence report.

This fork does not predict indexing, ranking, traffic, conversion, or Rufus recommendation probability, and it never rewrites or submits Listings automatically.

## Verify

```bash
python -m unittest discover -s tests -v
python scripts/quick_validate.py
```

The fork retains the upstream MIT license and attribution. See [`LICENSE`](LICENSE).
