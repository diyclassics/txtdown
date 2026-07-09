<img src="https://raw.githubusercontent.com/diyclassics/txtdown/main/assets/txtdown-logo.jpg" alt="txtdown" width="400">

[![PyPI version](https://img.shields.io/pypi/v/txtdown.svg)](https://pypi.org/project/txtdown/)
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

## License

MIT
