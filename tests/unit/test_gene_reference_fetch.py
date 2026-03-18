"""Unit tests for gene_reference.py web fallback logic and HGNC TSV parsing."""
import gzip
import io
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import duckdb
import pytest
import requests

from cbioportal.core.loader.gene_reference import (
    _fetch_datahub_file,
    _load_gene_aliases_from_hgnc,
    ensure_gene_reference,
    load_gene_aliases,
    load_gene_panel_definitions,
    load_gene_reference,
    load_gene_symbol_updates,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mem():
    return duckdb.connect(":memory:")


def _make_response(content: bytes, content_type: str = "application/json") -> MagicMock:
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.headers = {"content-length": str(len(content))}
    resp.iter_content.return_value = [content]
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# _fetch_datahub_file — cache hit skips download
# ---------------------------------------------------------------------------

def test_fetch_datahub_file_cache_hit(tmp_path, monkeypatch):
    """If the cached file is fresh, download is NOT triggered."""
    cache_dir = tmp_path / "datahub"
    cache_dir.mkdir()
    monkeypatch.setattr(
        "cbioportal.core.loader.gene_reference._DATAHUB_CACHE_DIR", cache_dir
    )
    dest = cache_dir / "genes.json"
    dest.write_bytes(b'[{"entrezGeneId": 1, "hugoGeneSymbol": "A1BG", "type": "protein-coding"}]')

    with patch("cbioportal.core.loader.gene_reference.requests.get") as mock_get:
        result = _fetch_datahub_file("http://example.com/genes.json", "genes.json")
        mock_get.assert_not_called()

    assert result == dest


def test_fetch_datahub_file_cache_miss_downloads(tmp_path, monkeypatch):
    """If the cached file is missing, download is triggered and file is written."""
    cache_dir = tmp_path / "datahub"
    cache_dir.mkdir()
    monkeypatch.setattr(
        "cbioportal.core.loader.gene_reference._DATAHUB_CACHE_DIR", cache_dir
    )
    payload = b'[{"entrezGeneId": 1, "hugoGeneSymbol": "A1BG"}]'
    mock_resp = _make_response(payload)

    with patch("cbioportal.core.loader.gene_reference.requests.get", return_value=mock_resp):
        result = _fetch_datahub_file("http://example.com/genes.json", "genes.json")

    assert result.exists()
    assert result.read_bytes() == payload


def test_fetch_datahub_file_stale_cache_redownloads(tmp_path, monkeypatch):
    """A cached file older than ttl_days triggers a fresh download."""
    cache_dir = tmp_path / "datahub"
    cache_dir.mkdir()
    monkeypatch.setattr(
        "cbioportal.core.loader.gene_reference._DATAHUB_CACHE_DIR", cache_dir
    )
    dest = cache_dir / "genes.json"
    dest.write_bytes(b"old content")
    # Backdate mtime by 31 days
    old_mtime = time.time() - (31 * 86400)
    import os
    os.utime(dest, (old_mtime, old_mtime))

    new_payload = b"new content"
    mock_resp = _make_response(new_payload)

    with patch("cbioportal.core.loader.gene_reference.requests.get", return_value=mock_resp):
        _fetch_datahub_file("http://example.com/genes.json", "genes.json", ttl_days=30)

    assert dest.read_bytes() == new_payload


# ---------------------------------------------------------------------------
# load_gene_reference — API fallback
# ---------------------------------------------------------------------------

def test_load_gene_reference_from_path(tmp_path):
    """load_gene_reference works when given an explicit path."""
    genes = [
        {"entrezGeneId": 1, "hugoGeneSymbol": "A1BG", "type": "protein-coding"},
        {"entrezGeneId": 2, "hugoGeneSymbol": "A2M", "type": "protein-coding"},
    ]
    p = tmp_path / "genes.json"
    p.write_text(json.dumps(genes))

    conn = _mem()
    load_gene_reference(conn, genes_json_path=p)

    rows = conn.execute("SELECT entrez_gene_id, hugo_gene_symbol FROM gene_reference ORDER BY entrez_gene_id").fetchall()
    assert rows == [(1, "A1BG"), (2, "A2M")]
    conn.close()


def test_load_gene_reference_web_fallback(tmp_path, monkeypatch):
    """Without CBIO_DATAHUB, gene_reference is fetched from the cBioPortal API."""
    monkeypatch.delenv("CBIO_DATAHUB", raising=False)
    cache_dir = tmp_path / "datahub"
    cache_dir.mkdir()
    monkeypatch.setattr(
        "cbioportal.core.loader.gene_reference._DATAHUB_CACHE_DIR", cache_dir
    )

    genes = [{"entrezGeneId": 3845, "hugoGeneSymbol": "KRAS", "type": "protein-coding"}]
    payload = json.dumps(genes).encode()
    mock_resp = _make_response(payload)

    with patch("cbioportal.core.loader.gene_reference.requests.get", return_value=mock_resp):
        conn = _mem()
        load_gene_reference(conn)

    row = conn.execute("SELECT hugo_gene_symbol FROM gene_reference WHERE entrez_gene_id=3845").fetchone()
    assert row[0] == "KRAS"
    conn.close()


def test_load_gene_reference_uses_datahub_env(tmp_path, monkeypatch):
    """When CBIO_DATAHUB is set, local file is used instead of the web."""
    datahub = tmp_path / "datahub_repo"
    portal_info = datahub / ".circleci" / "portalinfo"
    portal_info.mkdir(parents=True)
    genes = [{"entrezGeneId": 7157, "hugoGeneSymbol": "TP53", "type": "protein-coding"}]
    (portal_info / "genes.json").write_text(json.dumps(genes))

    monkeypatch.setenv("CBIO_DATAHUB", str(datahub))

    with patch("cbioportal.core.loader.gene_reference.requests.get") as mock_get:
        conn = _mem()
        load_gene_reference(conn)
        mock_get.assert_not_called()

    row = conn.execute("SELECT hugo_gene_symbol FROM gene_reference WHERE entrez_gene_id=7157").fetchone()
    assert row[0] == "TP53"
    conn.close()


# ---------------------------------------------------------------------------
# load_gene_symbol_updates — GitHub raw fallback
# ---------------------------------------------------------------------------

def test_load_gene_symbol_updates_from_path(tmp_path):
    """load_gene_symbol_updates parses a minimal gene-update.md correctly."""
    md_content = """\
# Gene Updates

```
MLL -1 -> KMT2A 4297
C10ORF12 -1 -> LCOR 140380
```
"""
    p = tmp_path / "gene-update.md"
    p.write_text(md_content)

    conn = _mem()
    load_gene_symbol_updates(conn, gene_update_md=p)

    rows = {r[0]: r[1] for r in conn.execute("SELECT old_symbol, new_symbol FROM gene_symbol_updates").fetchall()}
    assert rows["MLL"] == "KMT2A"
    assert rows["C10ORF12"] == "LCOR"
    conn.close()


def test_load_gene_symbol_updates_web_fallback(tmp_path, monkeypatch):
    """Without CBIO_DATAHUB, gene-update.md is fetched from GitHub."""
    monkeypatch.delenv("CBIO_DATAHUB", raising=False)
    cache_dir = tmp_path / "datahub"
    cache_dir.mkdir()
    monkeypatch.setattr(
        "cbioportal.core.loader.gene_reference._DATAHUB_CACHE_DIR", cache_dir
    )

    md_content = "# Gene Updates\n\n```\nMLL -1 -> KMT2A 4297\n```\n"
    mock_resp = _make_response(md_content.encode())

    with patch("cbioportal.core.loader.gene_reference.requests.get", return_value=mock_resp):
        conn = _mem()
        load_gene_symbol_updates(conn)

    row = conn.execute("SELECT new_symbol FROM gene_symbol_updates WHERE old_symbol='MLL'").fetchone()
    assert row[0] == "KMT2A"
    conn.close()


# ---------------------------------------------------------------------------
# _load_gene_aliases_from_hgnc — HGNC TSV parsing
# ---------------------------------------------------------------------------

_HGNC_TSV_HEADER = (
    "hgnc_id\tsymbol\tname\tlocus_group\tlocus_type\tstatus\tlocation\t"
    "location_sortable\talias_symbol\talias_name\tprev_symbol\tprev_name\t"
    "gene_family\tgene_family_id\tdate_approved_reserved\tdate_symbol_changed\t"
    "date_name_changed\tdate_modified\tentrez_id\tensembl_gene_id\t"
    "vega_id\tucsc_id\tena\trefseq_accession\tccds_id\tuniprot_ids\t"
    "pubmed_id\tmgd_id\trgd_id\tlsdb\tcosmic\tomim_id\tmirbase\t"
    "homeodb\tsnornabase\tbioparadigms_slc\torphanet\tpseudogene.org\t"
    "horde_id\tmerops\timgt\tiuphar\tkznf_gene_catalog\tmamit_trnadb\t"
    "cd\tlncrnadb\tenzymo\tpdb\tgtrnadb\thomeobox_db\tescg\tetc\n"
)

def _hgnc_row(**kwargs) -> str:
    """Build a minimal HGNC TSV row with given field overrides."""
    fields = {
        "hgnc_id": "HGNC:1", "symbol": "TEST", "name": "test gene",
        "locus_group": "", "locus_type": "", "status": "Approved",
        "location": "", "location_sortable": "",
        "alias_symbol": "", "alias_name": "", "prev_symbol": "", "prev_name": "",
        "gene_family": "", "gene_family_id": "", "date_approved_reserved": "",
        "date_symbol_changed": "", "date_name_changed": "", "date_modified": "",
        "entrez_id": "", "ensembl_gene_id": "",
    }
    fields.update(kwargs)
    # Build exactly enough fields to cover the columns we parse
    header_cols = _HGNC_TSV_HEADER.rstrip("\n").split("\t")
    row_fields = []
    for col in header_cols:
        row_fields.append(fields.get(col, ""))
    return "\t".join(row_fields) + "\n"


def test_hgnc_tsv_alias_symbol_parsed(tmp_path):
    """alias_symbol column is split on '|' and each symbol becomes a row."""
    tsv = _HGNC_TSV_HEADER + _hgnc_row(
        symbol="KMT2A", entrez_id="4297", alias_symbol="MLL|MLL1A", prev_symbol=""
    )
    hgnc_path = tmp_path / "hgnc_complete_set.txt"
    hgnc_path.write_text(tsv)

    conn = _mem()
    conn.execute("""
        CREATE TABLE gene_alias (
            entrez_gene_id INTEGER,
            alias_symbol VARCHAR,
            PRIMARY KEY (entrez_gene_id, alias_symbol)
        )
    """)
    with patch(
        "cbioportal.core.loader.gene_reference._fetch_datahub_file",
        return_value=hgnc_path,
    ):
        _load_gene_aliases_from_hgnc(conn)

    aliases = {r[0] for r in conn.execute("SELECT alias_symbol FROM gene_alias WHERE entrez_gene_id=4297").fetchall()}
    assert "MLL" in aliases
    assert "MLL1A" in aliases
    conn.close()


def test_hgnc_tsv_prev_symbol_parsed(tmp_path):
    """prev_symbol column is split on '|' and each symbol becomes a row."""
    tsv = _HGNC_TSV_HEADER + _hgnc_row(
        symbol="KMT2D", entrez_id="8085", alias_symbol="", prev_symbol="MLL2|ALR"
    )
    hgnc_path = tmp_path / "hgnc_complete_set.txt"
    hgnc_path.write_text(tsv)

    conn = _mem()
    conn.execute("""
        CREATE TABLE gene_alias (
            entrez_gene_id INTEGER,
            alias_symbol VARCHAR,
            PRIMARY KEY (entrez_gene_id, alias_symbol)
        )
    """)
    with patch(
        "cbioportal.core.loader.gene_reference._fetch_datahub_file",
        return_value=hgnc_path,
    ):
        _load_gene_aliases_from_hgnc(conn)

    aliases = {r[0] for r in conn.execute("SELECT alias_symbol FROM gene_alias WHERE entrez_gene_id=8085").fetchall()}
    assert "MLL2" in aliases
    assert "ALR" in aliases
    conn.close()


def test_hgnc_tsv_skips_rows_without_entrez(tmp_path):
    """Rows with empty entrez_id are skipped entirely."""
    tsv = _HGNC_TSV_HEADER + _hgnc_row(
        symbol="GENEX", entrez_id="", alias_symbol="OLD_NAME", prev_symbol=""
    )
    hgnc_path = tmp_path / "hgnc_complete_set.txt"
    hgnc_path.write_text(tsv)

    conn = _mem()
    conn.execute("""
        CREATE TABLE gene_alias (
            entrez_gene_id INTEGER,
            alias_symbol VARCHAR,
            PRIMARY KEY (entrez_gene_id, alias_symbol)
        )
    """)
    with patch(
        "cbioportal.core.loader.gene_reference._fetch_datahub_file",
        return_value=hgnc_path,
    ):
        _load_gene_aliases_from_hgnc(conn)

    count = conn.execute("SELECT COUNT(*) FROM gene_alias").fetchone()[0]
    assert count == 0
    conn.close()


def test_hgnc_tsv_kmt2_family(tmp_path):
    """KMT2 family aliases resolve correctly from HGNC TSV data."""
    rows = [
        _hgnc_row(symbol="KMT2A", entrez_id="4297",  alias_symbol="MLL|MLL1",   prev_symbol=""),
        _hgnc_row(symbol="KMT2B", entrez_id="9757",  alias_symbol="",           prev_symbol="MLL4|WBP7"),
        _hgnc_row(symbol="KMT2C", entrez_id="58508", alias_symbol="",           prev_symbol="MLL3|HALR"),
        _hgnc_row(symbol="KMT2D", entrez_id="8085",  alias_symbol="",           prev_symbol="MLL2|ALR"),
    ]
    hgnc_path = tmp_path / "hgnc_complete_set.txt"
    hgnc_path.write_text(_HGNC_TSV_HEADER + "".join(rows))

    conn = _mem()
    conn.execute("""
        CREATE TABLE gene_alias (
            entrez_gene_id INTEGER,
            alias_symbol VARCHAR,
            PRIMARY KEY (entrez_gene_id, alias_symbol)
        )
    """)
    with patch(
        "cbioportal.core.loader.gene_reference._fetch_datahub_file",
        return_value=hgnc_path,
    ):
        _load_gene_aliases_from_hgnc(conn)

    def aliases_for(entrez_id):
        return {r[0] for r in conn.execute(
            "SELECT alias_symbol FROM gene_alias WHERE entrez_gene_id=?", (entrez_id,)
        ).fetchall()}

    assert "MLL" in aliases_for(4297)    # MLL → KMT2A
    assert "MLL4" in aliases_for(9757)   # MLL4 → KMT2B
    assert "MLL3" in aliases_for(58508)  # MLL3 → KMT2C
    assert "MLL2" in aliases_for(8085)   # MLL2 → KMT2D
    conn.close()


# ---------------------------------------------------------------------------
# load_gene_aliases — fallback routing
# ---------------------------------------------------------------------------

def test_load_gene_aliases_uses_sql_when_path_provided(tmp_path):
    """Explicit seed SQL path bypasses HGNC fallback."""
    # Build a minimal gzipped seed SQL with one alias entry
    sql_line = "INSERT INTO `gene_alias` VALUES (4297,'MLL');\n"
    buf = io.BytesIO()
    with gzip.open(buf, "wt") as gz:
        gz.write(sql_line)
    sql_path = tmp_path / "seed.sql.gz"
    sql_path.write_bytes(buf.getvalue())

    conn = _mem()
    with patch("cbioportal.core.loader.gene_reference._load_gene_aliases_from_hgnc") as mock_hgnc:
        load_gene_aliases(conn, seed_sql_path=sql_path)
        mock_hgnc.assert_not_called()

    row = conn.execute("SELECT alias_symbol FROM gene_alias WHERE entrez_gene_id=4297").fetchone()
    assert row[0] == "MLL"
    conn.close()


def test_load_gene_aliases_falls_back_to_hgnc_when_no_datahub(monkeypatch):
    """Without CBIO_DATAHUB and no explicit path, HGNC fallback is used."""
    monkeypatch.delenv("CBIO_DATAHUB", raising=False)

    conn = _mem()
    with patch("cbioportal.core.loader.gene_reference._load_gene_aliases_from_hgnc") as mock_hgnc:
        load_gene_aliases(conn)
        mock_hgnc.assert_called_once_with(conn)
    conn.close()


# ---------------------------------------------------------------------------
# load_gene_panel_definitions — GitHub raw fallback
# ---------------------------------------------------------------------------

def test_load_gene_panel_definitions_web_fallback(tmp_path, monkeypatch):
    """Without CBIO_DATAHUB, gene-panels.json is fetched from GitHub."""
    monkeypatch.delenv("CBIO_DATAHUB", raising=False)
    cache_dir = tmp_path / "datahub"
    cache_dir.mkdir()
    monkeypatch.setattr(
        "cbioportal.core.loader.gene_reference._DATAHUB_CACHE_DIR", cache_dir
    )

    panels = [{
        "genePanelId": "IMPACT468",
        "description": "MSK IMPACT 468 gene panel",
        "genes": [{"hugoGeneSymbol": "KRAS", "entrezGeneId": 3845}],
    }]
    payload = json.dumps(panels).encode()
    mock_resp = _make_response(payload)

    with patch("cbioportal.core.loader.gene_reference.requests.get", return_value=mock_resp):
        conn = _mem()
        load_gene_panel_definitions(conn)

    row = conn.execute(
        "SELECT panel_id, hugo_gene_symbol FROM gene_panel_definitions"
    ).fetchone()
    assert row == ("IMPACT468", "KRAS")
    conn.close()


# ---------------------------------------------------------------------------
# ensure_gene_reference — no longer silently skips without CBIO_DATAHUB
# ---------------------------------------------------------------------------

def test_ensure_gene_reference_runs_without_datahub(monkeypatch):
    """ensure_gene_reference no longer silently skips when CBIO_DATAHUB is unset."""
    monkeypatch.delenv("CBIO_DATAHUB", raising=False)

    conn = _mem()
    call_log = []

    def fake_load_reference(c, **kw):
        call_log.append("gene_reference")

    def fake_load_updates(c, **kw):
        call_log.append("gene_symbol_updates")

    def fake_load_aliases(c, **kw):
        call_log.append("gene_alias")

    with (
        patch("cbioportal.core.loader.gene_reference.load_gene_reference", fake_load_reference),
        patch("cbioportal.core.loader.gene_reference.load_gene_symbol_updates", fake_load_updates),
        patch("cbioportal.core.loader.gene_reference.load_gene_aliases", fake_load_aliases),
    ):
        ensure_gene_reference(conn)

    assert "gene_reference" in call_log
    assert "gene_symbol_updates" in call_log
    assert "gene_alias" in call_log
    conn.close()


def test_ensure_gene_reference_skips_existing_tables(monkeypatch):
    """ensure_gene_reference skips tables that already exist."""
    monkeypatch.delenv("CBIO_DATAHUB", raising=False)

    conn = _mem()
    # Pre-create the tables so they appear in information_schema
    conn.execute("CREATE TABLE gene_reference (entrez_gene_id INTEGER PRIMARY KEY, hugo_gene_symbol VARCHAR, gene_type VARCHAR)")
    conn.execute("CREATE TABLE gene_symbol_updates (old_symbol VARCHAR PRIMARY KEY, new_symbol VARCHAR)")
    conn.execute("CREATE TABLE gene_alias (entrez_gene_id INTEGER, alias_symbol VARCHAR, PRIMARY KEY (entrez_gene_id, alias_symbol))")

    call_log = []

    def fail_if_called(c, **kw):
        call_log.append("called")

    with (
        patch("cbioportal.core.loader.gene_reference.load_gene_reference", fail_if_called),
        patch("cbioportal.core.loader.gene_reference.load_gene_symbol_updates", fail_if_called),
        patch("cbioportal.core.loader.gene_reference.load_gene_aliases", fail_if_called),
    ):
        ensure_gene_reference(conn)

    assert call_log == []
    conn.close()


def test_ensure_gene_reference_soft_fails_on_network_error(monkeypatch):
    """ensure_gene_reference catches exceptions and warns instead of crashing."""
    monkeypatch.delenv("CBIO_DATAHUB", raising=False)

    conn = _mem()

    def raise_error(c, **kw):
        raise requests.ConnectionError("network down")

    with patch("cbioportal.core.loader.gene_reference.load_gene_reference", raise_error):
        # Should not raise
        ensure_gene_reference(conn)

    conn.close()
