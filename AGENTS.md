# cbio-revamp: Implementation Blueprint

## Tech Stack (uv-managed)
- **Runtime:** Python 3.12+ (managed via `uv`)
- **CLI:** Typer (Command-line interface) + prompt_toolkit (Interactive TUI)
- **Web:** FastAPI + Jinja2 + HTMX + Alpine.js
- **Database:** DuckDB (Local persistence)
- **Cache:** Redis (Optional fragment caching)

## Project Structure (src-layout)
```text
cbio-revamp/
├── pyproject.toml           # uv project/dependency config
├── src/
│   └── cbioportal/          # Main package
│       ├── cli/             # CLI: cbio (TUI), beta db, serve commands
│       ├── core/            # Logic: DuckDB, data fetching, API caching
│       └── web/             # Web: app.py, routes, templates/
├── tests/                   # Pytest suite
└── data/                    # Local .duckdb storage (git-ignored)
```

## Architecture Notes

**Interactive TUI (`src/cbioportal/cli/display/tui`)**
- The CLI (`cbio`) is powered by `prompt_toolkit`.
- It uses an async event loop (`Application.run_async()`) and maintains a global `AppState` object for tracking history, interactive selections, and active background tasks.
- Avoid printing directly to `stdout`. Use `state.history.add()` and `event.app.invalidate()` to trigger UI renders.

**API Caching (`src/cbioportal/core/cache.py`)**
- Live cBioPortal and MoAlmanac API data is persistently cached in `~/.cbio/cache/cache.duckdb`.
- The `data_puller.py` orchestrator relies on this DuckDB cache for high-speed relational joins (e.g., joining OncoTree contexts with large genomic datasets).

## CLI Entry Points
- `cbio`: Launch the interactive Terminal UI (TUI) for searching and pulling API data.
- `cbio serve`: Launch FastAPI/HTMX webserver.
- `cbio beta db`: Add/Remove/Update studies in DuckDB from a local datahub.

## Testing

### Unit tests (fast, no real data)
All data-fetch functions in `src/cbioportal/core/` must have corresponding unit tests
in `tests/unit/` using an **in-memory DuckDB** (`duckdb.connect(":memory:")`).

Run unit tests:
```bash
uv run pytest tests/unit/ -v
```

Unit tests must cover:
- The "happy path" (data is returned correctly)
- Exclusion/inclusion logic (e.g. variant classifications, Mutation_Status filters)
- Edge cases (NULL values, empty tables, missing columns)

### Integration / Golden tests
`tests/test_study_view_charts.py` runs against the real DuckDB with loaded study data.
These are slower; run them before opening a PR:
```bash
uv run pytest tests/test_study_view_charts.py -v
```

### API & Export Validation Tests
Marked with `@pytest.mark.live_api` and `@pytest.mark.docker`. They are skipped by default. To run them, explicitly pass `--run-live-api` and `--run-docker`:
```bash
uv run pytest tests/integration/ -v --run-live-api --run-docker
```

**Any new feature that touches a repository function must pass both test suites.**

### Golden value protection
Exact numeric assertions in `test_study_view_charts.py` (Pearson/Spearman correlations,
gene counts, survival values, etc.) are pinned against the public cBioPortal portal.

**Never change a golden value to make a failing test pass.** A failing golden test signals
a computation divergence from the legacy portal — fix the code, not the number. Only update
a golden value when the user explicitly approves it after reviewing the discrepancy.

### Smoke test before committing

Any change to routes, schemas, or templates must be verified by running the server
and hitting every affected endpoint — a 200 on the HTML page is not sufficient.

```bash
uv run cbioportal serve --port 8002 &
STUDY=msk_chord_2024
FILTER='{"clinicalDataFilters":[],"mutationFilter":{"genes":[]},"svFilter":{"genes":[]}}'
BASE=http://127.0.0.1:8002/study/summary

# Page load
curl -sf "$BASE?id=$STUDY" > /dev/null && echo "OK page"

# charts-meta (GET)
curl -sf "$BASE/charts-meta?id=$STUDY" > /dev/null && echo "OK charts-meta"

# All chart endpoints (POST)
for ep in mutated-genes cna-genes sv-genes age scatter km data-types; do
  curl -sf -X POST "$BASE/chart/$ep" \
    -F "study_id=$STUDY" -F "filter_json=$FILTER" > /dev/null && echo "OK $ep"
done

# clinical (requires attribute_id)
curl -sf -X POST "$BASE/chart/clinical" \
  -F "study_id=$STUDY" -F "filter_json=$FILTER" -F "attribute_id=CANCER_TYPE" > /dev/null \
  && echo "OK clinical"

kill %1
```

## git
- every feature needs to be implemented on a feature branch
- don't credit the coding agents in commit messages, keep them short

## Worktree layout

The repo uses git worktrees so coding agents and the user never collide on branches.

```
cbio-revamp/
├── cbio-implement/    # main branch — user's primary working directory, never modify directly
├── claude-worktree/   # Claude's feature branch workspace
└── gemini-worktree/   # Gemini's feature branch workspace
```

**Rules for coding agents:**
- **Claude** does all feature work inside `claude-worktree/`
- **Gemini** does all feature work inside `gemini-worktree/`
- `cbio-implement/` always tracks `main` — agents never check out or commit there
- Each agent creates a feature branch inside its own worktree:
  ```bash
  git -C /path/to/claude-worktree checkout -b feature/my-feature
  ```
- When the feature is ready, the user merges from `cbio-implement/`:
  ```bash
  git merge feature/my-feature
  ```
- After merging, the agent resets its worktree to detached HEAD at main:
  ```bash
  git -C /path/to/claude-worktree checkout --detach main
  git branch -d feature/my-feature
  ```
