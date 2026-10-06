from pathlib import Path
import re
import duckdb


#SCENARIOS = ("increased", "winter", "reduced", "summer","gridsoc")
SCENARIOS = ("wbase",)


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
                        FROM read_csv_auto(?)
                        """,
                        [scenario, seed, str(csv_file)],
                    )
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
    finally:
        con.close()

#import_csvs_into_db(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\sumo\output", r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\eBuS\database\eBuS.duckdb")
import_csvs_into_db(Path(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\sumo\output"), Path(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\eBuS\database\eBuS.duckdb"))
