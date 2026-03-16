"""Tests for study_cache module and CbioPortalClient.search_studies."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from cbioportal.core.api.models import CancerType, Study
from cbioportal.core.api import study_cache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BREAST = Study(
    studyId="brca_tcga",
    name="Breast Invasive Carcinoma (TCGA)",
    description="TCGA breast cancer cohort",
    cancerType=CancerType(cancerTypeId="brca", name="Breast Cancer"),
    sequencedSampleCount=1084,
)

LUNG = Study(
    studyId="luad_tcga",
    name="Lung Adenocarcinoma (TCGA)",
    description="TCGA lung cohort",
    cancerType=CancerType(cancerTypeId="luad", name="Lung Adenocarcinoma"),
    sequencedSampleCount=230,
)

SMALL = Study(
    studyId="tiny_study",
    name="Small Pilot Study",
    description="Pilot cohort",
    cancerType=CancerType(cancerTypeId="other", name="Other Cancer"),
    sequencedSampleCount=10,
)

ALL_STUDIES = [BREAST, LUNG, SMALL]
PORTAL_URL = "https://www.cbioportal.org"


# ---------------------------------------------------------------------------
# study_cache.search tests
# ---------------------------------------------------------------------------


def test_search_local_match_name():
    results = study_cache.search(ALL_STUDIES, "breast")
    assert BREAST in results
    assert LUNG not in results


def test_search_local_match_study_id():
    results = study_cache.search(ALL_STUDIES, "luad_tcga")
    assert LUNG in results
    assert BREAST not in results


def test_search_local_multiword():
    # Both words must match somewhere in the study fields
    results = study_cache.search(ALL_STUDIES, "tcga breast")
    assert BREAST in results
    assert LUNG not in results


def test_search_local_no_match():
    results = study_cache.search(ALL_STUDIES, "xyzzy")
    assert results == []


def test_search_local_cancer_type_filter():
    results = study_cache.search(ALL_STUDIES, "", cancer_type="Lung")
    assert LUNG in results
    assert BREAST not in results


def test_search_local_min_samples_filter():
    results = study_cache.search(ALL_STUDIES, "", min_samples=500)
    assert BREAST in results
    assert LUNG not in results
    assert SMALL not in results


# ---------------------------------------------------------------------------
# study_cache.load / save tests
# ---------------------------------------------------------------------------


def _make_cache_payload(portal_url: str, fetched_at: str, studies: list[Study], version: int = study_cache.CACHE_VERSION) -> str:
    return json.dumps({
        "version": version,
        "portal_url": portal_url,
        "fetched_at": fetched_at,
        "studies": [s.model_dump() for s in studies],
    })


def test_cache_load_fresh(tmp_path, monkeypatch):
    cache_file = tmp_path / "studies_cache.json"
    monkeypatch.setattr(study_cache, "CACHE_PATH", cache_file)

    now = datetime.now(tz=timezone.utc).isoformat()
    cache_file.write_text(_make_cache_payload(PORTAL_URL, now, [BREAST]))

    result = study_cache.load(PORTAL_URL, ttl_days=180)
    assert result is not None
    assert len(result) == 1
    assert result[0].studyId == "brca_tcga"


def test_cache_load_stale(tmp_path, monkeypatch):
    cache_file = tmp_path / "studies_cache.json"
    monkeypatch.setattr(study_cache, "CACHE_PATH", cache_file)

    stale = (datetime.now(tz=timezone.utc) - timedelta(days=200)).isoformat()
    cache_file.write_text(_make_cache_payload(PORTAL_URL, stale, [BREAST]))

    result = study_cache.load(PORTAL_URL, ttl_days=180)
    assert result is None


def test_cache_load_old_version(tmp_path, monkeypatch):
    cache_file = tmp_path / "studies_cache.json"
    monkeypatch.setattr(study_cache, "CACHE_PATH", cache_file)

    now = datetime.now(tz=timezone.utc).isoformat()
    cache_file.write_text(_make_cache_payload(PORTAL_URL, now, [BREAST], version=1))

    result = study_cache.load(PORTAL_URL, ttl_days=180)
    assert result is None


def test_cache_load_wrong_portal(tmp_path, monkeypatch):
    cache_file = tmp_path / "studies_cache.json"
    monkeypatch.setattr(study_cache, "CACHE_PATH", cache_file)

    now = datetime.now(tz=timezone.utc).isoformat()
    cache_file.write_text(_make_cache_payload("https://other.portal.org", now, [BREAST]))

    result = study_cache.load(PORTAL_URL, ttl_days=180)
    assert result is None


# ---------------------------------------------------------------------------
# CbioPortalClient.fetch_all_studies tests
# ---------------------------------------------------------------------------


def _make_client(base_url: str = PORTAL_URL):
    from cbioportal.core.api.client import CbioPortalClient
    with patch("cbioportal.core.api.client.get_config") as mock_cfg:
        mock_cfg.return_value = {
            "portal": {"url": base_url},
            "cache": {"ttl_days": 180},
        }
        return CbioPortalClient(base_url=base_url)


def test_fetch_all_studies_ok():
    client = _make_client()
    raw = [
        {
            "studyId": "brca_tcga",
            "name": "Breast Invasive Carcinoma (TCGA)",
            "description": "TCGA breast",
            "cancerType": {"cancerTypeId": "brca", "name": "Breast Cancer"},
            "allSampleCount": 1084,
        }
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = raw
    mock_resp.raise_for_status.return_value = None

    with patch.object(client.http, "get", return_value=mock_resp):
        studies = client.fetch_all_studies()

    assert len(studies) == 1
    assert studies[0].studyId == "brca_tcga"
    assert studies[0].allSampleCount == 1084
    client.close()


def test_fetch_all_studies_error():
    client = _make_client()
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Server Error", request=MagicMock(), response=mock_resp
    )

    with patch.object(client.http, "get", return_value=mock_resp):
        with pytest.raises(httpx.HTTPStatusError):
            client.fetch_all_studies()

    client.close()
