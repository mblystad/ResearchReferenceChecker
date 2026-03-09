"""Reference validation and formatting toolkit."""

from .app import ReferenceCheckerApp
from .models import Citation, ReferenceEntry, ValidationIssue, DocumentExtraction
from .link_checker import LinkVerifier
from .web_metadata import WebPageMetadataProvider
from .crossref import CrossrefMetadataProvider, OnlineReferenceVerifier
from .doaj import DoajClient, DoajJournalMatch
from .predatory_db import PredatoryDbProvider

__all__ = [
    "ReferenceCheckerApp",
    "Citation",
    "ReferenceEntry",
    "ValidationIssue",
    "DocumentExtraction",
    "LinkVerifier",
    "WebPageMetadataProvider",
    "CrossrefMetadataProvider",
    "OnlineReferenceVerifier",
    "DoajClient",
    "DoajJournalMatch",
    "PredatoryDbProvider",
]
