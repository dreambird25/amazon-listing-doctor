# Input and Report Contract

## Input JSON

Fields may be absent. Never use an empty string or default boolean to pretend that evidence was confirmed.

```json
{
  "scope": {
    "seller_id": "SELLER_ID",
    "marketplace_id": "MARKETPLACE_ID",
    "sku": "SELLER_SKU",
    "asin": "OPTIONAL_ASIN",
    "product_type": "PRODUCT_TYPE",
    "language": "LOCALE"
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
      "status": "INVALID",
      "submission_id": "PREVIEW_ID",
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

`validation_preview.ran` must be explicitly `true` before empty issues mean the preview ran. Supported PTD constraints are `MAX_LENGTH`, `MIN_LENGTH`, `MAX_ITEMS`, and `MIN_ITEMS`; supported units are `CODE_POINTS`, `UTF8_BYTES`, and `ITEMS`. Unknown constraints become `NOT_EVALUATED`.

Default mapping: `title → item_name`, `item_highlight → item_highlight`, `backend_search_terms → generic_keyword`, and `bullets → bullet_point`. If the current PTD uses other attribute names, use those names in the normalized object.

## Output

- `gate`: `BLOCK`, `REVIEW`, `PASS_OFFICIAL_CHECKS`, `NOT_EVALUATED`, or `UNKNOWN`.
- `coverage`: `PROVIDED` or `MISSING` per content field.
- `findings`: `status`, `code`, `message`, `source`, optional `attribute`, and optional `evidence`.
- `counts`: counts for all five states.

A human report should also include identity, data timestamp, priority actions, completion criteria, recheck method, reconsideration conditions, and untested areas. “No finding” is not “passed” unless the corresponding official check completed successfully.
