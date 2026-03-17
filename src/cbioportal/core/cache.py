"""DuckDB-based cache for cBioPortal API responses and annotations."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from cbioportal.core.cbio_config import get_config

CACHE_DIR = Path.home() / ".cbio" / "cache"
CACHE_DB_PATH = CACHE_DIR / "cache.duckdb"


def get_cache_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Get a connection to the local DuckDB cache."""
    if not read_only:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = duckdb.connect(str(CACHE_DB_PATH), read_only=read_only)
    
    # Initialize schema if missing
    if not read_only:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_manifest (
                study_id VARCHAR,
                data_type VARCHAR,
                molecular_profile_id VARCHAR,
                fetched_at TIMESTAMP,
                PRIMARY KEY (study_id, data_type)
            );
            
            CREATE TABLE IF NOT EXISTS moalmanac_cache (
                variant_hash VARCHAR PRIMARY KEY,
                payload JSON,
                fetched_at TIMESTAMP
            );
        """)
    return conn


def get_study_cache_status(study_id: str, data_type: str) -> dict | None:
    """Check if a study's data is cached and within TTL."""
    try:
        conn = get_cache_connection(read_only=True)
    except duckdb.IOException:
        # DB doesn't exist yet
        return None
        
    try:
        res = conn.execute(
            "SELECT fetched_at, molecular_profile_id FROM cache_manifest WHERE study_id = ? AND data_type = ?",
            [study_id, data_type]
        ).fetchone()
        
        if not res:
            return None
            
        fetched_at, profile_id = res
        ttl_days = get_config().get("cache", {}).get("ttl_days", 180)
        
        # Ensure timezone info matches for comparison (DuckDB returns naive timestamps)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        age_days = (now - fetched_at).days
        
        if age_days > ttl_days:
            return None
            
        return {"fetched_at": fetched_at, "molecular_profile_id": profile_id}
    finally:
        conn.close()


def update_study_cache_manifest(study_id: str, data_type: str, molecular_profile_id: str) -> None:
    """Update the manifest timestamp for a cached study payload."""
    conn = get_cache_connection()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        conn.execute("""
            INSERT INTO cache_manifest (study_id, data_type, molecular_profile_id, fetched_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (study_id, data_type) DO UPDATE SET
                molecular_profile_id = excluded.molecular_profile_id,
                fetched_at = excluded.fetched_at
        """, [study_id, data_type, molecular_profile_id, now])
    finally:
        conn.close()
