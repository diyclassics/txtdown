"""Tests for inline cross-references: Markdown [X](Y) links and TEI ref/quote tags.

References encode a link to an opaque target URI; txtdown never resolves them.
"""

from txtdown import Reference, write
from txtdown import parse as _parse


def parse(source):
    return _parse(source, strict=False)


class TestMarkdownLinks:
    def test_link_strips_to_display_and_captures_target(self):
        doc = parse("--- 1\nvide [Alexandria](urn:cts:x) hic\n")
        line = doc.sections[0].lines[0]
        assert line.plain == "vide Alexandria hic"
        assert line.refs == [
            Reference("Alexandria", "urn:cts:x", "link", "markdown", 5, 15)
        ]

    def test_offsets_index_into_plain(self):
        doc = parse("--- 1\n[Vita insepulta](naevius.txtd#praetexta.2) canit\n")
        r = doc.sections[0].lines[0].refs[0]
        line = doc.sections[0].lines[0]
        assert line.plain[r.start:r.end] == "Vita insepulta" == r.display

    def test_target_is_opaque_uri(self):
        for target in (
            "naevius-clastidium.txtd#praetexta.2",
            "urn:cts:latinLit:phi0959.phi001:9.78",
            "https://example.com/x",
            "#9.78",
        ):
            doc = parse(f"--- 1\n[x]({target})\n")
            assert doc.sections[0].lines[0].refs[0].target == target

    def test_bare_bracket_stays_literal(self):
        # No (target) immediately after ] -> lacuna / editorial bracket, not a link.
        doc = parse("--- 1\nlacuna [- - -] et [verbum] manent\n")
        line = doc.sections[0].lines[0]
        assert line.plain == "lacuna [- - -] et [verbum] manent"
        assert line.refs == []

    def test_multiple_links_one_line_offsets(self):
        doc = parse("--- 1\n[a](x) et [bee](y) canit\n")
        line = doc.sections[0].lines[0]
        assert line.plain == "a et bee canit"
        first, second = line.refs
        assert line.plain[first.start:first.end] == "a"
        assert line.plain[second.start:second.end] == "bee"
        assert (first.target, second.target) == ("x", "y")

    def test_link_on_cross_source_quote_line(self):
        # The witness case: a > quotation whose text links to the fragment.
        doc = parse(
            "--- 9.78\n"
            "> [Vita insepulta laetus in patriam redux]"
            "(naevius-clastidium.txtd#praetexta.2)\n"
        )
        line = doc.sections[0].lines[0]
        assert line.is_quote is True
        assert line.plain == "Vita insepulta laetus in patriam redux"
        assert line.refs[0].target == "naevius-clastidium.txtd#praetexta.2"

    def test_whitespace_preserved(self):
        doc = parse("--- 1\nante [x](y) post\n")
        assert doc.sections[0].lines[0].plain == "ante x post"


class TestTeiReferences:
    def test_ref_target_promoted(self):
        doc = parse('--- 1\n<ref target="urn:cts:x">Alexandria</ref>\n')
        r = doc.sections[0].lines[0].refs[0]
        assert (r.kind, r.syntax, r.display, r.target) == (
            "ref", "tei", "Alexandria", "urn:cts:x"
        )

    def test_quote_corresp_promoted(self):
        doc = parse('--- 1\n<quote corresp="naevius#praet.2">Vita insepulta</quote>\n')
        r = doc.sections[0].lines[0].refs[0]
        assert (r.kind, r.syntax, r.target) == ("quote", "tei", "naevius#praet.2")

    def test_plain_tag_without_link_attr_is_not_a_ref(self):
        doc = parse("--- 1\n<persName>Cato</persName> dixit\n")
        line = doc.sections[0].lines[0]
        assert line.refs == []
        assert [t.name for t in line.tags] == ["persName"]  # still a tag

    def test_selfclosing_pointer(self):
        doc = parse('--- 1\nante <ptr target="urn:cts:x"/> post\n')
        r = doc.sections[0].lines[0].refs[0]
        assert r.display == "" and r.target == "urn:cts:x"

    def test_link_inside_attribute_is_not_a_markdown_link(self):
        # A [x](y) inside an attribute value belongs to the tag, not a link.
        doc = parse('--- 1\n<ref target="a[b](c)d">text</ref>\n')
        refs = doc.sections[0].lines[0].refs
        assert len(refs) == 1
        assert refs[0].syntax == "tei" and refs[0].target == "a[b](c)d"


class TestRefsGranularity:
    def test_section_and_document_refs(self):
        doc = parse("--- 1\n[a](x) hic\n\n--- 2\n[b](y) illic\n")
        assert [r.target for r in doc.sections[0].refs] == ["x"]
        assert [r.target for r in doc.sections[1].refs] == ["y"]
        assert [r.target for r in doc.refs] == ["x", "y"]

    def test_section_ref_offsets_into_section_plain(self):
        doc = parse("--- 1\nprima linea\n[Vita](naevius#2) altera\n")
        section = doc.sections[0]
        r = section.refs[0]
        assert section.plain[r.start:r.end] == "Vita"


class TestRefsCoexistence:
    def test_tag_and_link_on_same_line(self):
        doc = parse('--- 1\n<persName>Cato</persName> dixit [hoc](urn:x)\n')
        line = doc.sections[0].lines[0]
        assert line.plain == "Cato dixit hoc"
        assert [t.name for t in line.tags] == ["persName"]
        r = line.refs[0]
        assert r.target == "urn:x"
        assert line.plain[r.start:r.end] == "hoc"  # offsets survive both strips

    def test_west_supplement_and_link_coexist(self):
        doc = parse("--- 1\nsaeve <propinque> et [redux](naevius#2)\n")
        line = doc.sections[0].lines[0]
        assert "<propinque>" in line.plain  # West supplement stays literal
        assert line.plain.endswith("redux")  # link display kept
        assert line.refs[0].target == "naevius#2"

    def test_link_display_containing_paired_tag(self):
        # Regression: a tag inside the display is *enclosed* by the link's
        # span. An overlap (rather than containment) skip test discarded the
        # link, leaking raw "[...](...)" into .plain and yielding no Reference.
        doc = parse(
            "--- 1\ndixit [<persName>Ennius</persName>](enn.txtd#1) verba\n"
        )
        line = doc.sections[0].lines[0]
        assert line.plain == "dixit Ennius verba"
        assert [t.name for t in line.tags] == ["persName"]
        r = line.refs[0]
        assert r.target == "enn.txtd#1"
        assert r.display == "Ennius"
        assert line.plain[r.start:r.end] == r.display

    def test_link_display_containing_selfclosing_tag(self):
        doc = parse("--- 1\nalter [a<pb/>b](x.txtd) finis\n")
        line = doc.sections[0].lines[0]
        assert line.plain == "alter ab finis"
        r = line.refs[0]
        assert r.target == "x.txtd"
        assert line.plain[r.start:r.end] == "ab" == r.display

    def test_link_display_partially_tagged(self):
        # Tag covers only part of the display: still one link, one tag.
        doc = parse("--- 1\n[Q. <persName>Ennius</persName>](enn.txtd#2)\n")
        line = doc.sections[0].lines[0]
        assert line.plain == "Q. Ennius"
        r = line.refs[0]
        assert r.target == "enn.txtd#2"
        assert line.plain[r.start:r.end] == "Q. Ennius"

    def test_tag_in_link_target_is_not_a_link(self):
        # Regression: containment-only skip kept a link whose raw span encloses
        # a tag sitting in the ](target) region. _strip deletes that region, so
        # the tag and link interleave rather than nest: the cursor ran backwards
        # and emitted negative offsets, and plain[t.start:t.end] silently
        # returned text from the end of the string.
        doc = parse("--- 1\n[x](y<z/>)\n")
        line = doc.sections[0].lines[0]
        assert line.plain == "[x](y)"  # not a link; syntax stays literal
        assert line.refs == []
        (tag,) = line.tags
        assert (tag.start, tag.end) == (5, 5)
        assert tag.start >= 0 and tag.end >= 0

    def test_paired_tag_in_link_target_is_not_a_link(self):
        doc = parse("--- 1\n[x](y<z>)</z> tail text here\n")
        line = doc.sections[0].lines[0]
        assert line.plain == "[x](y) tail text here"
        assert line.refs == []
        (tag,) = line.tags
        assert line.plain[tag.start:tag.end] == ")"
        assert tag.start >= 0 and tag.end >= 0

    def test_link_inside_attribute_value_stays_literal(self):
        # A West supplement whose text contains link syntax: the tag owns the
        # text, so nothing is stripped and no Reference is produced.
        doc = parse('--- 1\n<ref n="[a">b](c)\n')
        line = doc.sections[0].lines[0]
        assert line.plain == '<ref n="[a">b](c)'
        assert line.refs == []

    def test_no_negative_offsets_at_any_scope(self):
        # The same corrupted plain_pos propagated to line-, section-, and
        # document-scope tags, and into literal_spans (which validate() reads).
        doc = parse("--- 1\n[x](y<z/>)\n[a](b<c>)</c> more\n")
        scopes = [doc, doc.sections[0], *doc.sections[0].lines]
        for scope in scopes:
            for tag in scope.tags:
                assert tag.start >= 0, (scope, tag)
                assert tag.end >= 0, (scope, tag)
                assert scope.plain[tag.start:tag.end] is not None


class TestRefsRoundTrip:
    def test_links_survive_write_parse(self):
        src = (
            "--- 1\n"
            "> [Vita insepulta laetus in patriam redux]"
            "(naevius-clastidium.txtd#praetexta.2)\n"
            'et <ref target="urn:cts:x">Alexandria</ref> canit\n'
        )
        doc = parse(src)
        assert parse(write(doc)) == doc

    def test_text_keeps_link_syntax_verbatim(self):
        doc = parse("--- 1\n[x](y) hic\n")
        assert doc.sections[0].lines[0].text == "[x](y) hic"
