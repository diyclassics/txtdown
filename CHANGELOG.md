# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-07-09

### Added
- **Direct-speech quote validation.** `Document.validate()` now checks inline direct
  speech in running narrative (distinct from `@Speaker:` dialogue lines and `>`
  cross-source quotation, both of which are excluded). Two new `Issue` kinds:
  `unmatched_quote` — a speech quote opened but never closed, a close-only character
  (`»`, `›`, `”`) with no span open, or a symmetric quote (`"`, `'`) in a context
  inconsistent with its role; pairs are matched across line boundaries so speeches may
  span multiple lines. A closing-shaped stray `'` is a warning rather than an error,
  since word-final elision (`satin'`, `viden'`) is indistinguishable from a closing
  quote. `quote_style_mismatch` (warning) — more than one primary quote style in the
  same document, which quoted formulae, titles, etc. can legitimately produce, so it 
  flags for human review rather than failing. Quote style is otherwise permissible: 
  any matched pair (`"…"`, `'…'`, `«…»`, `„…"`, `‹…›`) is valid.

### Fixed
- **Strict mode raises the real YAML front-matter error.** A malformed YAML block was
  swallowed into a warning and empty metadata, so strict `parse()` fell through to the
  misleading "requires a 'work' field" even when the field was present but the YAML was
  broken. Strict mode now raises `ValueError` naming the underlying YAML error;
  non-strict parsing keeps the tolerant warn-and-continue behavior.

## [0.3.0] - 2026-06-22

### Added
- **Hierarchical numeric section ids at any depth.** A section id may be a dotted
  hierarchy of Arabic integers — `--- 3.7` (chapter.section), `--- 1.2.3`
  (book.chapter.section), etc. The full label is `Section.id` (`"3.7"`), and two derived,
  read-only properties expose the structure: `Section.levels` (`(3, 7)`) and
  `Section.chapter` (the first level, for ids of depth ≥ 2). Dotted labels match Perseus
  CTS passage references (`...:3.7`) directly. Titles still work (`--- 3.7: De Senectute`),
  and the form round-trips through `write()`.
- **Hierarchy-aware citations.** `Document.get()` now matches the longest dotted prefix
  that names a section, so a section-id match takes precedence over the section.line
  reading: `doc.get("3.7")` returns the section and `doc.get("3.7.2")` returns its line 2.
  Non-hierarchical documents are unaffected — `doc.get("2.3")` still means section 2, line 3.
- **Opt-in structural validation.** `Document.validate()` returns a list of `Issue`
  objects (empty when clean) without raising; `Document.is_valid` is True unless there are
  error-severity issues. Section-hierarchy checks: duplicate labels and out-of-order
  labels (errors), and mixed depth (warning). Gaps between labels are intentionally not
  flagged (lacunae are normal). Speaker checks (only when a `speakers` roster is declared
  in the front matter): `unknown_speaker` (error) for an `@Speaker:` name not in the
  roster, and `unused_speaker` (warning) for a declared speaker that never speaks in the
  file. `Issue` is exported from the package.

## [0.2.0] - 2026-06-20

First public release.

### Added
- **Cross-source quotation markup.** Lines beginning with `>` are parsed as verbatim
  quotations of other literary sources; the marker is stripped and the line is flagged
  with `Line.is_quote`. Consecutive `>` lines form a multi-line quotation. Round-trips
  through `write()`. Demonstrated by the Cicero (quoting Ennius/Terence) and Augustine
  (quoting Virgil) examples.
- **Speaker markup for dramatic texts.** `@Speaker:` at the start of a line extracts the
  speaker into `Line.speaker` and keeps `Line.text` as clean speech (single-word names).
- **Explicit line numbering.** Leading `N.` prefixes override auto-increment, and trailing
  editorial labels (e.g. `983a`) are captured in `Line.label` and usable in citations.
- **Strict validation.** `parse()` now requires a YAML front matter block with a `work`
  field and raises `ValueError` when either is missing. Pass `parse(..., strict=False)` to
  parse a fragment (single line or section) without metadata.
- `examples/cicero-de-amicitia.txtd` — full *Laelius de Amicitia* with cross-source quotes.

## [0.1.0] - Initial format

- YAML front matter metadata (`author`, `work`, `source`, `scope`, plus arbitrary extras).
- Sections separated by `---`, with auto-numbering, explicit IDs, and optional titles.
- Auto-numbered lines with 1-indexed, citation-based access (`doc.get("2.3")`).
- Round-trip-safe `parse()` / `write()`.

[0.3.1]: https://github.com/diyclassics/txtdown/releases/tag/v0.3.1
[0.3.0]: https://github.com/diyclassics/txtdown/releases/tag/v0.3.0
[0.2.0]: https://github.com/diyclassics/txtdown/releases/tag/v0.2.0
