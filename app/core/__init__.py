"""Framework-independent redaction core."""

from .anonymizer import anonymize
from .entities import Entity
from .mapping import MappingDocument
from .restorer import restore

__all__ = ["Entity", "MappingDocument", "anonymize", "restore"]

