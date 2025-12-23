from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Tuple

from reference_checker.normalization import normalize_text

ROOT = Path(__file__).resolve().parents[1]
NORWEGIAN_PATH = ROOT / "2025-12-23 Scientific Journals and Series.csv"
PREDATORY_PATH = ROOT / "predatory_db_v6_manual_check_links.csv"
OUTPUT_PATH = ROOT / "predatory_db_v7_with_norwegian_levels.csv"

LEVEL_PRIORITY = {"2": 3, "1": 2, "0": 1}


def _level_columns(fieldnames: list[str]) -> list[str]:
    level_cols = []
    for name in fieldnames:
        if name.startswith("Level "):
            level_cols.append(name)
    level_cols.sort(key=lambda col: int(col.split()[-1]), reverse=True)
    return level_cols


def _pick_level(row: dict, level_cols: list[str]) -> Tuple[str | None, int | None]:
    for col in level_cols:
        value = (row.get(col) or "").strip()
        if value:
            year = int(col.split()[-1])
            return value, year
    return None, None


def _update_mapping(
    mapping: Dict[str, Tuple[str, int | None, str]],
    key: str,
    level: str,
    year: int | None,
    basis: str,
) -> None:
    if not key or level not in LEVEL_PRIORITY:
        return
    current = mapping.get(key)
    if not current:
        mapping[key] = (level, year, basis)
        return
    current_level, current_year, _ = current
    if LEVEL_PRIORITY[level] > LEVEL_PRIORITY.get(current_level, 0):
        mapping[key] = (level, year, basis)
        return
    if LEVEL_PRIORITY[level] == LEVEL_PRIORITY.get(current_level, 0):
        if year and (current_year is None or year > current_year):
            mapping[key] = (level, year, basis)


def build_mappings() -> tuple[dict, dict, str]:
    if not NORWEGIAN_PATH.exists():
        raise FileNotFoundError(f"Missing Norwegian CSV: {NORWEGIAN_PATH}")

    journal_map: Dict[str, Tuple[str, int | None, str]] = {}
    publisher_map: Dict[str, Tuple[str, int | None, str]] = {}

    with NORWEGIAN_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        if not reader.fieldnames:
            raise RuntimeError("Norwegian CSV missing headers")
        level_cols = _level_columns(reader.fieldnames)

        for row in reader:
            level, year = _pick_level(row, level_cols)
            if not level:
                continue
            original_title = (row.get("Original Title") or "").strip()
            international_title = (row.get("International Title") or "").strip()
            publisher = (row.get("Publisher") or "").strip()
            publishing_company = (row.get("Publishing Company") or "").strip()

            if original_title:
                _update_mapping(
                    journal_map,
                    normalize_text(original_title),
                    level,
                    year,
                    "norwegian_csv_original_title",
                )
            if international_title:
                _update_mapping(
                    journal_map,
                    normalize_text(international_title),
                    level,
                    year,
                    "norwegian_csv_international_title",
                )
            if publisher:
                _update_mapping(
                    publisher_map,
                    normalize_text(publisher),
                    level,
                    year,
                    "norwegian_csv_publisher",
                )
            if publishing_company:
                _update_mapping(
                    publisher_map,
                    normalize_text(publishing_company),
                    level,
                    year,
                    "norwegian_csv_publishing_company",
                )

    return journal_map, publisher_map, NORWEGIAN_PATH.name


def merge_levels() -> None:
    if not PREDATORY_PATH.exists():
        raise FileNotFoundError(f"Missing predatory CSV: {PREDATORY_PATH}")

    journal_map, publisher_map, source_name = build_mappings()

    updated = 0
    total = 0

    with PREDATORY_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = []

        for row in reader:
            total += 1
            entry_type = (row.get("type") or "").strip().lower()
            name = (row.get("name") or "").strip()
            key = normalize_text(name)

            match = None
            if entry_type == "journal":
                match = journal_map.get(key)
            elif entry_type == "publisher":
                match = publisher_map.get(key)

            if match:
                level, year, basis = match
                row["norwegian_level"] = level
                row["norwegian_level_checked"] = "True"
                if year:
                    row["norwegian_level_year"] = str(year)
                row["norwegian_level_basis"] = basis
                row["norwegian_level_source"] = source_name
                updated += 1

            rows.append(row)

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Updated Norwegian levels for {updated} / {total} entries.")
    print(f"Wrote merged file: {OUTPUT_PATH}")


if __name__ == "__main__":
    merge_levels()
