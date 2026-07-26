"""
DuckDB connection helpers for the dashboard.
"""

import duckdb
from pathlib import Path


def get_connection(db_path: Path) -> duckdb.DuckDBPyConnection:
    """
    Open a read-only connection to the shared DuckDB database.

    read_only=True lets the dashboard (and multiple dashboard windows)
    open the file at the same time as whatever process is writing new
    runs into it - DuckDB only allows a single read-write handle on a
    file at once, so the dashboard should never take a write lock.
    """
    return duckdb.connect(db_path, read_only=True)


def list_runs(conn: duckdb.DuckDBPyConnection) -> list[str]:
    """
    Return all distinct simulation_timestamp values present in the
    database - this is what identifies a "run" in the new schema
    (set by DBeBuS._load_output() at import time).
    """
    df = conn.execute(
        """
        SELECT DISTINCT simulation_timestamp AS run_id FROM sumo_config
        """
    ).df()
    return df["run_id"].tolist()