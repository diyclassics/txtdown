"""Tests for txtdown parser."""

from pathlib import Path

import pytest

from txtdown import Document, Line, Section
from txtdown import parse as strict_parse

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def parse(source, strict=False, **kwargs):
    """Test helper: lenient by default so fragment tests need no boilerplate.

    The library default is strict=True (front matter + ``work`` required); that
    behavior is exercised directly via ``strict_parse`` in TestStrictValidation.
    """
    return strict_parse(source, strict=strict, **kwargs)


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


class TestCompoundSectionIds:
    """Tests for compound ``N.M`` (chapter.section) section ids."""

    def test_compound_section(self):
        """Parse a compound chapter.section marker."""
        content = """--- 3.7

First line.
Second line.
"""
        doc = parse(content)

        assert len(doc.sections) == 1
        section = doc.sections[0]
        assert section.id == "3.7"
        assert section.levels == (3, 7)
        assert section.chapter == 3
        assert section.is_numbered

    def test_deep_hierarchy(self):
        """Parse an arbitrary-depth numeric label."""
        content = """--- 1.2.3

A line.
"""
        doc = parse(content)

        section = doc.sections[0]
        assert section.id == "1.2.3"
        assert section.levels == (1, 2, 3)
        assert section.chapter == 1  # first level
        assert section.is_numbered

    def test_flat_numeric_has_levels_but_no_chapter(self):
        """A flat "1" is numeric (levels=(1,)) but has no chapter."""
        content = """--- 1

A line.
"""
        doc = parse(content)

        section = doc.sections[0]
        assert section.levels == (1,)
        assert section.chapter is None
        assert section.is_numbered

    def test_compound_section_with_title(self):
        """Compound id with a title still splits on the colon."""
        content = """--- 3.7: De Senectute

First line.
"""
        doc = parse(content)

        section = doc.sections[0]
        assert section.id == "3.7"
        assert section.title == "De Senectute"
        assert section.chapter == 3

    def test_compound_section_with_metadata(self):
        """Section metadata immediately after a compound header still parses."""
        content = """--- 3.7
speaker_role: narrator
draft: true

First line.
"""
        doc = parse(content)

        section = doc.sections[0]
        assert section.id == "3.7"
        assert section.chapter == 3
        assert section.metadata["speaker_role"] == "narrator"
        assert section.metadata["draft"] is True

    def test_flat_and_named_sections_have_no_chapter(self):
        """Plain numeric and named ids leave chapter as None (regression guard)."""
        content = """--- 1

Numbered.

--- prooemium

Named.
"""
        doc = parse(content)

        assert doc.sections[0].id == "1"
        assert doc.sections[0].chapter is None
        assert doc.sections[1].id == "prooemium"
        assert doc.sections[1].chapter is None
        assert doc.sections[1].levels is None  # named id is not numeric

    def test_get_compound_section(self):
        """get("3.7") resolves to the compound section, not section 3 / line 7."""
        content = """--- 3.7

First line.
Second line.

--- 3.8

Other line.
"""
        doc = parse(content)

        section = doc.get("3.7")
        assert isinstance(section, Section)
        assert section.id == "3.7"
        assert section.chapter == 3

    def test_get_compound_line(self):
        """get("3.7.2") resolves to line 2 of compound section 3.7."""
        content = """--- 3.7

First line.
Second line.
"""
        doc = parse(content)

        line = doc.get("3.7.2")
        assert isinstance(line, Line)
        assert line.text == "Second line."
        assert line.number == 2

    def test_flat_citation_still_means_section_line(self):
        """In a non-compound doc, "2.3" still means section 2, line 3."""
        content = """A1
A2
A3

---

B1
B2
B3
"""
        doc = parse(content)

        line = doc.get("2.3")
        assert isinstance(line, Line)
        assert line.text == "B3"


class TestValidate:
    """Tests for opt-in structural validation via doc.validate()."""

    def test_clean_hierarchy_has_no_issues(self):
        content = """--- 1.1

a

--- 1.2

b

--- 2.1

c
"""
        doc = parse(content)

        assert doc.validate() == []
        assert doc.is_valid

    def test_duplicate_label_is_error(self):
        content = """--- 3.7

a

--- 3.7

b
"""
        doc = parse(content)

        issues = doc.validate()
        kinds = {i.kind for i in issues}
        assert "duplicate_label" in kinds
        assert any(i.severity == "error" for i in issues)
        assert not doc.is_valid

    def test_out_of_order_is_error(self):
        content = """--- 3.7

a

--- 3.6

b
"""
        doc = parse(content)

        issues = doc.validate()
        assert any(i.kind == "out_of_order" and i.label == "3.6" for i in issues)
        assert not doc.is_valid

    def test_mixed_depth_is_warning_not_invalid(self):
        content = """--- 1.1

a

--- 1.2

b

--- 1.2.1

c
"""
        doc = parse(content)

        issues = doc.validate()
        mixed = [i for i in issues if i.kind == "mixed_depth"]
        assert len(mixed) == 1
        assert mixed[0].label == "1.2.1"
        assert mixed[0].severity == "warning"
        # A warning alone does not make the document invalid.
        assert doc.is_valid

    def test_named_sections_do_not_trigger_order_or_depth(self):
        content = """--- prooemium

a

--- epilogue

b
"""
        doc = parse(content)

        assert doc.validate() == []
        assert doc.is_valid

    def test_speaker_roster_matches_usage(self):
        content = """---
work: Test
speakers: [Alpha, Beta]
---

@Alpha: salve
@Beta: et tu
"""
        doc = parse(content)

        assert doc.validate() == []
        assert doc.is_valid

    def test_unknown_speaker_is_error(self):
        content = """---
work: Test
speakers: [Alpha, Beta]
---

@Alpha: salve
@Gamma: quis sum?
"""
        doc = parse(content)

        issues = doc.validate()
        assert any(
            i.kind == "unknown_speaker" and i.label == "Gamma" for i in issues
        )
        assert not doc.is_valid

    def test_unused_speaker_is_warning(self):
        content = """---
work: Test
speakers: [Alpha, Beta]
---

@Alpha: solus loquor
"""
        doc = parse(content)

        issues = doc.validate()
        unused = [i for i in issues if i.kind == "unused_speaker"]
        assert len(unused) == 1
        assert unused[0].label == "Beta"
        assert unused[0].severity == "warning"
        # A warning alone does not make the document invalid.
        assert doc.is_valid

    def test_no_roster_means_no_speaker_checks(self):
        # Speakers used but no roster declared (the Dulcitius case): not flagged.
        content = """---
work: Test
---

@Alpha: salve
@Beta: et tu
"""
        doc = parse(content)

        assert not any(
            i.kind in ("unknown_speaker", "unused_speaker") for i in doc.validate()
        )
        assert doc.is_valid


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

    def test_multi_word_speaker_not_supported(self):
        """Multi-word speaker names are not supported; parsed as plain text."""
        doc = parse("@Coniunx Dulcitii: Heu, heu!")
        line = doc.sections[0].lines[0]
        assert line.speaker is None
        assert line.text == "@Coniunx Dulcitii: Heu, heu!"

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


class TestExplicitLineNumbering:
    """Tests for explicit line numbering (leading prefix and trailing label)."""

    def test_leading_prefix_matches_implicit(self):
        """Explicit N. prefix produces same result as implicit numbering."""
        implicit = parse("--- 3\n\nCum adhuc, inquit.\net ego dixi ei.")
        explicit = parse("--- 3\n\n1. Cum adhuc, inquit.\n2. et ego dixi ei.")

        s1, s2 = implicit.sections[0], explicit.sections[0]
        assert len(s1.lines) == len(s2.lines)
        for l1, l2 in zip(s1.lines, s2.lines):
            assert l1.number == l2.number
            assert l1.text == l2.text

    def test_leading_prefix_stripped(self):
        """Leading N. prefix is stripped from line text."""
        doc = parse("1. First line.\n2. Second line.")
        assert doc.sections[0].lines[0].text == "First line."
        assert doc.sections[0].lines[1].text == "Second line."

    def test_leading_prefix_reordering(self):
        """Leading prefixes override auto-numbering for reordered lines."""
        content = (
            "Suave, mari magno\n"
            "e terra magnum\n"
            "non quia vexari\n"
            "sed quibus ipse\n"
            "6. suave etiam belli\n"
            "5. per campos instructa\n"
            "7. sed nihil dulcius est\n"
            "edita doctrina\n"
            "despicere unde queas\n"
            "errare atque viam\n"
        )
        doc = parse(content)
        lines = doc.sections[0].lines

        assert lines[0].number == 1  # auto
        assert lines[1].number == 2  # auto
        assert lines[2].number == 3  # auto
        assert lines[3].number == 4  # auto
        assert lines[4].number == 6  # explicit
        assert lines[4].text == "suave etiam belli"
        assert lines[5].number == 5  # explicit (out of order)
        assert lines[5].text == "per campos instructa"
        assert lines[6].number == 7  # explicit
        assert lines[7].number == 8  # auto (continues from 7)
        assert lines[8].number == 9  # auto
        assert lines[9].number == 10  # auto

    def test_mixed_explicit_implicit(self):
        """Explicit numbers that match auto-increment are harmless."""
        doc = parse("1. First.\n2. Second.\n3. Third.")
        lines = doc.sections[0].lines
        assert [ln.number for ln in lines] == [1, 2, 3]
        assert [ln.text for ln in lines] == ["First.", "Second.", "Third."]

    def test_trailing_label(self):
        """Trailing labels are extracted into Line.label."""
        content = (
            "propterea eri imperium exsequor;         980\n"
            "atque mihi id prodest.\n"
        )
        doc = parse(content)
        lines = doc.sections[0].lines

        assert lines[0].text == "propterea eri imperium exsequor;"
        assert lines[0].label == "980"
        assert lines[0].number == 1  # auto-incremented
        assert lines[1].label is None
        assert lines[1].number == 2

    def test_trailing_label_with_letter(self):
        """Trailing labels can include a letter suffix (983a, 983b)."""
        content = (
            "[servi, qui cum culpa carent]         983a\n"
            "[nam illi, qui nil metuont]         983b\n"
        )
        doc = parse(content)
        lines = doc.sections[0].lines

        assert lines[0].label == "983a"
        assert lines[1].label == "983b"

    def test_trailing_label_not_false_positive(self):
        """Single space before a number is not a trailing label."""
        doc = parse("anno 203 facta est.")
        line = doc.sections[0].lines[0]
        assert line.label is None
        assert line.text == "anno 203 facta est."

    def test_citation_by_label(self):
        """doc.get() can find lines by label."""
        content = (
            "--- 1\n\n"
            "first line         980\n"
            "second line\n"
            "third line         983a\n"
        )
        doc = parse(content)

        line = doc.get("1.980")
        assert line.text == "first line"

        line = doc.get("1.983a")
        assert line.text == "third line"

    def test_citation_by_number_still_works(self):
        """Numeric citation still works alongside labels."""
        content = (
            "--- 1\n\n"
            "first line         980\n"
            "second line\n"
        )
        doc = parse(content)

        line = doc.get("1.1")
        assert line.text == "first line"

        line = doc.get("1.2")
        assert line.text == "second line"

    def test_leading_prefix_with_speaker(self):
        """Leading prefix works combined with speaker markup."""
        doc = parse("3. @Perpetua: Christiana sum.")
        line = doc.sections[0].lines[0]
        assert line.number == 3
        assert line.speaker == "Perpetua"
        assert line.text == "Christiana sum."

    def test_round_trip_reordered_lines(self):
        """Reordered lines round-trip with explicit prefixes preserved."""
        from txtdown import write

        content = (
            "line one\n"
            "line two\n"
            "4. line four\n"
            "3. line three\n"
            "line five\n"
        )
        doc = parse(content)
        written = write(doc)
        doc2 = parse(written)

        lines1 = doc.sections[0].lines
        lines2 = doc2.sections[0].lines
        for l1, l2 in zip(lines1, lines2):
            assert l1.number == l2.number
            assert l1.text == l2.text

    def test_round_trip_trailing_labels(self):
        """Trailing labels round-trip correctly."""
        from txtdown import write

        content = (
            "first line         980\n"
            "second line\n"
            "third line         983a\n"
        )
        doc = parse(content)
        written = write(doc)
        doc2 = parse(written)

        for l1, l2 in zip(doc.sections[0].lines, doc2.sections[0].lines):
            assert l1.text == l2.text
            assert l1.label == l2.label
            assert l1.number == l2.number


class TestQuoteMarkup:
    """Tests for > cross-source quotation markup."""

    def test_quote_extraction(self):
        """A > line is flagged as a quote with the marker stripped."""
        doc = parse("> Amicus certus in re incerta cernitur,")
        line = doc.sections[0].lines[0]
        assert line.is_quote is True
        assert line.text == "Amicus certus in re incerta cernitur,"

    def test_quote_marker_not_in_text(self):
        """The > marker does not survive in line.text."""
        doc = parse("> Obsequium amicos, veritas odium parit.")
        line = doc.sections[0].lines[0]
        assert not line.text.startswith(">")

    def test_quote_without_space(self):
        """A > with no following space still parses as a quote."""
        doc = parse(">Negat quis, nego;")
        line = doc.sections[0].lines[0]
        assert line.is_quote is True
        assert line.text == "Negat quis, nego;"

    def test_plain_line_not_quote(self):
        """Ordinary lines have is_quote False."""
        doc = parse("Quamquam Ennius recte:")
        line = doc.sections[0].lines[0]
        assert line.is_quote is False

    def test_multi_line_quote(self):
        """Consecutive > lines each flag as quotes."""
        content = (
            "> Negat quis, nego; ait, aio; postremo imperavi egomet mihi\n"
            "> Omnia adsentari,"
        )
        doc = parse(content)
        lines = doc.sections[0].lines
        assert len(lines) == 2
        assert all(ln.is_quote for ln in lines)
        assert lines[1].text == "Omnia adsentari,"

    def test_quote_among_prose(self):
        """A quote embedded in prose: only the > line is a quote."""
        content = (
            "Quamquam Ennius recte:\n"
            "> Amicus certus in re incerta cernitur,\n"
            "tamen haec duo levitatis."
        )
        doc = parse(content)
        lines = doc.sections[0].lines
        assert [ln.is_quote for ln in lines] == [False, True, False]
        assert lines[0].text == "Quamquam Ennius recte:"
        assert lines[2].text == "tamen haec duo levitatis."

    def test_quote_numbering(self):
        """Quote lines are auto-numbered in sequence like any line."""
        content = "First prose.\n> a quoted verse\nMore prose."
        doc = parse(content)
        lines = doc.sections[0].lines
        assert [ln.number for ln in lines] == [1, 2, 3]

    def test_quote_not_speaker(self):
        """A quote line is not parsed as a speaker line."""
        doc = parse("> @Diocletianus is mentioned in this quote")
        line = doc.sections[0].lines[0]
        assert line.is_quote is True
        assert line.speaker is None

    def test_quote_text_is_verbatim(self):
        """Quoted text is preserved verbatim (no line-number extraction)."""
        doc = parse("> 1. ut ait idem Terentius")
        line = doc.sections[0].lines[0]
        assert line.is_quote is True
        assert line.text == "1. ut ait idem Terentius"


class TestParseExamples:
    """The shipped example files parse and round-trip correctly."""

    EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

    def test_cicero_quotes(self):
        """The Cicero example flags its Ennius/Terence quotations."""
        doc = parse(self.EXAMPLES_DIR / "cicero-de-amicitia.txtd")
        quotes = [ln.text for s in doc.sections for ln in s.lines if ln.is_quote]
        assert len(quotes) == 6
        assert quotes[0] == "Amicus certus in re incerta cernitur,"

    def test_augustine_quotes(self):
        """The Augustine example flags its Virgil quotations."""
        doc = parse(self.EXAMPLES_DIR / "augustine-civ-dei-1.2.txtd")
        quotes = [ln for s in doc.sections for ln in s.lines if ln.is_quote]
        assert len(quotes) >= 1
        assert all(not ln.text.startswith(">") for ln in quotes)

    def test_examples_round_trip(self):
        """Every shipped example round-trips through write()."""
        from txtdown import write

        for name in (
            "cicero-de-amicitia.txtd",
            "augustine-civ-dei-1.2.txtd",
            "sulpicia.txtd",
            "sulpicia-tei.txtd",
        ):
            doc = parse(self.EXAMPLES_DIR / name)
            assert parse(write(doc)) == doc

    def test_tei_example_strips_clean(self):
        """The TEI example yields tag-free plaintext with the West supplement
        kept literal, and validates clean."""
        doc = parse(self.EXAMPLES_DIR / "sulpicia-tei.txtd")
        assert "<persName>" not in doc.plain
        assert "<placeName" not in doc.plain
        assert "<milestone" not in doc.plain
        assert "<propinque>" in doc.plain  # West supplement, not a tag
        assert any(t.attrs.get("n") == "pleiades:413032" for t in doc.tags)
        assert doc.validate() == []


class TestStrictValidation:
    """parse() is strict by default: front matter with a `work` field required."""

    VALID = "---\nwork: Epistulae\nauthor: Sulpicia\n---\n\nTandem venit amor."

    def test_valid_document_ok(self):
        """A document with front matter and work parses without error."""
        doc = strict_parse(self.VALID)
        assert doc.metadata.work == "Epistulae"

    def test_missing_front_matter_raises(self):
        """No front matter block raises ValueError in strict mode."""
        with pytest.raises(ValueError, match="front matter"):
            strict_parse("Tandem venit amor, qualem texisse pudori")

    def test_missing_work_raises(self):
        """Front matter without a work field raises ValueError."""
        content = "---\nauthor: Sulpicia\n---\n\nTandem venit amor."
        with pytest.raises(ValueError, match="work"):
            strict_parse(content)

    def test_broken_yaml_names_the_real_cause(self):
        """Invalid front-matter YAML raises the YAML error in strict mode — it must
        NOT fall through to the misleading "requires a 'work' field" (the egeria
        failure: a quoted scalar followed by trailing content)."""
        content = ('---\nwork: Itinerarium\n'
                   'markup: "<text>" = editorial conjecture\n---\n\nText.')
        with pytest.raises(ValueError, match="YAML") as exc:
            strict_parse(content)
        assert "work" in content  # the field IS present; the YAML is what's broken
        assert "file line 3" in str(exc.value)

    def test_broken_yaml_warns_in_non_strict(self):
        """strict=False keeps the old tolerant behavior: warn, empty metadata."""
        content = ('---\nwork: Itinerarium\n'
                   'markup: "<text>" = editorial conjecture\n---\n\nText.')
        with pytest.warns(UserWarning, match="YAML"):
            doc = strict_parse(content, strict=False)
        assert doc.metadata.work is None
        assert doc.sections  # body still parsed

    def test_empty_string_raises(self):
        """An empty string has no front matter and raises in strict mode."""
        with pytest.raises(ValueError):
            strict_parse("")

    def test_strict_false_allows_fragment(self):
        """strict=False parses a fragment with no metadata."""
        doc = strict_parse("@Diocletianus: Quid?", strict=False)
        assert doc.sections[0].lines[0].speaker == "Diocletianus"

    def test_strict_false_allows_missing_work(self):
        """strict=False parses front matter without a work field."""
        doc = strict_parse("---\nauthor: Sulpicia\n---\n\nText.", strict=False)
        assert doc.metadata.author == "Sulpicia"
        assert doc.metadata.work is None

    def test_shipped_examples_pass_strict(self):
        """Every shipped example satisfies strict validation."""
        examples_dir = Path(__file__).parent.parent / "examples"
        for name in (
            "cicero-de-amicitia.txtd",
            "augustine-civ-dei-1.2.txtd",
            "sulpicia.txtd",
            "sulpicia-tei.txtd",
        ):
            doc = strict_parse(examples_dir / name)  # must not raise
            assert doc.metadata.work
