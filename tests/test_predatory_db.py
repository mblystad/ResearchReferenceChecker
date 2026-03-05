from pathlib import Path
import json

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


def test_raw_text_name_scan_catches_publisher_without_structured_fields(tmp_path: Path):
    csv_path = tmp_path / "custom_watchlist.csv"
    csv_path.write_text(
        "name,type,url_domain,risk_level\n"
        "Springer,publisher,,Medium\n",
        encoding="utf-8",
    )

    provider = PredatoryDbProvider.from_csv_paths([csv_path])
    reference = ReferenceEntry(
        raw_text=(
            "Hastie, T., Tibshirani, R., & Friedman, J. (2009). The elements of statistical learning. "
            "Springer. https://doi.org/10.1007/978-0-387-84858-7"
        ),
    )

    default_matches = provider.match_reference(reference, fuzzy=True)
    text_scan_matches = provider.match_reference(reference, fuzzy=True, scan_raw_text=True)

    assert not default_matches
    assert text_scan_matches
    assert any(m.record.name == "Springer" and m.basis == "text-name" for m in text_scan_matches)


def test_single_letter_registry_rows_are_ignored_in_simple_lists(tmp_path: Path):
    csv_path = tmp_path / JOURNAL_REGISTRY_FILENAME
    csv_path.write_text(
        "1,C\n"
        "2,Example Predatory Journal\n"
        "3,J\n",
        encoding="utf-8",
    )
    provider = PredatoryDbProvider.from_csv_paths([csv_path])

    reference = ReferenceEntry(
        raw_text="Smith A. Title. J. 2024.",
        journal="J",
    )
    matches = provider.match_reference(reference)

    assert not matches


def test_single_letter_name_not_indexed_from_standard_csv(tmp_path: Path):
    csv_path = tmp_path / "custom_watchlist.csv"
    csv_path.write_text(
        "name,type,url_domain,risk_level\n"
        "J,journal,,High\n"
        "Nature,journal,,Medium\n",
        encoding="utf-8",
    )
    provider = PredatoryDbProvider.from_csv_paths([csv_path])

    bad_reference = ReferenceEntry(raw_text="J.", journal="J")
    good_reference = ReferenceEntry(raw_text="Nature article.", journal="Nature")

    assert not provider.match_reference(bad_reference)
    assert provider.match_reference(good_reference)


def test_abbreviation_expansion_matches_journal_name(tmp_path: Path):
    csv_path = tmp_path / "custom_watchlist.csv"
    csv_path.write_text(
        "name,type,url_domain,risk_level\n"
        "World Journal of Engineering and Technology,journal,,High\n",
        encoding="utf-8",
    )
    abbr_path = tmp_path / "abbr_to_full.json"
    abbr_path.write_text(
        json.dumps(
            {
                "abbr_to_full": {
                    "World J Eng Technol": [
                        "World Journal of Engineering and Technology",
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    provider = PredatoryDbProvider.from_csv_paths(
        [csv_path],
        abbreviation_paths=[abbr_path],
    )
    reference = ReferenceEntry(
        raw_text=(
            "Nashif S. Heart disease detection. "
            "World J. Eng. Technol. 2018;6:854-873."
        ),
        journal="World J. Eng. Technol.",
    )

    matches = provider.match_reference(reference, fuzzy=True)

    assert any(match.basis == "abbrev-name" for match in matches)
    assert any(
        match.expanded_title == "World Journal of Engineering and Technology"
        for match in matches
    )
    assert provider.abbreviation_candidates(reference.journal) == [
        "World Journal of Engineering and Technology"
    ]


def test_abbreviation_collisions_keep_all_candidate_titles(tmp_path: Path):
    csv_path = tmp_path / "custom_watchlist.csv"
    csv_path.write_text(
        "name,type,url_domain,risk_level\n"
        "Alpha Science Journal,journal,,High\n"
        "Applied Systems Journal,journal,,Medium\n",
        encoding="utf-8",
    )
    abbr_path = tmp_path / "abbr_to_full.json"
    abbr_path.write_text(
        json.dumps(
            {
                "abbr_to_full": {
                    "A S J": [
                        "Alpha Science Journal",
                        "Applied Systems Journal",
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    provider = PredatoryDbProvider.from_csv_paths(
        [csv_path],
        abbreviation_paths=[abbr_path],
    )
    reference = ReferenceEntry(
        raw_text="Doe J. Study title. A. S. J. 2022.",
        journal="A. S. J.",
    )

    matches = provider.match_reference(reference)
    matched_names = {match.record.name for match in matches}
    candidates = provider.abbreviation_candidates(reference.journal)

    assert matched_names == {"Alpha Science Journal", "Applied Systems Journal"}
    assert candidates == ["Alpha Science Journal", "Applied Systems Journal"]
