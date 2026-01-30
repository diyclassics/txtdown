"""Tests for txtdown writer."""

from pathlib import Path

import pytest

from txtdown import Document, Line, Metadata, Section, parse, write


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestWriteBasic:
    """Basic writing tests."""

    def test_write_minimal(self):
        """Write minimal document."""
        doc = Document(
            sections=[
                Section(id="1", lines=[Line("Hello world", 1)])
            ]
        )
        output = write(doc)

        assert "Hello world" in output
        assert output.endswith("\n")

    def test_write_with_metadata(self):
        """Write document with metadata."""
        doc = Document(
            metadata=Metadata(author="Test Author", work="Test Work"),
            sections=[
                Section(id="1", lines=[Line("Content", 1)])
            ]
        )
        output = write(doc)

        assert "---" in output
        assert "author: Test Author" in output
        assert "work: Test Work" in output

    def test_write_multiple_sections(self):
        """Write document with multiple sections."""
        doc = Document(
            sections=[
                Section(id="1", lines=[Line("First", 1)]),
                Section(id="2", lines=[Line("Second", 1)]),
            ]
        )
        output = write(doc)

        # Count section separators
        separator_count = output.count("\n---\n")
        assert separator_count == 1  # One separator between sections


class TestRoundTrip:
    """Round-trip tests: parse → write → parse should preserve content."""

    def test_roundtrip_simple(self):
        """Simple document round-trips correctly."""
        original = """---
author: Test
work: Example
---

Line one.
Line two.

---

Second section.
"""
        doc1 = parse(original)
        written = write(doc1)
        doc2 = parse(written)

        assert doc2.metadata.author == doc1.metadata.author
        assert doc2.metadata.work == doc1.metadata.work
        assert len(doc2.sections) == len(doc1.sections)

        for s1, s2 in zip(doc1.sections, doc2.sections):
            assert s1.id == s2.id
            assert len(s1.lines) == len(s2.lines)
            for l1, l2 in zip(s1.lines, s2.lines):
                assert l1.text == l2.text

    def test_roundtrip_sulpicia(self):
        """Sulpicia fixture round-trips correctly."""
        doc1 = parse(FIXTURES_DIR / "sulpicia.txtd")
        written = write(doc1)
        doc2 = parse(written)

        # Metadata preserved
        assert doc2.metadata.author == "Sulpicia"
        assert doc2.metadata.work == "Epistulae"

        # Section count preserved
        assert len(doc2.sections) == 6

        # Content preserved
        for s1, s2 in zip(doc1.sections, doc2.sections):
            assert s1.id == s2.id
            assert len(s1.lines) == len(s2.lines)
            for l1, l2 in zip(s1.lines, s2.lines):
                assert l1.text == l2.text

    def test_roundtrip_named_sections(self):
        """Named sections round-trip correctly."""
        original = """---
author: Test
---

--- prooemium

Introduction.

--- 1

First section.

--- epilogue

Conclusion.
"""
        doc1 = parse(original)
        written = write(doc1)
        doc2 = parse(written)

        assert doc2.sections[0].id == "prooemium"
        assert doc2.sections[1].id == "1"
        assert doc2.sections[2].id == "epilogue"


class TestWriteToFile:
    """Tests for writing to file."""

    def test_write_to_file(self, tmp_path):
        """Write document to file."""
        doc = Document(
            metadata=Metadata(author="Test"),
            sections=[Section(id="1", lines=[Line("Content", 1)])]
        )

        output_path = tmp_path / "output.txtd"
        write(doc, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "author: Test" in content
        assert "Content" in content

    def test_write_and_reread(self, tmp_path):
        """Write to file, then read back."""
        doc1 = Document(
            metadata=Metadata(author="Roundtrip Test"),
            sections=[
                Section(id="1", lines=[
                    Line("Line one", 1),
                    Line("Line two", 2),
                ])
            ]
        )

        output_path = tmp_path / "test.txtd"
        write(doc1, output_path)
        doc2 = parse(output_path)

        assert doc2.metadata.author == "Roundtrip Test"
        assert len(doc2.sections[0].lines) == 2
