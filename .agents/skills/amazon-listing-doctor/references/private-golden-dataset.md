# Private Golden Dataset practice

Use production-like Listing records only in an authorized private environment. The public repository must contain synthetic fixtures, never raw or reversibly transformed seller data.

## Read-only sampling

1. Define the eligible population and record a fixed random seed before selection.
2. Sample across marketplaces, locales, Product Types, parentage, and issue/no-issue states. Fetch only the fields needed by the public contract.
3. A parent Agent may call side-effect-free Listings Items or Catalog Items GET adapters to complete the evidence before delegation. Do not call synchronization, cache-refresh-with-persistence, recheck, Preview, PUT, PATCH, feed, or submission endpoints as part of an observational practice run.
4. Normalize in memory. Do not write raw responses, titles, attributes, image URLs, seller IDs, SKUs, ASINs, issue messages/codes, request IDs, or access credentials into the public checkout.
5. Run each normalized input twice and compare the deterministic report fields.

## Parent-to-sub-agent handoff

The authorized parent environment owns SP-API authentication, evidence collection, normalization, and completeness accounting. When sub-agents are available, semantic assessment must run in a fresh, short-context sub-agent by default. If the runtime has no sub-agent facility, use a separate clean process or isolated context phase rather than mixing data acquisition and model judgment in one long context.

Write one complete normalized input to a private temporary path, record its collection time and missing datasets, and pass only that path plus the public Skill resources to the semantic worker. Do not pass credentials, private endpoint or database topology, raw response archives, or unrelated parent conversation history. The semantic worker must not call SP-API, ERP synchronization, cache refresh, Preview, PUT, PATCH, feed, submission, or production endpoints. It assesses the supplied evidence only and returns a contract-bound assessment for deterministic merging.

Keep two outputs:

- a private audit artifact containing stable codes, original Amazon messages, evidence hashes, and Seller Listing identity;
- a user report containing localized conclusions, reasons, and actions only. For a Chinese user report, do not show English verdicts, gate names, stable error codes, or raw Amazon error messages. ASIN and suggested Listing content may remain when the user needs them.

## Choose the dataset mode

- `observation`: no expected labels are required. Use it to measure aggregate gate distributions and deterministic reruns without claiming correctness.
- `quality-observation`: every sample contains a bound semantic `assessment`, but no expected quality label is required. Use it to aggregate verdict, score coverage, dimension ratings, weak dimensions, candidate availability, merge failures, and deterministic reruns without claiming correctness.
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

For an unlabeled quality observation, store `input + assessment` outside the repository and run:

```bash
python scripts/evaluate_batch.py \
  --file /private/path/listing-quality-observation.jsonl \
  --mode quality-observation \
  --output /private/path/quality-observation-result.json
```

The quality-observation result contains only aggregate distributions and non-identifying merge-failure references. It never emits Listing text, raw identifiers, assessment prose, or raw merge errors.

```bash
export LISTING_DOCTOR_SAMPLE_REF_KEY='replace-with-at-least-32-random-bytes'
python scripts/evaluate_batch.py --file /private/path/listing-golden.jsonl --mode golden-official
```

The key must contain at least 32 UTF-8 bytes. The tool uses separate versioned HMAC domains for truncated sample references and full suggestion digests, so the same value cannot be correlated across those purposes. It never emits a raw identifier or a reversible/guessable unsalted identifier hash.

## Quality-summary regression

To regress the default user conclusion, store the bound `assessment_version=1.4` assessment and only non-identifying expected outcomes alongside each private input:

```json
{
  "sample_id": "PRIVATE_REFERENCE",
  "input": {"scope": {}, "official": {}},
  "assessment": {"assessment_version": "1.4"},
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
