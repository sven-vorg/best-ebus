# AI generated on 2026-07-18

"""
Creates the DuckDB database schema for SUMO simulation results.
"""
import duckdb
import os
from pathlib import Path
from dotenv import load_dotenv

class DBeBuS():
    def __init__(self) -> None:
        load_dotenv()
        self.latest_timestamp = os.getenv("latest_timestamp")

    def _load_output(self):
        files = [
            f"best-ebus/scenario/sumo/output/electric_bus_{self.latest_timestamp}_battery.parquet",
            f"best-ebus/scenario/sumo/output/electric_bus_{self.latest_timestamp}_tripinfo.parquet",
            f"best-ebus/scenario/sumo/output/electric_bus_{self.latest_timestamp}_chargingstations.parquet",
        ]

        db_path = "best-ebus/scenario/eBuS/database/ebus.db"

        with duckdb.connect(db_path) as conn:
            for file in files:
                table_name = Path(file).stem.removeprefix(
                    f"electric_bus_{self.latest_timestamp}_"
                )
                print(table_name)
                # Create the table on the first import
                conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table_name} AS
                    SELECT *,
                        ? AS simulation_timestamp
                    FROM read_parquet(?)
                    LIMIT 0
                    """,
                    [self.latest_timestamp, file],
                )

                # Append this simulation's data
                conn.execute(
                    f"""
                    INSERT INTO {table_name}
                    SELECT *,
                        ? AS simulation_timestamp
                    FROM read_parquet(?)
                    """,
                    [self.latest_timestamp, file],
                )
        
    def _load_pv(self):
        file = "best-ebus/scenario/eBuS/ext_data/solar_power_v6.csv"
        db_path = "best-ebus/scenario/eBuS/database/ebus.db"
        with duckdb.connect(db_path) as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS solar_power_v6 AS
                SELECT *,

                FROM read_csv_auto(?, header=true)
                """,
                [file],
            )

if __name__ == "__main__":
    db = DBeBuS()
    db._load_output()
    db._load_pv()
    print("Database loaded.")