import duckdb
import pytest

STUDY = "test_study"


@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    conn.execute(f"""
        CREATE TABLE "{STUDY}_sample" (SAMPLE_ID VARCHAR, PATIENT_ID VARCHAR)
    """)
    conn.execute(f"""
        CREATE TABLE "{STUDY}_patient" (PATIENT_ID VARCHAR)
    """)
    conn.execute(f"""
        CREATE TABLE "{STUDY}_mutations" (
            SAMPLE_ID VARCHAR,
            Hugo_Symbol VARCHAR,
            Entrez_Gene_Id VARCHAR,
            Variant_Classification VARCHAR,
            Mutation_Status VARCHAR
        )
    """)
    # Minimal studies table required by get_mutated_genes freq calculation
    conn.execute("""
        CREATE TABLE studies (
            study_id VARCHAR,
            type_of_cancer VARCHAR,
            name VARCHAR,
            description VARCHAR,
            short_name VARCHAR,
            public_study BOOLEAN,
            pmid VARCHAR,
            citation VARCHAR,
            groups VARCHAR,
            category VARCHAR
        )
    """)
    conn.execute("INSERT INTO studies (study_id, name) VALUES (?, ?)", (STUDY, "Test Study"))
    yield conn
    conn.close()


@pytest.fixture
def db_with_clinical_meta():
    """In-memory DuckDB with clinical_attribute_meta and study_data_types populated."""
    conn = duckdb.connect(":memory:")
    conn.execute(f'CREATE TABLE "{STUDY}_sample" (SAMPLE_ID VARCHAR, PATIENT_ID VARCHAR, CANCER_TYPE VARCHAR, SAMPLE_ATTR VARCHAR)')
    conn.execute(f'CREATE TABLE "{STUDY}_patient" (PATIENT_ID VARCHAR, GENDER VARCHAR, AGE DOUBLE, OS_MONTHS DOUBLE, OS_STATUS VARCHAR)')
    conn.execute("CREATE TABLE studies (study_id VARCHAR, name VARCHAR)")
    conn.execute("INSERT INTO studies VALUES (?, ?)", (STUDY, "Test Study"))
    conn.execute("""
        CREATE TABLE study_data_types (
            study_id VARCHAR NOT NULL,
            data_type VARCHAR NOT NULL,
            PRIMARY KEY (study_id, data_type)
        )
    """)
    conn.execute("INSERT INTO study_data_types VALUES (?, ?)", (STUDY, "mutation"))
    conn.execute("""
        CREATE TABLE clinical_attribute_meta (
            study_id          VARCHAR NOT NULL,
            attr_id           VARCHAR NOT NULL,
            display_name      VARCHAR,
            description       VARCHAR,
            datatype          VARCHAR,
            patient_attribute BOOLEAN,
            priority          INTEGER,
            PRIMARY KEY (study_id, attr_id)
        )
    """)
    conn.executemany("INSERT INTO clinical_attribute_meta VALUES (?, ?, ?, ?, ?, ?, ?)", [
        (STUDY, "CANCER_TYPE",  "Cancer Type",  "Type of cancer",     "STRING", False, 3000),
        (STUDY, "SAMPLE_ATTR",  "Sample Attr",  "A sample attribute", "STRING", False, 5),
        (STUDY, "GENDER",       "Sex",          "Patient gender",     "STRING", True,  9),
        (STUDY, "AGE",          "Age",          "Age at diagnosis",   "NUMBER", True,  9),
        (STUDY, "OS_MONTHS",    "OS Months",    "Survival months",    "NUMBER", True,  1),
        (STUDY, "OS_STATUS",    "OS Status",    "Survival status",    "STRING", True,  1),
        (STUDY, "HIDDEN_ATTR",  "Hidden",       "Priority 0 attr",    "STRING", False, 0),
    ])
    yield conn
    conn.close()


@pytest.fixture
def db_with_gene_ref():
    conn = duckdb.connect(":memory:")
    conn.execute(f'CREATE TABLE "{STUDY}_sample" (SAMPLE_ID VARCHAR, PATIENT_ID VARCHAR)')
    conn.execute(f"""CREATE TABLE "{STUDY}_mutations" (
        SAMPLE_ID VARCHAR, Hugo_Symbol VARCHAR, Entrez_Gene_Id VARCHAR,
        Variant_Classification VARCHAR, Mutation_Status VARCHAR
    )""")
    conn.execute("""
        CREATE TABLE gene_reference (
            entrez_gene_id INTEGER PRIMARY KEY,
            hugo_gene_symbol VARCHAR,
            gene_type VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE gene_symbol_updates (
            old_symbol VARCHAR PRIMARY KEY,
            new_symbol VARCHAR
        )
    """)
    # KMT2D (8085), KMT2C (58508), KMT2A (4297), KMT2B (9757)
    conn.executemany("INSERT INTO gene_reference VALUES (?, ?, ?)", [
        (8085, "KMT2D", "protein-coding"),
        (58508, "KMT2C", "protein-coding"),
        (4297, "KMT2A", "protein-coding"),
        (9757, "KMT2B", "protein-coding"),
        (3845, "KRAS", "protein-coding"),
    ])
    conn.executemany("INSERT INTO gene_symbol_updates VALUES (?, ?)", [
        ("MLL2", "KMT2D"),
        ("MLL3", "KMT2C"),
        ("MLL", "KMT2A"),
        ("MLL4", "KMT2B"),
    ])
    yield conn
    conn.close()
