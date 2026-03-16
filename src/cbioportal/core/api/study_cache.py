"""Local cache for cBioPortal study list, keyed by portal URL."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from cbioportal.core.api.models import Study

CACHE_PATH = Path.home() / ".cbio" / "studies_cache.json"
CACHE_VERSION = 2  # bump when cache schema changes


def load(portal_url: str, ttl_days: int) -> list[Study] | None:
    """Return cached studies if fresh and matching portal_url, else None."""
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    if data.get("version", 1) != CACHE_VERSION:
        return None

    if data.get("portal_url") != portal_url:
        return None

    fetched_at = data.get("fetched_at")
    if not fetched_at:
        return None

    age_days = (
        datetime.now(tz=timezone.utc)
        - datetime.fromisoformat(fetched_at)
    ).days
    if age_days > ttl_days:
        return None

    return [Study.model_validate(s) for s in data.get("studies", [])]


def save(portal_url: str, studies: list[Study]) -> None:
    """Write studies to cache file."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": CACHE_VERSION,
        "portal_url": portal_url,
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        "studies": [s.model_dump() for s in studies],
    }
    CACHE_PATH.write_text(json.dumps(payload, indent=2))


def search(
    studies: list[Study],
    query: str,
    cancer_type: str | None = None,
    min_samples: int | None = None,
) -> list[Study]:
    """Filter studies by query words (case-insensitive substring match)."""
    words = query.lower().split()
    results = []
    for study in studies:
        haystack = " ".join([
            study.studyId,
            study.name,
            study.description or "",
            study.cancerType.name if study.cancerType else "",
        ]).lower()
        if all(w in haystack for w in words):
            results.append(study)

    if cancer_type is not None:
        ct_lower = cancer_type.lower()
        results = [
            s for s in results
            if s.cancerType and ct_lower in s.cancerType.name.lower()
        ]

    if min_samples is not None:
        results = [s for s in results if s.sequencedSampleCount >= min_samples]

    return results
