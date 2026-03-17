"""Orchestrator for pulling, caching, and exporting annotated cBioPortal data."""
import os
from pathlib import Path
import json

import duckdb

from cbioportal.core.api.client import CbioPortalClient
from cbioportal.core.cache import get_cache_connection, get_study_cache_status, update_study_cache_manifest
from cbioportal.core.annotators.moalmanac import annotate_variants


def pull_and_export_mutations(study_id: str, output_path: str | Path) -> None:
    """Pull mutations for a study, cache them, annotate, and export to TSV."""
    output_path = Path(output_path)
    status = get_study_cache_status(study_id, "mutations")
    
    conn = get_cache_connection()
    
    try:
        if not status:
            print(f"Cache miss or expired for {study_id} mutations. Fetching from API...")
            with CbioPortalClient() as client:
                profile_id = client.get_mutation_profile_id(study_id)
                if not profile_id:
                    raise ValueError(f"No MUTATION_EXTENDED profile found for study {study_id}")
                
                sample_list_id = client.get_default_sample_list_id(study_id)
                if not sample_list_id:
                    raise ValueError(f"No sample lists found for study {study_id}")
                    
                raw_mutations = client.get_mutations_raw(profile_id, sample_list_id)
                
            # Create a table for these raw mutations to leverage DuckDB's querying power
            conn.execute("CREATE TABLE IF NOT EXISTS raw_mutations (study_id VARCHAR, data VARCHAR)")
            conn.execute("DELETE FROM raw_mutations WHERE study_id = ?", [study_id])
            
            # Fast batch insert by letting DuckDB read from Python structures directly
            if raw_mutations:
                # We inject the study_id and dump the raw record to JSON for flexible parsing
                data_tuples = [(study_id, json.dumps(m)) for m in raw_mutations]
                conn.executemany("INSERT INTO raw_mutations (study_id, data) VALUES (?, ?)", data_tuples)
                
            update_study_cache_manifest(study_id, "mutations", profile_id)
        else:
            print(f"Using cached mutations for {study_id} (fetched at {status['fetched_at']})")
            
        # Extract unique Gene + Alteration pairs from the loaded JSON
        # Example JSON: {"gene": {"hugoGeneSymbol": "BRAF"}, "proteinChange": "V600E", ...}
        print("Extracting unique variants for annotation...")
        unique_vars = conn.execute("""
            SELECT DISTINCT 
                json_extract_string(data, '$.gene.hugoGeneSymbol') as gene, 
                json_extract_string(data, '$.proteinChange') as alteration
            FROM raw_mutations 
            WHERE study_id = ? 
              AND json_extract_string(data, '$.gene.hugoGeneSymbol') IS NOT NULL 
              AND json_extract_string(data, '$.proteinChange') IS NOT NULL
        """, [study_id]).fetchall()
        
        # Run annotator
        annotate_variants(conn, unique_vars)
        
        # Build the final view joining the raw JSON mutations with the MoAlmanac JSON responses
        print(f"Exporting annotated data to {output_path}...")
        
        # We flatten out the main mutation fields, and extract the annotation 'description' 
        # from the MoAlmanac payload if one exists.
        export_query = f"""
            COPY (
                SELECT 
                    json_extract_string(m.data, '$.gene.hugoGeneSymbol') AS Hugo_Symbol,
                    json_extract_string(m.data, '$.entrezGeneId') AS Entrez_Gene_Id,
                    json_extract_string(m.data, '$.sampleId') AS Tumor_Sample_Barcode,
                    json_extract_string(m.data, '$.proteinChange') AS Protein_Change,
                    json_extract_string(m.data, '$.mutationType') AS Variant_Classification,
                    -- Squash multiple annotations into a single semicolon-separated string
                    string_agg(
                        COALESCE(a_sign.clinical_significance || ' (' || COALESCE(a_sign.drug, 'N/A') || '): ' || COALESCE(a_sign.disease, 'N/A'), NULL),
                        '; '
                    ) AS MoAlmanac_Annotation
                FROM raw_mutations m
                LEFT JOIN moalmanac_features_bulk a_feat 
                  ON json_extract_string(m.data, '$.gene.hugoGeneSymbol') = a_feat.gene 
                  AND json_extract_string(m.data, '$.proteinChange') = a_feat.alteration
                LEFT JOIN moalmanac_assertions_bulk a_sign
                  ON a_feat.feature_id = a_sign.feature_id
                WHERE m.study_id = ?
                GROUP BY ALL
            ) TO '{output_path}' (HEADER, DELIMITER '\t');
        """
        conn.execute(export_query, [study_id])
        print(f"Successfully exported to {output_path}")

    finally:
        conn.close()
