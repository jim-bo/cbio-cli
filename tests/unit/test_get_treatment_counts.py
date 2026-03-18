"""Unit tests for get_patient_treatment_counts and get_sample_treatment_counts.

Tests are written before implementation (TDD) — they will fail until the
functions and meta.py treatment chart injection are implemented.
"""
import duckdb
import pytest

STUDY = "test_study"


def _make_base_conn():
    """Create in-memory DuckDB with minimal schema needed for treatment tests."""
    conn = duckdb.connect(":memory:")
    conn.execute(f'CREATE TABLE "{STUDY}_sample" (SAMPLE_ID VARCHAR, PATIENT_ID VARCHAR)')
    conn.execute(f'CREATE TABLE "{STUDY}_patient" (PATIENT_ID VARCHAR)')
    conn.execute("CREATE TABLE studies (study_id VARCHAR, name VARCHAR)")
    conn.execute("INSERT INTO studies VALUES (?, ?)", (STUDY, "Test Study"))
    conn.execute("""
        CREATE TABLE study_data_types (
            study_id VARCHAR NOT NULL,
            data_type VARCHAR NOT NULL,
            PRIMARY KEY (study_id, data_type)
        )
    """)
    return conn


# ---------------------------------------------------------------------------
# Test A: meta.py adds treatment charts when timeline_treatment table exists
# ---------------------------------------------------------------------------

def test_get_charts_meta_includes_treatment_charts():
    """get_charts_meta should include _patient_treatments and _sample_treatments
    when study_data_types contains 'treatment' and the timeline_treatment table exists."""
    from cbioportal.core.study_view.meta import get_charts_meta

    conn = _make_base_conn()
    conn.execute("INSERT INTO study_data_types VALUES (?, ?)", (STUDY, "treatment"))
    conn.execute(f"""
        CREATE TABLE "{STUDY}_timeline_treatment" (
            study_id VARCHAR,
            PATIENT_ID VARCHAR,
            START_DATE INTEGER,
            STOP_DATE INTEGER,
            EVENT_TYPE VARCHAR,
            SUBTYPE VARCHAR,
            AGENT VARCHAR
        )
    """)
    conn.execute(f'INSERT INTO "{STUDY}_timeline_treatment" VALUES (?, ?, ?, ?, ?, ?, ?)',
                 (STUDY, "P1", 0, 100, "Treatment", "Medical Therapy", "CISPLATIN"))

    charts = get_charts_meta(conn, STUDY)
    chart_ids = [c["attr_id"] for c in charts]

    assert "_patient_treatments" in chart_ids, \
        f"Expected _patient_treatments in charts, got: {chart_ids}"
    assert "_sample_treatments" in chart_ids, \
        f"Expected _sample_treatments in charts, got: {chart_ids}"


def test_get_charts_meta_omits_treatment_charts_when_table_missing():
    """get_charts_meta should NOT add treatment charts if the timeline_treatment
    table is absent, even when the 'treatment' data type is registered."""
    from cbioportal.core.study_view.meta import get_charts_meta

    conn = _make_base_conn()
    conn.execute("INSERT INTO study_data_types VALUES (?, ?)", (STUDY, "treatment"))
    # No timeline_treatment table created

    charts = get_charts_meta(conn, STUDY)
    chart_ids = [c["attr_id"] for c in charts]

    assert "_patient_treatments" not in chart_ids
    assert "_sample_treatments" not in chart_ids


# ---------------------------------------------------------------------------
# Test B: get_patient_treatment_counts — basic counts
# ---------------------------------------------------------------------------

def test_get_patient_treatment_counts_basic():
    """3 distinct patients on CISPLATIN, 2 on CARBOPLATIN."""
    from cbioportal.core.study_view.treatments import get_patient_treatment_counts

    conn = _make_base_conn()
    conn.executemany(
        f'INSERT INTO "{STUDY}_sample" VALUES (?, ?)',
        [("S1", "P1"), ("S2", "P2"), ("S3", "P3"), ("S4", "P4"), ("S5", "P5")],
    )
    conn.execute(f"""
        CREATE TABLE "{STUDY}_timeline_treatment" (
            study_id VARCHAR, PATIENT_ID VARCHAR,
            START_DATE INTEGER, STOP_DATE INTEGER,
            EVENT_TYPE VARCHAR, SUBTYPE VARCHAR, AGENT VARCHAR
        )
    """)
    conn.executemany(
        f'INSERT INTO "{STUDY}_timeline_treatment" VALUES (?, ?, ?, ?, ?, ?, ?)',
        [
            (STUDY, "P1", 0, 100, "Treatment", "Medical Therapy", "CISPLATIN"),
            (STUDY, "P2", 0, 100, "Treatment", "Medical Therapy", "CISPLATIN"),
            (STUDY, "P3", 0, 100, "Treatment", "Medical Therapy", "CISPLATIN"),
            (STUDY, "P4", 0, 50,  "Treatment", "Medical Therapy", "CARBOPLATIN"),
            (STUDY, "P5", 0, 50,  "Treatment", "Medical Therapy", "CARBOPLATIN"),
            # Duplicate row for P1/CISPLATIN — should NOT increase count (DISTINCT)
            (STUDY, "P1", 10, 110, "Treatment", "Medical Therapy", "CISPLATIN"),
        ],
    )

    result = get_patient_treatment_counts(conn, STUDY, None)
    by_name = {r["treatment"]: r["count"] for r in result}

    assert by_name["CISPLATIN"] == 3
    assert by_name["CARBOPLATIN"] == 2


def test_get_patient_treatment_counts_null_agent_excluded():
    """Rows with NULL or empty AGENT should not appear in results."""
    from cbioportal.core.study_view.treatments import get_patient_treatment_counts

    conn = _make_base_conn()
    conn.execute(f'INSERT INTO "{STUDY}_sample" VALUES (?, ?)', ("S1", "P1"))
    conn.execute(f"""
        CREATE TABLE "{STUDY}_timeline_treatment" (
            study_id VARCHAR, PATIENT_ID VARCHAR,
            START_DATE INTEGER, STOP_DATE INTEGER,
            EVENT_TYPE VARCHAR, SUBTYPE VARCHAR, AGENT VARCHAR
        )
    """)
    conn.executemany(
        f'INSERT INTO "{STUDY}_timeline_treatment" VALUES (?, ?, ?, ?, ?, ?, ?)',
        [
            (STUDY, "P1", 0, 100, "Treatment", "Medical Therapy", "CISPLATIN"),
            (STUDY, "P1", 0, 100, "Treatment", "Medical Therapy", None),
            (STUDY, "P1", 0, 100, "Treatment", "Medical Therapy", ""),
            (STUDY, "P1", 0, 100, "Treatment", "Medical Therapy", "NA"),
        ],
    )

    result = get_patient_treatment_counts(conn, STUDY, None)
    agents = [r["treatment"] for r in result]

    assert "CISPLATIN" in agents
    assert None not in agents
    assert "" not in agents
    assert "NA" not in agents


def test_get_patient_treatment_counts_missing_table_returns_empty():
    """Returns [] gracefully when timeline_treatment table does not exist."""
    from cbioportal.core.study_view.treatments import get_patient_treatment_counts

    conn = _make_base_conn()
    result = get_patient_treatment_counts(conn, STUDY, None)
    assert result == []


# ---------------------------------------------------------------------------
# Test C: get_sample_treatment_counts — pre/post split
# ---------------------------------------------------------------------------

def test_get_sample_treatment_counts_pre_post():
    """Pre/Post classification: sample collected before treatment start = Pre, else Post."""
    from cbioportal.core.study_view.treatments import get_sample_treatment_counts

    conn = _make_base_conn()
    conn.executemany(
        f'INSERT INTO "{STUDY}_sample" VALUES (?, ?)',
        [("S1", "P1"), ("S2", "P1")],
    )
    # Treatment starts at day 100
    conn.execute(f"""
        CREATE TABLE "{STUDY}_timeline_treatment" (
            study_id VARCHAR, PATIENT_ID VARCHAR,
            START_DATE INTEGER, STOP_DATE INTEGER,
            EVENT_TYPE VARCHAR, SUBTYPE VARCHAR, AGENT VARCHAR
        )
    """)
    conn.execute(
        f'INSERT INTO "{STUDY}_timeline_treatment" VALUES (?, ?, ?, ?, ?, ?, ?)',
        (STUDY, "P1", 100, 200, "Treatment", "Medical Therapy", "CISPLATIN"),
    )
    # Sample S1 collected at day 50 (Pre), S2 at day 150 (Post)
    conn.execute(f"""
        CREATE TABLE "{STUDY}_timeline_specimen" (
            study_id VARCHAR, PATIENT_ID VARCHAR,
            START_DATE INTEGER, STOP_DATE INTEGER,
            EVENT_TYPE VARCHAR, SAMPLE_ID VARCHAR
        )
    """)
    conn.executemany(
        f'INSERT INTO "{STUDY}_timeline_specimen" VALUES (?, ?, ?, ?, ?, ?)',
        [
            (STUDY, "P1", 50,  50,  "Sequencing", "S1"),
            (STUDY, "P1", 150, 150, "Sequencing", "S2"),
        ],
    )

    result = get_sample_treatment_counts(conn, STUDY, None)
    by_key = {(r["treatment"], r["time"]): r["count"] for r in result}

    assert by_key[("CISPLATIN", "Pre")] == 1
    assert by_key[("CISPLATIN", "Post")] == 1


def test_get_sample_treatment_counts_missing_specimen_table_returns_empty():
    """Returns [] gracefully when timeline_specimen table does not exist."""
    from cbioportal.core.study_view.treatments import get_sample_treatment_counts

    conn = _make_base_conn()
    conn.execute(f'INSERT INTO "{STUDY}_sample" VALUES (?, ?)', ("S1", "P1"))
    conn.execute(f"""
        CREATE TABLE "{STUDY}_timeline_treatment" (
            study_id VARCHAR, PATIENT_ID VARCHAR,
            START_DATE INTEGER, STOP_DATE INTEGER,
            EVENT_TYPE VARCHAR, SUBTYPE VARCHAR, AGENT VARCHAR
        )
    """)
    conn.execute(
        f'INSERT INTO "{STUDY}_timeline_treatment" VALUES (?, ?, ?, ?, ?, ?, ?)',
        (STUDY, "P1", 100, 200, "Treatment", "Medical Therapy", "CISPLATIN"),
    )
    # No timeline_specimen table

    result = get_sample_treatment_counts(conn, STUDY, None)
    assert result == []


def test_get_sample_treatment_counts_missing_treatment_table_returns_empty():
    """Returns [] gracefully when timeline_treatment table does not exist."""
    from cbioportal.core.study_view.treatments import get_sample_treatment_counts

    conn = _make_base_conn()
    result = get_sample_treatment_counts(conn, STUDY, None)
    assert result == []


# ---------------------------------------------------------------------------
# Test D: Filter propagation
# ---------------------------------------------------------------------------

def test_get_patient_treatment_counts_respects_filter():
    """When a clinical attribute filter scopes to one patient, treatment count drops to 1."""
    from cbioportal.core.study_view.treatments import get_patient_treatment_counts

    conn = _make_base_conn()
    # Re-create sample table with SAMPLE_TYPE for filtering
    conn.execute(f'DROP TABLE "{STUDY}_sample"')
    conn.execute(f'CREATE TABLE "{STUDY}_sample" (SAMPLE_ID VARCHAR, PATIENT_ID VARCHAR, SAMPLE_TYPE VARCHAR)')
    conn.execute("""
        CREATE TABLE clinical_attribute_meta (
            study_id VARCHAR, attr_id VARCHAR, display_name VARCHAR,
            description VARCHAR, datatype VARCHAR,
            patient_attribute BOOLEAN, priority INTEGER,
            PRIMARY KEY (study_id, attr_id)
        )
    """)
    conn.executemany(
        f'INSERT INTO "{STUDY}_sample" VALUES (?, ?, ?)',
        [("S1", "P1", "Primary"), ("S2", "P2", "Metastasis")],
    )
    conn.execute(f"""
        CREATE TABLE "{STUDY}_timeline_treatment" (
            study_id VARCHAR, PATIENT_ID VARCHAR,
            START_DATE INTEGER, STOP_DATE INTEGER,
            EVENT_TYPE VARCHAR, SUBTYPE VARCHAR, AGENT VARCHAR
        )
    """)
    conn.executemany(
        f'INSERT INTO "{STUDY}_timeline_treatment" VALUES (?, ?, ?, ?, ?, ?, ?)',
        [
            (STUDY, "P1", 0, 100, "Treatment", "Medical Therapy", "CISPLATIN"),
            (STUDY, "P2", 0, 100, "Treatment", "Medical Therapy", "CISPLATIN"),
        ],
    )

    # Filter: only Primary samples (scopes to P1)
    import json
    filter_json = json.dumps({
        "clinicalDataFilters": [
            {"attributeId": "SAMPLE_TYPE", "values": [{"value": "Primary"}]}
        ],
        "mutationFilter": {"genes": []},
        "svFilter": {"genes": []},
    })

    result = get_patient_treatment_counts(conn, STUDY, filter_json)
    by_name = {r["treatment"]: r["count"] for r in result}

    assert by_name.get("CISPLATIN") == 1, \
        f"Expected 1 patient on CISPLATIN after filter, got: {by_name}"
