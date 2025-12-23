"""Normalization helpers for reference parsing and database matching."""
from __future__ import annotations

from urllib.parse import urlparse
import re
import unicodedata


def normalize_text(value: str | None) -> str:
    """Normalize text for matching against CSV registries."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("&", " and ").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_domain(value: str | None) -> str | None:
    """Extract a normalized domain from a URL or hostname."""
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"http://{raw}"
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    domain = parsed.netloc or parsed.path
    if not domain:
        return None
    domain = domain.split("/")[0].lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain or None


def iter_domain_candidates(domain: str) -> list[str]:
    """Yield domain suffixes for matching (e.g., a.b.com -> a.b.com, b.com, com)."""
    if not domain:
        return []
    parts = [part for part in domain.split(".") if part]
    if len(parts) < 2:
        return [domain]
    return [".".join(parts[i:]) for i in range(len(parts) - 1)]
