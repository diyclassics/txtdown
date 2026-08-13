"""Inline TEI/XML tag detection, pairing, and stripping.

On the markdown~HTML analogy, txtdown tolerates inline TEI/XML markup: a
project may wrap text in tags such as ``<persName>`` or
``<placeName n="pleiades:874341">`` and the document still parses, still
round-trips, and still yields clean plaintext for NLP via the ``.plain``
accessors on ``Line``, ``Section``, and ``Document``.

The parser itself never interprets angle brackets: tags pass through to
``Line.text`` verbatim (the same passthrough model as direct-speech quote
validation). Everything in this module is a lazy, read-only view computed
from the stored text.

Disambiguation vs. West (1973) editorial notation
-------------------------------------------------
In the CRAWL/LatinCy ecosystem ``<text>`` already means an editorial
supplement (West 1973), so a lone ``<dominus>`` must remain literal text.
The two are told apart *structurally*: an XML-shaped token counts as a tag
only when it is

- self-closing (``<pb/>``), or
- an end tag (``</persName>``), or
- a start tag with a matching end tag later in the document.

An unmatched start tag is literal text — a West supplement. A stray end tag
is still stripped (West notation never produces ``</word>``) but is
reported by validation. Other West notation (``†crux†``, ``{deletion}``,
``M(arcus)``) contains no angle brackets and is never affected.

Out of scope (always literal): comments, CDATA, processing instructions,
DOCTYPE; unquoted attribute values; angle brackets in attribute values; tag
tokens split across lines (tag *spans* may cross lines and even sections; a
single ``<...>`` token may not).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

# XML-ish element/attribute name, with an optional single namespace prefix.
_NAME = r"[A-Za-z_][A-Za-z0-9_.\-]*"
_QNAME = rf"{_NAME}(?::{_NAME})?"
_ATTR = rf"{_QNAME}\s*=\s*(?:\"[^\"<>]*\"|'[^'<>]*')"

# One XML-shaped token on a single line. Malformed text (``<multa verba>``,
# ``x < 3``, ``<!-- -->``) simply never matches; the combinations the regex
# alone cannot exclude (``</x/>``, ``</x a="b">``) are rejected after the
# match.
_TOKEN_PATTERN = re.compile(
    rf"<(?P<close>/)?(?P<name>{_QNAME})(?P<attrs>(?:\s+{_ATTR})*)\s*(?P<selfclose>/)?>"
)

_ATTR_PATTERN = re.compile(rf"({_QNAME})\s*=\s*(\"[^\"<>]*\"|'[^'<>]*')")

# Markdown-style inline link: ``[display](target)``. A ``[`` is a link only
# when immediately followed by ``](target)`` — a bare ``[verbum]`` (lacuna,
# editorial bracket) stays literal, mirroring the structural rule for ``<>``.
# ``display`` excludes brackets/newlines; ``target`` is any run without spaces
# or parens, i.e. an opaque URI (relative ``path#frag``, ``urn:cts:…``,
# ``https://…``, …). The target is never resolved or validated.
_LINK_PATTERN = re.compile(r"\[(?P<display>[^\[\]\n]*)\]\((?P<target>[^()\s]+)\)")

# Tag attributes that carry a link target, in priority order. A resolved tag
# pair bearing one of these is promoted into the shared Reference view: the
# TEI equivalent of the Markdown link (``<ref target=…>``, ``<quote corresp=…>``).
_LINK_ATTRS = ("target", "corresp", "source")


@dataclass
class Tag:
    """A resolved inline XML tag span.

    ``start``/``end`` index into the *plain* (tag-stripped) text of the
    container the tag was retrieved from (``Line.plain``, ``Section.plain``,
    or ``Document.plain``): ``plain[start:end]`` is the enclosed text. For a
    self-closing milestone ``start == end`` marks the insertion point.

    Attributes:
        name: Element name, including any namespace prefix (``"tei:seg"``)
        attrs: Attribute name -> value (quotes removed; duplicates last-wins)
        start: Offset of the enclosed text in the container's plain text
        end: Offset one past the enclosed text
        self_closing: True for milestone tags like ``<pb n="2"/>``
    """
    name: str
    attrs: dict[str, str]
    start: int
    end: int
    self_closing: bool = False


@dataclass
class Reference:
    """A resolved inline cross-reference — a hyperlink to an opaque target URI.

    Two surface syntaxes compile to this, on the markdown~TEI analogy: the
    Markdown-style ``[display](target)`` link, and the TEI equivalents
    ``<ref target="…">display</ref>`` and ``<quote corresp="…">display</quote>``.

    ``target`` is stored verbatim and **never resolved or validated** — it may
    be a relative ``.txtd`` path with a ``#citation`` fragment, a CTS URN, a
    URL, or anything else, and it may dangle. Resolving a target against a set
    of documents is a separate, best-effort concern.

    ``start``/``end`` index into the container's plain text
    (``plain[start:end] == display``). For an empty pointer (e.g. a
    self-closing ``<ptr target="…"/>``) ``start == end`` and ``display == ""``.

    Attributes:
        display: The link text as it appears in plain text (tags within it are
            already stripped)
        target: The opaque target URI, verbatim
        kind: ``"link"`` (Markdown), ``"quote"`` (``<quote>``), or ``"ref"``
            (``<ref>`` / any other link-bearing tag)
        syntax: ``"markdown"`` or ``"tei"``
        start: Offset of ``display`` in the container's plain text
        end: Offset one past ``display``
    """
    display: str
    target: str
    kind: str
    syntax: str
    start: int
    end: int


@dataclass
class Resolution:
    """Everything :func:`resolve` learned about one pairing scope.

    Sections and lines are addressed by 0-based index into the
    ``section_texts`` that was passed to :func:`resolve`.

    Attributes:
        plain_lines: Per-section list of tag-stripped line texts
        line_tags: ``[si][li]`` -> tags contained entirely in that line,
            offsets local to the line's plain text
        section_tags: ``[si]`` -> tags contained entirely in that section
            (including cross-line pairs), offsets into the section's plain
            text (lines joined with ``"\\n"``)
        document_tags: All tags (including cross-section pairs), offsets
            into the document plain text (sections joined with ``"\\n\\n"``)
        stray_closes: ``(name, si, li)`` end tags with no matching start
        unmatched_attr_opens: ``(name, si, li)`` attribute-bearing start
            tags with no matching end (kept literal, but suspicious —
            a bare unmatched ``<word>`` is a West supplement and is not
            recorded)
        overlaps: ``(name_a, (si, li), name_b, (si, li))`` pairs that cross
            without nesting (``<a><b></a></b>``)
        cross_section: ``(name, open (si, li), close (si, li))`` pairs whose
            start and end tags sit in different sections
        tag_only_lines: ``(si, li)`` lines whose text is nothing but markup
        literal_spans: ``[si][li]`` -> ``(start, end)`` spans (in the line's
            plain text) of XML-shaped tokens that stayed literal (unmatched
            opens, malformed end tags). Content inside them — notably quote
            characters in attribute values — is markup-shaped, not prose
        line_tags/section_tags/document_tags have Reference twins
        line_refs/section_refs/document_refs at the same three granularities:
        Markdown ``[X](Y)`` links (always same-line) plus link-bearing tag
        pairs / self-closing pointers, offsets into the matching plain text
    """
    plain_lines: list[list[str]]
    line_tags: list[list[list[Tag]]]
    section_tags: list[list[Tag]]
    document_tags: list[Tag]
    stray_closes: list[tuple[str, int, int]]
    unmatched_attr_opens: list[tuple[str, int, int]]
    overlaps: list[tuple[str, tuple[int, int], str, tuple[int, int]]]
    cross_section: list[tuple[str, tuple[int, int], tuple[int, int]]]
    tag_only_lines: list[tuple[int, int]]
    literal_spans: list[list[list[tuple[int, int]]]]
    line_refs: list[list[list[Reference]]]
    section_refs: list[list[Reference]]
    document_refs: list[Reference]


@dataclass
class _Token:
    """One XML-shaped ``<...>`` occurrence, before/after pairing."""
    kind: str  # "open" | "close" | "selfclose"
    name: str
    attrs: dict[str, str]
    section: int
    line: int
    raw_start: int  # offsets into the raw line text
    raw_end: int
    plain_pos: int = -1  # line-local offset in the stripped text
    stripped: bool = False
    pair: "_Token | None" = field(default=None, repr=False)


@dataclass
class _Link:
    """One Markdown ``[display](target)`` occurrence on a single line."""
    section: int
    line: int
    target: str
    open_start: int   # raw offset of '['
    open_end: int     # raw offset just past '['
    close_start: int  # raw offset of ']'
    close_end: int    # raw offset just past ')'
    disp_start: int = -1  # plain offset where display begins
    disp_end: int = -1    # plain offset where display ends


def resolve(section_texts: list[list[str]]) -> Resolution:
    """Resolve inline XML tags across one pairing scope.

    Args:
        section_texts: Raw line texts, one inner list per section. Pass a
            single-section, single-line scope (``[[text]]``) to resolve a
            lone line.

    Returns:
        A :class:`Resolution` with stripped text and tag spans at line,
        section, and document granularity.
    """
    tokens = _scan(section_texts)
    links = _scan_links(section_texts, tokens)
    pairs, strays, unmatched_opens = _pair(tokens)
    plain_lines = _strip(section_texts, tokens, links)

    # Plain-offset bases: line within its section ("\n" joins), section
    # within the document ("\n\n" joins).
    line_bases: list[list[int]] = []
    section_bases: list[int] = []
    doc_offset = 0
    for row in plain_lines:
        section_bases.append(doc_offset)
        bases = []
        offset = 0
        for plain in row:
            bases.append(offset)
            offset += len(plain) + 1
        line_bases.append(bases)
        doc_offset += (offset - 1 if row else 0) + 2

    def sec_pos(tok: _Token) -> int:
        return line_bases[tok.section][tok.line] + tok.plain_pos

    def doc_pos(tok: _Token) -> int:
        return section_bases[tok.section] + sec_pos(tok)

    line_tags: list[list[list[Tag]]] = [[[] for _ in row] for row in plain_lines]
    section_tags: list[list[Tag]] = [[] for _ in plain_lines]
    document_tags: list[Tag] = []

    for tok in tokens:
        if tok.kind == "selfclose":
            # Each scope gets its own attrs copy: one dict shared across the
            # line/section/document Tags (and the cached token) would make a
            # mutation through any one of them visible through all the others.
            line_tags[tok.section][tok.line].append(
                Tag(tok.name, dict(tok.attrs), tok.plain_pos, tok.plain_pos, True)
            )
            section_tags[tok.section].append(
                Tag(tok.name, dict(tok.attrs), sec_pos(tok), sec_pos(tok), True)
            )
            document_tags.append(
                Tag(tok.name, dict(tok.attrs), doc_pos(tok), doc_pos(tok), True)
            )

    for opener, closer in pairs:
        document_tags.append(
            Tag(opener.name, dict(opener.attrs), doc_pos(opener), doc_pos(closer))
        )
        if opener.section == closer.section:
            section_tags[opener.section].append(
                Tag(opener.name, dict(opener.attrs), sec_pos(opener), sec_pos(closer))
            )
            if opener.line == closer.line:
                line_tags[opener.section][opener.line].append(
                    Tag(opener.name, dict(opener.attrs), opener.plain_pos,
                        closer.plain_pos)
                )

    # References: Markdown [X](Y) links and link-bearing tags, at the same
    # three granularities as tags. display is sliced from the document plain
    # so one string serves every coordinate frame.
    section_plains = ["\n".join(row) for row in plain_lines]
    doc_plain = "\n\n".join(section_plains)
    line_refs: list[list[list[Reference]]] = [[[] for _ in row] for row in plain_lines]
    section_refs: list[list[Reference]] = [[] for _ in plain_lines]
    document_refs: list[Reference] = []

    for lk in links:
        sec_start = line_bases[lk.section][lk.line] + lk.disp_start
        sec_end = line_bases[lk.section][lk.line] + lk.disp_end
        doc_start = section_bases[lk.section] + sec_start
        doc_end = section_bases[lk.section] + sec_end
        disp = doc_plain[doc_start:doc_end]
        line_refs[lk.section][lk.line].append(
            Reference(disp, lk.target, "link", "markdown", lk.disp_start, lk.disp_end)
        )
        section_refs[lk.section].append(
            Reference(disp, lk.target, "link", "markdown", sec_start, sec_end)
        )
        document_refs.append(
            Reference(disp, lk.target, "link", "markdown", doc_start, doc_end)
        )

    def _link_target(attrs: dict[str, str]) -> str | None:
        return next((attrs[a] for a in _LINK_ATTRS if a in attrs), None)

    for tok in tokens:
        if tok.kind == "selfclose":
            target = _link_target(tok.attrs)
            if target is None:
                continue
            document_refs.append(
                Reference("", target, "ref", "tei", doc_pos(tok), doc_pos(tok))
            )
            section_refs[tok.section].append(
                Reference("", target, "ref", "tei", sec_pos(tok), sec_pos(tok))
            )
            line_refs[tok.section][tok.line].append(
                Reference("", target, "ref", "tei", tok.plain_pos, tok.plain_pos)
            )

    for opener, closer in pairs:
        target = _link_target(opener.attrs)
        if target is None:
            continue
        kind = "quote" if opener.name == "quote" else "ref"
        d_start, d_end = doc_pos(opener), doc_pos(closer)
        disp = doc_plain[d_start:d_end]
        document_refs.append(Reference(disp, target, kind, "tei", d_start, d_end))
        if opener.section == closer.section:
            section_refs[opener.section].append(
                Reference(disp, target, kind, "tei", sec_pos(opener), sec_pos(closer))
            )
            if opener.line == closer.line:
                line_refs[opener.section][opener.line].append(
                    Reference(disp, target, kind, "tei",
                              opener.plain_pos, closer.plain_pos)
                )

    by_span = lambda t: (t.start, t.end)  # noqa: E731
    for coll in (document_tags, document_refs):
        coll.sort(key=by_span)
    for level in (section_tags, section_refs):
        for group in level:
            group.sort(key=by_span)
    for level in (line_tags, line_refs):
        for row in level:
            for group in row:
                group.sort(key=by_span)

    return Resolution(
        plain_lines=plain_lines,
        line_tags=line_tags,
        section_tags=section_tags,
        document_tags=document_tags,
        stray_closes=[(t.name, t.section, t.line) for t in strays],
        unmatched_attr_opens=[
            (t.name, t.section, t.line) for t in unmatched_opens if t.attrs
        ],
        overlaps=_find_overlaps(tokens),
        cross_section=[
            (o.name, (o.section, o.line), (c.section, c.line))
            for o, c in pairs
            if o.section != c.section
        ],
        tag_only_lines=[
            (si, li)
            for si, row in enumerate(plain_lines)
            for li, plain in enumerate(row)
            if not plain.strip() and section_texts[si][li].strip()
        ],
        literal_spans=_literal_spans(plain_lines, tokens),
        line_refs=line_refs,
        section_refs=section_refs,
        document_refs=document_refs,
    )


def _scan(section_texts: list[list[str]]) -> list[_Token]:
    """Find XML-shaped tokens in document order. Everything else is literal."""
    tokens: list[_Token] = []
    for si, line_texts in enumerate(section_texts):
        for li, text in enumerate(line_texts):
            for m in _TOKEN_PATTERN.finditer(text):
                closing = m.group("close") is not None
                attrs_src = m.group("attrs") or ""
                if closing and (m.group("selfclose") is not None
                                or attrs_src.strip()):
                    continue  # </x/> or </x a="b">: not XML, stays literal
                if closing:
                    kind = "close"
                elif m.group("selfclose") is not None:
                    kind = "selfclose"
                else:
                    kind = "open"
                attrs = {
                    am.group(1): am.group(2)[1:-1]
                    for am in _ATTR_PATTERN.finditer(attrs_src)
                }
                tokens.append(
                    _Token(kind, m.group("name"), attrs, si, li,
                           m.start(), m.end())
                )
    return tokens


def _pair(
    tokens: list[_Token],
) -> tuple[list[tuple[_Token, _Token]], list[_Token], list[_Token]]:
    """Match start/end tags with per-name LIFO stacks.

    Per-name stacks (rather than one strict stack) let cross-nested pairs
    like ``<a><b></a></b>`` still strip cleanly; the crossing itself is
    reported separately by :func:`_find_overlaps`.

    Returns:
        (matched pairs in close order, stray closes, unmatched opens)
    """
    stacks: dict[str, list[_Token]] = {}
    pairs: list[tuple[_Token, _Token]] = []
    strays: list[_Token] = []
    for tok in tokens:
        if tok.kind == "open":
            stacks.setdefault(tok.name, []).append(tok)
        elif tok.kind == "close":
            stack = stacks.get(tok.name)
            if stack:
                opener = stack.pop()
                opener.pair = tok
                tok.pair = opener
                opener.stripped = tok.stripped = True
                pairs.append((opener, tok))
            else:
                tok.stripped = True  # West never writes </word>
                strays.append(tok)
        else:
            tok.stripped = True
    unmatched_opens = [t for stack in stacks.values() for t in stack]
    return pairs, strays, unmatched_opens


def _scan_links(section_texts: list[list[str]],
                tokens: list[_Token]) -> list[_Link]:
    """Find Markdown ``[display](target)`` links, in document order.

    A match that falls *wholly* inside an XML tag token's raw span (e.g. a
    ``[x](y)`` sitting in an attribute value) is skipped — the tag owns that
    text. A link that merely overlaps a tag is kept: a display containing
    inline tags (``[<persName>Ennius</persName>](enn.txtd#1)``) encloses those
    tags, and is a link whose display happens to be tagged.
    """
    tag_spans: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for tok in tokens:
        tag_spans[(tok.section, tok.line)].append((tok.raw_start, tok.raw_end))

    links: list[_Link] = []
    for si, line_texts in enumerate(section_texts):
        for li, text in enumerate(line_texts):
            spans = tag_spans.get((si, li), [])
            for m in _LINK_PATTERN.finditer(text):
                if any(s <= m.start() and m.end() <= e for s, e in spans):
                    continue  # wholly inside a tag token
                close_start = m.start("display") + len(m.group("display"))
                links.append(
                    _Link(si, li, m.group("target"),
                          m.start(), m.start() + 1, close_start, m.end())
                )
    return links


def _strip(section_texts: list[list[str]],
           tokens: list[_Token],
           links: list[_Link]) -> list[list[str]]:
    """Strip tag tokens and Markdown link syntax from each line in one pass.

    Tag tokens marked ``stripped`` are removed; every tag token (stripped or
    literal) gets its ``plain_pos`` so literal spans can be reported. Each
    link's ``[`` and ``](target)`` are removed while its display survives; the
    link's ``disp_start``/``disp_end`` record where that display lands in the
    plain text. All edits are applied left-to-right in raw order so offsets
    stay consistent when tags and links share a line.
    """
    # Per line, an ordered work-list of edits: ("tag", token),
    # ("link_open"/"link_close", link), keyed by raw start.
    by_line: dict[tuple[int, int], list[tuple[int, str, object]]] = defaultdict(list)
    for tok in tokens:
        by_line[(tok.section, tok.line)].append((tok.raw_start, "tag", tok))
    for lk in links:
        by_line[(lk.section, lk.line)].append((lk.open_start, "link_open", lk))
        by_line[(lk.section, lk.line)].append((lk.close_start, "link_close", lk))

    plain_lines: list[list[str]] = []
    for si, line_texts in enumerate(section_texts):
        row: list[str] = []
        for li, text in enumerate(line_texts):
            pieces: list[str] = []
            cursor = 0
            removed = 0
            for raw_start, kind, payload in sorted(by_line.get((si, li), []),
                                                   key=lambda e: e[0]):
                if kind == "tag":
                    tok = payload
                    tok.plain_pos = tok.raw_start - removed
                    if tok.stripped:
                        pieces.append(text[cursor:tok.raw_start])
                        removed += tok.raw_end - tok.raw_start
                        cursor = tok.raw_end
                elif kind == "link_open":
                    lk = payload
                    pieces.append(text[cursor:lk.open_start])
                    lk.disp_start = lk.open_start - removed
                    removed += lk.open_end - lk.open_start
                    cursor = lk.open_end
                else:  # link_close
                    lk = payload
                    pieces.append(text[cursor:lk.close_start])
                    lk.disp_end = lk.close_start - removed
                    removed += lk.close_end - lk.close_start
                    cursor = lk.close_end
            pieces.append(text[cursor:])
            row.append("".join(pieces))
        plain_lines.append(row)
    return plain_lines


def _literal_spans(
    plain_lines: list[list[str]],
    tokens: list[_Token],
) -> list[list[list[tuple[int, int]]]]:
    """Plain-coordinate spans of XML-shaped tokens that stayed literal."""
    spans: list[list[list[tuple[int, int]]]] = [
        [[] for _ in row] for row in plain_lines
    ]
    for tok in tokens:
        if not tok.stripped:
            length = tok.raw_end - tok.raw_start
            spans[tok.section][tok.line].append(
                (tok.plain_pos, tok.plain_pos + length)
            )
    return spans


def _find_overlaps(
    tokens: list[_Token],
) -> list[tuple[str, tuple[int, int], str, tuple[int, int]]]:
    """Detect matched pairs that cross without nesting."""
    overlaps: list[tuple[str, tuple[int, int], str, tuple[int, int]]] = []
    open_stack: list[_Token] = []
    for tok in tokens:
        if tok.pair is None:
            continue
        if tok.kind == "open":
            open_stack.append(tok)
        elif tok.kind == "close":
            opener = tok.pair
            if open_stack and open_stack[-1] is opener:
                open_stack.pop()
            elif opener in open_stack:
                top = open_stack[-1]
                overlaps.append(
                    (opener.name, (opener.section, opener.line),
                     top.name, (top.section, top.line))
                )
                open_stack.remove(opener)
    return overlaps
