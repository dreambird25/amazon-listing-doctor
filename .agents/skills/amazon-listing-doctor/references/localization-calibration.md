# Localization quality calibration

`scope.locale` controls which Listing attribute elements and marketplace language are evaluated. `report_locale` controls only the report's display language. Never substitute one for the other.

## Evidence rules

- Evaluate every supplied attribute element whose `marketplace_id` and `language_tag` match the diagnostic scope. Elements without scope tags may be used only when the adapter documents that they already belong to the selected Listing scope.
- Preserve Unicode text. Do not treat code points, UTF-8 bytes, words, or visual width as interchangeable; use only the unit declared by PTD evidence.
- Judge localization from supplied marketplace evidence: language consistency, natural phrasing, units, decimal conventions, compatibility terminology, and buyer comprehension.
- Do not apply English sentence length, capitalization, punctuation, keyword-density, or word-boundary heuristics to German, French, Italian, Spanish, Dutch, Polish, Swedish, Japanese, or other locales.
- If the assessor cannot competently judge the supplied language, return `localization_quality=NOT_EVALUATED` and name the missing reviewer/model capability.

## Calibration set

Maintain private, expert-reviewed examples for each production locale. Include clearly good, borderline, and weak content plus expected evidence citations. Record `assessment_model`, `prompt_version`, `assessment_version`, and `assessed_at` for every run. A model or prompt change must be compared against this set before unattended use.

Localization quality is `HEURISTIC_ADVICE`; it never becomes an Amazon official error without a bound Amazon issue or PTD validation result.
