from pathlib import Path
import re
import duckdb


SCENARIOS = ("increased", "winter", "reduced", "summer","gridsoc","pscbase","wbase")


# Maps file extension -> DuckDB table function used to read it
READERS = {
    ".csv": "read_csv_auto",
    ".parquet": "read_parquet",
}


def import_files_into_db(output_dir: Path, db_file: Path) -> None:
    output_dir = Path(output_dir)

    # DuckDB 2.x writes storage version 999 by default ("latest"), which older readers
    # (e.g. the VS Code DuckDB extension, max. storage version 68) cannot open.
    # v1.5.0 -> storage version 68. Only applies when the file is newly created.
    con = duckdb.connect(
        str(db_file), config={"storage_compatibility_version": "v1.5.0"}
    )

    try:
        data_files = sorted(
            f for f in output_dir.rglob("*") if f.suffix.lower() in READERS
        )

        for data_file in data_files:
            # Expected layout: {scenario}_run_{timestamp}/{seed}_directory/{seed}_multirun_{datatype}.{csv|parquet}
            relative_path = data_file.relative_to(output_dir)
            scenario_match = re.match(
                rf"({'|'.join(SCENARIOS)})_run_", relative_path.parts[0], re.IGNORECASE
            )
            seed_match = re.match(r"(\d+)_", data_file.stem)

            if scenario_match and seed_match:
                scenario = scenario_match.group(1).lower()
                seed = int(seed_match.group(1))
                datatype = data_file.stem[seed_match.end():]
                table_name = re.sub(r"[^a-zA-Z0-9_]", "_", datatype)
                reader = READERS[data_file.suffix.lower()]

                table_exists = con.execute(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_name = ?
                    """,
                    [table_name],
                ).fetchone()[0] > 0

                if not table_exists:
                    con.execute(
                        f"""
                        CREATE TABLE "{table_name}" AS
                        SELECT *, ? AS scenario, ? AS seed
                        FROM {reader}(?)
                        """,
                        [scenario, seed, str(data_file)],
                    )
                else:
                    con.execute(
                        f"""
                        INSERT INTO "{table_name}"
                        SELECT *, ? AS scenario, ? AS seed
                        FROM {reader}(?)
                        """,
                        [scenario, seed, str(data_file)],
                    )

                print(
                    f"Imported {data_file} -> {table_name} "
                    f"(scenario={scenario}, seed={seed})"
                )
    finally:
        con.close()

# Paths relative to this script (tools/), independent of the current working directory
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR.parent.parent / "sumo" / "output"
DB_FILE = SCRIPT_DIR.parent / "database" / "ebus.duckdb"

DB_FILE.parent.mkdir(parents=True, exist_ok=True)
import_files_into_db(OUTPUT_DIR, DB_FILE)
