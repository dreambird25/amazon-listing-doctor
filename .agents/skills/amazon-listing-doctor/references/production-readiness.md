# Production readiness

Use this guide when an ERP, CI gate, or release workflow will consume the report automatically.

## Required evidence pipeline

1. Read the seller Listing by `seller_id + marketplace_id + sku` and explicitly request `issues`. Record request ID, included datasets, capture time, and a caller-defined expiry.
2. Validate the candidate with a Draft 2019-09 validator that supports Amazon PTD Meta-Schema vocabulary. Feed the complete PTD result into the adapter; the bundled constraint checker remains `LIGHTWEIGHT_SUBSET`.
3. For a small number of release candidates, run the correctly rate-limited `VALIDATION_PREVIEW`. Record the actual request and response metadata before interpreting `VALID`, `INVALID`, or issues.
4. Keep diagnosis, Preview, real submission, and post-submission verification as separate permissions and audit events.

`VALIDATION_PREVIEW` has a lower rate limit and Amazon describes it as suitable for testing a small number of Listings, not as a high-throughput production workflow. Batch systems should run complete local Schema validation first and queue only selected candidates for Preview.

## Binding requirements

- `listing_snapshot` is complete only when seller, marketplace, SKU, request ID, `included_data`, issues, capture time, and expiry are valid and mutually consistent.
- PTD evidence is usable only when seller, marketplace, requested product type, resolved version, requirements, requirements enforcement, parentage, locale, checksum, capture time, and expiry are bound.
- Candidate Preview binding uses a deterministic `request_fingerprint_sha256` derived from operation, seller, marketplace, SKU, product type, candidate requirements context, mode, and Payload SHA-256.
- `PUT` Preview evidence must record the request `requirements`. Amazon PATCH requests do not have a `requirements` field; for PATCH it remains PTD/local-validation context and must not be described as an Amazon PATCH request parameter.
- Candidate and Preview timestamps must be ordered and not expired at `data_as_of`. A Preview older than the PTD evidence in the same report must be rerun.

## Safe automation boundary

An integration may automatically block a correctly bound `OFFICIAL_ERROR`. Do not automatically release a candidate unless all required evidence is complete, the local PTD result is genuinely full-schema rather than the bundled subset, the Preview is bound and current, and the integrating system has a separate authorized submission and post-submit reconciliation workflow.

The official-source research behind these constraints is maintained in the repository at `docs/production-readiness-research.md`.
