from pathlib import Path
import re
import duckdb


SCENARIOS = ("increased", "winter", "reduced", "summer")


def import_csvs_into_db(output_dir: Path, db_file: Path) -> None:
    output_dir = Path(output_dir)

    con = duckdb.connect(str(db_file))
    created_tables = set()

    try:
        csv_files = sorted(output_dir.rglob("*.csv"))

        for csv_file in csv_files:
            # Expected layout: {scenario}_run_{timestamp}/{seed}_directory/{seed}_multirun_{datatype}.csv
            relative_path = csv_file.relative_to(output_dir)
            scenario_match = re.match(
                rf"({'|'.join(SCENARIOS)})_run_", relative_path.parts[0], re.IGNORECASE
            )
            seed_match = re.match(r"(\d+)_", csv_file.stem)

            if scenario_match and seed_match:
                scenario = scenario_match.group(1).lower()
                seed = int(seed_match.group(1))
                datatype = csv_file.stem[seed_match.end():]
                table_name = re.sub(r"[^a-zA-Z0-9_]", "_", datatype)

                if table_name not in created_tables:
                    con.execute(
                        f"""
                        CREATE OR REPLACE TABLE "{table_name}" AS
                        SELECT *, ? AS scenario, ? AS seed
                        FROM read_csv_auto(?)
                        """,
                        [scenario, seed, str(csv_file)],
                    )
                    created_tables.add(table_name)
                else:
                    con.execute(
                        f"""
                        INSERT INTO "{table_name}"
                        SELECT *, ? AS scenario, ? AS seed
                        FROM read_csv_auto(?)
                        """,
                        [scenario, seed, str(csv_file)],
                    )

                print(
                    f"Imported {csv_file} -> {table_name} "
                    f"(scenario={scenario}, seed={seed})"
                )
            else:
                # Fallback for files that don't match the expected layout.
                table_name = re.sub(
                    r"[^a-zA-Z0-9_]",
                    "_",
                    str(relative_path.with_suffix("")),
                )
                con.execute(
                    f"""
                    CREATE OR REPLACE TABLE "{table_name}" AS
                    SELECT *
                    FROM read_csv_auto(?)
                    """,
                    [str(csv_file)],
                )
                print(f"Imported {csv_file} -> {table_name} (no scenario/seed detected)")

    finally:
        con.close()

#import_csvs_into_db(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\sumo\output", r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\eBuS\database\eBuS.duckdb")
import_csvs_into_db(Path(r"C:\Users\svens\Documents\FU-Berlin\BeST-eBuS\best-ebus\scenario\sumo\output"), Path(r"C:\Users\svens\Documents\FU-Berlin\BeST-eBuS\best-ebus\scenario\eBuS\database\eBuS.duckdb"))
