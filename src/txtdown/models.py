"""Data models for txtdown documents."""

import functools
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .tags import Resolution, Tag, resolve


@dataclass
class Metadata:
    """Document metadata from YAML front matter.

    Attributes:
        author: Author name
        work: Work title
        source: Source URL or reference
        scope: For partial files (e.g., "1" or "1-12")
        extras: Additional key-value pairs
    """
    author: str | None = None
    work: str | None = None
    source: str | None = None
    scope: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Metadata":
        """Create Metadata from a dictionary (e.g., parsed YAML)."""
        known_fields = {"author", "work", "source", "scope"}
        extras = {k: v for k, v in data.items() if k not in known_fields}
        # Ensure scope is always a string (YAML may parse "1" as int)
        scope = data.get("scope")
        if scope is not None:
            scope = str(scope)
        return cls(
            author=data.get("author"),
            work=data.get("work"),
            source=data.get("source"),
            scope=scope,
            extras=extras,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result: dict[str, Any] = {}
        if self.author:
            result["author"] = self.author
        if self.work:
            result["work"] = self.work
        if self.source:
            result["source"] = self.source
        if self.scope:
            result["scope"] = self.scope
        result.update(self.extras)
        return result


@dataclass
class Line:
    """A single line of text.

    Attributes:
        text: The line content
        number: Line number within the section (1-indexed)
        speaker: Speaker name for dramatic texts (None for non-dialogue)
        label: Editorial line label when it differs from number (e.g., "983a")
        is_quote: True if the line is a cross-source quotation (``>`` markup),
            i.e. verbatim text quoted from another author/work
        section: Back-reference to the containing Section (set automatically;
            excluded from equality/repr)

    Note:
        ``text`` keeps any inline TEI/XML markup verbatim; use :attr:`plain`
        for the tag-stripped text and :attr:`tags` for the resolved spans
        (see :mod:`txtdown.tags` for what counts as a tag).
    """
    text: str
    number: int
    speaker: str | None = None
    label: str | None = None
    is_quote: bool = False
    section: "Section | None" = field(default=None, repr=False, compare=False)

    @property
    def plain(self) -> str:
        """Line text with inline XML tags stripped (NLP-ready).

        Tag pairing uses the widest reachable scope — the whole document
        when this line belongs to one, so a span opened here and closed in
        a later line still strips (structural pairing: a lone unmatched
        ``<word>`` is a West-style supplement and stays literal).
        """
        resolution, si, li = self._tag_view()
        return resolution.plain_lines[si][li]

    @property
    def tags(self) -> list[Tag]:
        """Inline XML tags contained entirely in this line.

        Offsets index into :attr:`plain`. Pairs whose end tag sits on a
        later line appear in ``Section.tags`` / ``Document.tags`` instead.
        """
        resolution, si, li = self._tag_view()
        return list(resolution.line_tags[si][li])

    def _tag_view(self) -> tuple[Resolution, int, int]:
        """Tag resolution covering this line, at the widest reachable scope."""
        section = self.section
        document = section.document if section is not None else None
        if document is not None:
            resolution, _, line_index = document._tag_state
            coords = line_index.get(id(self))
            if coords is not None:
                return resolution, coords[0], coords[1]
        if section is not None:
            resolution, line_index = section._tag_state
            li = line_index.get(id(self))
            if li is not None:
                return resolution, 0, li
        return resolve([[self.text]]), 0, 0

    def __str__(self) -> str:
        return self.text


@dataclass
class Section:
    """A section of text (poem, chapter, etc.).

    Attributes:
        id: Section identifier (number or name)
        lines: List of lines in this section
        is_numbered: Whether the ID is numeric (a single integer or a dotted
            hierarchy of integers) vs. a name
        title: Optional section title
        metadata: Section-specific metadata (supersedes document metadata)
        document: Back-reference to the containing Document (set
            automatically; excluded from equality/repr)

    Note:
        Indexing with [] uses 1-based indexing to match scholarly citations.
        Use section[1] for the first line, not section[0].

        ``levels`` and ``chapter`` are derived from ``id`` (the source of truth),
        so a hierarchical id like ``"3.7"`` always reports ``levels == (3, 7)``
        and ``chapter == 3`` without any extra bookkeeping.
    """
    id: str
    lines: list[Line] = field(default_factory=list)
    is_numbered: bool = True
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    document: "Document | None" = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        for line in self.lines:
            line.section = self

    @property
    def levels(self) -> tuple[int, ...] | None:
        """Integer components of a purely numeric, dot-separated id.

        ``"1"`` -> ``(1,)``; ``"3.7"`` -> ``(3, 7)``; ``"1.2.3"`` -> ``(1, 2, 3)``.
        ``None`` for named or otherwise non-numeric ids (``"prooemium"``,
        ``"1a"``, malformed ``"3."``). Any depth is supported.
        """
        parts = self.id.split(".")
        if self.id and all(part.isdigit() for part in parts):
            return tuple(int(part) for part in parts)
        return None

    @property
    def chapter(self) -> int | None:
        """First hierarchy level of a compound id, or ``None``.

        For a ``chapter.section`` text this is the chapter (id ``"3.7"`` -> 3).
        Only defined for ids with two or more levels: a flat section such as
        ``"1"`` is a section, not a chapter, so it reports ``None``. At depths
        other than two the first level may name a different unit (e.g. a book).
        """
        levels = self.levels
        return levels[0] if levels is not None and len(levels) >= 2 else None

    @property
    def text(self) -> str:
        """Return section text as a single string."""
        return "\n".join(line.text for line in self.lines)

    @property
    def plain(self) -> str:
        """Section text with inline XML tags stripped (NLP-ready).

        Lines are joined with ``"\\n"``, mirroring :attr:`text`. Tag pairing
        uses the whole document when this section belongs to one.
        """
        resolution, si = self._tag_view()
        return "\n".join(resolution.plain_lines[si])

    @property
    def tags(self) -> list[Tag]:
        """Inline XML tags contained entirely in this section.

        Includes pairs that span lines; offsets index into :attr:`plain`.
        Pairs crossing into another section appear only in ``Document.tags``.
        """
        resolution, si = self._tag_view()
        return list(resolution.section_tags[si])

    @functools.cached_property
    def _tag_state(self) -> tuple[Resolution, dict[int, int]]:
        """Section-scope tag resolution, for sections outside a Document.

        Cached on first access; stale if lines are mutated afterwards
        (``del section._tag_state`` to recompute).
        """
        resolution = resolve([[line.text for line in self.lines]])
        return resolution, {id(line): li for li, line in enumerate(self.lines)}

    def _tag_view(self) -> tuple[Resolution, int]:
        """Tag resolution covering this section, at the widest reachable scope."""
        if self.document is not None:
            resolution, section_index, _ = self.document._tag_state
            si = section_index.get(id(self))
            if si is not None:
                return resolution, si
        return self._tag_state[0], 0

    def __len__(self) -> int:
        return len(self.lines)

    def __getitem__(self, index: int) -> Line:
        """Get line by 1-indexed number."""
        if index < 1 or index > len(self.lines):
            raise IndexError(f"Line {index} out of range (1-{len(self.lines)})")
        return self.lines[index - 1]


@dataclass
class Issue:
    """A structural problem reported by ``Document.validate()``.

    Attributes:
        kind: Machine-readable category — one of ``"duplicate_label"``,
            ``"out_of_order"``, ``"mixed_depth"``, ``"unknown_speaker"``,
            ``"unused_speaker"``, ``"unmatched_quote"``,
            ``"quote_style_mismatch"``, ``"unmatched_tag"``,
            ``"tag_overlap"``, ``"tag_crosses_section"``,
            ``"tag_only_line"``.
        severity: ``"error"`` (breaks lookup / almost certainly a mistake) or
            ``"warning"`` (suspicious but sometimes legitimate).
        message: Human-readable explanation.
        label: The offending section id or speaker name, when applicable.
    """
    kind: str
    severity: str
    message: str
    label: str | None = None


# Direct-speech quote pairs: opening character -> set of valid closers.
# The „…“ (low-9) style accepts either “ or ” as its closer.
_QUOTE_PAIRS: dict[str, frozenset[str]] = {
    '"': frozenset('"'),
    "“": frozenset("”"),   # “ … ”
    "'": frozenset("'"),
    "‘": frozenset("’"),   # ‘ … ’
    "«": frozenset("»"),   # « … »
    "„": frozenset("“”"),  # „ … “ / „ … ”
    "‹": frozenset("›"),   # ‹ … ›
}

# Characters that only ever close a pair. A stray one with no span open is an
# unmatched quote. U+2019 (’) is deliberately absent: it doubles as the
# typographic apostrophe, so a stray one is not evidence of a broken pair.
_CLOSE_ONLY = frozenset("»›”")

# Symmetric quote characters (same char opens and closes). These cannot be
# paired lexically, so their role is judged from context: an opener follows
# start-of-line, whitespace, or an introducer character; a closer follows a
# word or punctuation character. Blind toggling would silently absorb
# resumption quotes and misplaced closers.
#
# The colon is deliberately absent: a speech-introducer colon always has
# whitespace before the quote (dixit: "…), while a quote directly after a
# colon ("plena, uiri:" dixit) closes a span that ends in a colon. A bare
# colon-before-quote therefore only counts as opener context when no span
# is open (see the closed-state check below).
_SYMMETRIC = frozenset("\"'")
_OPENER_PREV = frozenset(" \t(—–-")

# Human-readable style names keyed by opening character.
_STYLE_NAMES = {
    '"': '"…"',
    "“": "“…”",
    "'": "'…'",
    "‘": "‘…’",
    "«": "«…»",
    "„": "„…“",
    "‹": "‹…›",
}


@dataclass
class Document:
    """A complete txtdown document.

    Attributes:
        metadata: Document metadata
        sections: List of sections

    Note:
        Indexing with [] uses 1-based indexing to match scholarly citations.
        Use doc[1] for the first section, not doc[0].
        For citation-based access, use doc.get("1") or doc.get("1.3").
    """
    metadata: Metadata = field(default_factory=Metadata)
    sections: list[Section] = field(default_factory=list)

    def __post_init__(self) -> None:
        for section in self.sections:
            section.document = self

    @property
    def plain(self) -> str:
        """Document text with inline XML tags stripped (NLP-ready).

        Lines are joined with ``"\\n"`` within a section and sections with
        ``"\\n\\n"``. See :mod:`txtdown.tags` for what counts as a tag
        (structural pairing: a lone unmatched ``<word>`` is a West-style
        supplement and stays literal).
        """
        resolution, _, _ = self._tag_state
        return "\n\n".join("\n".join(row) for row in resolution.plain_lines)

    @property
    def tags(self) -> list[Tag]:
        """All resolved inline XML tags, offsets into :attr:`plain`."""
        return list(self._tag_state[0].document_tags)

    @functools.cached_property
    def _tag_state(
        self,
    ) -> tuple[Resolution, dict[int, int], dict[int, tuple[int, int]]]:
        """Document-scope tag resolution plus id()-keyed section/line indexes.

        Cached on first access; stale if sections or lines are mutated
        afterwards (``del document._tag_state`` to recompute).
        """
        resolution = resolve(
            [[line.text for line in s.lines] for s in self.sections]
        )
        section_index = {id(s): si for si, s in enumerate(self.sections)}
        line_index = {
            id(line): (si, li)
            for si, s in enumerate(self.sections)
            for li, line in enumerate(s.lines)
        }
        return resolution, section_index, line_index

    def get(self, citation: str) -> Line | Section:
        """Retrieve content by citation.

        Args:
            citation: Citation string like "2" (section), "2.3" (section.line),
                or "3.7" / "3.7.2" when section ids are compound ``chapter.section``
                labels (section, then section.line).

        Returns:
            Section if the citation resolves to a whole section, Line otherwise.

        Raises:
            KeyError: If section or line not found

        Note:
            A section-id match takes precedence over the section.line reading.
            The longest dotted prefix that names an existing section wins, so a
            compound id like "3.7" resolves to that section while "3.7.2" resolves
            to its line 2. In a non-compound document, "2.3" still falls back to
            section "2", line 3.
        """
        parts = citation.split(".")

        # Find the section by longest dotted prefix that matches a section id.
        # This lets compound ids ("3.7") win over the section.line interpretation
        # while staying backward compatible for flat ids ("2.3" -> section 2, line 3).
        section = None
        consumed = 0
        for n in range(len(parts), 0, -1):
            candidate = ".".join(parts[:n])
            for s in self.sections:
                if s.id == candidate:
                    section = s
                    consumed = n
                    break
            if section is not None:
                break

        if section is None:
            raise KeyError(f"Section '{parts[0]}' not found")

        remainder = parts[consumed:]

        # Return section or line
        if not remainder:
            return section

        line_ref = remainder[0]
        section_id = section.id

        # Try label lookup first (handles "983a" etc.)
        for line in section.lines:
            if line.label == line_ref:
                return line

        # Fall back to numeric line number
        try:
            line_num = int(line_ref)
            return section[line_num]
        except (ValueError, IndexError) as e:
            msg = f"Line '{line_ref}' not found in section '{section_id}'"
            raise KeyError(msg) from e

    def validate(self) -> list["Issue"]:
        """Check the section hierarchy for structural problems.

        Opt-in and non-raising: parsing stays permissive, and this reports
        *all* problems at once so a caller can decide what to do (warn, raise,
        ignore). An empty list means the hierarchy is clean.

        Section-hierarchy checks (numeric labels only, except duplicates):

        - ``duplicate_label`` (error): the same label appears twice. Only the
          first is reachable via :meth:`get`, so the rest silently shadow.
        - ``out_of_order`` (error): a numeric label sorts before its
          predecessor in document order (component-wise on ``levels``).
        - ``mixed_depth`` (warning): a numeric label whose depth differs from
          the most common depth (a stray ``3.7.1`` among ``N.M`` labels). A
          warning, not an error — e.g. a depth-1 prologue beside depth-2
          chapters can be intentional.

        Speaker checks (only when a ``speakers`` roster is declared in the
        front matter; the roster lives in ``metadata.extras["speakers"]``):

        - ``unknown_speaker`` (error): an ``@Speaker:`` name used in the body
          that is not in the declared roster — catches typos.
        - ``unused_speaker`` (warning): a declared speaker that never speaks in
          this file. A warning, not an error — a partial-``scope`` file may
          legitimately omit some of the cast.

        Direct-speech quote checks (inline speech in running narrative;
        ``@Speaker:`` dialogue lines and ``>`` cross-source quotation lines
        are excluded):

        - ``unmatched_quote``: a speech quote is opened but never closed
          with its matching character; a close-only character (``»``, ``›``,
          ``”``) appears with no span open; or a symmetric quote (``"``,
          ``'``) appears in a context inconsistent with its expected role —
          an opening-shaped quote while a span is already open (a
          paragraph-resumption quote or missing close), or a closing-shaped
          quote with nothing open. Pairs are matched across line boundaries
          — speeches span multiple lines. Severity is ``"error"`` except for
          a closing-shaped stray ``'``, which is a ``"warning"``: word-final
          elision (``satin'``, ``viden'``) is indistinguishable from a
          closing quote.
        - ``quote_style_mismatch`` (warning): more than one quote style is
          used at the primary level in the same document (e.g. both ``"…"``
          and ``'…'``). The CRAWL/LatinCy standard is one style per document
          for direct speech, but quoted formulae or titles (``de pace 'uti
          rogas'``) are a different function the validator cannot
          distinguish, so this needs human review rather than failing the
          document.

        Nesting is out of scope for now (single-depth): while a span is open,
        only its own closing character is significant, so nested quotes of a
        different style pass through unexamined. A ``'`` or ``’`` with letters
        on both sides is an apostrophe/elision, never a quote. Quote scanning
        operates on tag-stripped (``plain``) text, so quotes inside XML
        attribute values (``<placeName n="pleiades:874341">``) are never
        mistaken for speech.

        Inline XML tag checks (all warnings — a suspicious tag never breaks
        citation lookup; see :mod:`txtdown.tags` for the pairing rules):

        - ``unmatched_tag``: an end tag with no matching start tag (stripped
          from plain text anyway), or an attribute-bearing start tag that is
          never closed (kept as literal text). A *bare* unmatched ``<word>``
          is never flagged — it is by definition a West-style supplement.
        - ``tag_overlap``: two tag pairs cross without nesting
          (``<a><b></a></b>``). Both still strip.
        - ``tag_crosses_section``: a pair opens in one section and closes in
          another. Legitimate TEI rarely does this; it usually means a
          West-style supplement was absorbed by a distant unrelated end tag.
        - ``tag_only_line``: a line containing only markup (e.g. a lone
          ``<pb n="2"/>``) still consumes a line number, shifting the
          numbering of every following line.
        """
        issues: list[Issue] = []

        # Duplicate labels (applies to every id, named or numeric).
        seen: set[str] = set()
        for s in self.sections:
            if s.id in seen:
                issues.append(
                    Issue(
                        "duplicate_label",
                        "error",
                        f"Duplicate section label '{s.id}'; only the first is "
                        "reachable via get().",
                        s.id,
                    )
                )
            seen.add(s.id)

        numeric = [s for s in self.sections if s.levels is not None]

        # Out-of-order numeric labels (document order vs. component order).
        prev = None
        for s in numeric:
            if prev is not None and s.levels < prev.levels:
                issues.append(
                    Issue(
                        "out_of_order",
                        "error",
                        f"Section '{s.id}' is out of order (follows '{prev.id}').",
                        s.id,
                    )
                )
            prev = s

        # Mixed depth: flag labels that deviate from the most common depth.
        if numeric:
            modal_depth = Counter(len(s.levels) for s in numeric).most_common(1)[0][0]
            for s in numeric:
                if len(s.levels) != modal_depth:
                    issues.append(
                        Issue(
                            "mixed_depth",
                            "warning",
                            f"Section '{s.id}' has depth {len(s.levels)}, but most "
                            f"sections have depth {modal_depth}.",
                            s.id,
                        )
                    )

        # Speaker roster consistency, only when a roster is declared.
        roster = self.metadata.extras.get("speakers")
        if isinstance(roster, list):
            declared = set(roster)
            used = {
                line.speaker
                for s in self.sections
                for line in s.lines
                if line.speaker
            }
            for name in sorted(used - declared):
                issues.append(
                    Issue(
                        "unknown_speaker",
                        "error",
                        f"Speaker '{name}' is used (@{name}:) but not in the "
                        "declared 'speakers' roster.",
                        name,
                    )
                )
            for name in dict.fromkeys(roster):  # declared order, de-duplicated
                if name not in used:
                    issues.append(
                        Issue(
                            "unused_speaker",
                            "warning",
                            f"Speaker '{name}' is declared but never speaks in "
                            "this file.",
                            name,
                        )
                    )

        issues.extend(self._validate_quotes())
        issues.extend(self._validate_tags())

        return issues

    def _validate_quotes(self) -> list["Issue"]:
        """Direct-speech quote pairing and style consistency (see validate)."""
        issues: list[Issue] = []
        open_style: str | None = None
        open_at: tuple[str, int] | None = None  # (section id, line number)
        styles_used: dict[str, tuple[str, int]] = {}  # style -> first location
        resolution = self._tag_state[0]

        for si, section in enumerate(self.sections):
            for li, line in enumerate(section.lines):
                # Inline narrative speech only: skip drama dialogue and
                # cross-source quotations.
                if line.speaker or line.is_quote:
                    continue
                # Scan tag-stripped text: quotes inside XML attribute values
                # are markup, not speech. XML-shaped tokens that stayed
                # literal (e.g. an unclosed attribute-bearing tag) are
                # likewise skipped — their quotes are markup-shaped too.
                text = resolution.plain_lines[si][li]
                literal_spans = resolution.literal_spans[si][li]
                for i, ch in enumerate(text):
                    if any(s <= i < e for s, e in literal_spans):
                        continue
                    # Apostrophe/elision, never a quote: letters on both sides.
                    if ch in ("'", "’") and 0 < i < len(text) - 1 \
                            and text[i - 1].isalpha() and text[i + 1].isalpha():
                        continue
                    prev = text[i - 1] if i > 0 else None
                    opener_shaped = prev is None or prev in _OPENER_PREV
                    if open_style is not None:
                        if ch in _QUOTE_PAIRS[open_style]:
                            # A symmetric quote in opener position while its
                            # own span is open is not a close: it is a
                            # paragraph-resumption quote or a missing close.
                            if ch == open_style and ch in _SYMMETRIC \
                                    and opener_shaped:
                                issues.append(
                                    Issue(
                                        "unmatched_quote",
                                        "error",
                                        f"Opening-shaped quote {ch!r} at "
                                        f"section '{section.id}', line "
                                        f"{line.number} while the span opened "
                                        f"at section '{open_at[0]}', line "
                                        f"{open_at[1]} is still open "
                                        "(resumption quote or missing close).",
                                        f"{section.id}.{line.number}",
                                    )
                                )
                            else:
                                open_style = None
                                open_at = None
                        # Anything else — including nested quotes of another
                        # style — is not significant at depth 1.
                    elif ch in _QUOTE_PAIRS:
                        if ch in _SYMMETRIC and not opener_shaped \
                                and prev != ":":
                            # A stray closing-shaped ' may be word-final
                            # elision (satin', viden') — warn, don't error.
                            issues.append(
                                Issue(
                                    "unmatched_quote",
                                    "warning" if ch == "'" else "error",
                                    f"Closing-shaped quote {ch!r} at section "
                                    f"'{section.id}', line {line.number} has "
                                    "no matching opening quote (or word-final "
                                    "elision).",
                                    f"{section.id}.{line.number}",
                                )
                            )
                        else:
                            open_style = ch
                            open_at = (section.id, line.number)
                            styles_used.setdefault(ch, open_at)
                    elif ch in _CLOSE_ONLY:
                        issues.append(
                            Issue(
                                "unmatched_quote",
                                "error",
                                f"Closing quote '{ch}' at section "
                                f"'{section.id}', line {line.number} has no "
                                "matching opening quote.",
                                f"{section.id}.{line.number}",
                            )
                        )

        if open_style is not None and open_at is not None:
            sec_id, line_no = open_at
            issues.append(
                Issue(
                    "unmatched_quote",
                    "error",
                    f"Speech quote {_STYLE_NAMES[open_style]} opened at "
                    f"section '{sec_id}', line {line_no} is never closed.",
                    f"{sec_id}.{line_no}",
                )
            )

        if len(styles_used) > 1:
            listing = ", ".join(
                f"{_STYLE_NAMES[s]} (first at section '{loc[0]}', line {loc[1]})"
                for s, loc in styles_used.items()
            )
            issues.append(
                Issue(
                    "quote_style_mismatch",
                    "warning",
                    f"Document mixes {len(styles_used)} primary quote "
                    f"styles: {listing}. One style per document for direct "
                    "speech; quoted formulae or titles may be legitimate.",
                )
            )

        return issues

    def _validate_tags(self) -> list["Issue"]:
        """Inline XML tag hygiene (see validate). All warnings."""
        issues: list[Issue] = []
        resolution = self._tag_state[0]

        def where(si: int, li: int) -> tuple[str, int]:
            section = self.sections[si]
            return section.id, section.lines[li].number

        for name, si, li in resolution.stray_closes:
            sec_id, num = where(si, li)
            issues.append(
                Issue(
                    "unmatched_tag",
                    "warning",
                    f"Closing tag </{name}> at section '{sec_id}', line "
                    f"{num} has no matching opening tag (stripped from "
                    "plain text anyway).",
                    f"{sec_id}.{num}",
                )
            )
        for name, si, li in resolution.unmatched_attr_opens:
            sec_id, num = where(si, li)
            issues.append(
                Issue(
                    "unmatched_tag",
                    "warning",
                    f"Tag <{name} ...> at section '{sec_id}', line {num} "
                    "has attributes but is never closed; kept as literal "
                    "text.",
                    f"{sec_id}.{num}",
                )
            )
        for name_a, pos_a, name_b, pos_b in resolution.overlaps:
            a_id, a_num = where(*pos_a)
            b_id, b_num = where(*pos_b)
            issues.append(
                Issue(
                    "tag_overlap",
                    "warning",
                    f"Tags <{name_a}> (section '{a_id}', line {a_num}) and "
                    f"<{name_b}> (section '{b_id}', line {b_num}) overlap "
                    "without nesting.",
                    f"{a_id}.{a_num}",
                )
            )
        for name, open_pos, close_pos in resolution.cross_section:
            o_id, o_num = where(*open_pos)
            c_id, c_num = where(*close_pos)
            issues.append(
                Issue(
                    "tag_crosses_section",
                    "warning",
                    f"Tag <{name}> opened at section '{o_id}', line {o_num} "
                    f"closes in section '{c_id}', line {c_num}. If the "
                    "opener is a West-style supplement, it has been absorbed "
                    "by an unrelated end tag.",
                    f"{o_id}.{o_num}",
                )
            )
        for si, li in resolution.tag_only_lines:
            sec_id, num = where(si, li)
            issues.append(
                Issue(
                    "tag_only_line",
                    "warning",
                    f"Line {num} of section '{sec_id}' contains only markup "
                    "but still consumes a line number.",
                    f"{sec_id}.{num}",
                )
            )
        return issues

    @property
    def is_valid(self) -> bool:
        """True when :meth:`validate` finds no error-severity issues.

        Warnings (e.g. ``mixed_depth``) do not make a document invalid.
        """
        return not any(i.severity == "error" for i in self.validate())

    def __len__(self) -> int:
        return len(self.sections)

    def __getitem__(self, index: int) -> Section:
        """Get section by 1-indexed number."""
        if index < 1 or index > len(self.sections):
            raise IndexError(f"Section {index} out of range (1-{len(self.sections)})")
        return self.sections[index - 1]
