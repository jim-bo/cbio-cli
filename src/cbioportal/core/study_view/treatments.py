"""Treatment timeline chart queries for the Study View dashboard."""
from __future__ import annotations

from .filters import _build_filter_subquery


def get_patient_treatment_counts(
    conn,
    study_id: str,
    filter_json: str | None = None,
) -> list[dict]:
    """Return distinct patient counts per treatment agent.

    Counts distinct patients whose samples are in the filtered cohort and
    who received each named treatment.

    Returns [] if the timeline_treatment table does not exist.
    """
    filter_sql, params = _build_filter_subquery(conn, study_id, filter_json)
    sql = f"""
        SELECT AGENT as treatment, COUNT(DISTINCT PATIENT_ID) as count
        FROM "{study_id}_timeline_treatment"
        WHERE PATIENT_ID IN (
            SELECT PATIENT_ID FROM "{study_id}_sample"
            WHERE SAMPLE_ID IN ({filter_sql})
        )
        AND AGENT IS NOT NULL AND AGENT != '' AND AGENT != 'NA'
        GROUP BY AGENT
        ORDER BY count DESC, AGENT
    """
    try:
        rows = conn.execute(sql, params).fetchall()
        return [{"treatment": r[0], "count": r[1]} for r in rows]
    except Exception:
        return []


def get_sample_treatment_counts(
    conn,
    study_id: str,
    filter_json: str | None = None,
) -> list[dict]:
    """Return sample counts by treatment agent and pre/post timing.

    For each treatment, classifies samples as Pre (collected before treatment
    start) or Post (collected on or after treatment start) by joining the
    specimen timeline (collection dates) with the treatment timeline.

    Returns [] if either timeline table does not exist.
    """
    filter_sql, params = _build_filter_subquery(conn, study_id, filter_json)
    sql = f"""
        WITH filtered_samples AS (
            SELECT SAMPLE_ID, PATIENT_ID FROM "{study_id}_sample"
            WHERE SAMPLE_ID IN ({filter_sql})
        ),
        sample_dates AS (
            SELECT fs.SAMPLE_ID, fs.PATIENT_ID, sp.START_DATE as collection_date
            FROM filtered_samples fs
            JOIN "{study_id}_timeline_specimen" sp ON fs.SAMPLE_ID = sp.SAMPLE_ID
        )
        SELECT
            t.AGENT as treatment,
            CASE WHEN sd.collection_date < t.START_DATE THEN 'Pre' ELSE 'Post' END as time,
            COUNT(DISTINCT sd.SAMPLE_ID) as count
        FROM "{study_id}_timeline_treatment" t
        JOIN sample_dates sd ON t.PATIENT_ID = sd.PATIENT_ID
        WHERE t.AGENT IS NOT NULL AND t.AGENT != '' AND t.AGENT != 'NA'
        GROUP BY t.AGENT, time
        ORDER BY count DESC, t.AGENT, time
    """
    try:
        rows = conn.execute(sql, params).fetchall()
        return [{"treatment": r[0], "time": r[1], "count": r[2]} for r in rows]
    except Exception:
        return []
