# Private Golden Dataset practice

Use production-like Listing records only in an authorized private environment. The public repository must contain synthetic fixtures, never raw or reversibly transformed seller data.

## Read-only sampling

1. Define the eligible population and record a fixed random seed before selection.
2. Sample across marketplaces, locales, Product Types, parentage, and issue/no-issue states. Fetch only the fields needed by the public contract.
3. Do not call synchronization, recheck, Preview, PUT, PATCH, feed, or submission endpoints as part of an observational practice run.
4. Normalize in memory. Do not write raw responses, titles, attributes, image URLs, seller IDs, SKUs, ASINs, issue messages/codes, request IDs, or access credentials into the public checkout.
5. Run each normalized input twice and compare the deterministic report fields.

## Private fixture shape

Store private JSON or JSONL outside the repository and outside shared logs:

```json
{
  "sample_id": "PRIVATE_REFERENCE",
  "input": {"scope": {}, "official": {}},
  "expected": {
    "current_listing_gate": "BLOCK",
    "release_decision": "BLOCK"
  }
}
```

Run:

```bash
python scripts/evaluate_batch.py --file /private/path/listing-golden.jsonl
```

The command emits aggregate gate distributions, expectation mismatch counts, deterministic-rerun status, and SHA-256-truncated sample references. It never echoes input content or raw sample identifiers.

## Public reporting boundary

Safe public statements include sample count, broad marketplace families, deterministic consistency, engine error count, and generalized evidence gaps. Do not publish per-Listing output or cross-tabulations that can re-identify a small seller portfolio.

The v1.3.0 practice used an independent Luna sub-agent, a fixed seed, and 30 private read-only Listings. The same sample was run against the v1.2 baseline and replayed against the final v1.3 working tree; aggregate gates were identical, all v1.3 reruns were deterministic, and no engine system error occurred. It also confirmed safe degradation when traceable evidence was missing and possible disagreement between issue views. No source record was committed.
