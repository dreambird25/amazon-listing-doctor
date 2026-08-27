# Examples

Run `render_report.py` without `--view` for the default concise user conclusion. Add `--view detailed` to inspect all findings, stable codes, and original messages. The semantic assessment is synthetic and demonstrates the seven-dimension merge contract; it contains no real Listing identifier or private product record.

These fixtures contain placeholders only. They demonstrate the public contract and contain no real seller, SKU, ASIN, credential, or endpoint.

Run from the Skill directory:

```bash
python scripts/diagnose_listing.py --file examples/listing-valid.json
python scripts/diagnose_listing.py --file examples/listing-full-schema-valid.json
python scripts/diagnose_listing.py --file examples/listing-blocked.json
python scripts/diagnose_listing.py --file examples/listing-incomplete.json
python scripts/diagnose_listing.py --file examples/listing-practice-sanitized.json
```

Expected primary results:

| Input | Current Listing | Candidate Preview | Release |
|---|---|---|---|
| `listing-valid.json` | `NO_KNOWN_OFFICIAL_ISSUES` | `PASS` | `REVIEW` |
| `listing-full-schema-valid.json` | `NO_KNOWN_OFFICIAL_ISSUES` | `PASS` | `PASS` |
| `listing-blocked.json` | `BLOCK` | `BLOCK` | `BLOCK` |
| `listing-incomplete.json` | `NOT_EVALUATED` | `NOT_EVALUATED` | `NOT_EVALUATED` |
| `listing-practice-sanitized.json` | `BLOCK` | `NOT_EVALUATED` | `BLOCK` |

`listing-practice-sanitized.json` preserves only the behavior observed in a real read-only exercise: a known official error plus incomplete traceability must remain `BLOCK + INCOMPLETE`. All identities, product content, issue codes, timestamps, and dimensions were replaced; it cannot be used to reconstruct the source Listing.

`listing-valid.json` proves that a correctly bound Preview can pass its own candidate gate. Its release result remains `REVIEW` because the bundled PTD checker is intentionally only `LIGHTWEIGHT_SUBSET`, not a full Draft 2019-09 validator with Amazon vocabulary support.

`listing-full-schema-valid.json` is fully synthetic and demonstrates the external validator attestation contract. Its `PASS` means the evidence conditions are met; it does not represent a real submission or publication.

`semantic-assessment.json` demonstrates all seven quality dimensions and the v1.4 `assessment_version=1.3` scope/content/report/manifest, locale, time, and Evidence Policy binding. It is bound specifically to the deterministic report generated from `listing-valid.json`; changing that input or report correctly makes the merge fail. Merge it with a freshly generated official report using `scripts/merge_report.py`. Generated reports are intentionally not committed because the scripts and tests are their source of truth.
