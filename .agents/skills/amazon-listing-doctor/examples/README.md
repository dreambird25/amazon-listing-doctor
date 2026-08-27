# Examples

These fixtures contain placeholders only. They demonstrate the public contract and contain no real seller, SKU, ASIN, credential, or endpoint.

Run from the Skill directory:

```bash
python scripts/diagnose_listing.py --file examples/listing-valid.json
python scripts/diagnose_listing.py --file examples/listing-blocked.json
python scripts/diagnose_listing.py --file examples/listing-incomplete.json
```

Expected primary results:

| Input | Current Listing | Candidate Preview | Release |
|---|---|---|---|
| `listing-valid.json` | `NO_KNOWN_OFFICIAL_ISSUES` | `PASS` | `PASS` |
| `listing-blocked.json` | `BLOCK` | `BLOCK` | `BLOCK` |
| `listing-incomplete.json` | `NOT_EVALUATED` | `NOT_EVALUATED` | `NOT_EVALUATED` |

`semantic-assessment.json` demonstrates all seven quality dimensions. Merge it with a generated official report using `scripts/merge_report.py`. Generated reports are intentionally not committed because the scripts and tests are their source of truth.
