"""txtdown: Minimal markup for Latin text collections.

Example usage:
    >>> from txtdown import parse
    >>> doc = parse("sulpicia.txtd")
    >>> print(doc.metadata.author)
    Sulpicia
    >>> print(doc.sections[0].lines[0].text)
    Tandem venit amor, qualem texisse pudori
    >>> line = doc.get("1.3")
    >>> print(line.text)
    exorata meis illum Cytherea Camenis
"""

from .models import Document, Line, Metadata, Section
from .parser import parse
from .writer import write

__version__ = "0.2.0"

__all__ = [
    "Document",
    "Line",
    "Metadata",
    "Section",
    "parse",
    "write",
    "__version__",
]
