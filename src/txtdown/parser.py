"""Parser for txtdown format."""

import re
from pathlib import Path
from typing import Any

import yaml

from .models import Document, Line, Metadata, Section

# Pattern for section separator: --- optionally followed by ID
# Must be at start of line, at least 3 dashes
SECTION_SEP_PATTERN = re.compile(r"^-{3,}\s*(.*)$")


def parse(source: str | Path) -> Document:
    """Parse a txtdown file or string.

    Args:
        source: File path or txtdown content string

    Returns:
        Parsed Document object
    """
    # Handle file path vs string
    is_path = isinstance(source, Path)
    is_path = is_path or (isinstance(source, str) and _looks_like_path(source))
    if is_path:
        path = Path(source)
        content = path.read_text(encoding="utf-8")
    else:
        content = source

    return _parse_content(content)


def _looks_like_path(s: str) -> bool:
    """Heuristic to detect if string is a file path."""
    # If it starts with ---, it's content
    if s.strip().startswith("---"):
        return False
    # If it contains newlines, it's content
    if "\n" in s:
        return False
    # If it ends with .txtdown or .td, it's a path
    if s.endswith((".txtd", ".txtdown")):
        return True
    # If it exists as a file, it's a path
    return Path(s).exists()


def _parse_content(content: str) -> Document:
    """Parse txtdown content string."""
    lines = content.split("\n")

    # Extract front matter
    metadata, body_start = _parse_front_matter(lines)

    # Parse body into sections
    sections = _parse_sections(lines[body_start:])

    return Document(metadata=metadata, sections=sections)


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
    except yaml.YAMLError:
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
    line_num = 0
    for text in raw_lines:
        if text.strip():  # Skip blank lines for numbering
            line_num += 1
            lines.append(Line(text=text, number=line_num))

    # Determine if ID is numeric
    is_numbered = section_id.isdigit()

    return Section(
        id=section_id,
        lines=lines,
        is_numbered=is_numbered,
        title=title,
        metadata=metadata or {},
    )
