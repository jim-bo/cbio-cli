# [Beta] Web App & Local Database

The experimental web app provides a local UI, and relies on an extensive offline ingestion process utilizing a local clone of the cBioPortal datahub.

## Beta Prerequisites
- A local clone of [cBioPortal/datahub](https://github.com/cBioPortal/datahub)

## Beta Setup

1. Set environment variables:
   ```bash
   export CBIO_DATAHUB=/path/to/your/datahub
   # Optional: override DuckDB path (default: data/cbioportal.duckdb)
   export CBIO_DB_PATH=/path/to/cbioportal.duckdb
   ```

2. Install web extras:
   ```bash
   uv sync --extra web
   ```

## Running the Web App

The web application requires the `web` optional dependencies (FastAPI, uvicorn, etc.).

```bash
# Launch the server
uv run cbio serve
```

The server starts on `http://localhost:8000` by default.

## Advanced Database Commands (`cbio beta db`)

If you need to manually load data from the local datahub clone (bypassing the interactive API puller):

- `uv run cbio beta db load-all`: Load all studies from the datahub into DuckDB.
- `uv run cbio beta db add <study_id>`: Load a single study.
- `uv run cbio beta db sync-oncotree`: Fetch the OncoTree hierarchy.
- `uv run cbio beta db sync-gene-reference`: Load the `gene_reference` table.

## Testing (Web)

### Web & Study View Tests

These tests require the `[web]` optional dependencies (specifically `scipy` for genomic statistics).

```bash
uv run pytest tests/web/ -v
```

### Golden Integration Tests

Compares Study View chart data against JSON fixtures from the public portal. Requires a real DuckDB with `msk_chord_2024` loaded.

```bash
uv run pytest tests/web/test_study_view_charts.py -v
```

## Institutional Knowledge (Beta Loaders)

### Gene counts must match cBioPortal's logic exactly

**1. Variant Classification filtering at load time**

8 variant classifications are excluded at import:
`Silent`, `Intron`, `IGR`, `3'UTR`, `5'UTR`, `3'Flank`, `5'Flank`

This matches cBioPortal File-Formats.md. Rows with these VCs are never stored in DuckDB.

**Exception:** TERT `5'Flank` (promoter mutations) is kept. Note: ONLY `5'Flank`, not all
TERT variants. Using a broad `Hugo_Symbol='TERT'` exception would include TERT `5'UTR`
rows, overcounting mutated samples by ~1.

**2. Hugo symbol normalization is required for accurate gene counts**

Many studies ship stale Hugo symbols paired with correct Entrez IDs. Without normalization,
e.g. MLL2 and KMT2D count as separate genes, causing significant undercounting. Three
reference tables are needed (all sourced from the datahub):

| Table | Source | Purpose |
|-------|--------|---------|
| `gene_reference` | `genes.json` | Entrez ID → canonical Hugo symbol (~40k entries) |
| `gene_symbol_updates` | `gene-update.md` | Explicitly renamed genes (~75 entries) |
| `gene_alias` | seed SQL `gene_alias` table | NCBI aliases, needed when `Entrez_Gene_Id=0` (~55k entries) |

The alias table is specifically needed for the KMT2 family: studies like `msk_chord_2024`
encode these genes with `Entrez_Gene_Id=0` using old names (MLL→KMT2A, MLL2→KMT2D,
MLL3→KMT2C, MLL4→KMT2B).

**3. CBIO_DATAHUB must be set when loading studies**

Without it, `ensure_gene_reference()` is skipped and gene counts will diverge from the
public portal. No error is raised — the load succeeds silently with unnormalized symbols.

**4. Mutation_Status=UNCALLED filtering happens at query time, not load time**

UNCALLED rows are kept in DuckDB. The repository layer filters them out when counting
mutated samples. This matches cBioPortal's behavior and allows future query flexibility.
