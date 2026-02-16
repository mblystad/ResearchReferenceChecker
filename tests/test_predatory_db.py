from pathlib import Path

from reference_checker.models import ReferenceEntry
from reference_checker.predatory_db import (
    JOURNAL_REGISTRY_FILENAME,
    JOURNAL_REGISTRY_SOURCE,
    JOURNAL_REGISTRY_SOURCE_URL,
    PUBLISHER_REGISTRY_FILENAME,
    PUBLISHER_REGISTRY_SOURCE,
    PUBLISHER_REGISTRY_SOURCE_URL,
    PredatoryDbProvider,
    _default_csv_paths,
)


def test_publisher_registry_csv_matches_reference_publisher(tmp_path: Path):
    csv_path = tmp_path / PUBLISHER_REGISTRY_FILENAME
    csv_path.write_text(
        "1,Example Predatory Press\n"
        "2,\"Another Predatory Publisher, Ltd.\"\n",
        encoding="utf-8",
    )

    provider = PredatoryDbProvider.from_csv_paths([csv_path])
    reference = ReferenceEntry(
        raw_text="Doe J. Book title. Example Predatory Press; 2021.",
        publisher="Example Predatory Press",
    )

    matches = provider.match_reference(reference)

    assert matches, "Expected publisher-list match for known publisher"
    match = matches[0]
    assert match.record.entry_type == "publisher"
    assert match.record.name == "Example Predatory Press"
    assert match.record.source == PUBLISHER_REGISTRY_SOURCE
    assert match.record.source_url == PUBLISHER_REGISTRY_SOURCE_URL
    assert match.record.risk_level == "High"


def test_default_csv_paths_include_publisher_registry(tmp_path: Path):
    publisher_list_path = tmp_path / PUBLISHER_REGISTRY_FILENAME
    publisher_list_path.write_text("1,Example Predatory Press\n", encoding="utf-8")

    paths = _default_csv_paths(base_dir=tmp_path)

    assert publisher_list_path in paths


def test_journal_registry_csv_matches_reference_journal(tmp_path: Path):
    csv_path = tmp_path / JOURNAL_REGISTRY_FILENAME
    csv_path.write_text(
        "1,Example Predatory Journal\n"
        "2,\"Another Questionable Journal\"\n",
        encoding="utf-8",
    )

    provider = PredatoryDbProvider.from_csv_paths([csv_path])
    reference = ReferenceEntry(
        raw_text="Doe J. Article title. Example Predatory Journal. 2021.",
        journal="Example Predatory Journal",
    )

    matches = provider.match_reference(reference)

    assert matches, "Expected journal-list match for known journal"
    match = matches[0]
    assert match.record.entry_type == "journal"
    assert match.record.name == "Example Predatory Journal"
    assert match.record.source == JOURNAL_REGISTRY_SOURCE
    assert match.record.source_url == JOURNAL_REGISTRY_SOURCE_URL
    assert match.record.risk_level == "High"


def test_default_csv_paths_include_journal_registry(tmp_path: Path):
    journal_list_path = tmp_path / JOURNAL_REGISTRY_FILENAME
    journal_list_path.write_text("1,Example Predatory Journal\n", encoding="utf-8")

    paths = _default_csv_paths(base_dir=tmp_path)

    assert journal_list_path in paths
