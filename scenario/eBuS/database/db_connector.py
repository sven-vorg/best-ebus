"""
DuckDB connection helpers for the dashboard.

Replaces the old sqlite3-based db.py. Only two functions are needed
by dashboard.py: get_connection() and list_runs().
"""

import duckdb


def get_connection(db_path: str):
    """
    Open a read-only connection to the shared DuckDB database.

    read_only=True lets the dashboard (and multiple dashboard windows)
    open the file at the same time as whatever process is writing new
    runs into it - DuckDB only allows a single read-write handle on a
    file at once, so the dashboard should never take a write lock.
    """
    return duckdb.connect(db_path, read_only=True)


def list_runs(conn) -> list[str]:
    """
    Return all distinct simulation_timestamp values present in the
    database - this is what identifies a "run" in the new schema
    (set by DBeBuS._load_output() at import time).

    Pulled as a UNION of battery and chargingstations so a run shows
    up even if one of the two tables is missing rows for it.
    solar_power_v6 has no simulation_timestamp - it looks like a
    single static solar profile reused across every run.
    """
    df = conn.execute(
        """
        SELECT DISTINCT simulation_timestamp AS run_id FROM battery
        UNION
        SELECT DISTINCT simulation_timestamp AS run_id FROM chargingstations
        ORDER BY run_id
        """
    ).df()
    return df["run_id"].tolist()