# Input and Report Contract

## Input JSON

Fields may be absent, but missing official scope or preview traceability prevents a candidate pass. Never use an empty string or default boolean to pretend that evidence was confirmed.

```json
{
  "report_locale": "zh-CN",
  "attribute_aliases": {
    "item_highlight": "title_differentiation"
  },
  "scope": {
    "seller_id": "SELLER_ID",
    "marketplace_id": "MARKETPLACE_ID",
    "sku": "SELLER_SKU",
    "asin": "OPTIONAL_ASIN",
    "product_type": "PRODUCT_TYPE",
    "requirements": "LISTING",
    "parentage_level": "CHILD",
    "locale": "en_US"
  },
  "candidate": {
    "operation": "PUT",
    "requirements": "LISTING",
    "parentage_level": "CHILD",
    "payload_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "touched_attributes": null,
    "created_at": "2026-01-01T00:00:00Z",
    "content": {
      "attributes": {
        "item_name": [{
          "value": "Candidate title",
          "language_tag": "en_US",
          "marketplace_id": "MARKETPLACE_ID"
        }]
      }
    }
  },
  "current_content": {
    "title": "...",
    "item_highlight": "...",
    "bullets": ["..."],
    "description": "...",
    "backend_search_terms": "...",
    "images": [{
      "url": "https://example.invalid/image.jpg",
      "is_main": true,
      "width": 1600,
      "height": 1600,
      "white_background": null,
      "watermark": null
    }]
  },
  "official": {
    "listing_snapshot": {
      "seller_id": "SELLER_ID",
      "marketplace_id": "MARKETPLACE_ID",
      "sku": "SELLER_SKU",
      "request_id": "LISTING_REQUEST_ID",
      "fetched_at": "2026-01-01T00:00:00Z",
      "expires_at": "2026-01-01T00:10:00Z",
      "included_data": ["attributes", "issues", "summaries"],
      "issues": []
    },
    "validation_preview": {
      "ran": true,
      "mode": "VALIDATION_PREVIEW",
      "operation": "PUT",
      "payload_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "seller_id": "SELLER_ID",
      "marketplace_id": "MARKETPLACE_ID",
      "sku": "SELLER_SKU",
      "product_type": "PRODUCT_TYPE",
      "requirements": "LISTING",
      "request_fingerprint_sha256": "FINGERPRINT_SHA256",
      "request_id": "REQUEST_ID",
      "submission_id": "PREVIEW_ID",
      "requested_at": "2026-01-01T00:00:01Z",
      "responded_at": "2026-01-01T00:00:02Z",
      "expires_at": "2026-01-01T00:10:00Z",
      "http_status": 200,
      "status": "VALID",
      "issues": []
    },
    "ptd": {
      "validation_target": "CANDIDATE",
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
        "item_name": [{"type": "MAX_LENGTH", "value": 125, "unit": "CODE_POINTS"}]
      },
      "full_schema_validation": {
        "complete": true,
        "valid": true,
        "validator": "VALIDATOR_NAME",
        "validator_version": "VALIDATOR_VERSION",
        "schema_draft": "2019-09",
        "amazon_vocabulary": true,
        "schema_checksum": "SCHEMA_CHECKSUM",
        "meta_schema_checksum": "META_SCHEMA_CHECKSUM",
        "payload_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "validated_at": "2026-01-01T00:00:02.500Z",
        "errors": []
      }
    }
  },
  "data_as_of": "2026-01-01T00:00:03Z"
}
```

`current_content` is the observed Listing. `candidate.content` is the exact candidate being assessed. The legacy top-level `content` remains readable as shared content for v1.2 compatibility, but its report is marked `content_contract.mode=LEGACY_SHARED_CONTENT`; new production integrations must use the explicit fields.

Amazon attribute values should be preserved under `attributes` as complete arrays. Do not select only the first value. Each element may carry `language_tag` and `marketplace_id`; the lightweight validator evaluates every element matching `scope.locale` and `scope.marketplace_id`. `attribute_aliases` maps a source field name to the current PTD attribute name and is also used when comparing PATCH `touched_attributes` with current issue attributes.

## Preview evidence rules

- `validation_preview.ran` must be explicitly `true`.
- `status=VALID` is the only passing preview status. `ACCEPTED` belongs to a real submission response and becomes `SYSTEM_ERROR / PREVIEW_MODE_MISMATCH`.
- `mode`, `operation`, seller, marketplace, SKU, product type, `payload_sha256`, and `request_fingerprint_sha256` must match the current candidate and diagnostic scope.
- A completed preview requires an explicit `issues` array, request/submission identifiers, ordered request/response/expiry timestamps, and successful 2xx HTTP status.
- `payload_sha256` is a 64-character hexadecimal SHA-256 digest of the exact canonical candidate payload. The integrating adapter must document its canonicalization method.
- `request_fingerprint_sha256` is the SHA-256 of canonical compact JSON with sorted keys: `marketplace_id`, `mode`, `operation`, `payload_sha256`, `product_type`, `requirements`, `seller_id`, and `sku`. It is adapter traceability evidence, not an Amazon response field.
- A PUT Preview records and matches Amazon request `requirements`. Amazon PATCH requests have no `requirements` field; the candidate value remains PTD/local-validation context for PATCH.
- A PATCH candidate must include non-empty `touched_attributes`. Passing a partial PATCH preview does not prove untouched historical errors were fixed.
- A PATCH candidate cannot receive release `PASS` unless `listing_snapshot` is complete and current.
- Preview ERROR/WARNING findings from a mismatched request remain in `findings` with `applies_to_candidate=false`; the candidate gate becomes `UNKNOWN`, not `BLOCK`.
- `requirements`, `parentage_level`, and `locale` are required when PTD or Preview evidence is used because they define diagnostic validation scope.

## Current Listing snapshot rules

- `listing_snapshot` must bind seller, marketplace, SKU, request ID, capture/expiry times, `included_data`, and an explicit issues array.
- `included_data` must contain `issues`; an empty issues array without that marker is not evidence of no issues.
- ERROR/WARNING findings from a mismatched or stale snapshot remain visible with `applies_to_current=false`; they cannot block another Listing scope.
- Legacy `official.listing_issues` arrays remain readable, but they always add `LISTING_SNAPSHOT_TRACEABILITY_MISSING` and cannot establish a complete snapshot.

## PTD evidence rules

- PTD scope must include seller, marketplace, requested product type, actual product type version, requirements, requirements enforcement, parentage level, and locale.
- Schema and Meta-Schema checksums, resolved version, boolean `latest` / `release_candidate` flags, fetched time, and expiry are required. `requirements_enforced` must be `ENFORCED` or `NOT_ENFORCED`. Stale-within-grace evidence also requires a valid grace deadline.
- Candidate evidence retrieved with `requirements_enforced=NOT_ENFORCED` produces `OFFICIAL_WARNING` and can never produce unattended release `PASS`.
- `validation_target=CURRENT|CANDIDATE` declares which content object the PTD evidence evaluates. Candidate findings cannot change `current_listing_gate`.
- Constraint findings from an invalid PTD binding remain visible with the corresponding applicability flag set to `false`; a foreign or expired Schema cannot block another scope.
- The lightweight engine supports only the constraints below. An external adapter may set `full_schema_validation=true` only through the complete evidence object shown above. The evidence must bind Draft 2019-09 plus Amazon vocabulary capability, validator/version, both Schema checksums, candidate Payload hash, ordered timestamp, and errors. A boolean assertion is `SYSTEM_ERROR`.

Supported lightweight PTD constraints are `MAX_LENGTH`, `MIN_LENGTH`, `MAX_ITEMS`, and `MIN_ITEMS`; supported units are `CODE_POINTS`, `UTF8_BYTES`, and `ITEMS`. Unknown constraints become `NOT_EVALUATED`. This lightweight subset is not a complete PTD JSON Schema validator.

Legacy convenience mapping is `title → item_name`, `item_highlight → item_highlight`, `backend_search_terms → generic_keyword`, and `bullets → bullet_point`. For real Amazon names such as `title_differentiation`, declare `attribute_aliases`; never change a canonical name silently inside the engine.

## Output

- `current_listing_gate`: current Listings Items/PTD result — `BLOCK`, `REVIEW`, `NO_KNOWN_OFFICIAL_ISSUES`, `NOT_EVALUATED`, or `UNKNOWN`.
- `candidate_preview_gate`: exact candidate preview result — `BLOCK`, `REVIEW`, `PASS`, `NOT_EVALUATED`, or `UNKNOWN`.
- `candidate_local_validation_gate`: PTD result for explicit `candidate.content` — `BLOCK`, `REVIEW`, `PASS`, `NOT_EVALUATED`, or `UNKNOWN`.
- `release_decision`: conservative combined result — `BLOCK`, `REVIEW`, `PASS`, `NOT_EVALUATED`, or `UNKNOWN`.
- `release_reasons`: stable reason codes explaining the combined decision.
- `official_scope`: candidate operation, `FULL/PARTIAL/UNKNOWN` coverage, and PATCH touched attributes.
- `official_validation_completeness`: `COMPLETE` or `INCOMPLETE`. It is independent from blockers, so known ERROR plus another evidence failure remains `BLOCK + INCOMPLETE`. The bundled `LIGHTWEIGHT_SUBSET` PTD checker always keeps this field `INCOMPLETE` and keeps `release_decision=REVIEW`, even when the bound Preview passes.
- `official_evidence_coverage`: separate completeness for current snapshot, candidate Preview, and local PTD subset.
- `ptd_validation_coverage`: records validation target and either `LIGHTWEIGHT_SUBSET` or a verified external `FULL_JSON_SCHEMA` attestation.
- `gate`: 1.0.x compatibility mirror. It returns `PASS_OFFICIAL_CHECKS` when `release_decision=PASS`; otherwise it mirrors `release_decision`.
- `coverage`: `PROVIDED` or `MISSING` per content field.
- `findings`: `status`, `code`, `message`, `source`, optional `attribute`, and optional `evidence`.
- `counts`: counts for all five evidence states.
- `candidate`, `listing_snapshot`, and `validation_preview`: normalized traceability summaries; candidate content and seller credentials are not copied into the report.
- `report_locale` and `content_contract`: display language and current/candidate normalization traceability. `report_locale` never changes `scope.locale` or validation results.
- `executive_summary`: concise user-facing facts derived during a successful quality merge. It contains the ASIN context, a copy of the official gates and completeness, the internal quality score, primary reason, primary action, and `performance_verdict=NOT_EVALUATED`. It is additive and never replaces or alters the canonical official fields.

`scripts/render_report.py` defaults to `--view concise`, which shows identity, canonical current/release decisions, official validation completeness, score coverage, primary reason, and one action. Use `--view detailed` for the complete findings audit. “No finding” is not “passed” unless the corresponding official check completed successfully.

When content quality is requested, create and validate the separate object defined in [the quality assessment contract](quality-assessment.md), then merge it with `scripts/merge_report.py`. Quality fields never alter the official gates above.
