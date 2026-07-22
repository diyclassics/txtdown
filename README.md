<img src="https://raw.githubusercontent.com/diyclassics/txtdown/main/assets/txtdown-logo.jpg" alt="txtdown" width="400">

[![PyPI version](https://img.shields.io/badge/pypi-v0.4.0-orange.svg)](https://pypi.org/project/txtdown/)
[![Python versions](https://img.shields.io/pypi/pyversions/txtdown.svg)](https://pypi.org/project/txtdown/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Minimal markup for Latin text collections using human-readable markup with inferrable hierarchical structure for scholarly citation.

## Installation

```bash
pip install txtdown
```

Or install the latest development version from source:

```bash
pip install git+https://github.com/diyclassics/txtdown.git
```

## Quick Start

```python
from txtdown import parse, write

# Parse a .txtd file
doc = parse("sulpicia.txtd")

# Access metadata
print(doc.metadata.author)  # "Sulpicia"
print(doc.metadata.work)    # "Epistulae"

# Access by citation
line = doc.get("2.3")       # Section 2, line 3
section = doc.get("1")      # Entire section 1

# Iterate sections and lines
for section in doc.sections:
    for line in section.lines:
        print(f"{section.id}.{line.number}: {line.text}")

# Write back to file (round-trip safe)
write(doc, "output.txtd")
```

## Format Specification

A `.txtd` file consists of a YAML front matter block followed by sections separated by horizontal rules (`---`). The front matter block is required and must include a `work` field; `parse()` raises `ValueError` otherwise. To parse a fragment without metadata (e.g. a single line or section), pass `strict=False`.

### Basic Structure

```
---
author: Sulpicia
work: Epistulae
source: https://thelatinlibrary.com/sulpicia.html
---

--- 1

Tandem venit amor, qualem texisse pudori
    quam nudasse alicui sit mihi fama magis.
exorata meis illum Cytherea Camenis
    attulit in nostrum deposuitque sinum.
etc.

--- 2

Invisus natalis adest, qui rure molesto
    et sine Cerintho tristis agendus erit.
etc.
```

### Sections

- Sections are separated by `---` (three or more hyphens)
- Sections auto-number (1, 2, 3...) unless given explicit IDs (best practice)
- Explicit section ID: `--- prooemium` or `--- 1a`
- Section with title: `--- prooemium: Introduction`

#### Hierarchical section ids

- A section id may be a dotted hierarchy of Arabic integers at **any depth**: `--- 3.7`
  (chapter.section), `--- 1.2.3` (e.g. book.chapter.section), etc.
- The full label is the `id` (`section.id == "3.7"`). Derived, read-only properties expose
  the structure:
  - `section.levels` — the integer components as a tuple (`(3, 7)`; `(1, 2, 3)`;
    `(1,)` for a flat `1`). `None` for named/non-numeric ids (`prooemium`, `1a`).
  - `section.chapter` — the first level, but only for ids with **two or more** levels
    (`"3.7"` → `3`). A flat `"1"` is a section, not a chapter, so it reports `None`.
- This matches Perseus CTS passage references (`...:3.7`) directly, so txtdown labels
  round-trip to/from CTS without a crosswalk.
- A title still works: `--- 3.7: De Senectute` parses to `id="3.7"`, `title="De Senectute"`.
- **Citation:** a section-id match takes precedence over the section.line reading, so a
  hierarchical section is cited `doc.get("3.7")` and a line within it is cited
  `doc.get("3.7.2")` (label.line). In a non-hierarchical document, `doc.get("2.3")`
  continues to mean section 2, line 3.

#### Validating the hierarchy

Parsing is always permissive — any well-formed label is accepted. Structural checks are
opt-in and non-raising:

```python
for issue in doc.validate():           # [] when clean
    print(issue.severity, issue.kind, issue.message)

if not doc.is_valid:                    # True unless there are *error*-severity issues
    ...
```

`validate()` reports every problem at once. It flags **duplicate labels** and
**out-of-order** labels as errors, and **mixed depth** (a stray `3.7.1` among `N.M`
labels) as a warning. It deliberately does *not* flag gaps (`3.6` → `3.8`) to allow for lacunae, partial text editions, etc.

### Lines (for verse)

- Lines auto-number within each section (1, 2, 3...)
- Blank lines don't count toward line numbering
- Access via citation: `doc.get("2.3")` returns section 2, line 3

**Line indentation** (`mode: verse`): Leading whitespace indicates poetic structure (e.g., pentameter lines in elegiac couplets):

```
Tandem venit amor, qualem texisse pudori
    quam nudasse alicui sit mihi fama magis.
```

The parser preserves indentation. For NLP, TxtdownReader strips leading whitespace when joining lines for sentence segmentation.

### Speaker Markup (dramatic texts)

For dramatic texts, use `@Speaker:` at the start of a line to mark speaker attribution:

```
@Diocletianus: Quid sibi vult ista, quae vos agitat, fatuitas?
@Agapes: quod signum fatuitatis nobis inesse deprehendis?
@Diocletianus: Evidens magnumque.
```

The parser extracts the speaker name into `line.speaker` and keeps `line.text` as pure speech text — ideal for NLP pipelines that need clean text without markup.

```python
doc = parse("dulcitius.txtd")
for line in doc.sections[0].lines:
    print(f"{line.speaker}: {line.text}")
# Diocletianus: Quid sibi vult ista...
```

Non-speaker lines (stage directions, prose) have `line.speaker = None`. Speaker markup round-trips through `write()`.

**Declaring the cast (optional).** A `speakers` list in the front matter records the cast
of a dialogue:

```
---
work: Laelius de Amicitia
speakers: [Fannius, Scaevola, Laelius]
---
```

It is kept in `doc.metadata.extras["speakers"]` (a convention, like `genre` or `mode`, not
a typed field). When a roster is present, `doc.validate()` cross-checks it against the
`@Speaker:` names actually used: a used-but-undeclared name is an `unknown_speaker` error
(catches typos like `@Fanius:`), and a declared-but-unused name is an `unused_speaker`
warning. Files that don't declare a roster are not checked.

### Cross-source Quotation

Use `>` at the start of a line to mark text quoted verbatim from *another* literary
source — an author embedding a poet's verse in their own prose, for example. This
repurposes the familiar blockquote convention for the citational habits of classical texts:

```
Quamquam Ennius recte:

> Amicus certus in re incerta cernitur,

tamen haec duo levitatis et infirmitatis plerosque convincunt.
```

The parser strips the `>` marker and flags the line with `line.is_quote = True`, keeping
`line.text` as clean quoted text. Consecutive `>` lines form a multi-line quotation:

```
> Negat quis, nego; ait, aio; postremo imperavi egomet mihi
> Omnia adsentari,
```

```python
doc = parse("cicero-de-amicitia.txtd")
quotes = [line.text for s in doc.sections for line in s.lines if line.is_quote]
# ['Amicus certus in re incerta cernitur,', ...]
```

Non-quote lines have `line.is_quote = False`. Quotation markup round-trips through `write()`.
See `examples/cicero-de-amicitia.txtd` (Cicero quoting Ennius and Terence) and
`examples/augustine-civ-dei-1.2.txtd` (Augustine quoting Virgil).

### Direct Speech

Inline direct speech in running narrative is written with ordinary quotation marks —
no special marker. This is distinct from `@Speaker:` dialogue lines (drama) and from `>`
cross-source quotation (verbatim quotes of *other* works):

```
Aeolus haec contra: "Tuus, O regina, quid optes
explorare labor; mihi iussa capessere fas est.
Tu mihi, quodcumque hoc regni, tu sceptra Iovemque
concilias, tu das epulis accumbere divom,
nimborumque facis tempestatumque potentem."
```

The parser passes quote characters through to `line.text` unchanged — this is a
validation-only feature. Quote **style is permissible**: any matched pair is valid
(`"…"`, `'…'`, `"…"`, `«…»`, `„…"`, `‹…›`). The internal CRAWL/LatinCy standard is a
colon speech-introducer with double curly quotes `"…"` (or straight `"…"`).

`doc.validate()` enforces two rules (both scoped to inline speech; `@Speaker:` and `>`
lines are excluded):

- **`unmatched_quote`** — a speech quote is opened but never closed, a close-only
  character (`»`, `›`, `"`) appears with no span open, or a symmetric quote (`"`, `'`)
  appears in a role-inconsistent context. Pairs are matched across line boundaries, so a
  speech may span many lines. A stray closing-shaped `'` is a *warning*, not an error:
  word-final elision (`satin'`, `viden'`) is indistinguishable from a closing quote.
- **`quote_style_mismatch`** (warning) — more than one primary quote style is used in the
  same document. One style per document is the standard for direct speech, but quoted
  formulae or titles (`de pace 'uti rogas'`) are a different function the validator can't
  distinguish, so this is flagged for human review rather than failing the document.

Nesting is out of scope (single depth): while a span is open, only its own closing
character is significant, so a nested quote of another style passes through unexamined.

### Inline TEI/XML Tags

txtdown tolerates inline TEI/XML markup: valid TEI fragments inside a txtdown body parse 
seamlessly and still yield clean plaintext for NLP. For example, txtdown defines no 
named-entity syntax  of its own, but a project that wants one can use TEI tags directly 
(see e.g. Berti, Crane & Babeu 2026 p. 26 on inline TEI for citation structure, quotation, 
and named entities):

```
exorata meis illum <persName>Cytherea</persName> Camenis
    atque <placeName n="pleiades:413032">Arretino</placeName> frigidus amnis agro?
```

The parser passes tags through to `line.text` verbatim (like direct speech, this is an
accessor/validation feature — `write()` round-trips them unchanged). Tag-stripped text
and resolved spans are exposed at every level:

```python
line.plain      # 'exorata meis illum Cytherea Camenis'
section.plain   # lines joined with '\n', tags stripped
doc.plain       # sections joined with '\n\n', tags stripped
line.tags       # [Tag(name='persName', attrs={}, start=19, end=27)]
section.tags    # includes pairs that span lines
doc.tags        # everything, incl. pairs that span sections
```

`Tag.start`/`Tag.end` index into the corresponding `.plain` text, so
`plain[tag.start:tag.end]` is the enclosed text — standoff-annotation friendly. A
self-closing milestone (`<pb n="2"/>`) has `start == end`.

**Coexistence with West (1973) editorial notation.** In the CRAWL/LatinCy ecosystem
`<text>` already means an editorial supplement, so angle brackets are disambiguated
*structurally*: a token counts as an XML tag only when it is self-closing (`<gap/>`), an
end tag (`</persName>`), or a start tag with a matching end tag later in the document. A
lone unmatched `<word>` stays literal text — a West supplement:

```
    non tempestivae, saeve <propinque>, viae.
```

Here `<propinque>` survives in `.plain` untouched, while the `<persName>` pair above is
stripped.

`doc.validate()` adds four tag checks, all **warnings** (a suspicious tag never breaks
citation lookup): **`unmatched_tag`** (a stray end tag, or an *attribute-bearing* start
tag that is never closed — a bare unmatched `<word>` is never flagged, it is by
definition a West supplement), **`tag_overlap`** (`<a><b></a></b>`),
**`tag_crosses_section`** (a pair opening in one section and closing in another —
usually a West supplement absorbed by an unrelated end tag), and **`tag_only_line`** (a
line containing only markup still consumes a line number, shifting verse numbering —
prefer attaching milestones to a text line: `<milestone n="4"/>hic animum...`).

Out of scope (always literal): comments, CDATA, processing instructions, DOCTYPE,
unquoted attribute values. Block-structure tags (`<div>`, `<lg>`) are tolerated like any
inline tag but are **not** mapped onto txtdown sections — `---` remains the only
structural grammar. See `examples/sulpicia-tei.txtd`.

### Metadata

| Field | Description |
|-------|-------------|
| `work` | Work title (**required**) |
| `author` | Author name |
| `source` | Source URL or reference |
| `scope` | Portion of work in file (e.g., `1-6` for books 1-6) |

Additional fields are preserved in `metadata.extras`.

## API Reference

### Functions

- `parse(path_or_content: str, *, strict: bool = True) -> Document` — Parse a `.txtd` file or string. Strict by default: raises `ValueError` if the front matter block or `work` field is missing; pass `strict=False` for fragments.
- `write(doc: Document, path: str | None) -> str` — Write to file if path given; always returns serialized string

### Classes

- `Document` — Container with `metadata: Metadata` and `sections: list[Section]`
- `Section` — Container with `id: str`, `lines: list[Line]`, optional `title` and `metadata`
- `Line` — Container with `text: str`, `number: int`, optional `speaker: str | None` and `label: str | None`, and `is_quote: bool` (cross-source quotation)
- `Metadata` — Container with `author`, `work`, `source`, `scope`, and `extras` dict
- `Tag` — A resolved inline XML tag: `name`, `attrs: dict`, `start`/`end` offsets into the corresponding `.plain` text, `self_closing: bool`

`Document`, `Section`, and `Line` all expose `.plain` (text with inline XML tags
stripped) and `.tags` (resolved `Tag` spans at that granularity).

## Development

```bash
# Clone and install dev dependencies
git clone https://github.com/diyclassics/txtdown.git
cd txtdown
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=txtdown --cov-report=term-missing
```

## Project History

The idea for txtdown originated in January 2018, inspired by the need for a document format for Latin text collections that balanced the simplicity of plaintext with the more involved markup of XML-based formats like TEI. The goal was to create a format that is both human-readable and computer-tractable, supporting hierarchical structures, fundamental annotations, and embedded metadata. Txtdown has since been influenced by ongoing work on annotation projects such as the [Representing Women Authorship in the Latin Treebanks (RWALT)](https://diyclassics.github.io/rwalt-site/) project.

## References

- Berti, M., Crane, G.R., and Babeu, A. 2026. "Philology and Digital Texts." In Barker, E., Bobou, O., and Raja, R., eds., *The Oxford Handbook of Digital Classical Studies*. Oxford. https://doi.org/10.1093/9780197835210.003.0002
- DeRose, S.J., Durand, D.G., Mylonas, E., and Renear, A.H. 1990. "What Is Text, Really?" *Journal of Computing in Higher Education* 1 (2): 3–26. https://doi.org/10.1007/BF02941632
- Gruber, J. 2004. "Markdown" (version 1.0.1). https://daringfireball.net/projects/markdown/
- West, M.L. 1973. *Textual Criticism and Editorial Technique Applicable to Greek and Latin Texts*. Stuttgart.

## License

MIT
