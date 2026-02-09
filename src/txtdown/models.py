"""Data models for txtdown documents."""

from dataclasses import dataclass, field
from typing import Any


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
    """
    text: str
    number: int
    speaker: str | None = None

    def __str__(self) -> str:
        return self.text


@dataclass
class Section:
    """A section of text (poem, chapter, etc.).

    Attributes:
        id: Section identifier (number or name)
        lines: List of lines in this section
        is_numbered: Whether the ID is a number (vs. a name)
        title: Optional section title
        metadata: Section-specific metadata (supersedes document metadata)

    Note:
        Indexing with [] uses 1-based indexing to match scholarly citations.
        Use section[1] for the first line, not section[0].
    """
    id: str
    lines: list[Line] = field(default_factory=list)
    is_numbered: bool = True
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Return section text as a single string."""
        return "\n".join(line.text for line in self.lines)

    def __len__(self) -> int:
        return len(self.lines)

    def __getitem__(self, index: int) -> Line:
        """Get line by 1-indexed number."""
        if index < 1 or index > len(self.lines):
            raise IndexError(f"Line {index} out of range (1-{len(self.lines)})")
        return self.lines[index - 1]


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

    def get(self, citation: str) -> Line | Section:
        """Retrieve content by citation.

        Args:
            citation: Citation string like "2" (section) or "2.3" (section.line)

        Returns:
            Section if single-level citation, Line if two-level

        Raises:
            KeyError: If section or line not found
        """
        parts = citation.split(".")

        # Find section
        section_id = parts[0]
        section = None
        for s in self.sections:
            if s.id == section_id:
                section = s
                break

        if section is None:
            raise KeyError(f"Section '{section_id}' not found")

        # Return section or line
        if len(parts) == 1:
            return section

        try:
            line_num = int(parts[1])
            return section[line_num]
        except (ValueError, IndexError) as e:
            msg = f"Line '{parts[1]}' not found in section '{section_id}'"
            raise KeyError(msg) from e

    def __len__(self) -> int:
        return len(self.sections)

    def __getitem__(self, index: int) -> Section:
        """Get section by 1-indexed number."""
        if index < 1 or index > len(self.sections):
            raise IndexError(f"Section {index} out of range (1-{len(self.sections)})")
        return self.sections[index - 1]
