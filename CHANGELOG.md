# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.2.0]: https://github.com/diyclassics/txtdown/releases/tag/v0.2.0
