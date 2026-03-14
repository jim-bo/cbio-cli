# study_view templates

One dashboard, one URL: `GET /study/summary?id=<study_id>` → `page.html`.

---

## ECharts vanilla dashboard (`page.html`)

Single-page template with **GridStack** layout and **ECharts 5.5**. All chart updates
are driven by JS `fetch()` calls to `?format=json` endpoints — no server-rendered HTML
partials.

### Global JS state

```js
const DashboardState = { studyId, nPatients, nSamples, filters: { ... } };
const Charts = { Pies: {}, AgeHistogram: null, MutatedGenes: null, /* one entry per chart type */ };
```

### How a chart works

1. A `<div class="grid-stack-item" gs-w gs-h gs-x gs-y>` block defines the widget
   position. The inner `<div id="chart-<name>" class="echarts-container">` is the
   ECharts mount point.
2. An `async function update<Name>Widget()` function:
   - Lazily inits the chart: `if (!Charts.X) Charts.X = echarts.init(chartDom)`
   - POSTs to the `?format=json` endpoint via `fetch()` with `FormData` carrying
     `study_id` and `filter_json`.
   - Calls `chart.setOption({...})` with the returned data.
3. `updateAll()` calls every `update*Widget()` — runs on page load and whenever
   `cbio-filter-changed` is dispatched.
4. The GridStack `resizestop` handler and `window resize` handler call `.resize()` on
   every initialized chart instance.

### Adding a chart

1. Ensure the route handler returns `{"data": [...], ...}` (always JSON — no HTML branch needed).
2. Add a `grid-stack-item` block in `page.html` with a unique `id` on the ECharts div.
3. Add a `null` entry in `Charts` (e.g. `Charts.MyChart: null`).
4. Write `async function updateMyChartWidget()` following the pattern above.
5. Call `updateMyChartWidget()` inside `updateAll()`.
6. Add `if (Charts.MyChart) Charts.MyChart.resize()` in the resizer.

---

## Dynamic chart layout

Dashboard widgets are no longer hardcoded in `page.html`. On load, JS fetches
`GET /study/summary/charts-meta?id=<study_id>` which returns an ordered list of
chart descriptors. `buildDashboard(chartsMeta, grid)` then creates each widget via
`grid.addWidget({ content: buildWidgetHTML(chart) })` using a simple 12-column
left-to-right bin-packer.

### `clinical_attribute_meta` table

Populated by `loader.py` at study load time by parsing the 4 metadata header rows
from `data_clinical_patient.txt` and `data_clinical_sample.txt`.

```sql
clinical_attribute_meta (
    study_id, attr_id, display_name, description,
    datatype VARCHAR,        -- 'STRING' | 'NUMBER' | 'BOOLEAN'
    patient_attribute BOOLEAN,
    priority INTEGER,
    PRIMARY KEY (study_id, attr_id)
)
```

### `GET /study/summary/charts-meta` response

Returns a JSON array sorted by `priority DESC`. Each item:

```json
{
  "attr_id": "CANCER_TYPE",
  "display_name": "Cancer Type",
  "chart_type": "table",
  "patient_attribute": false,
  "priority": 3000,
  "w": 4,
  "h": 10
}
```

Special genomic charts use `_`-prefixed `attr_id` values:
`_mutated_genes`, `_cna_genes`, `_sv_genes`, `_scatter`, `_km`.

### Chart-type assignment rules

| Condition | chart_type |
|---|---|
| `attr_id` is `CANCER_TYPE` or `CANCER_TYPE_DETAILED` | `table` |
| `DATATYPE = STRING` or `BOOLEAN` | `pie` |
| `DATATYPE = NUMBER` | `bar` |
| `mutation` in `study_data_types` | `_mutated_genes` |
| `cna` in `study_data_types` | `_cna_genes` |
| `sv` in `study_data_types` | `_sv_genes` |
| both `mutation` + `cna` | `_scatter` |
| `OS_MONTHS` + `OS_STATUS` columns present | `_km` |

Grid dimensions: `pie` → w=2,h=5 | `bar` → w=4,h=5 | `table`/genomic → w=4,h=10.

### JS pattern

- `buildWidgetHTML(chart)` → generates inner HTML string for each `chart_type`.
- `routeUpdateWidget(chart)` → dispatches to the appropriate `update*Widget()` call.
- `updateAll()` → iterates `DashboardState.chartsMeta` calling `routeUpdateWidget`.
- `updateBarWidget(attrId)` → handles any `bar` chart; AGE-like attrs use `/age`
  endpoint for 5-year binning, others use `/clinical`.
- `Charts.Bars = {}` registry alongside `Charts.Pies` for resize handling.

### Backward-compat fallback

If `clinical_attribute_meta` doesn't exist or has no rows for the study,
`get_charts_meta()` falls back to `get_clinical_attributes()` + DuckDB column
type introspection (`DESCRIBE`), with canonical priority overrides for known attrs.

---

## Backend endpoint conventions

Chart routes live in `src/cbioportal/web/routes/study_view.py`.

- Endpoints accept `POST` with form fields: `study_id`, `filter_json` (JSON string).
- All endpoints return JSON — the `?format=json` query param is accepted but ignored
  (kept for backwards compatibility with tests).
- Repository functions live in `src/cbioportal/core/study_view_repository.py`.
- Every repository function must have unit tests in `tests/unit/` using in-memory
  DuckDB, and integration tests in `tests/test_study_view_charts.py`.
