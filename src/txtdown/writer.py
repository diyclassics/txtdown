"""Writer for txtdown format."""

from pathlib import Path

import yaml

from .models import Document


def write(doc: Document, path: str | Path | None = None) -> str:
    """Write a Document to txtdown format.

    Args:
        doc: Document to serialize
        path: Optional file path to write to

    Returns:
        The txtdown content as a string
    """
    content = _serialize(doc)

    if path is not None:
        Path(path).write_text(content, encoding="utf-8")

    return content


def _serialize(doc: Document) -> str:
    """Serialize Document to txtdown string."""
    parts: list[str] = []

    # Front matter
    meta_dict = doc.metadata.to_dict()
    if meta_dict:
        parts.append("---")
        # Use yaml.dump with default_flow_style=False for readable output
        yaml_str = yaml.dump(meta_dict, default_flow_style=False, allow_unicode=True)
        parts.append(yaml_str.rstrip())
        parts.append("---")
        parts.append("")

    # Sections
    for i, section in enumerate(doc.sections):
        # Section separator (except before first section)
        if i > 0:
            parts.append("")
            parts.append("---")

        # Add explicit ID if section has non-numeric or non-sequential ID
        expected_id = str(i + 1)
        needs_header = section.id != expected_id or section.title
        if needs_header:
            # Build header: "--- id" or "--- id: title"
            if section.title:
                header = f"--- {section.id}: {section.title}"
            else:
                header = f"--- {section.id}"
            # Rewrite the separator with ID/title
            if i > 0:
                parts[-1] = header
            else:
                # First section with explicit ID
                parts.append(header)

        # Section metadata (immediately after separator, no blank line)
        if section.metadata:
            for key, value in section.metadata.items():
                if isinstance(value, bool):
                    value_str = "true" if value else "false"
                else:
                    value_str = str(value)
                parts.append(f"{key}: {value_str}")

        # Blank line before content
        parts.append("")

        # Section content
        for line in section.lines:
            if line.speaker:
                parts.append(f"@{line.speaker}: {line.text}")
            else:
                parts.append(line.text)

    # Ensure trailing newline
    content = "\n".join(parts)
    if not content.endswith("\n"):
        content += "\n"

    return content
