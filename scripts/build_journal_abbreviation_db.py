#!/usr/bin/env python3
"""Build and enrich journal abbreviation datasets for matching workflows."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from urllib.request import urlopen
import argparse
import csv
import json
import sqlite3
import unicodedata
import re

NCBI_JSON_URL = (
    "https://raw.githubusercontent.com/citation-style-language/abbreviations/master/"
    "ncbi/json/ncbi-abbreviations.json"
)
COMBINED_TERMS_URL = (
    "https://raw.githubusercontent.com/dcsuka/Journal_Abbreviations/master/Combined_Terms.txt"
)


def norm(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("&", " and ").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_text(value: str | None) -> str:
    text = (value or "").strip()
    return re.sub(r"\s+", " ", text)


class AbbreviationDbBuilder:
    def __init__(self) -> None:
        self.abbr_to_full: Dict[str, List[str]] = {}
        self.full_to_abbr: Dict[str, List[str]] = {}
        self.source_links: Dict[str, str] = {
            "csl_ncbi": NCBI_JSON_URL,
            "combined_terms": COMBINED_TERMS_URL,
        }
        self.source_counts: Dict[str, int] = defaultdict(int)
        self.rejected_rows: Dict[str, int] = defaultdict(int)

    def add_mapping(self, abbreviation: str, full_title: str, *, source: str) -> None:
        abbr_clean = clean_text(abbreviation)
        full_clean = clean_text(full_title)
        abbr_norm = norm(abbr_clean)
        title_norm = norm(full_clean)
        if len(abbr_norm) <= 1 or len(title_norm) <= 1:
            self.rejected_rows[source] += 1
            return

        titles = self.abbr_to_full.setdefault(abbr_norm, [])
        if full_clean not in titles:
            titles.append(full_clean)

        abbrs = self.full_to_abbr.setdefault(title_norm, [])
        if abbr_clean not in abbrs:
            abbrs.append(abbr_clean)
        self.source_counts[source] += 1

    def load_csl_ncbi(self) -> int:
        with urlopen(NCBI_JSON_URL) as response:
            payload = json.loads(response.read().decode("utf-8"))
        default_block = payload.get("default", {})
        if not isinstance(default_block, dict):
            return 0
        mapping = default_block.get("container-title", default_block)
        if not isinstance(mapping, dict):
            return 0
        for full_title, abbreviation in mapping.items():
            self.add_mapping(str(abbreviation), str(full_title), source="csl_ncbi")
        return len(mapping)

    def load_combined_terms(self) -> int:
        with urlopen(COMBINED_TERMS_URL) as response:
            raw_text = response.read().decode("utf-8-sig", errors="replace")
        reader = csv.reader(raw_text.splitlines(), delimiter="\t")
        rows = 0
        for cells in reader:
            if not cells:
                continue
            full_title = clean_text(cells[0] if len(cells) >= 1 else "")
            if not full_title:
                self.rejected_rows["combined_terms"] += 1
                continue
            abbreviations = [clean_text(cell) for cell in cells[1:] if clean_text(cell)]
            if not abbreviations:
                self.rejected_rows["combined_terms"] += 1
                continue
            for abbr in abbreviations:
                self.add_mapping(abbr, full_title, source="combined_terms")
            rows += 1
        return rows

    def build_report(self) -> dict:
        collisions = [
            {"abbr_norm": key, "candidate_count": len(values), "candidates": values[:10]}
            for key, values in self.abbr_to_full.items()
            if len(values) > 1
        ]
        collisions.sort(key=lambda row: row["candidate_count"], reverse=True)
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "sources": self.source_links,
            "source_mapping_counts": dict(sorted(self.source_counts.items())),
            "source_rejected_rows": dict(sorted(self.rejected_rows.items())),
            "abbreviation_key_count": len(self.abbr_to_full),
            "full_title_key_count": len(self.full_to_abbr),
            "collision_key_count": len(collisions),
            "largest_collisions": collisions[:50],
        }


def write_json(builder: AbbreviationDbBuilder, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": builder.build_report(),
        "abbr_to_full": dict(sorted(builder.abbr_to_full.items())),
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_sqlite(builder: AbbreviationDbBuilder, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(output_path))
    cur = con.cursor()
    cur.execute("DROP TABLE IF EXISTS abbr_map")
    cur.execute(
        "CREATE TABLE abbr_map (abbr_norm TEXT NOT NULL, full_title TEXT NOT NULL, "
        "PRIMARY KEY (abbr_norm, full_title))"
    )
    rows = [
        (abbr_norm, full_title)
        for abbr_norm, titles in builder.abbr_to_full.items()
        for full_title in titles
    ]
    cur.executemany(
        "INSERT OR REPLACE INTO abbr_map(abbr_norm, full_title) VALUES (?, ?)",
        rows,
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_abbr_map_abbr_norm ON abbr_map(abbr_norm)")
    con.commit()
    con.close()


def write_report(builder: AbbreviationDbBuilder, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(builder.build_report(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def enrich_registry_csv(
    input_path: Path,
    output_path: Path,
    title_to_abbr: Dict[str, List[str]],
) -> dict:
    if not input_path.exists():
        return {"enriched": 0, "journal_rows": 0, "input_found": False}

    with input_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "abbr" not in fieldnames:
        fieldnames.append("abbr")
    if "abbr_norm" not in fieldnames:
        fieldnames.append("abbr_norm")

    enriched = 0
    journal_rows = 0
    for row in rows:
        entry_type = clean_text(row.get("type") or "").lower()
        if entry_type != "journal":
            continue
        journal_rows += 1
        existing_abbr = clean_text(row.get("abbr") or "")
        title_norm = norm(row.get("name"))
        candidates = title_to_abbr.get(title_norm, [])
        if not existing_abbr and candidates:
            row["abbr"] = candidates[0]
            existing_abbr = candidates[0]
            enriched += 1
        row["abbr_norm"] = norm(existing_abbr) if existing_abbr else ""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return {"enriched": enriched, "journal_rows": journal_rows, "input_found": True}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build journal abbreviation datasets")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("data/abbr_to_full.json"),
        help="JSON output path",
    )
    parser.add_argument(
        "--output-sqlite",
        type=Path,
        default=Path("data/abbr_to_full.sqlite"),
        help="SQLite output path",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=Path("data/abbr_build_report.json"),
        help="Build report output path",
    )
    parser.add_argument(
        "--enrich-input",
        type=Path,
        default=Path("predatory_db_v7_with_norwegian_levels.csv"),
        help="Input registry CSV to enrich with journal abbreviations",
    )
    parser.add_argument(
        "--enrich-output",
        type=Path,
        default=Path("data/predatory_db_v7_with_norwegian_levels_enriched.csv"),
        help="Output path for enriched registry CSV",
    )
    parser.add_argument(
        "--skip-enrich",
        action="store_true",
        help="Skip generating enriched registry CSV",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    builder = AbbreviationDbBuilder()
    builder.load_csl_ncbi()
    builder.load_combined_terms()

    write_json(builder, args.output_json)
    write_sqlite(builder, args.output_sqlite)
    write_report(builder, args.output_report)

    enrich_stats = {}
    if not args.skip_enrich:
        enrich_stats = enrich_registry_csv(
            args.enrich_input,
            args.enrich_output,
            builder.full_to_abbr,
        )

    report = builder.build_report()
    print(f"Built {report['abbreviation_key_count']:,} normalized abbreviation keys.")
    print(f"Collision keys: {report['collision_key_count']:,}")
    print(f"Wrote JSON: {args.output_json}")
    print(f"Wrote SQLite: {args.output_sqlite}")
    print(f"Wrote report: {args.output_report}")
    if enrich_stats:
        if not enrich_stats.get("input_found"):
            print(f"Skipped enrichment: input not found at {args.enrich_input}")
        else:
            print(
                "Enriched journal rows with abbreviations: "
                f"{enrich_stats['enriched']:,}/{enrich_stats['journal_rows']:,}"
            )
            print(f"Wrote enriched registry: {args.enrich_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
