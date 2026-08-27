# Production readiness

Use this guide when an ERP, CI gate, or release workflow will consume the report automatically.

## Required evidence pipeline

1. Read the seller Listing by `seller_id + marketplace_id + sku` and explicitly request `issues`. Record request ID, included datasets, capture time, and a caller-defined expiry.
2. Validate the exact `candidate.content` with a Draft 2019-09 validator that supports Amazon PTD Meta-Schema vocabulary. Feed the bound attestation into `ptd.full_schema_validation`; the bundled constraint checker remains `LIGHTWEIGHT_SUBSET`.
3. For a small number of release candidates, run the correctly rate-limited `VALIDATION_PREVIEW`. Record the actual request and response metadata before interpreting `VALID`, `INVALID`, or issues.
4. Keep diagnosis, Preview, real submission, and post-submission verification as separate permissions and audit events.

`VALIDATION_PREVIEW` has a lower rate limit and Amazon describes it as suitable for testing a small number of Listings, not as a high-throughput production workflow. Batch systems should run complete local Schema validation first and queue only selected candidates for Preview.

## Binding requirements

- `listing_snapshot` is complete only when seller, marketplace, SKU, request ID, `included_data`, issues, capture time, and expiry are valid and mutually consistent.
- PTD evidence is usable only when seller, marketplace, requested product type, resolved version, requirements, requirements enforcement, parentage, locale, checksum, capture time, and expiry are bound.
- `requirements_enforced=NOT_ENFORCED` can be diagnosed but cannot support unattended release, even when an external validator reports the returned Schema as valid.
- Candidate Preview binding uses a deterministic `request_fingerprint_sha256` derived from operation, seller, marketplace, SKU, product type, candidate requirements context, mode, and Payload SHA-256.
- `PUT` Preview evidence must record the request `requirements`. Amazon PATCH requests do not have a `requirements` field; for PATCH it remains PTD/local-validation context and must not be described as an Amazon PATCH request parameter.
- Candidate and Preview timestamps must be ordered and not expired at `data_as_of`. A Preview older than the PTD evidence in the same report must be rerun.
- Full-schema evidence must set `complete=true`, use boolean `valid`, and bind validator/version, `schema_draft=2019-09`, `amazon_vocabulary=true`, Schema and Meta-Schema checksums, the exact candidate Payload SHA-256, `validated_at`, and an explicit errors array. A bare `full_schema_validation=true` is never trusted.

## Safe automation boundary

An integration may automatically block a correctly bound `OFFICIAL_ERROR`. Do not automatically release a candidate unless all required evidence is complete, the candidate PTD result is backed by a verified full-schema attestation rather than the bundled subset, the Preview is bound and current, and the integrating system has a separate authorized submission and post-submit reconciliation workflow. `release_decision=PASS` means the evidence gate is satisfied; it does not mean the Listing was submitted or published.

The official-source research behind these constraints is maintained in the repository at `docs/production-readiness-research.md`.
