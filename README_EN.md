# Amazon Listing Doctor — Evidence-first Edition

This public fork of [`buluslan/amazon-listing-doctor`](https://github.com/buluslan/amazon-listing-doctor) keeps structured input, data coverage, field checks, semantic coverage, and action lists while replacing unofficial aggregate scores with traceable evidence states.

It contains no company-specific source code, endpoints, schemas, account identifiers, SKUs, ASINs, or runtime configuration. It is intended as a public reference for ERP and operations integrations.

## Evidence states

| State | Meaning | Submission gate |
|---|---|---|
| `OFFICIAL_ERROR` | Amazon ERROR/INVALID or a deterministic current-PTD violation | Block same candidate |
| `OFFICIAL_WARNING` | Amazon WARNING or official evidence requiring review | Review |
| `HEURISTIC_ADVICE` | Content, image, intent, or buyer-question advice | Never blocks |
| `NOT_EVALUATED` | Missing data, schema, permissions, or metadata | Unknown |
| `SYSTEM_ERROR` | API, parsing, or checker failure | Gate unknown |

The authoritative path is Listings Items attributes/issues → current Product Type Definition → deterministic local validation → Listings Items `VALIDATION_PREVIEW`. Heuristics are appended after official evidence.

Amazon documentation:

- [Retrieve a Product Type Definition](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/retrieve-a-product-type-definition)
- [Manage Product Listings with SP-API](https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/manage-product-listings-guide)
- [SP-API release notes for `VALIDATION_PREVIEW`](https://developer-docs.amazon.com/sp-api/docs/sp-api-release-notes)

## Run

```bash
python scripts/diagnose_listing.py --file listing.json
```

The checker uses only the Python standard library, makes no network calls, and performs no writes. See [`references/report-contract.md`](references/report-contract.md) for the data contract and [`references/erp-integration.md`](references/erp-integration.md) for a vendor-neutral adapter design.

## Breaking changes from upstream 0.4.x

The former scoring scripts, static category rules, third-party fetcher, and aggregate score report were removed. `scripts/compliance_report.py` remains as a compatibility entry point but emits the five-state evidence report.

This fork does not predict indexing, ranking, traffic, conversion, or Rufus recommendation probability, and it never rewrites or submits Listings automatically.

## Verify

```bash
python -m unittest discover -s tests -v
python scripts/quick_validate.py
```

The fork retains the upstream MIT license and attribution. See [`LICENSE`](LICENSE).
