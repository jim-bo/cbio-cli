"""Variant annotation pipeline.

Public API:
    annotate_study(conn, study_id, cache_db_path, force, skip_vibe_vep)
    refresh_reference_data()
"""
from __future__ import annotations

import logging

from ..cache import CACHE_DB_PATH, get_cache_connection
from .annotators import annotate_cna, annotate_mutations, annotate_sv
from .reference import ensure_all_reference_data, refresh_all_reference_data
from .vep import annotate_with_vep, is_vep_available
from .writer import TABLE_SUFFIX, write_variant_annotations  # noqa: F401

logger = logging.getLogger(__name__)

__all__ = ["annotate_study", "refresh_reference_data", "TABLE_SUFFIX"]


def _is_annotated(conn, study_id: str) -> bool:
    """Return True if a non-empty annotations table already exists."""
    table = f"{study_id}_variant_annotations"
    exists = conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_name = ?",
        (table,),
    ).fetchone()
    if not exists:
        return False
    count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    return count > 0


def annotate_study(
    conn,
    study_id: str,
    cache_db_path: str | None = None,
    force: bool = False,
    skip_vibe_vep: bool = False,
) -> dict:
    """Annotate all alterations for a study and write variant_annotations table.

    Args:
        conn:           Open connection to the study DuckDB.
        study_id:       Study identifier.
        cache_db_path:  Path to cache DuckDB; defaults to CACHE_DB_PATH.
        force:          Drop and rebuild even if already annotated.
        skip_vibe_vep:  Skip vibe-vep even if available.

    Returns:
        dict with keys: mutations, cna, sv, total (row counts), skipped (bool).
    """
    if cache_db_path is None:
        cache_db_path = str(CACHE_DB_PATH)

    if not force and _is_annotated(conn, study_id):
        logger.info("Study %s already annotated; use force=True to rebuild", study_id)
        count = conn.execute(
            f'SELECT COUNT(*) FROM "{study_id}_variant_annotations"'
        ).fetchone()[0]
        return {"mutations": 0, "cna": 0, "sv": 0, "total": count, "skipped": True}

    # ── 1. Ensure reference data is up-to-date ───────────────────────────────
    conn_cache = get_cache_connection()
    try:
        ensure_all_reference_data(conn_cache)
    finally:
        conn_cache.close()

    # ── 2. vibe-vep (optional) ───────────────────────────────────────────────
    vep_lookup: dict | None = None
    if not skip_vibe_vep and is_vep_available():
        logger.info("Running vibe-vep for %s", study_id)
        vep_lookup = annotate_with_vep(conn, study_id)

    # ── 3. Annotators ────────────────────────────────────────────────────────
    logger.info("Annotating mutations for %s", study_id)
    mut_rows = annotate_mutations(conn, study_id, cache_db_path, vep_lookup)

    logger.info("Annotating CNAs for %s", study_id)
    cna_rows = annotate_cna(conn, study_id, cache_db_path)

    logger.info("Annotating SVs for %s", study_id)
    sv_rows = annotate_sv(conn, study_id, cache_db_path)

    all_rows = mut_rows + cna_rows + sv_rows

    # ── 4. Write ──────────────────────────────────────────────────────────────
    total = write_variant_annotations(conn, study_id, all_rows)

    summary = {
        "mutations": len(mut_rows),
        "cna": len(cna_rows),
        "sv": len(sv_rows),
        "total": total,
        "skipped": False,
    }
    logger.info(
        "Annotation complete for %s: %d mutations, %d cna, %d sv (%d total rows)",
        study_id,
        summary["mutations"],
        summary["cna"],
        summary["sv"],
        total,
    )
    return summary


def refresh_reference_data() -> None:
    """Force re-download all reference data."""
    conn_cache = get_cache_connection()
    try:
        refresh_all_reference_data(conn_cache)
    finally:
        conn_cache.close()
