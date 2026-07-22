"""Tests for inline TEI/XML tag tolerance (structural pairing, .plain, .tags)."""

from txtdown import Line, Tag, write
from txtdown import parse as _parse


def parse(source):
    return _parse(source, strict=False)


def kinds(doc):
    return [i.kind for i in doc.validate()]


class TestTagDetection:
    def test_matched_pair_is_a_tag(self):
        doc = parse("--- 1\narma <persName>Cato</persName> dixit\n")
        line = doc.sections[0].lines[0]
        assert line.plain == "arma Cato dixit"
        assert line.tags == [Tag("persName", {}, 5, 9)]

    def test_self_closing_is_a_tag(self):
        doc = parse("--- 1\nprima pars <pb n=\"2\"/>altera pars\n")
        line = doc.sections[0].lines[0]
        assert line.plain == "prima pars altera pars"
        assert line.tags == [Tag("pb", {"n": "2"}, 11, 11, self_closing=True)]

    def test_lone_west_supplement_stays_literal(self):
        doc = parse("--- 1\nsaeve <propinque>, viae\n")
        line = doc.sections[0].lines[0]
        assert line.plain == "saeve <propinque>, viae"
        assert line.tags == []
        assert doc.validate() == []

    def test_pleiades_attribute_example(self):
        # The named-entity example from Berti, Crane & Babeu 2026, p. 26.
        doc = parse(
            "--- 1\n"
            'urbs <placeName n="pleiades:874341">Alexandria</placeName> erat\n'
        )
        line = doc.sections[0].lines[0]
        assert line.plain == "urbs Alexandria erat"
        assert line.tags == [
            Tag("placeName", {"n": "pleiades:874341"}, 5, 15)
        ]

    def test_multiple_attributes_and_single_quotes(self):
        doc = parse(
            "--- 1\n"
            "vide <ref target='urn:cts:latinLit:phi0959' type=\"urn\">hoc</ref> nunc\n"
        )
        (tag,) = doc.sections[0].lines[0].tags
        assert tag.attrs == {"target": "urn:cts:latinLit:phi0959", "type": "urn"}

    def test_namespaced_name(self):
        doc = parse("--- 1\nen <tei:seg>verba</tei:seg> mea\n")
        (tag,) = doc.sections[0].lines[0].tags
        assert tag.name == "tei:seg"

    def test_names_are_case_sensitive(self):
        # <persName> is not closed by </persname>: both stay literal.
        doc = parse("--- 1\nen <persName>Cato</persname> dixit\n")
        line = doc.sections[0].lines[0]
        assert "<persName>" in line.plain
        assert line.tags == []

    def test_comparison_operators_stay_literal(self):
        doc = parse("--- 1\nnumeri x < 3 et y > 4 manent\n")
        line = doc.sections[0].lines[0]
        assert line.plain == line.text
        assert doc.validate() == []

    def test_comment_and_pi_stay_literal(self):
        doc = parse("--- 1\nverba <!-- nota --> et <?pi?> manent\n")
        line = doc.sections[0].lines[0]
        assert line.plain == line.text

    def test_tag_at_line_start_is_not_structural_markup(self):
        # A line-initial tag must not be read as a section/speaker/quote marker.
        doc = parse("--- 1\n<persName>Cato</persName> dixit\n")
        line = doc.sections[0].lines[0]
        assert line.speaker is None
        assert line.is_quote is False
        assert line.plain == "Cato dixit"
        assert line.tags == [Tag("persName", {}, 0, 4)]

    def test_west_and_tei_coexist_in_one_line(self):
        doc = parse(
            "--- 1\n"
            "<persName>Marcus</persName> ait †cruce† et <domino> {seclusa} manet\n"
        )
        line = doc.sections[0].lines[0]
        assert line.plain == "Marcus ait †cruce† et <domino> {seclusa} manet"
        assert [t.name for t in line.tags] == ["persName"]

    def test_stray_close_is_stripped_but_flagged(self):
        # West never writes </word>, so a stray end tag is markup, not text.
        doc = parse("--- 1\nverba prima</quote> sequuntur\n")
        line = doc.sections[0].lines[0]
        assert line.plain == "verba prima sequuntur"
        assert kinds(doc) == ["unmatched_tag"]

    def test_malformed_end_tags_stay_literal(self):
        doc = parse("--- 1\nen </x/> et </x a=\"b\"> manent\n")
        assert doc.sections[0].lines[0].plain == "en </x/> et </x a=\"b\"> manent"


class TestPlainAccessors:
    DOC = (
        "--- 1\n"
        "arma <persName>Cato</persName> canit\n"
        "altera linea manet\n"
        "\n"
        "--- 2\n"
        "tertia <pb n=\"2\"/>linea venit\n"
    )

    def test_line_plain(self):
        doc = parse(self.DOC)
        assert doc.sections[0].lines[0].plain == "arma Cato canit"

    def test_section_plain_joins_with_newline(self):
        doc = parse(self.DOC)
        assert doc.sections[0].plain == "arma Cato canit\naltera linea manet"

    def test_document_plain_joins_sections_with_blank_line(self):
        doc = parse(self.DOC)
        assert doc.plain == (
            "arma Cato canit\naltera linea manet\n\ntertia linea venit"
        )

    def test_plain_equals_text_when_no_tags(self):
        doc = parse("--- 1\nTandem venit amor, qualem texisse pudori\n")
        section = doc.sections[0]
        assert section.plain == section.text
        assert doc.plain == section.text

    def test_whitespace_preserved_verbatim(self):
        # Stripping never normalizes whitespace: adjacent spaces stay.
        doc = parse("--- 1\nverbum <pb/> alterum\n")
        assert doc.sections[0].lines[0].plain == "verbum  alterum"

    def test_bare_line_falls_back_to_line_scope(self):
        line = Line(text="en <q>verba</q> mea", number=1)
        assert line.plain == "en verba mea"
        assert line.tags == [Tag("q", {}, 3, 8)]

    def test_bare_line_unmatched_open_is_literal(self):
        # Without a document, the pairing scope is the line itself, so an
        # opener whose close would sit on a later line stays literal.
        line = Line(text="en <q>verba mea", number=1)
        assert line.plain == "en <q>verba mea"


class TestTagSpans:
    def test_multiple_tags_one_line_offsets(self):
        doc = parse(
            "--- 1\n"
            "<persName>Cato</persName> et <persName>Cicero</persName> dixerunt\n"
        )
        line = doc.sections[0].lines[0]
        assert line.plain == "Cato et Cicero dixerunt"
        first, second = line.tags
        assert line.plain[first.start:first.end] == "Cato"
        assert line.plain[second.start:second.end] == "Cicero"

    def test_adjacent_tags(self):
        doc = parse("--- 1\n<q>a</q><q>b</q>\n")
        line = doc.sections[0].lines[0]
        assert line.plain == "ab"
        assert line.tags == [Tag("q", {}, 0, 1), Tag("q", {}, 1, 2)]

    def test_zero_width_milestone_span(self):
        doc = parse("--- 1\nante <lb/>post\n")
        (tag,) = doc.sections[0].lines[0].tags
        assert tag.start == tag.end == 5
        assert tag.self_closing is True

    def test_cross_line_pair_in_section_tags_not_line_tags(self):
        doc = parse(
            "--- 1\n"
            "una <quote>pars incipit\n"
            "et hic desinit</quote> tandem\n"
        )
        section = doc.sections[0]
        assert section.lines[0].tags == []
        assert section.lines[1].tags == []
        assert section.lines[0].plain == "una pars incipit"
        (tag,) = section.tags
        assert section.plain[tag.start:tag.end] == "pars incipit\net hic desinit"

    def test_cross_section_pair_only_in_document_tags(self):
        doc = parse(
            "--- 1\n"
            "hic <quote>oratio incipit\n"
            "\n"
            "--- 2\n"
            "et hic desinit</quote> tandem\n"
        )
        assert doc.sections[0].tags == []
        assert doc.sections[1].tags == []
        (tag,) = doc.tags
        assert doc.plain[tag.start:tag.end] == (
            "oratio incipit\n\net hic desinit"
        )
        assert "tag_crosses_section" in kinds(doc)


class TestTagValidation:
    def test_stray_close_warns(self):
        doc = parse("--- 1\nverba</quote> manent\n")
        (issue,) = doc.validate()
        assert issue.kind == "unmatched_tag"
        assert issue.severity == "warning"
        assert issue.label == "1.1"
        assert doc.is_valid

    def test_unclosed_attribute_tag_warns_and_stays_literal(self):
        # Attributes mark intent to write XML, so an unclosed one is
        # suspicious — unlike a bare <word>, which is West notation.
        doc = parse("--- 1\nurbs <placeName n=\"pleiades:874341\"> erat\n")
        line = doc.sections[0].lines[0]
        assert "<placeName" in line.plain
        (issue,) = doc.validate()
        assert issue.kind == "unmatched_tag"
        assert issue.severity == "warning"

    def test_overlapping_pairs_warn_but_strip(self):
        doc = parse("--- 1\n<a>una <b>ambae</a> altera</b> res\n")
        line = doc.sections[0].lines[0]
        assert line.plain == "una ambae altera res"
        issues = [i for i in doc.validate() if i.kind == "tag_overlap"]
        assert len(issues) == 1
        assert issues[0].severity == "warning"

    def test_cross_section_pair_warns(self):
        doc = parse(
            "--- 1\n<quote>incipit\n\n--- 2\ndesinit</quote>\n"
        )
        issues = [i for i in doc.validate() if i.kind == "tag_crosses_section"]
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert issues[0].label == "1.1"

    def test_tag_only_line_warns(self):
        doc = parse(
            "--- 1\n"
            "prima linea\n"
            "<pb n=\"2\"/>\n"
            "tertia linea\n"
        )
        issues = [i for i in doc.validate() if i.kind == "tag_only_line"]
        assert len(issues) == 1
        assert issues[0].label == "1.2"
        # The trap being flagged: the milestone consumed line number 2.
        assert doc.sections[0].lines[2].number == 3

    def test_all_tag_issues_are_warnings(self):
        doc = parse(
            "--- 1\n"
            "stray</x> et <y n=\"1\"> hic\n"
            "<pb/>\n"
            "<a>una <b>ambae</a> altera</b>\n"
        )
        tag_issues = [
            i for i in doc.validate()
            if i.kind.startswith(("unmatched_tag", "tag_"))
        ]
        assert tag_issues and all(i.severity == "warning" for i in tag_issues)
        assert doc.is_valid

    def test_clean_tei_document_validates_clean(self):
        doc = parse(
            "--- 1\n"
            "arma <persName>Cato</persName> canit\n"
            "atque <placeName n=\"pleiades:874341\">Alexandria</placeName> manet\n"
        )
        assert doc.validate() == []


class TestQuoteTagInteraction:
    def test_attribute_quotes_are_not_speech(self):
        # Regression: before 0.4.0 the two ASCII quotes in the attribute
        # value produced false unmatched_quote errors.
        doc = parse(
            "--- 1\n"
            'urbs <placeName n="pleiades:874341">Alexandria</placeName> erat\n'
        )
        assert doc.validate() == []

    def test_real_speech_still_validated_around_tags(self):
        doc = parse(
            "--- 1\n"
            'tum <persName>Cato</persName> inquit: "oratio sine fine\n'
        )
        issues = [i for i in doc.validate() if i.kind == "unmatched_quote"]
        assert len(issues) == 1

    def test_speech_inside_quote_tags_pairs_normally(self):
        doc = parse(
            "--- 1\n"
            'ille <q>"salve," amice</q> dixit\n'
        )
        assert doc.validate() == []


class TestTagRoundTrip:
    def test_tags_survive_write_parse(self):
        source = (
            "--- 1\n"
            "arma <persName>Cato</persName> canit\n"
            "saeve <propinque>, viae\n"
            "una <quote>pars incipit\n"
            "et hic desinit</quote> tandem\n"
        )
        doc = parse(source)
        assert parse(write(doc)) == doc

    def test_text_keeps_tags_verbatim(self):
        doc = parse("--- 1\narma <persName>Cato</persName> canit\n")
        assert doc.sections[0].lines[0].text == (
            "arma <persName>Cato</persName> canit"
        )
        assert doc.sections[0].text == doc.sections[0].lines[0].text
