# Input and Report Contract

## Input JSON

Fields may be absent, but missing official scope or preview traceability prevents a candidate pass. Never use an empty string or default boolean to pretend that evidence was confirmed.

```json
{
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
    "created_at": "2026-01-01T00:00:00Z"
  },
  "content": {
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
    "listing_issues": [{
      "code": "AMAZON_ISSUE_CODE",
      "message": "...",
      "severity": "ERROR",
      "attributeNames": ["item_name"]
    }],
    "validation_preview": {
      "ran": true,
      "mode": "VALIDATION_PREVIEW",
      "operation": "PUT",
      "payload_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "seller_id": "SELLER_ID",
      "marketplace_id": "MARKETPLACE_ID",
      "sku": "SELLER_SKU",
      "product_type": "PRODUCT_TYPE",
      "request_id": "REQUEST_ID",
      "submission_id": "PREVIEW_ID",
      "requested_at": "2026-01-01T00:00:01Z",
      "responded_at": "2026-01-01T00:00:02Z",
      "http_status": 200,
      "status": "VALID",
      "issues": []
    },
    "ptd": {
      "status": "FRESH",
      "schema_checksum": "SCHEMA_CHECKSUM",
      "resolved_version": "VERSION",
      "constraints": {
        "item_name": [{"type": "MAX_LENGTH", "value": 125, "unit": "CODE_POINTS"}]
      }
    }
  },
  "data_as_of": "2026-01-01T00:00:00Z"
}
```

## Preview evidence rules

- `validation_preview.ran` must be explicitly `true`.
- `status=VALID` is the only passing preview status. `ACCEPTED` belongs to a real submission response and becomes `SYSTEM_ERROR / PREVIEW_MODE_MISMATCH`.
- `mode`, `operation`, seller, marketplace, SKU, product type, and `payload_sha256` must match the current candidate and diagnostic scope.
- A completed preview requires an explicit `issues` array, request/submission identifiers, request/response timestamps, and successful 2xx HTTP status.
- `payload_sha256` is a 64-character hexadecimal SHA-256 digest of the exact canonical candidate payload. The integrating adapter must document its canonicalization method.
- A PATCH candidate must include non-empty `touched_attributes`. Passing a partial PATCH preview does not prove untouched historical errors were fixed.
- `requirements`, `parentage_level`, and `locale` are required when PTD or Preview evidence is used because they define official validation scope.

Supported lightweight PTD constraints are `MAX_LENGTH`, `MIN_LENGTH`, `MAX_ITEMS`, and `MIN_ITEMS`; supported units are `CODE_POINTS`, `UTF8_BYTES`, and `ITEMS`. Unknown constraints become `NOT_EVALUATED`. This lightweight subset is not a complete PTD JSON Schema validator.

Default mapping: `title → item_name`, `item_highlight → item_highlight`, `backend_search_terms → generic_keyword`, and `bullets → bullet_point`. If the current PTD uses other attribute names, use those names in the normalized object.

## Output

- `current_listing_gate`: current Listings Items/PTD result — `BLOCK`, `REVIEW`, `NO_KNOWN_OFFICIAL_ISSUES`, `NOT_EVALUATED`, or `UNKNOWN`.
- `candidate_preview_gate`: exact candidate preview result — `BLOCK`, `REVIEW`, `PASS`, `NOT_EVALUATED`, or `UNKNOWN`.
- `release_decision`: conservative combined result — `BLOCK`, `REVIEW`, `PASS`, `NOT_EVALUATED`, or `UNKNOWN`.
- `release_reasons`: stable reason codes explaining the combined decision.
- `official_scope`: candidate operation, `FULL/PARTIAL/UNKNOWN` coverage, and PATCH touched attributes.
- `official_validation_completeness`: `COMPLETE` or `INCOMPLETE`. It is independent from blockers, so known ERROR plus another evidence failure remains `BLOCK + INCOMPLETE`.
- `gate`: 1.0.x compatibility mirror. It returns `PASS_OFFICIAL_CHECKS` when `release_decision=PASS`; otherwise it mirrors `release_decision`.
- `coverage`: `PROVIDED` or `MISSING` per content field.
- `findings`: `status`, `code`, `message`, `source`, optional `attribute`, and optional `evidence`.
- `counts`: counts for all five evidence states.
- `candidate` and `validation_preview`: normalized traceability summaries; the candidate payload itself is not copied into the report.

A human report should include identity, separate current/candidate/release conclusions, validation completeness, timestamps, priority actions, completion criteria, recheck method, reconsideration conditions, and untested areas. “No finding” is not “passed” unless the corresponding official check completed successfully.
