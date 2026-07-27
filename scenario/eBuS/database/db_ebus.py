# AI generated on 2026-07-18

"""
Creates the DuckDB database schema for SUMO simulation results.
"""

from pathlib import Path
from lxml import etree
import duckdb
import os
from dotenv import load_dotenv

class DBeBuS:
    def __init__(self) -> None:
        load_dotenv()
        self.latest_timestamp = os.getenv("latest_timestamp")

    def _update_db(self):
        self._load_output()
        self._load_pricing()
        self._load_pv()
        self._load_sumo_config(
            xml_file="best-ebus/scenario/sumo/e_berlin-bus.sumocfg",
            db_path="best-ebus/scenario/eBuS/database/ebus.db",
        )

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
                print(f"Loading data for table: {table_name}")
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
                """
                CREATE TABLE IF NOT EXISTS solar_power_v6 AS
                SELECT *,

                FROM read_csv_auto(?, header=true)
                """,
                [file],
            )
        print("Loading data for table: solar_power_v6")

    def _load_pricing(self):
        file = "best-ebus/scenario/eBuS/ext_data/day_ahead_prices_long.csv"
        db_path = "best-ebus/scenario/eBuS/database/ebus.db"
        with duckdb.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS day_ahead_prices_long AS
                SELECT *,

            FROM read_csv_auto(?, header=true)
            """,
            [file],
        )
        print("Loading data for table: day_ahead_prices_long")

    def _load_sumo_config(self, xml_file, db_path):
        """Load a SUMO configuration XML into DuckDB."""

        tree = etree.parse(xml_file)

        rows = [
            (
                self.latest_timestamp,
                section.tag,
                option.tag,
                option.get("value"),
            )
            for section in tree.getroot()
            for option in section
        ]

        with duckdb.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sumo_config (
                    simulation_timestamp VARCHAR,
                    section VARCHAR,
                    option VARCHAR,
                    value VARCHAR
                )
            """)

            conn.executemany(
                "INSERT INTO sumo_config VALUES (?, ?, ?, ?)",
                rows,
            )

    def _manual_update_db(self, timestamp):

        files = [
            f"best-ebus/scenario/sumo/output/electric_bus_{timestamp}_battery.parquet",
            f"best-ebus/scenario/sumo/output/electric_bus_{timestamp}_tripinfo.parquet",
            f"best-ebus/scenario/sumo/output/electric_bus_{timestamp}_chargingstations.parquet",
        ]

        db_path = "best-ebus/scenario/eBuS/database/ebus.db"

        with duckdb.connect(db_path) as conn:
            for file in files:
                table_name = Path(file).stem.removeprefix(
                    f"electric_bus_{timestamp}_"
                )
                print(f"Loading data for table: {table_name}")
                # Create the table on the first import
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS {table_name} AS
                    SELECT *,
                        ? AS simulation_timestamp
                    FROM read_parquet(?)
                    LIMIT 0
                    """,
                [   self.latest_timestamp, file],
                )

                # Append this simulation's data
                conn.execute(
                    """
                    INSERT INTO {table_name}
                    SELECT *,
                        ? AS simulation_timestamp
                    FROM read_parquet(?)
                    """,
                    [self.latest_timestamp, file],
                )

if __name__ == "__main__":
    db = DBeBuS()
    db._update_db()
    db._load_pricing()
    db._load_pv()
    db._load_sumo_config(
        xml_file="best-ebus/scenario/sumo/e_berlin-bus.sumocfg",
        db_path="best-ebus/scenario/eBuS/database/ebus.db",
    )
    print("Database loaded.")