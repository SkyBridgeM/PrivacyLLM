"""Validated local configuration and persistence."""

from .models import CustomRegexRule, DictionaryEntry
from .store import JsonConfigStore

__all__ = ["CustomRegexRule", "DictionaryEntry", "JsonConfigStore"]

