"""Tests for txtdown parser."""

from pathlib import Path

import pytest

from txtdown import Document, Line, Section, parse

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


class TestSectionTitles:
    """Tests for section titles."""

    def test_section_with_title(self):
        """Parse section with title."""
        content = """--- prooemium: Introduction

This is the introduction.

--- 1: Book One

First book content.
"""
        doc = parse(content)

        assert len(doc.sections) == 2
        assert doc.sections[0].id == "prooemium"
        assert doc.sections[0].title == "Introduction"
        assert doc.sections[1].id == "1"
        assert doc.sections[1].title == "Book One"

    def test_section_title_round_trip(self):
        """Section titles survive round-trip."""
        from txtdown import write

        content = """--- intro: Preface

Opening remarks.
"""
        doc = parse(content)
        output = write(doc)
        doc2 = parse(output)

        assert doc2.sections[0].id == "intro"
        assert doc2.sections[0].title == "Preface"


class TestIndexAccess:
    """Tests for 1-indexed bracket access."""

    def test_document_getitem(self):
        """Document[] uses 1-indexed access."""
        content = """--- 1

First section.

--- 2

Second section.

--- 3

Third section.
"""
        doc = parse(content)

        assert doc[1].id == "1"
        assert doc[2].id == "2"
        assert doc[3].id == "3"

    def test_document_getitem_out_of_range(self):
        """Document[] raises IndexError for invalid index."""
        content = "Single section."
        doc = parse(content)

        with pytest.raises(IndexError):
            doc[0]  # 0 is invalid (1-indexed)
        with pytest.raises(IndexError):
            doc[2]  # Only 1 section

    def test_section_getitem(self):
        """Section[] uses 1-indexed access."""
        content = """Line one.
Line two.
Line three.
"""
        doc = parse(content)
        section = doc.sections[0]

        assert section[1].text == "Line one."
        assert section[2].text == "Line two."
        assert section[3].text == "Line three."

    def test_section_getitem_out_of_range(self):
        """Section[] raises IndexError for invalid index."""
        content = "Only one line."
        doc = parse(content)
        section = doc.sections[0]

        with pytest.raises(IndexError):
            section[0]  # 0 is invalid
        with pytest.raises(IndexError):
            section[2]  # Only 1 line


class TestMalformedInput:
    """Tests for edge cases and malformed input."""

    def test_empty_content(self):
        """Empty content produces empty document."""
        doc = parse("")
        assert len(doc.sections) == 0

    def test_whitespace_only(self):
        """Whitespace-only content produces empty document."""
        doc = parse("   \n\n   \n")
        assert len(doc.sections) == 0

    def test_invalid_yaml_warns(self):
        """Invalid YAML in front matter emits warning."""
        content = """---
invalid: yaml: content: here
  bad indentation
---

Content.
"""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            doc = parse(content)
            # Should still parse, just with empty metadata
            assert len(doc.sections) == 1
            # Should have warned
            assert len(w) == 1
            assert "YAML" in str(w[0].message)

    def test_speaker_not_metadata(self):
        """Speaker lines should not be confused with metadata."""
        content = """---
author: Test
---

@Speaker: This is speech.
Regular line.
"""
        doc = parse(content)
        section = doc.sections[0]
        # Should have 2 lines, first is speaker
        assert len(section.lines) == 2
        assert section.lines[0].speaker == "Speaker"
        assert section.lines[0].text == "This is speech."
        assert section.lines[1].speaker is None
        assert section.lines[1].text == "Regular line."

    def test_unclosed_front_matter(self):
        """Unclosed front matter treated as no front matter."""
        content = """---
author: Test
This never closes

So this is all content.
"""
        doc = parse(content)
        # Should treat entire thing as content (no metadata)
        assert doc.metadata.author is None
        assert len(doc.sections) == 1


class TestSpeakerMarkup:
    """Tests for @Speaker: inline markup."""

    def test_speaker_extraction(self):
        """Speaker name is extracted from @Speaker: line."""
        doc = parse("@Diocletianus: Quid sibi vult ista?")
        line = doc.sections[0].lines[0]
        assert line.speaker == "Diocletianus"
        assert line.text == "Quid sibi vult ista?"

    def test_text_only_in_line_text(self):
        """line.text contains only the speech, not the speaker markup."""
        doc = parse("@Agapes: Esto securus curarum.")
        line = doc.sections[0].lines[0]
        assert "@" not in line.text
        assert "Agapes" not in line.text
        assert line.text == "Esto securus curarum."

    def test_section_text_excludes_speakers(self):
        """Section.text joins line.text values (speech only, no speaker markup)."""
        content = "@Dulcitius: Producite!\n@Milites: Ecce!"
        doc = parse(content)
        section = doc.sections[0]
        assert section.text == "Producite!\nEcce!"

    def test_mixed_speaker_and_plain_lines(self):
        """Sections can have both speaker and non-speaker lines."""
        content = "Stage direction here.\n@Hirena: My speech.\nAnother direction."
        doc = parse(content)
        lines = doc.sections[0].lines
        assert len(lines) == 3
        assert lines[0].speaker is None
        assert lines[0].text == "Stage direction here."
        assert lines[1].speaker == "Hirena"
        assert lines[1].text == "My speech."
        assert lines[2].speaker is None
        assert lines[2].text == "Another direction."

    def test_multi_word_speaker(self):
        """Multi-word speaker names are supported."""
        doc = parse("@Coniunx Dulcitii: Heu, heu!")
        line = doc.sections[0].lines[0]
        assert line.speaker == "Coniunx Dulcitii"
        assert line.text == "Heu, heu!"

    def test_line_numbering_with_speakers(self):
        """Speaker lines are numbered normally."""
        content = "@Agapes: First.\n@Chionia: Second.\n@Hirena: Third."
        doc = parse(content)
        lines = doc.sections[0].lines
        assert lines[0].number == 1
        assert lines[1].number == 2
        assert lines[2].number == 3

    def test_colon_in_speech_text(self):
        """Colons within the speech text are preserved."""
        doc = parse("@Diocletianus: In hoc: praecipue quod.")
        line = doc.sections[0].lines[0]
        assert line.speaker == "Diocletianus"
        assert line.text == "In hoc: praecipue quod."

    def test_non_speaker_at_line(self):
        """Lines starting with @ but not matching speaker pattern stay plain."""
        doc = parse("@incomplete")
        line = doc.sections[0].lines[0]
        assert line.speaker is None
        assert line.text == "@incomplete"

    def test_speaker_empty_speech(self):
        """Speaker with no speech text after colon."""
        doc = parse("@Milites:")
        line = doc.sections[0].lines[0]
        assert line.speaker == "Milites"
        assert line.text == ""

    def test_speaker_with_metadata(self):
        """Speaker lines in a document with metadata."""
        content = """---
author: Hrotsvitha
work: Dulcitius
---

@Diocletianus: Parentelae claritas.
@Agapes: Esto securus.
"""
        doc = parse(content)
        assert doc.metadata.author == "Hrotsvitha"
        lines = doc.sections[0].lines
        assert len(lines) == 2
        assert lines[0].speaker == "Diocletianus"
        assert lines[1].speaker == "Agapes"


class TestParseDulcitius:
    """Tests using the Dulcitius Scene I fixture."""

    @pytest.fixture
    def dulcitius_doc(self) -> Document:
        """Load and parse the Dulcitius fixture."""
        return parse(FIXTURES_DIR / "dulcitius-scene1.txtd")

    def test_metadata(self, dulcitius_doc):
        """Check metadata parsing."""
        assert dulcitius_doc.metadata.author == "Hrotsvitha"
        assert dulcitius_doc.metadata.work == "Dulcitius"
        assert dulcitius_doc.metadata.extras["genre"] == "drama"

    def test_section_count(self, dulcitius_doc):
        """Fixture has one scene."""
        assert len(dulcitius_doc.sections) == 1

    def test_section_id(self, dulcitius_doc):
        """Section ID is 'Scaena I'."""
        section = dulcitius_doc.sections[0]
        assert section.id == "Scaena I"
        assert not section.is_numbered

    def test_all_lines_have_speakers(self, dulcitius_doc):
        """Every line in Scene I is a speaker line."""
        section = dulcitius_doc.sections[0]
        for line in section.lines:
            assert line.speaker is not None, f"Line {line.number} missing speaker"

    def test_speaker_names(self, dulcitius_doc):
        """Check specific speaker names appear."""
        section = dulcitius_doc.sections[0]
        speakers = {line.speaker for line in section.lines}
        assert "Diocletianus" in speakers
        assert "Agapes" in speakers
        assert "Chionia" in speakers
        assert "Hirena" in speakers

    def test_first_speech(self, dulcitius_doc):
        """First speech is Diocletianus."""
        line = dulcitius_doc.sections[0].lines[0]
        assert line.speaker == "Diocletianus"
        assert line.text.startswith("Parentelae claritas")

    def test_text_is_speech_only(self, dulcitius_doc):
        """line.text contains only speech, no @ markup."""
        section = dulcitius_doc.sections[0]
        for line in section.lines:
            assert not line.text.startswith("@")

    def test_line_count(self, dulcitius_doc):
        """Scene I has 25 speech lines."""
        assert len(dulcitius_doc.sections[0].lines) == 25

    def test_round_trip(self, dulcitius_doc):
        """Dulcitius fixture round-trips correctly."""
        from txtdown import write

        written = write(dulcitius_doc)
        doc2 = parse(written)

        assert doc2.metadata.author == "Hrotsvitha"
        assert len(doc2.sections) == 1
        for l1, l2 in zip(dulcitius_doc.sections[0].lines, doc2.sections[0].lines):
            assert l1.speaker == l2.speaker
            assert l1.text == l2.text
