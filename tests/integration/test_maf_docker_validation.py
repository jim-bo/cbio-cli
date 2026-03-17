"""Integration test for MAF validation using Docker and maftools."""

import os
import subprocess
import pytest
from pathlib import Path

from cbioportal.core.data_puller import pull_and_export_mutations

def has_docker():
    """Check if docker is installed and daemon is running."""
    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

@pytest.mark.docker
@pytest.mark.live_api
def test_maf_validation_with_maftools(tmp_path):
    """
    1. Pull real data for brca_bccrc.
    2. Assert Docker is available.
    3. Run maftools validation inside Docker.
    4. Assert no fatal errors and reasonable mutation counts.
    """
    if not has_docker():
        pytest.fail("Docker is required but not installed or daemon is not running.")

    study_id = "brca_bccrc"
    maf_file = tmp_path / f"{study_id}.maf"
    
    # Generate the file
    pull_and_export_mutations(study_id, maf_file)
    assert maf_file.exists()

    # R script to run inside container
    # We use a simple script that reads the maf and prints the summary.
    # If read.maf fails, R will exit with non-zero code.
    r_command = (
        "library(maftools); "
        f"m = read.maf(maf='/data/{maf_file.name}', verbose=TRUE); "
        "if(nrow(m@data) < 100) stop('Too few mutations found'); "
        "print(m)"
    )

    # Run Docker
    # We mount the tmp_path to /data so the container can see our generated file
    try:
        result = subprocess.run([
            "docker", "run", "--rm",
            "-v", f"{tmp_path}:/data",
            "-w", "/data",
            "quay.io/biocontainers/bioconductor-maftools:2.22.0--r44h15a9599_0",
            "Rscript", "-e", r_command
        ], capture_output=True, text=True, check=True)
        
        output = result.stdout
        assert "An object of class  MAF" in output
        assert "total" in output
        # Based on previous run, we expect around 2365 total
        assert "2365" in output or "2366" in output

    except subprocess.CalledProcessError as e:
        pytest.fail(f"MAF validation failed with exit code {e.returncode}.\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}")
