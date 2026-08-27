# Vendor-neutral ERP Integration

Keep the public skill independent from private tables, endpoints, credentials, and domain classes. An ERP adapter should provide the normalized input contract without exposing its internal implementation.

## Required adapter capabilities

1. **Resolve identity**: seller, marketplace, Seller SKU, optional ASIN, product type, and locale.
2. **Read seller Listing state**: current attributes, summaries, issues, status, source timestamp, and dataset completeness.
3. **Read PTD evidence**: schema status, checksum/version, effective scope, extracted constraints, expiry, and last refresh result.
4. **Run candidate preview**: submit a candidate payload with `mode=VALIDATION_PREVIEW` and return status, issues, submission/request identifier, and timestamp.
5. **Read catalog context**: optional Catalog Items data clearly labeled as merged catalog context, never seller contribution.

The adapter may use REST, files, a read-only database view, or an in-process service. The public report contract must not reveal internal URLs, table names, credentials, tenant identifiers, or production topology.

## Identity and freshness

- Use `seller + marketplace + Seller SKU` as the seller Listing identity. ASIN alone is insufficient.
- Include product type, parentage level when known, locale, data source, fetched-at time, and dataset completeness.
- Do not combine attributes from different marketplaces or sellers into one diagnostic object.
- Mark delayed, partial, or stale snapshots explicitly. Do not silently promote cached data to current evidence.

## PTD adapter output

Return only the public fields needed by the classifier:

```json
{
  "status": "FRESH",
  "schema_checksum": "SCHEMA_CHECKSUM",
  "resolved_version": "VERSION",
  "constraints": {
    "item_name": [
      {"type": "MAX_LENGTH", "value": 125, "unit": "CODE_POINTS"}
    ]
  }
}
```

Recommended statuses are `FRESH`, `STALE_WITHIN_GRACE`, and `UNAVAILABLE`. A refresh failure must not overwrite the last successful schema. Whether a stale schema is acceptable for a real submission remains the ERP's policy; this public checker reports it as a warning.

## External action boundary

- Reading a Listing or running `VALIDATION_PREVIEW` must be distinct from a real update.
- The diagnostic workflow never calls the real update adapter.
- A production integration should add authorization, preview, idempotency, audit history, rate limiting, and post-submission verification outside this repository.
- Store secrets in the integrating system, never in this public repository or diagnostic JSON fixtures.
