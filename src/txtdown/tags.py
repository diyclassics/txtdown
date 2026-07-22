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
    pairs, strays, unmatched_opens = _pair(tokens)
    plain_lines = _strip(section_texts, tokens)

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
            line_tags[tok.section][tok.line].append(
                Tag(tok.name, tok.attrs, tok.plain_pos, tok.plain_pos, True)
            )
            section_tags[tok.section].append(
                Tag(tok.name, tok.attrs, sec_pos(tok), sec_pos(tok), True)
            )
            document_tags.append(
                Tag(tok.name, tok.attrs, doc_pos(tok), doc_pos(tok), True)
            )

    for opener, closer in pairs:
        document_tags.append(
            Tag(opener.name, opener.attrs, doc_pos(opener), doc_pos(closer))
        )
        if opener.section == closer.section:
            section_tags[opener.section].append(
                Tag(opener.name, opener.attrs, sec_pos(opener), sec_pos(closer))
            )
            if opener.line == closer.line:
                line_tags[opener.section][opener.line].append(
                    Tag(opener.name, opener.attrs, opener.plain_pos,
                        closer.plain_pos)
                )

    by_span = lambda t: (t.start, t.end)  # noqa: E731
    document_tags.sort(key=by_span)
    for tags in section_tags:
        tags.sort(key=by_span)
    for row in line_tags:
        for tags in row:
            tags.sort(key=by_span)

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


def _strip(section_texts: list[list[str]],
           tokens: list[_Token]) -> list[list[str]]:
    """Remove stripped tokens from each line, recording plain offsets.

    Every token — stripped or literal — gets its ``plain_pos`` set so that
    the plain-coordinate spans of literal tokens can be reported too.
    """
    by_line: dict[tuple[int, int], list[_Token]] = {}
    for tok in tokens:
        by_line.setdefault((tok.section, tok.line), []).append(tok)

    plain_lines: list[list[str]] = []
    for si, line_texts in enumerate(section_texts):
        row: list[str] = []
        for li, text in enumerate(line_texts):
            pieces: list[str] = []
            cursor = 0
            removed = 0
            for tok in by_line.get((si, li), []):  # already in scan order
                tok.plain_pos = tok.raw_start - removed
                if tok.stripped:
                    pieces.append(text[cursor:tok.raw_start])
                    removed += tok.raw_end - tok.raw_start
                    cursor = tok.raw_end
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
