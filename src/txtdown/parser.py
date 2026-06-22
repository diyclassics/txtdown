"""Parser for txtdown format."""

import re
import warnings
from pathlib import Path
from typing import Any

import yaml

from .models import Document, Line, Metadata, Section

# Pattern for section separator: --- optionally followed by ID
# Must be at start of line, at least 3 dashes
SECTION_SEP_PATTERN = re.compile(r"^-{3,}\s*(.*)$")

# Pattern for speaker markup: @SingleWord: speech text
SPEAKER_PATTERN = re.compile(r"^@(\w+):\s*(.*)")

# Pattern for cross-source quotation: > verbatim quoted text
# The single optional space after > is part of the marker, not the text.
QUOTE_PATTERN = re.compile(r"^>\s?(.*)")

# Pattern for leading explicit line number: "6. text" or "983. text"
LEADING_NUMBER_PATTERN = re.compile(r"^(\d+)\.\s+(.*)")

# Pattern for trailing line label: "text         980" or "text         983a"
# Requires 2+ whitespace chars before the label to avoid false positives
TRAILING_LABEL_PATTERN = re.compile(r"^(.*?)\s{2,}(\d+[a-z]?)\s*$")


def parse(source: str | Path, *, strict: bool = True) -> Document:
    """Parse a txtdown file or string.

    Args:
        source: File path or txtdown content string
        strict: When True (default), require a YAML front matter block with a
            ``work`` field and raise ValueError if either is missing. Pass
            ``strict=False`` to parse a fragment (e.g. a single line or section)
            without metadata.

    Returns:
        Parsed Document object

    Raises:
        ValueError: In strict mode, when the front matter block or the ``work``
            field is missing.
    """
    # Handle file path vs string
    is_path = isinstance(source, Path)
    is_path = is_path or (isinstance(source, str) and _looks_like_path(source))
    if is_path:
        path = Path(source)
        content = path.read_text(encoding="utf-8")
    else:
        content = source

    return _parse_content(content, strict=strict)


def _looks_like_path(s: str) -> bool:
    """Heuristic to detect if string is a file path."""
    # Empty string is not a path
    if not s or not s.strip():
        return False
    # If it starts with ---, it's content
    if s.strip().startswith("---"):
        return False
    # If it contains newlines, it's content
    if "\n" in s:
        return False
    # If it ends with .txtdown or .td, it's a path
    if s.endswith((".txtd", ".txtdown")):
        return True
    # If it exists as a file (not directory), it's a path
    p = Path(s)
    return p.exists() and p.is_file()


def _parse_content(content: str, strict: bool = True) -> Document:
    """Parse txtdown content string."""
    lines = content.split("\n")

    # Extract front matter (body_start > 0 only when a closed block was found)
    metadata, body_start = _parse_front_matter(lines)
    had_front_matter = body_start > 0

    # Parse body into sections
    sections = _parse_sections(lines[body_start:])

    doc = Document(metadata=metadata, sections=sections)

    if strict:
        _validate(doc, had_front_matter)

    return doc


def _validate(doc: Document, had_front_matter: bool) -> None:
    """Enforce the required document structure in strict mode."""
    if not had_front_matter:
        raise ValueError(
            "txtdown requires a YAML front matter block (--- ... ---). "
            "Pass strict=False to parse a fragment without metadata."
        )
    if not doc.metadata.work:
        raise ValueError(
            "txtdown requires a 'work' field in the front matter. "
            "Pass strict=False to parse without it."
        )


def _parse_front_matter(lines: list[str]) -> tuple[Metadata, int]:
    """Parse YAML front matter.

    Returns:
        Tuple of (Metadata, index of first body line)
    """
    # Find opening ---
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1

    if start >= len(lines) or lines[start].strip() != "---":
        return Metadata(), 0

    # Find closing ---
    end = start + 1
    while end < len(lines):
        line = lines[end].strip()
        if line == "---" or line == "...":
            break
        end += 1

    if end >= len(lines):
        # No closing delimiter - treat as no front matter
        return Metadata(), 0

    # Parse YAML
    yaml_content = "\n".join(lines[start + 1 : end])
    try:
        data = yaml.safe_load(yaml_content) or {}
    except yaml.YAMLError as e:
        warnings.warn(f"Failed to parse YAML front matter: {e}", stacklevel=3)
        data = {}

    return Metadata.from_dict(data), end + 1


def _parse_section_header(header: str) -> tuple[str | None, str | None]:
    """Parse section header into ID and title.

    Formats supported:
        "99" -> id="99", title=None
        "99: Title here" -> id="99", title="Title here"
        "prooemium" -> id="prooemium", title=None
        "prooemium: Introduction" -> id="prooemium", title="Introduction"

    Returns:
        Tuple of (id, title), either may be None.
    """
    if not header:
        return None, None

    # Check for "id: title" format
    if ":" in header:
        id_part, title_part = header.split(":", 1)
        return id_part.strip(), title_part.strip() or None

    return header.strip(), None


def _is_metadata_line(line: str) -> bool:
    """Check if a line looks like YAML metadata (key: value)."""
    stripped = line.strip()
    if not stripped:
        return False
    # Must have colon with content on both sides
    if ":" not in stripped:
        return False
    # Split on first colon
    key, _, value = stripped.partition(":")
    # Key must be a simple identifier (no spaces, alphanumeric + underscore)
    if not key or not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
        return False
    return True


def _parse_section_metadata(
    lines: list[str], start_idx: int
) -> tuple[dict[str, Any], int]:
    """Parse section metadata from lines immediately following section separator.

    Args:
        lines: All lines in the section
        start_idx: Index to start looking for metadata

    Returns:
        Tuple of (metadata dict, index of first content line)
    """
    metadata: dict[str, Any] = {}
    idx = start_idx

    # Skip any leading blank lines - metadata must immediately follow separator
    # Actually, no - metadata must IMMEDIATELY abut the separator (no blank line)
    # So if first line is blank, there's no section metadata

    while idx < len(lines):
        line = lines[idx]

        # Blank line signals end of metadata, start of content
        if not line.strip():
            break

        # Check if this looks like metadata
        if _is_metadata_line(line):
            key, _, value = line.strip().partition(":")
            value = value.strip()
            # Try to parse as YAML-ish value (bool, int, etc.)
            if value.lower() == "true":
                metadata[key] = True
            elif value.lower() == "false":
                metadata[key] = False
            elif value.isdigit():
                metadata[key] = int(value)
            else:
                metadata[key] = value
            idx += 1
        else:
            # Not metadata - this is content
            break

    return metadata, idx


def _parse_sections(lines: list[str]) -> list[Section]:
    """Parse body into sections."""
    sections: list[Section] = []
    current_lines: list[str] = []
    current_id: str | None = None
    current_title: str | None = None
    current_metadata: dict[str, Any] = {}
    section_counter = 0

    def has_content(lines: list[str]) -> bool:
        """Check if lines have any non-whitespace content."""
        return any(line.strip() for line in lines)

    i = 0
    while i < len(lines):
        line = lines[i]
        match = SECTION_SEP_PATTERN.match(line)
        if match:
            # Save previous section only if it has actual content
            if has_content(current_lines):
                section_counter += 1
                section_id = current_id if current_id else str(section_counter)
                sec = _make_section(
                    section_id, current_lines, current_title, current_metadata
                )
                sections.append(sec)
            current_lines = []
            current_metadata = {}

            # Extract ID and title from separator line
            header = match.group(1).strip()
            current_id, current_title = _parse_section_header(header)

            # Check for section metadata immediately following separator
            i += 1
            if i < len(lines):
                current_metadata, content_start = _parse_section_metadata(lines, i)
                i = content_start
                continue  # Don't increment i again at end of loop
        else:
            current_lines.append(line)

        i += 1

    # Don't forget the last section
    if has_content(current_lines):
        section_counter += 1
        section_id = current_id if current_id else str(section_counter)
        sec = _make_section(
            section_id, current_lines, current_title, current_metadata
        )
        sections.append(sec)

    return sections


def _make_section(
    section_id: str,
    raw_lines: list[str],
    title: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Section:
    """Create a Section from raw lines."""
    # Strip leading/trailing blank lines
    while raw_lines and not raw_lines[0].strip():
        raw_lines.pop(0)
    while raw_lines and not raw_lines[-1].strip():
        raw_lines.pop()

    # Create numbered Line objects (only for non-empty lines)
    lines: list[Line] = []
    last_number = 0
    for text in raw_lines:
        if text.strip():  # Skip blank lines for numbering
            # Cross-source quotation: > marks verbatim text quoted from another
            # source. Quoted text is preserved as-is (no number/label extraction).
            quote_match = QUOTE_PATTERN.match(text.lstrip())
            if quote_match:
                number = last_number + 1
                last_number = number
                lines.append(
                    Line(text=quote_match.group(1), number=number, is_quote=True)
                )
                continue

            text, number, label = _extract_line_numbering(text, last_number)
            last_number = number

            speaker_match = SPEAKER_PATTERN.match(text)
            if speaker_match:
                speaker = speaker_match.group(1)
                speech = speaker_match.group(2)
                lines.append(
                    Line(text=speech, number=number, speaker=speaker, label=label)
                )
            else:
                lines.append(Line(text=text, number=number, label=label))

    # A label is numeric if it is a single integer or a dotted hierarchy of
    # integers ("1", "3.7", "1.2.3"). Chapter/levels are derived from the id on
    # the Section itself, so nothing extra needs to be passed here.
    parts = section_id.split(".")
    is_numbered = bool(section_id) and all(part.isdigit() for part in parts)

    return Section(
        id=section_id,
        lines=lines,
        is_numbered=is_numbered,
        title=title,
        metadata=metadata or {},
    )


def _extract_line_numbering(
    text: str, last_number: int
) -> tuple[str, int, str | None]:
    """Extract explicit line numbering from a line of text.

    Handles three styles:
    - Leading prefix: "6. suave etiam..." → number=6, text="suave etiam..."
    - Trailing label: "servo id;         980" → number=auto, label="980"
    - Implicit: auto-increment from last_number

    Args:
        text: Raw line text
        last_number: Previous line's number (for auto-increment)

    Returns:
        Tuple of (cleaned_text, number, label)
    """
    label: str | None = None

    # Check for trailing label first (e.g., "text         980" or "983a")
    trailing_match = TRAILING_LABEL_PATTERN.match(text)
    if trailing_match:
        text = trailing_match.group(1).rstrip()
        label = trailing_match.group(2)

    # Check for leading explicit number (e.g., "6. text")
    leading_match = LEADING_NUMBER_PATTERN.match(text)
    if leading_match:
        number = int(leading_match.group(1))
        text = leading_match.group(2)
        return text, number, label

    # Implicit: auto-increment
    number = last_number + 1
    return text, number, label
