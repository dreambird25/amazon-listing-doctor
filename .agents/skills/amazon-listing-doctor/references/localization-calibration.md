# Localization quality calibration

`scope.locale` controls which Listing attribute elements and marketplace language are evaluated. `report_locale` controls only the report's display language. Never substitute one for the other.

## Evidence rules

- Evaluate every supplied attribute element whose `marketplace_id` and `language_tag` match the diagnostic scope. Elements without scope tags may be used only when the adapter documents that they already belong to the selected Listing scope.
- Preserve Unicode text. Do not treat code points, UTF-8 bytes, words, or visual width as interchangeable; use only the unit declared by PTD evidence.
- Judge localization from supplied marketplace evidence: language consistency, natural phrasing, units, decimal conventions, compatibility terminology, and buyer comprehension.
- Do not apply English sentence length, capitalization, punctuation, keyword-density, or word-boundary heuristics to German, French, Italian, Spanish, Dutch, Polish, Swedish, Japanese, or other locales.
- If the assessor can understand the supplied language, perform the basic localization review from bound text. The absence of a separate native human reviewer is a limitation, not missing Listing evidence; do not use it alone to return `localization_quality=NOT_EVALUATED`.
- If the assessor genuinely cannot understand the supplied language, return `localization_quality=NOT_EVALUATED` and name the missing model language capability. A publication-grade native review may still be recommended as an optional final check without erasing the model's evidence-based basic assessment.

## Calibration set

Maintain private, expert-reviewed examples for each production locale. Include clearly good, borderline, and weak content plus expected evidence citations. Record `assessment_model`, `prompt_version`, `assessment_version`, `evidence_policy_version`, `assessment_locale`, `assessed_at`, and the derived `comparison_cohort_sha256` for every run. A model, prompt, policy, or locale change starts a new comparison cohort and must be evaluated against the reviewed set before unattended use.

Localization quality is `HEURISTIC_ADVICE`; it never becomes an Amazon official error without a bound Amazon issue or PTD validation result.
