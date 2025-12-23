"""CSV-backed screening for predatory journal/publisher registries."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import csv

from .models import ReferenceEntry, ValidationIssue
from .normalization import extract_domain, iter_domain_candidates, normalize_text


@dataclass(frozen=True)
class PredatoryDbRecord:
    name: str
    entry_type: str
    url: Optional[str]
    url_domain: Optional[str]
    url_root: Optional[str]
    risk_level: Optional[str]
    norwegian_level: Optional[str]
    warning_summary: Optional[str]
    manual_links: Dict[str, str]
    entry_id: Optional[str]


@dataclass(frozen=True)
class PredatoryDbMatch:
    record: PredatoryDbRecord
    basis: str
    matched_value: str


_DEFAULT_PROVIDER: "PredatoryDbProvider | None" = None


class PredatoryDbProvider:
    """Load predatory journal/publisher registries and match against references."""

    def __init__(
        self,
        records: List[PredatoryDbRecord],
        name_index: Dict[str, List[PredatoryDbRecord]],
        domain_index: Dict[str, List[PredatoryDbRecord]],
    ) -> None:
        self.records = records
        self._name_index = name_index
        self._domain_index = domain_index

    @classmethod
    def from_csv_paths(cls, paths: Iterable[Path]) -> "PredatoryDbProvider":
        records: Dict[str, PredatoryDbRecord] = {}
        name_index: Dict[str, List[PredatoryDbRecord]] = {}
        domain_index: Dict[str, List[PredatoryDbRecord]] = {}

        for path in paths:
            if not path.exists():
                continue
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    record = _record_from_row(row)
                    record_key = record.entry_id or _record_fallback_key(record)
                    if record_key in records:
                        continue
                    records[record_key] = record
                    _index_record(record, row, name_index, domain_index)

        return cls(list(records.values()), name_index, domain_index)

    @classmethod
    def load_default(cls, base_dir: Path | None = None) -> "PredatoryDbProvider | None":
        global _DEFAULT_PROVIDER
        if _DEFAULT_PROVIDER is not None:
            return _DEFAULT_PROVIDER
        paths = _default_csv_paths(base_dir)
        if not paths:
            return None
        _DEFAULT_PROVIDER = cls.from_csv_paths(paths)
        return _DEFAULT_PROVIDER

    def check_reference(self, reference: ReferenceEntry) -> List[ValidationIssue]:
        matches = self.match_reference(reference)
        issues: List[ValidationIssue] = []
        seen = set()
        for match in matches:
            if match.record in seen:
                continue
            seen.add(match.record)
            issues.append(
                ValidationIssue(
                    code=f"predatory-db-{match.record.entry_type}",
                    message=_build_match_message(match),
                    context=reference.raw_text,
                    severity="warning",
                )
            )
        return issues

    def match_reference(self, reference: ReferenceEntry) -> List[PredatoryDbMatch]:
        matches: List[PredatoryDbMatch] = []
        if reference.journal:
            matches.extend(
                self._match_name(reference.journal, expected_types={"journal", "publisher"})
            )
        if reference.publisher:
            matches.extend(
                self._match_name(reference.publisher, expected_types={"publisher"})
            )
        url_domain = extract_domain(reference.url)
        if url_domain:
            matches.extend(
                self._match_domain(url_domain, expected_types={"journal", "publisher"})
            )
        return matches

    def _match_name(
        self, name: str, expected_types: set[str]
    ) -> List[PredatoryDbMatch]:
        normalized = normalize_text(name)
        if not normalized:
            return []
        records = self._name_index.get(normalized, [])
        matches: List[PredatoryDbMatch] = []
        for record in records:
            if record.entry_type in expected_types:
                matches.append(
                    PredatoryDbMatch(
                        record=record,
                        basis="name",
                        matched_value=name,
                    )
                )
        return matches

    def _match_domain(
        self, domain: str, expected_types: set[str]
    ) -> List[PredatoryDbMatch]:
        matches: List[PredatoryDbMatch] = []
        for candidate in iter_domain_candidates(domain):
            records = self._domain_index.get(candidate, [])
            for record in records:
                if record.entry_type in expected_types:
                    matches.append(
                        PredatoryDbMatch(
                            record=record,
                            basis="domain",
                            matched_value=domain,
                        )
                    )
        return matches


def _record_from_row(row: Dict[str, str]) -> PredatoryDbRecord:
    manual_links = {
        key: value
        for key, value in row.items()
        if key.startswith("manual_check_") and value
    }
    return PredatoryDbRecord(
        name=(row.get("name") or "").strip(),
        entry_type=(row.get("type") or "unknown").strip().lower() or "unknown",
        url=_clean_value(row.get("url")),
        url_domain=_clean_value(row.get("url_domain")),
        url_root=_clean_value(row.get("url_root")),
        risk_level=_clean_value(row.get("risk_level") or row.get("risk")),
        norwegian_level=_clean_value(row.get("norwegian_level")),
        warning_summary=_clean_value(row.get("warning_summary")),
        manual_links=manual_links,
        entry_id=_clean_value(row.get("entry_id")),
    )


def _record_fallback_key(record: PredatoryDbRecord) -> str:
    return f"{record.entry_type}:{normalize_text(record.name)}:{record.url_domain or record.url_root or ''}"


def _index_record(
    record: PredatoryDbRecord,
    row: Dict[str, str],
    name_index: Dict[str, List[PredatoryDbRecord]],
    domain_index: Dict[str, List[PredatoryDbRecord]],
) -> None:
    for key in ("name_norm", "name", "abbr_norm", "abbr"):
        value = row.get(key)
        normalized = normalize_text(value)
        if normalized:
            name_index.setdefault(normalized, []).append(record)

    for key in ("url_domain", "url_root", "url"):
        value = row.get(key)
        domain = extract_domain(value)
        if domain:
            domain_index.setdefault(domain, []).append(record)


def _build_match_message(match: PredatoryDbMatch) -> str:
    record = match.record
    risk = record.risk_level or "unknown"
    norwegian = record.norwegian_level or "Unknown"
    summary = record.warning_summary
    parts = [
        f"Possible predatory {record.entry_type} match: {record.name}",
        f"risk={risk}",
        f"Norwegian level={norwegian}",
        f"match={match.basis}",
    ]
    if summary:
        parts.append(summary)
    link_summary = _format_links(record.manual_links)
    if link_summary:
        parts.append(link_summary)
    return " | ".join(parts)


def _format_links(links: Dict[str, str]) -> str | None:
    if not links:
        return None
    priority = [
        "manual_check_homepage",
        "manual_check_doaj",
        "manual_check_cope",
        "manual_check_nlm_catalog",
        "manual_check_pubmed_search",
        "manual_check_scimagojr",
        "manual_check_kanalregister",
        "manual_check_google",
    ]
    parts = []
    for key in priority:
        url = links.get(key)
        if url:
            label = key.replace("manual_check_", "").replace("_", " ")
            parts.append(f"{label}: {url}")
    if not parts:
        return None
    return "manual checks -> " + "; ".join(parts)


def _default_csv_paths(base_dir: Path | None = None) -> List[Path]:
    candidates: List[Path] = []
    roots = []
    if base_dir:
        roots.append(base_dir)
    roots.extend([Path.cwd(), Path(__file__).resolve().parents[2]])

    preferred = [
        "predatory_db_v7_with_norwegian_levels.csv",
        "predatory_db_v6_manual_check_links.csv",
        "predatory_db_v5_norwegian_levels.csv",
        "predatory_db_v5_norwegian_matches.csv",
    ]

    found_v6 = False
    for root in roots:
        for name in preferred:
            path = root / name
            if path.exists():
                if name == "predatory_db_v7_with_norwegian_levels.csv":
                    candidates = [path]
                    found_v6 = True
                    break
                if not found_v6:
                    candidates.append(path)
        if found_v6:
            break
        data_root = root / "data"
        if data_root.exists() and not found_v6:
            for name in preferred:
                path = data_root / name
                if path.exists():
                    if name == "predatory_db_v7_with_norwegian_levels.csv":
                        candidates = [path]
                        found_v6 = True
                        break
                    candidates.append(path)
        if found_v6:
            break

    # Deduplicate while preserving order.
    unique: List[Path] = []
    seen = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def _clean_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


__all__ = ["PredatoryDbProvider", "PredatoryDbRecord", "PredatoryDbMatch"]
