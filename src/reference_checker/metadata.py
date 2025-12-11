"""Metadata enrichment providers."""
from __future__ import annotations

from typing import List

from .models import ReferenceEntry


class MetadataProvider:
    """Base interface for metadata enrichment."""

    name: str = "base"

    def enrich(self, entry: ReferenceEntry) -> ReferenceEntry:  # pragma: no cover - interface
        raise NotImplementedError


class CompositeMetadataProvider(MetadataProvider):
    """Chain multiple providers until data is enriched."""

    def __init__(self, providers: List[MetadataProvider]):
        self.providers = providers
        self.name = "composite"

    def enrich(self, entry: ReferenceEntry) -> ReferenceEntry:
        enriched = entry
        for provider in self.providers:
            enriched = provider.enrich(enriched)
        return enriched


class StaticMetadataProvider(MetadataProvider):
    """Simple provider suitable for tests and offline enrichment."""

    def __init__(self, static_map: dict[str, dict[str, str]]):
        self.static_map = static_map
        self.name = "static"

    def enrich(self, entry: ReferenceEntry) -> ReferenceEntry:
        key = entry.formatted_key()
        if key in self.static_map:
            data = self.static_map[key]
            for field, value in data.items():
                if getattr(entry, field, None) in (None, "") and value:
                    setattr(entry, field, value)
        return entry
