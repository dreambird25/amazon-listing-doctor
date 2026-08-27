# Private Golden Dataset practice

Use production-like Listing records only in an authorized private environment. The public repository must contain synthetic fixtures, never raw or reversibly transformed seller data.

## Read-only sampling

1. Define the eligible population and record a fixed random seed before selection.
2. Sample across marketplaces, locales, Product Types, parentage, and issue/no-issue states. Fetch only the fields needed by the public contract.
3. Do not call synchronization, recheck, Preview, PUT, PATCH, feed, or submission endpoints as part of an observational practice run.
4. Normalize in memory. Do not write raw responses, titles, attributes, image URLs, seller IDs, SKUs, ASINs, issue messages/codes, request IDs, or access credentials into the public checkout.
5. Run each normalized input twice and compare the deterministic report fields.

## Choose the dataset mode

- `observation`: no expected labels are required. Use it to measure aggregate gate distributions and deterministic reruns without claiming correctness.
- `golden-official`: every sample must contain `expected` with at least one official gate field. Missing or unknown expectation fields make the batch invalid.
- `golden-quality`: every sample must contain a bound semantic `assessment` plus `expected_quality` with at least one supported quality field or `score_range`. Missing or unknown expectation fields make the batch invalid.

The legacy names `official-gates` and `quality-summary` remain CLI aliases, but output always records the canonical mode.

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
python scripts/evaluate_batch.py \
  --file /private/path/listing-golden.jsonl \
  --mode golden-official
```

The command emits aggregate gate distributions, expectation mismatch counts, and deterministic-rerun status. Without a private key, sample references are non-identifying row indexes such as `sample-000001`; they cannot be joined across reordered datasets. If stable cross-run references are required, set a secret that never enters the repository or logs:

```bash
export LISTING_DOCTOR_SAMPLE_REF_KEY='replace-with-at-least-32-random-bytes'
python scripts/evaluate_batch.py --file /private/path/listing-golden.jsonl --mode golden-official
```

The key must contain at least 32 UTF-8 bytes. The tool uses separate versioned HMAC domains for truncated sample references and full suggestion digests, so the same value cannot be correlated across those purposes. It never emits a raw identifier or a reversible/guessable unsalted identifier hash.

## Quality-summary regression

To regress the default user conclusion, store the bound `assessment_version=1.3` assessment and only non-identifying expected outcomes alongside each private input:

```json
{
  "sample_id": "PRIVATE_REFERENCE",
  "input": {"scope": {}, "official": {}},
  "assessment": {"assessment_version": "1.3"},
  "expected_quality": {
    "quality_verdict": "NEEDS_IMPROVEMENT",
    "score_status": "FULL",
    "score_range": [7.0, 9.0],
    "structurally_comparable": true,
    "comparison_cohort_sha256": "COHORT_SHA256",
    "weak_dimensions": ["clarity_and_readability"],
    "primary_reason_dimension": "clarity_and_readability",
    "primary_action_dimension": "clarity_and_readability",
    "suggested_value_allowed": false,
    "fact_binding_count": 0,
    "unbound_fact_count": 0
  }
}
```

Run:

```bash
python scripts/evaluate_batch.py \
  --file /private/path/listing-quality-golden.jsonl \
  --mode golden-quality
```

The quality mode re-runs diagnosis and merge, checks only explicitly supplied expectations, and can regress verdict, score coverage/range, comparison cohort, weak dimensions, stable official reason/action codes, fact-binding counts, and `suggested_value_hmac_sha256`. The suggestion digest is disabled unless the private HMAC key is present; a plain SHA-256 of product text is never emitted. Use exact expected fields for contract tests and a documented `score_range` only when human labels intentionally allow judgment variance.

Observation output is evidence about behavior, not correctness. Golden output is evidence about correctness only to the extent that expected labels were independently reviewed and kept current with the same contract/cohort.

## Public reporting boundary

Safe public statements include sample count, broad marketplace families, deterministic consistency, engine error count, and generalized evidence gaps. Do not publish per-Listing output, HMAC keys/references, exact small-cell cross-tabulations, titles, issue payloads, identifiers, or source-system metadata that can re-identify a seller portfolio.

The v1.3.0 practice used an independent Luna sub-agent, a fixed seed, and 30 private read-only Listings. The same sample was run against the v1.2 baseline and replayed against the final v1.3 working tree; aggregate gates were identical, all v1.3 reruns were deterministic, and no engine system error occurred. It also confirmed safe degradation when traceable evidence was missing and possible disagreement between issue views. No source record was committed.
