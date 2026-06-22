"""Tests for txtdown writer."""

from pathlib import Path

from txtdown import Document, Line, Metadata, Section, write
from txtdown import parse as strict_parse

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def parse(source, strict=False, **kwargs):
    """Test helper: lenient by default so round-trip fragment tests need no
    front matter. The library default is strict=True."""
    return strict_parse(source, strict=strict, **kwargs)


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

    def test_roundtrip_compound_sections(self):
        """Compound chapter.section ids round-trip, including the chapter field."""
        original = """---
work: De Senectute
---

--- 3.7: First

Line one.
Line two.

--- 3.8

Line three.
"""
        doc1 = parse(original)
        written = write(doc1)
        doc2 = parse(written)

        assert "--- 3.7" in written
        assert doc2.sections[0].id == "3.7"
        assert doc2.sections[0].title == "First"
        assert doc2.sections[0].chapter == 3
        assert doc2.sections[1].id == "3.8"
        assert doc2.sections[1].chapter == 3


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


class TestWriteSpeaker:
    """Tests for writing speaker markup."""

    def test_write_speaker_line(self):
        """Speaker lines serialize as @Speaker: text."""
        doc = Document(
            sections=[
                Section(id="1", lines=[
                    Line("Quid sibi vult?", 1, speaker="Diocletianus"),
                ])
            ]
        )
        output = write(doc)
        assert "@Diocletianus: Quid sibi vult?" in output

    def test_write_non_speaker_line(self):
        """Non-speaker lines serialize without @ prefix."""
        doc = Document(
            sections=[
                Section(id="1", lines=[Line("Plain text.", 1)])
            ]
        )
        output = write(doc)
        assert "Plain text." in output
        assert "@" not in output

    def test_roundtrip_speaker(self):
        """Speaker markup round-trips correctly."""
        content = "@Agapes: Esto securus.\n@Diocletianus: Quid?"
        doc1 = parse(content)
        written = write(doc1)
        doc2 = parse(written)

        assert len(doc2.sections[0].lines) == 2
        assert doc2.sections[0].lines[0].speaker == "Agapes"
        assert doc2.sections[0].lines[0].text == "Esto securus."
        assert doc2.sections[0].lines[1].speaker == "Diocletianus"
        assert doc2.sections[0].lines[1].text == "Quid?"

    def test_roundtrip_speaker_single_word(self):
        """Single-word speaker names round-trip correctly."""
        content = "@Coniunx: Heu, heu!"
        doc1 = parse(content)
        written = write(doc1)
        doc2 = parse(written)

        line = doc2.sections[0].lines[0]
        assert line.speaker == "Coniunx"
        assert line.text == "Heu, heu!"

    def test_roundtrip_mixed(self):
        """Mixed speaker and non-speaker lines round-trip correctly."""
        content = "Stage direction.\n@Hirena: My line.\nAnother direction."
        doc1 = parse(content)
        written = write(doc1)
        doc2 = parse(written)

        lines = doc2.sections[0].lines
        assert len(lines) == 3
        assert lines[0].speaker is None
        assert lines[0].text == "Stage direction."
        assert lines[1].speaker == "Hirena"
        assert lines[1].text == "My line."
        assert lines[2].speaker is None
        assert lines[2].text == "Another direction."


class TestWriteQuotes:
    """Cross-source quotation (> markup) writing and round-trip."""

    def test_quote_written_with_marker(self):
        """A quote line serializes with a leading > marker."""
        doc = Document(
            sections=[
                Section(id="1", lines=[Line("a quoted verse", 1, is_quote=True)])
            ]
        )
        output = write(doc)
        assert "> a quoted verse" in output

    def test_plain_line_no_marker(self):
        """Non-quote lines serialize without a > marker."""
        doc = Document(
            sections=[Section(id="1", lines=[Line("plain prose", 1)])]
        )
        output = write(doc)
        assert "> " not in output

    def test_roundtrip_quote(self):
        """A quote among prose round-trips correctly."""
        content = (
            "Quamquam Ennius recte:\n"
            "> Amicus certus in re incerta cernitur,\n"
            "tamen haec duo levitatis."
        )
        doc1 = parse(content)
        doc2 = parse(write(doc1))
        assert doc1 == doc2
        assert [ln.is_quote for ln in doc2.sections[0].lines] == [False, True, False]

    def test_roundtrip_multi_line_quote(self):
        """A multi-line quote block round-trips correctly."""
        content = (
            "> Negat quis, nego; ait, aio; postremo imperavi egomet mihi\n"
            "> Omnia adsentari,"
        )
        doc1 = parse(content)
        doc2 = parse(write(doc1))
        assert doc1 == doc2
        assert all(ln.is_quote for ln in doc2.sections[0].lines)
