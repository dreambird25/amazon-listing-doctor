# Vendor-neutral ERP Integration

Keep the public skill independent from private tables, endpoints, credentials, and domain classes. An ERP adapter should provide the normalized input contract without exposing its internal implementation.

## Required adapter capabilities

1. **Resolve identity**: seller, marketplace, Seller SKU, optional ASIN, product type, and locale.
2. **Read seller Listing state**: current attributes, summaries, issues, status, request ID, source timestamp, expiry, and exact included datasets.
3. **Read PTD evidence**: schema status, checksum/version, effective scope, extracted constraints, expiry, and last refresh result.
4. **Run candidate preview**: hash the exact canonical candidate payload, compute the public request fingerprint, submit it with `mode=VALIDATION_PREVIEW`, and return the normalized request scope, response status, issues, request/submission identifiers, HTTP status, ordered timestamps, and expiry.
5. **Read catalog context**: optional Catalog Items data clearly labeled as merged catalog context, never seller contribution.
6. **Read buyer-visible content when required**: collect the scoped marketplace storefront title, visible bullets, description, images, and capture time without presenting Listings Items or Catalog Items as a storefront substitute.

The adapter may use REST, files, a read-only database view, or an in-process service. The public report contract must not reveal internal URLs, table names, credentials, tenant identifiers, or production topology.

## Local development adapter

An integrating project may expose a configurable loopback development API so the parent Agent can complete Listing evidence without entering a production environment.

- Bind the adapter to an explicit development profile and development database. Do not infer the environment from a hostname alone.
- Use the project's real development authentication and authorization path; do not disable access control or embed a token in this Skill.
- Permit only side-effect-free reads such as Listings Items GET, Catalog Items GET, or an equivalent read-only RPC. A route that synchronizes, refreshes a persisted cache, runs Preview, or submits changes is not a data-collection adapter.
- Keep the local base URL, route, credentials, store mapping, Seller Listing identity, and response archive in the integrating project's private environment. Public examples use placeholders only.
- Normalize the response to this Skill's public contract in the parent environment, record missing datasets explicitly, and write the private normalized file outside the public checkout.
- Keep production connectivity disabled by default. Accessing production requires a separate, explicit user-authorized workflow and is never implied by a request to run this Skill locally.

After collection, hand the normalized file to an isolated semantic worker as described in [the private practice guide](private-golden-dataset.md). The worker receives no API access or credentials.

## Identity and freshness

- Use `seller + marketplace + Seller SKU` as the seller Listing identity. ASIN alone is insufficient.
- Include product type, parentage level when known, locale, data source, fetched-at time, and dataset completeness.
- Keep the observed Listing in `current_content` and the exact proposed projection in `candidate.content`; never reuse one object implicitly in a new integration.
- Populate `current_content_evidence` and optional `candidate.content_evidence`. Use `LISTINGS_ITEMS + SELLER_CONTRIBUTION` for Listings Items attributes, `CATALOG_ITEMS + SUPPLIED_CONTENT` for catalog context, and `STOREFRONT_OBSERVATION + BUYER_VISIBLE` only for an actual scoped storefront observation.
- A partial API projection, a browser page that did not finish loading, or an adapter that selected only some fields must use `coverage=PARTIAL|UNKNOWN` and `missing_field_semantics=UNKNOWN`. Do not turn omitted data into a missing-content defect.
- Preserve complete Amazon attribute arrays with `language_tag` and `marketplace_id`. Declare source-to-PTD names in `attribute_aliases`; do not hide alias rules inside adapter code.
- Do not combine attributes from different marketplaces or sellers into one diagnostic object.
- Mark delayed, partial, or stale snapshots explicitly. Do not silently promote cached data to current evidence.

## Candidate and preview binding

- Calculate `payload_sha256` from one documented canonical JSON representation before the preview request; use the same digest on the candidate and preview evidence objects.
- Record `PUT` or `PATCH`. A PATCH must list `touched_attributes`; never interpret a successful price-only PATCH preview as a full-Listing pass.
- Attach seller, marketplace, Seller SKU, product type, request fingerprint, request ID, submission ID, request/response/expiry timestamps, and HTTP status to the normalized preview evidence.
- Only Amazon status `VALID` belongs to a successful validation preview. Treat `ACCEPTED` as a real-submission response mismatch.
- Record Amazon request `requirements` for PUT. PATCH requests do not contain this field; PATCH requirements remain local PTD validation context.
- Rate-limit Preview independently and use it for selected release candidates, not uncontrolled bulk scans.

## PTD adapter output

Return only the public fields needed by the classifier:

```json
{
  "status": "FRESH",
  "schema_checksum": "SCHEMA_CHECKSUM",
  "meta_schema_checksum": "META_SCHEMA_CHECKSUM",
  "resolved_version": "VERSION",
  "latest": true,
  "release_candidate": false,
  "fetched_at": "2026-01-01T00:00:00Z",
  "expires_at": "2026-01-01T00:10:00Z",
  "scope": {
    "seller_id": "SELLER_ID",
    "marketplace_id": "MARKETPLACE_ID",
    "product_type": "PRODUCT_TYPE",
    "product_type_version": "VERSION",
    "requirements": "LISTING",
    "requirements_enforced": "ENFORCED",
    "parentage_level": "CHILD",
    "locale": "en_US"
  },
  "constraints": {
    "item_name": [
      {"type": "MAX_LENGTH", "value": 125, "unit": "CODE_POINTS"}
    ]
  }
}
```

Recommended statuses are `FRESH`, `STALE_WITHIN_GRACE`, and `UNAVAILABLE`. A refresh failure must not overwrite the last successful schema. Whether a stale schema is acceptable for a real submission remains the ERP's policy; this public checker reports it as a warning. Preserve Schema and Meta-Schema checksums plus the resolved version's `latest` and `release_candidate` flags. The adapter must not describe extracted length/item constraints as full JSON Schema validation.

## External action boundary

- Reading a Listing or running `VALIDATION_PREVIEW` must be distinct from a real update.
- The diagnostic workflow never calls the real update adapter.
- A production integration should add authorization, preview, idempotency, audit history, rate limiting, and post-submission verification outside this repository.
- Store secrets in the integrating system, never in this public repository or diagnostic JSON fixtures.
- Keep private observation and Golden Dataset records outside the checkout. `scripts/evaluate_batch.py` emits aggregate results plus non-identifying row indexes by default; use a private HMAC key only when stable cross-run references are necessary.
