"""CSV-backed screening for predatory journal/publisher registries."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import sys
import csv
from difflib import SequenceMatcher

from .journal_abbreviations import (
    ABBR_JSON_FILENAME,
    ABBR_SQLITE_FILENAME,
    abbreviation_candidates,
    load_abbreviation_index,
)
from .models import ReferenceEntry, ValidationIssue
from .normalization import extract_domain, iter_domain_candidates, normalize_text

ENRICHED_PRIMARY_REGISTRY_FILENAME = "predatory_db_v7_with_norwegian_levels_enriched.csv"
PRIMARY_REGISTRY_FILENAME = "predatory_db_v7_with_norwegian_levels.csv"
PUBLISHER_REGISTRY_FILENAME = "pred_pub_list.csv"
JOURNAL_REGISTRY_FILENAME = "pred_jour_list.csv"
PUBLISHER_REGISTRY_SOURCE = "Predatory Journals"
PUBLISHER_REGISTRY_SOURCE_URL = "https://www.predatoryjournals.org/the-list/publishers"
PUBLISHER_REGISTRY_WARNING = "Listed on Predatory Journals publisher list"
JOURNAL_REGISTRY_SOURCE = "Predatory Journals"
JOURNAL_REGISTRY_SOURCE_URL = "https://www.predatoryjournals.org/the-list/journals"
JOURNAL_REGISTRY_WARNING = "Listed on Predatory Journals journal list"


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
    source: Optional[str]
    source_url: Optional[str]
    manual_links: Dict[str, str]
    entry_id: Optional[str]


@dataclass(frozen=True)
class PredatoryDbMatch:
    record: PredatoryDbRecord
    basis: str
    matched_value: str
    score: float | None = None
    expanded_title: str | None = None
    abbreviation_candidates: tuple[str, ...] = ()


_DEFAULT_PROVIDER: "PredatoryDbProvider | None" = None


class PredatoryDbProvider:
    """Load predatory journal/publisher registries and match against references."""

    def __init__(
        self,
        records: List[PredatoryDbRecord],
        name_index: Dict[str, List[PredatoryDbRecord]],
        domain_index: Dict[str, List[PredatoryDbRecord]],
        abbreviation_index: Dict[str, List[str]] | None = None,
    ) -> None:
        self.records = records
        self._name_index = name_index
        self._domain_index = domain_index
        self._abbreviation_index = abbreviation_index or {}

    @classmethod
    def from_csv_paths(
        cls,
        paths: Iterable[Path],
        *,
        abbreviation_paths: Iterable[Path] | None = None,
    ) -> "PredatoryDbProvider":
        records: Dict[str, PredatoryDbRecord] = {}
        name_index: Dict[str, List[PredatoryDbRecord]] = {}
        domain_index: Dict[str, List[PredatoryDbRecord]] = {}

        for path in paths:
            if not path.exists():
                continue
            for record, row in _iter_records_from_path(path):
                record_key = record.entry_id or _record_fallback_key(record)
                if record_key in records:
                    continue
                records[record_key] = record
                _index_record(record, row, name_index, domain_index)

        abbreviation_index = load_abbreviation_index(abbreviation_paths or [])
        return cls(
            list(records.values()),
            name_index,
            domain_index,
            abbreviation_index=abbreviation_index,
        )

    @classmethod
    def load_default(cls, base_dir: Path | None = None) -> "PredatoryDbProvider | None":
        global _DEFAULT_PROVIDER
        if _DEFAULT_PROVIDER is not None:
            return _DEFAULT_PROVIDER
        paths = _default_csv_paths(base_dir)
        if not paths:
            return None
        _DEFAULT_PROVIDER = cls.from_csv_paths(
            paths,
            abbreviation_paths=_default_abbreviation_paths(base_dir),
        )
        return _DEFAULT_PROVIDER

    def abbreviation_candidates(self, value: str | None, *, limit: int = 15) -> List[str]:
        return abbreviation_candidates(self._abbreviation_index, value, limit=limit)

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

    def match_reference(
        self,
        reference: ReferenceEntry,
        *,
        fuzzy: bool = False,
        scan_raw_text: bool = False,
        fuzzy_threshold: float = 0.88,
        max_fuzzy_matches: int = 3,
        fuzzy_token_threshold: float = 0.8,
        abbreviation_limit: int = 15,
        abbreviation_fuzzy_limit: int = 5,
    ) -> List[PredatoryDbMatch]:
        matches: List[PredatoryDbMatch] = []
        name_candidates: list[tuple[str, set[str]]] = []
        if reference.journal:
            name_candidates.append((reference.journal, {"journal", "publisher"}))
            matches.extend(
                self._match_abbreviation(
                    reference.journal,
                    expected_types={"journal", "publisher"},
                    max_candidates=abbreviation_limit,
                    fuzzy=fuzzy,
                    fuzzy_threshold=fuzzy_threshold,
                    max_fuzzy_matches=max_fuzzy_matches,
                    fuzzy_token_threshold=fuzzy_token_threshold,
                    max_fuzzy_expansions=abbreviation_fuzzy_limit,
                )
            )
        if reference.publisher:
            name_candidates.append((reference.publisher, {"publisher"}))
        if fuzzy and not name_candidates and reference.raw_text:
            name_candidates.append((reference.raw_text, {"journal", "publisher"}))

        for name, expected_types in name_candidates:
            matches.extend(self._match_name(name, expected_types=expected_types))
            if fuzzy:
                matches.extend(
                    self._match_name_fuzzy(
                        name,
                        expected_types=expected_types,
                        threshold=fuzzy_threshold,
                        max_matches=max_fuzzy_matches,
                        token_threshold=fuzzy_token_threshold,
                    )
                )
        url_domain = extract_domain(reference.url)
        if url_domain:
            matches.extend(
                self._match_domain(url_domain, expected_types={"journal", "publisher"})
            )
        if scan_raw_text and reference.raw_text:
            matches.extend(
                self._match_name_in_text(
                    reference.raw_text,
                    expected_types={"journal", "publisher"},
                )
            )
        return _dedupe_matches(matches)

    def _match_name(
        self, name: str, expected_types: set[str]
    ) -> List[PredatoryDbMatch]:
        normalized = normalize_text(name)
        if not normalized or len(normalized) <= 1:
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
                        score=1.0,
                    )
                )
        return matches

    def _match_name_fuzzy(
        self,
        name: str,
        expected_types: set[str],
        *,
        threshold: float,
        max_matches: int,
        token_threshold: float,
    ) -> List[PredatoryDbMatch]:
        normalized = normalize_text(name)
        if not normalized or len(normalized) <= 1:
            return []
        token_set = set(normalized.split())
        if not token_set:
            return []
        scored: list[tuple[float, PredatoryDbRecord]] = []
        for candidate_norm, records in self._name_index.items():
            candidate_tokens = set(candidate_norm.split())
            token_ratio = _token_overlap_ratio(token_set, candidate_tokens)
            if token_ratio < token_threshold:
                continue
            score = SequenceMatcher(None, normalized, candidate_norm).ratio()
            if score < threshold:
                continue
            for record in records:
                if record.entry_type in expected_types:
                    scored.append((score, record))
        if not scored:
            return []
        scored.sort(key=lambda item: item[0], reverse=True)
        matches: List[PredatoryDbMatch] = []
        seen: set[str] = set()
        for score, record in scored:
            record_key = record.entry_id or _record_fallback_key(record)
            if record_key in seen:
                continue
            seen.add(record_key)
            matches.append(
                PredatoryDbMatch(
                    record=record,
                    basis="fuzzy-name",
                    matched_value=name,
                    score=score,
                )
            )
            if len(matches) >= max_matches:
                break
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
                            score=1.0,
                        )
                    )
        return matches

    def _match_abbreviation(
        self,
        name: str,
        *,
        expected_types: set[str],
        max_candidates: int,
        fuzzy: bool,
        fuzzy_threshold: float,
        max_fuzzy_matches: int,
        fuzzy_token_threshold: float,
        max_fuzzy_expansions: int,
    ) -> List[PredatoryDbMatch]:
        normalized = normalize_text(name)
        if not normalized or len(normalized) <= 1:
            return []
        candidates = self._abbreviation_index.get(normalized, [])
        if not candidates:
            return []

        capped = list(candidates[:max_candidates]) if max_candidates > 0 else list(candidates)
        candidate_tuple = tuple(capped)
        matches: List[PredatoryDbMatch] = []

        for full_title in capped:
            title_norm = normalize_text(full_title)
            if not title_norm:
                continue
            records = self._name_index.get(title_norm, [])
            for record in records:
                if record.entry_type in expected_types:
                    matches.append(
                        PredatoryDbMatch(
                            record=record,
                            basis="abbrev-name",
                            matched_value=name,
                            score=0.99,
                            expanded_title=full_title,
                            abbreviation_candidates=candidate_tuple,
                        )
                    )

        if matches or not fuzzy:
            return matches

        fuzzy_cap = max(0, min(max_fuzzy_expansions, len(capped)))
        for full_title in capped[:fuzzy_cap]:
            fuzzy_matches = self._match_name_fuzzy(
                full_title,
                expected_types=expected_types,
                threshold=fuzzy_threshold,
                max_matches=max_fuzzy_matches,
                token_threshold=fuzzy_token_threshold,
            )
            for fuzzy_match in fuzzy_matches:
                matches.append(
                    PredatoryDbMatch(
                        record=fuzzy_match.record,
                        basis="abbrev-fuzzy-name",
                        matched_value=name,
                        score=fuzzy_match.score,
                        expanded_title=full_title,
                        abbreviation_candidates=candidate_tuple,
                    )
                )

        return matches

    def _match_name_in_text(
        self,
        text: str,
        *,
        expected_types: set[str],
        min_single_token_len: int = 5,
    ) -> List[PredatoryDbMatch]:
        normalized_text = normalize_text(text)
        if not normalized_text:
            return []

        padded_text = f" {normalized_text} "
        text_tokens = set(normalized_text.split())
        matches: List[PredatoryDbMatch] = []

        for candidate_norm, records in self._name_index.items():
            candidate_tokens = candidate_norm.split()
            if not candidate_tokens:
                continue
            if len(candidate_tokens) == 1 and len(candidate_tokens[0]) < min_single_token_len:
                continue
            if not set(candidate_tokens).issubset(text_tokens):
                continue
            if f" {candidate_norm} " not in padded_text:
                continue
            for record in records:
                if record.entry_type in expected_types:
                    matches.append(
                        PredatoryDbMatch(
                            record=record,
                            basis="text-name",
                            matched_value=record.name,
                            score=0.95,
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
        source=_clean_value(row.get("source")),
        source_url=_clean_value(row.get("source_url")),
        manual_links=manual_links,
        entry_id=_clean_value(row.get("entry_id")),
    )


def _iter_records_from_path(path: Path) -> List[tuple[PredatoryDbRecord, Dict[str, str]]]:
    if path.name.lower() == JOURNAL_REGISTRY_FILENAME:
        return _load_journal_registry(path)
    if path.name.lower() == PUBLISHER_REGISTRY_FILENAME:
        return _load_publisher_registry(path)
    return _load_standard_registry(path)


def _load_standard_registry(path: Path) -> List[tuple[PredatoryDbRecord, Dict[str, str]]]:
    for encoding in ("utf-8", "latin-1"):
        try:
            with path.open(newline="", encoding=encoding) as handle:
                reader = csv.DictReader(handle)
                rows: List[tuple[PredatoryDbRecord, Dict[str, str]]] = []
                for row in reader:
                    if not any(value and value.strip() for value in row.values()):
                        continue
                    record = _record_from_row(row)
                    if not record.name:
                        continue
                    rows.append((record, row))
                return rows
        except UnicodeDecodeError:
            continue
    return []


def _load_publisher_registry(path: Path) -> List[tuple[PredatoryDbRecord, Dict[str, str]]]:
    return _load_simple_named_registry(
        path,
        entry_type="publisher",
        warning_summary=PUBLISHER_REGISTRY_WARNING,
        source=PUBLISHER_REGISTRY_SOURCE,
        source_url=PUBLISHER_REGISTRY_SOURCE_URL,
        skip_tokens={"name", "publisher", "publishers"},
    )


def _load_journal_registry(path: Path) -> List[tuple[PredatoryDbRecord, Dict[str, str]]]:
    return _load_simple_named_registry(
        path,
        entry_type="journal",
        warning_summary=JOURNAL_REGISTRY_WARNING,
        source=JOURNAL_REGISTRY_SOURCE,
        source_url=JOURNAL_REGISTRY_SOURCE_URL,
        skip_tokens={"name", "journal", "journals"},
    )


def _load_simple_named_registry(
    path: Path,
    *,
    entry_type: str,
    warning_summary: str,
    source: str,
    source_url: str,
    skip_tokens: set[str],
) -> List[tuple[PredatoryDbRecord, Dict[str, str]]]:
    for encoding in ("utf-8", "latin-1"):
        try:
            with path.open(newline="", encoding=encoding) as handle:
                reader = csv.reader(handle)
                rows: List[tuple[PredatoryDbRecord, Dict[str, str]]] = []
                for cells in reader:
                    cleaned_cells = [cell.strip() for cell in cells if cell and cell.strip()]
                    if not cleaned_cells:
                        continue

                    non_numeric = [cell for cell in cleaned_cells if not cell.isdigit()]
                    if not non_numeric:
                        continue
                    name = non_numeric[-1]
                    if name.lower() in skip_tokens:
                        continue
                    # Some source lists include alphabet separators like "C", "J".
                    # Treat 1-character names as non-record noise.
                    if len(normalize_text(name)) <= 1:
                        continue

                    row = {
                        "name": name,
                        "type": entry_type,
                        "risk_level": "High",
                        "warning_summary": warning_summary,
                        "source": source,
                        "source_url": source_url,
                    }
                    record = _record_from_row(row)
                    rows.append((record, row))
                return rows
        except UnicodeDecodeError:
            continue
    return []


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
        if normalized and len(normalized) > 1:
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
    if match.score is not None and match.basis.startswith("fuzzy"):
        parts.append(f"similarity={match.score:.2f}")
    if match.expanded_title:
        parts.append(f"expanded={match.expanded_title}")
    if len(match.abbreviation_candidates) > 1:
        parts.append(f"abbrev-candidates={len(match.abbreviation_candidates)}")
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


def _bundle_roots() -> List[Path]:
    roots: List[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))
    try:
        roots.append(Path(sys.executable).resolve().parent)
    except Exception:
        pass
    return roots


def _default_csv_paths(base_dir: Path | None = None) -> List[Path]:
    roots: List[Path] = []
    if base_dir:
        roots.append(base_dir)
    roots.extend(_bundle_roots())
    roots.extend([Path.cwd(), Path(__file__).resolve().parents[2]])

    filenames = [
        ENRICHED_PRIMARY_REGISTRY_FILENAME,
        PRIMARY_REGISTRY_FILENAME,
        PUBLISHER_REGISTRY_FILENAME,
        JOURNAL_REGISTRY_FILENAME,
    ]
    candidates: List[Path] = []
    for root in roots:
        for filename in filenames:
            direct = root / filename
            if direct.exists():
                candidates.append(direct)
            data_path = root / "data" / filename
            if data_path.exists():
                candidates.append(data_path)

    unique: List[Path] = []
    seen = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def _default_abbreviation_paths(base_dir: Path | None = None) -> List[Path]:
    roots: List[Path] = []
    if base_dir:
        roots.append(base_dir)
    roots.extend(_bundle_roots())
    roots.extend([Path.cwd(), Path(__file__).resolve().parents[2]])

    filenames = [ABBR_JSON_FILENAME, ABBR_SQLITE_FILENAME]
    candidates: List[Path] = []
    for root in roots:
        for filename in filenames:
            direct = root / filename
            if direct.exists():
                candidates.append(direct)
            data_path = root / "data" / filename
            if data_path.exists():
                candidates.append(data_path)

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


def _dedupe_matches(matches: List[PredatoryDbMatch]) -> List[PredatoryDbMatch]:
    best: Dict[str, PredatoryDbMatch] = {}
    for match in matches:
        record_key = match.record.entry_id or _record_fallback_key(match.record)
        key = f"{record_key}:{match.basis}"
        current = best.get(key)
        current_score = current.score if current and current.score is not None else 0.0
        match_score = match.score if match.score is not None else 0.0
        if current is None or match_score > current_score:
            best[key] = match
    return list(best.values())


def _token_overlap_ratio(tokens: set[str], candidate_tokens: set[str]) -> float:
    if not tokens or not candidate_tokens:
        return 0.0
    overlap = len(tokens & candidate_tokens)
    return overlap / max(len(tokens), len(candidate_tokens))
