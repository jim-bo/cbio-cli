"""Parse meta_*.txt files and store molecular profile metadata in DuckDB."""
from __future__ import annotations

from pathlib import Path

from .discovery import parse_meta_file


def load_molecular_profiles(conn, study_id: str, study_path: Path) -> None:
    """Parse molecular-profile meta files and insert into molecular_profiles table.

    Legacy ref: each study directory contains meta_*.txt files that define
    molecular profiles (e.g. meta_mutations.txt, meta_cna.txt). The legacy Java
    importer reads these into the genetic_profile table; we mirror that here.

    Only files containing a ``genetic_alteration_type`` key are treated as
    molecular-profile metadata — others (meta_study.txt, meta_clinical_*.txt)
    are silently skipped.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS molecular_profiles (
            study_id                      VARCHAR NOT NULL,
            stable_id                     VARCHAR NOT NULL,
            genetic_alteration_type       VARCHAR NOT NULL,
            generic_assay_type            VARCHAR,
            datatype                      VARCHAR,
            profile_name                  VARCHAR,
            profile_description           VARCHAR,
            show_profile_in_analysis_tab  BOOLEAN DEFAULT true,
            data_filename                 VARCHAR,
            pivot_threshold               DOUBLE,
            sort_order                    VARCHAR,
            PRIMARY KEY (study_id, stable_id)
        )
    """)
    # Add new columns to existing tables (idempotent ALTER TABLE)
    for col, typedef in [
        ("generic_assay_type", "VARCHAR"),
        ("pivot_threshold", "DOUBLE"),
        ("sort_order", "VARCHAR"),
    ]:
        try:
            conn.execute(f"ALTER TABLE molecular_profiles ADD COLUMN {col} {typedef}")
        except Exception:
            pass  # column already exists

    # Idempotent: remove stale rows before re-inserting
    conn.execute(
        "DELETE FROM molecular_profiles WHERE study_id = ?", [study_id]
    )

    for meta_path in sorted(study_path.glob("meta_*.txt")):
        name = meta_path.name
        # Skip non-molecular meta files
        if name == "meta_study.txt" or name.startswith("meta_clinical_"):
            continue

        meta = parse_meta_file(meta_path)
        # Must have both genetic_alteration_type and stable_id to be a
        # molecular profile.  Timeline metas (CLINICAL), seg metas, and
        # gene-panel-matrix metas lack stable_id and should be skipped.
        if "genetic_alteration_type" not in meta or not meta.get("stable_id"):
            continue

        show = meta.get("show_profile_in_analysis_tab", "true").lower() == "true"

        pivot = meta.get("pivot_threshold_value")
        try:
            pivot = float(pivot) if pivot is not None else None
        except (ValueError, TypeError):
            pivot = None

        conn.execute(
            """INSERT INTO molecular_profiles
               (study_id, stable_id, genetic_alteration_type, generic_assay_type,
                datatype, profile_name, profile_description,
                show_profile_in_analysis_tab, data_filename,
                pivot_threshold, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (study_id, stable_id) DO UPDATE SET
                   genetic_alteration_type = excluded.genetic_alteration_type,
                   generic_assay_type = excluded.generic_assay_type,
                   datatype = excluded.datatype,
                   profile_name = excluded.profile_name,
                   profile_description = excluded.profile_description,
                   show_profile_in_analysis_tab = excluded.show_profile_in_analysis_tab,
                   data_filename = excluded.data_filename,
                   pivot_threshold = excluded.pivot_threshold,
                   sort_order = excluded.sort_order""",
            [
                study_id,
                meta.get("stable_id", ""),
                meta["genetic_alteration_type"],
                meta.get("generic_assay_type"),
                meta.get("datatype", ""),
                meta.get("profile_name", ""),
                meta.get("profile_description", ""),
                show,
                meta.get("data_filename", ""),
                pivot,
                meta.get("value_sort_order"),
            ],
        )
