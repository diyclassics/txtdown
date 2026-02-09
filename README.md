# txtdown

Minimal markup for Latin text collections using human-readable markup with inferrable hierarchical structure for scholarly citation.

## Installation

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

A `.txtd` file consists of optional YAML front matter followed by sections separated by horizontal rules (`---`).

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

The parser extracts the speaker name into `line.speaker` and keeps `line.text` as pure speech text — ideal for NLP pipelines that need clean text without markup. Multi-word speaker names are supported:

```
@Coniunx Dulcitii: Heu, heu! mi senior Dulciti, quid pateris?
```

```python
doc = parse("dulcitius.txtd")
for line in doc.sections[0].lines:
    print(f"{line.speaker}: {line.text}")
# Diocletianus: Quid sibi vult ista...
```

Non-speaker lines (stage directions, prose) have `line.speaker = None`. Speaker markup round-trips through `write()`.

### Inline Markup (planned)

Blockquotes for embedded verse in prose:

```
Nonne uidit Aeneas Priamum per aras

> Sanguine foedantem quos ipse sacrauerat ignes?

Nonne Diomedes et Vlixes

>   caesis summae custodibus arcis.
> Corripuere sacram effigiem manibusque cruentis
> Virgineas ausi diuae contingere uittas?
```

The parser preserves indentation. For NLP, TxtdownReader joins these into a single sentence:
`"Nonne uidit Aeneas Priamum per aras Sanguine foedantem quos ipse sacrauerat ignes?"`

### Metadata

Standard fields (all optional):

| Field | Description |
|-------|-------------|
| `author` | Author name |
| `work` | Work title |
| `source` | Source URL or reference |
| `scope` | Portion of work in file (e.g., `1-6` for books 1-6) |

Additional fields are preserved in `metadata.extras`.

## API Reference

### Functions

- `parse(path_or_content: str) -> Document` — Parse a `.txtd` file or string
- `write(doc: Document, path: str | None) -> str` — Write to file if path given; always returns serialized string

### Classes

- `Document` — Container with `metadata: Metadata` and `sections: list[Section]`
- `Section` — Container with `id: str`, `lines: list[Line]`, optional `title` and `metadata`
- `Line` — Container with `text: str`, `number: int`, and optional `speaker: str | None`
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
