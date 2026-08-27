# Examples

These fixtures contain placeholders only. They demonstrate the public contract and contain no real seller, SKU, ASIN, credential, or endpoint.

Run from the Skill directory:

```bash
python scripts/diagnose_listing.py --file examples/listing-valid.json
python scripts/diagnose_listing.py --file examples/listing-blocked.json
python scripts/diagnose_listing.py --file examples/listing-incomplete.json
python scripts/diagnose_listing.py --file examples/listing-practice-sanitized.json
```

Expected primary results:

| Input | Current Listing | Candidate Preview | Release |
|---|---|---|---|
| `listing-valid.json` | `NO_KNOWN_OFFICIAL_ISSUES` | `PASS` | `REVIEW` |
| `listing-blocked.json` | `BLOCK` | `BLOCK` | `BLOCK` |
| `listing-incomplete.json` | `NOT_EVALUATED` | `NOT_EVALUATED` | `NOT_EVALUATED` |
| `listing-practice-sanitized.json` | `BLOCK` | `NOT_EVALUATED` | `BLOCK` |

`listing-practice-sanitized.json` preserves only the behavior observed in a real read-only exercise: a known official error plus incomplete traceability must remain `BLOCK + INCOMPLETE`. All identities, product content, issue codes, timestamps, and dimensions were replaced; it cannot be used to reconstruct the source Listing.

`listing-valid.json` proves that a correctly bound Preview can pass its own candidate gate. Its release result remains `REVIEW` because the bundled PTD checker is intentionally only `LIGHTWEIGHT_SUBSET`, not a full Draft 2019-09 validator with Amazon vocabulary support.

`semantic-assessment.json` demonstrates all seven quality dimensions. Merge it with a generated official report using `scripts/merge_report.py`. Generated reports are intentionally not committed because the scripts and tests are their source of truth.
