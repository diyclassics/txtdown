"""Tests for txtdown parser."""

from pathlib import Path

import pytest

from txtdown import Document, Line, Metadata, Section, parse


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestParseBasic:
    """Basic parsing tests."""

    def test_parse_minimal(self):
        """Parse minimal document with just content."""
        content = "Line one\nLine two"
        doc = parse(content)

        assert len(doc.sections) == 1
        assert len(doc.sections[0].lines) == 2
        assert doc.sections[0].lines[0].text == "Line one"

    def test_parse_with_metadata(self):
        """Parse document with YAML front matter."""
        content = """---
author: Test Author
work: Test Work
---

First line of content.
"""
        doc = parse(content)

        assert doc.metadata.author == "Test Author"
        assert doc.metadata.work == "Test Work"
        assert len(doc.sections) == 1

    def test_parse_multiple_sections(self):
        """Parse document with multiple sections."""
        content = """---
author: Test
---

Section one line one.
Section one line two.

---

Section two line one.
Section two line two.
"""
        doc = parse(content)

        assert len(doc.sections) == 2
        assert doc.sections[0].id == "1"
        assert doc.sections[1].id == "2"
        assert len(doc.sections[0].lines) == 2
        assert len(doc.sections[1].lines) == 2


class TestParseSulpicia:
    """Tests using the Sulpicia fixture."""

    @pytest.fixture
    def sulpicia_doc(self) -> Document:
        """Load and parse the Sulpicia fixture."""
        return parse(FIXTURES_DIR / "sulpicia.txtd")

    def test_metadata(self, sulpicia_doc):
        """Check metadata parsing."""
        assert sulpicia_doc.metadata.author == "Sulpicia"
        assert sulpicia_doc.metadata.work == "Epistulae"
        assert "thelatinlibrary" in sulpicia_doc.metadata.source

    def test_section_count(self, sulpicia_doc):
        """Sulpicia has 6 poems."""
        assert len(sulpicia_doc.sections) == 6

    def test_section_ids(self, sulpicia_doc):
        """Sections should be numbered 1-6."""
        for i, section in enumerate(sulpicia_doc.sections):
            assert section.id == str(i + 1)
            assert section.is_numbered

    def test_first_poem_lines(self, sulpicia_doc):
        """First poem has 10 lines."""
        first_poem = sulpicia_doc.sections[0]
        assert len(first_poem.lines) == 10
        assert first_poem.lines[0].text.startswith("Tandem venit amor")

    def test_line_numbering(self, sulpicia_doc):
        """Lines should be numbered correctly within sections."""
        first_poem = sulpicia_doc.sections[0]
        for i, line in enumerate(first_poem.lines):
            assert line.number == i + 1


class TestCitation:
    """Tests for citation access."""

    @pytest.fixture
    def doc(self) -> Document:
        """Simple test document."""
        content = """---
author: Test
---

Line one.
Line two.
Line three.

---

Second section line one.
Second section line two.
"""
        return parse(content)

    def test_get_section(self, doc):
        """Get section by citation."""
        section = doc.get("1")
        assert isinstance(section, Section)
        assert len(section.lines) == 3

    def test_get_line(self, doc):
        """Get line by citation."""
        line = doc.get("1.2")
        assert isinstance(line, Line)
        assert line.text == "Line two."
        assert line.number == 2

    def test_get_from_second_section(self, doc):
        """Get line from second section."""
        line = doc.get("2.1")
        assert line.text == "Second section line one."

    def test_get_missing_section(self, doc):
        """Raise KeyError for missing section."""
        with pytest.raises(KeyError):
            doc.get("99")

    def test_get_missing_line(self, doc):
        """Raise KeyError for missing line."""
        with pytest.raises(KeyError):
            doc.get("1.99")


class TestExplicitSectionIds:
    """Tests for explicit section IDs."""

    def test_named_section(self):
        """Parse document with named sections."""
        content = """---
author: Test
---

--- prooemium

Introduction text.

--- 1

First numbered section.
"""
        doc = parse(content)

        assert len(doc.sections) == 2
        assert doc.sections[0].id == "prooemium"
        assert not doc.sections[0].is_numbered
        assert doc.sections[1].id == "1"
        assert doc.sections[1].is_numbered

    def test_get_named_section(self):
        """Access named section by citation."""
        content = """--- prooemium

Intro here.

--- epilogue

Outro here.
"""
        doc = parse(content)

        section = doc.get("prooemium")
        assert section.lines[0].text == "Intro here."


class TestMetadataExtras:
    """Tests for extra metadata fields."""

    def test_extra_fields_preserved(self):
        """Unknown fields go to extras."""
        content = """---
author: Test
custom_field: custom value
another: 123
---

Content.
"""
        doc = parse(content)

        assert doc.metadata.extras["custom_field"] == "custom value"
        assert doc.metadata.extras["another"] == 123

    def test_scope_field(self):
        """Scope field parsed correctly."""
        content = """---
author: Virgil
work: Aeneid
scope: 1
---

Arma virumque cano...
"""
        doc = parse(content)

        assert doc.metadata.scope == "1"
