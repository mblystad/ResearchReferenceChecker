"""Simple URL/DOI link verification helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional
import urllib.request


@dataclass
class LinkCheckResult:
    url: str
    reachable: bool
    status_code: Optional[int] = None
    error: Optional[str] = None


class LinkVerifier:
    """Performs lightweight HTTP reachability checks for DOIs/URLs."""

    def __init__(self, requester: Callable[[str], int] | None = None, timeout: float = 5.0):
        self.requester = requester or self._default_requester
        self.timeout = timeout

    def check(self, url: str) -> LinkCheckResult:
        try:
            status = self.requester(url)
            return LinkCheckResult(url=url, reachable=200 <= status < 400, status_code=status)
        except Exception as exc:  # pragma: no cover - network errors are surfaced as issues
            return LinkCheckResult(url=url, reachable=False, error=str(exc))

    def _default_requester(self, url: str) -> int:
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # type: ignore[attr-defined]
            return getattr(response, "status", response.getcode())
