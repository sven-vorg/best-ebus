# AI generated on 2026-07-18, adapted for star schema on 2026-07-26

"""
Creates the DuckDB database schema for SUMO simulation results.

The `chargingstations` output is normalized into a star schema:
    - dim_simulation_run   (registry of simulation runs)
    - dim_station          (one row per station per run)
    - dim_session          (one row per vehicle charging session per run)
    - fact_charging_step   (one row per charging step, referencing the above)

`battery` and `tripinfo` outputs, plus `solar_power_v6`, `day_ahead_prices_long`,
and `sumo_config`, are kept as-is (unchanged from the original flat-table loader).
"""

from pathlib import Path
from lxml import etree
import duckdb
import os
from dotenv import load_dotenv

DB_PATH = "best-ebus/scenario/eBuS/database/ebus.db"


class DBeBuS:
    def __init__(self) -> None:
        load_dotenv()
        self.latest_timestamp = os.getenv("latest_timestamp")

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    def _update_db(self):
        self._load_output()
        self._load_pricing()
        self._load_pv()
        self._load_sumo_config(
            xml_file="best-ebus/scenario/sumo/e_berlin-bus.sumocfg",
            db_path=DB_PATH,
        )

    # ------------------------------------------------------------------
    # Star schema setup
    # ------------------------------------------------------------------
    def _register_simulation_run(self, conn, timestamp):
        """Ensure a registry table exists and record this run's timestamp."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dim_simulation_run (
                simulation_timestamp VARCHAR PRIMARY KEY
            )
        """)
        conn.execute(
            "INSERT INTO dim_simulation_run VALUES (?) ON CONFLICT DO NOTHING",
            [timestamp],
        )

    def _ensure_star_schema(self, conn):
        """Create sequences + star schema tables if they don't exist yet."""
        conn.execute("CREATE SEQUENCE IF NOT EXISTS station_key_seq START 1")
        conn.execute("CREATE SEQUENCE IF NOT EXISTS session_key_seq START 1")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS dim_station (
                station_key BIGINT PRIMARY KEY DEFAULT nextval('station_key_seq'),
                simulation_timestamp VARCHAR REFERENCES dim_simulation_run(simulation_timestamp),
                chargingStation_id VARCHAR,
                chargingStation_totalEnergyCharged DOUBLE,
                chargingStation_chargingSteps INTEGER
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS dim_session (
                session_key BIGINT PRIMARY KEY DEFAULT nextval('session_key_seq'),
                simulation_timestamp VARCHAR REFERENCES dim_simulation_run(simulation_timestamp),
                vehicle_id VARCHAR,
                vehicle_type VARCHAR,
                vehicle_chargingBegin VARCHAR,
                vehicle_chargingEnd VARCHAR,
                vehicle_totalEnergyChargedIntoVehicle DOUBLE,
                chargingStation_id VARCHAR
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS fact_charging_step (
                station_key BIGINT REFERENCES dim_station(station_key),
                session_key BIGINT REFERENCES dim_session(session_key),
                simulation_timestamp VARCHAR REFERENCES dim_simulation_run(simulation_timestamp),
                step_time VARCHAR,
                step_chargingStatus VARCHAR,
                step_energyCharged DOUBLE,
                step_partialCharge DOUBLE,
                step_power DOUBLE,
                step_efficiency DOUBLE,
                step_actualBatteryCapacity DOUBLE,
                step_maximumBatteryCapacity DOUBLE
            )
        """)

    def _load_chargingstations_star(self, conn, file, timestamp):
        """Load one run's chargingstations parquet directly into the star schema."""
        self._register_simulation_run(conn, timestamp)
        self._ensure_star_schema(conn)

        # Stage this run's raw rows in a temp view (not persisted to disk)
        conn.execute(
            "CREATE OR REPLACE TEMP VIEW _staging AS "
            "SELECT *, ? AS simulation_timestamp FROM read_parquet(?)",
            [timestamp, file],
        )

        # --- dim_station: one row per station for this run ---
        conn.execute("""
            INSERT INTO dim_station (
                simulation_timestamp, chargingStation_id,
                chargingStation_totalEnergyCharged, chargingStation_chargingSteps
            )
            SELECT
                simulation_timestamp,
                chargingStation_id,
                ANY_VALUE(chargingStation_totalEnergyCharged),
                ANY_VALUE(chargingStation_chargingSteps)
            FROM _staging
            GROUP BY simulation_timestamp, chargingStation_id
        """)

        # --- dim_session: one row per (vehicle, session) for this run ---
        conn.execute("""
            INSERT INTO dim_session (
                simulation_timestamp, vehicle_id, vehicle_type,
                vehicle_chargingBegin, vehicle_chargingEnd,
                vehicle_totalEnergyChargedIntoVehicle, chargingStation_id
            )
            SELECT
                simulation_timestamp,
                vehicle_id,
                vehicle_type,
                vehicle_chargingBegin,
                vehicle_chargingEnd,
                ANY_VALUE(vehicle_totalEnergyChargedIntoVehicle),
                ANY_VALUE(chargingStation_id)
            FROM _staging
            GROUP BY simulation_timestamp, vehicle_id, vehicle_type,
                     vehicle_chargingBegin, vehicle_chargingEnd
        """)

        # --- fact_charging_step: one row per step, resolved to surrogate keys ---
        conn.execute("""
            INSERT INTO fact_charging_step (
                station_key, session_key, simulation_timestamp, step_time,
                step_chargingStatus, step_energyCharged, step_partialCharge,
                step_power, step_efficiency, step_actualBatteryCapacity,
                step_maximumBatteryCapacity
            )
            SELECT
                ds.station_key,
                dv.session_key,
                s.simulation_timestamp,
                s.step_time,
                s.step_chargingStatus,
                s.step_energyCharged,
                s.step_partialCharge,
                s.step_power,
                s.step_efficiency,
                s.step_actualBatteryCapacity,
                s.step_maximumBatteryCapacity
            FROM _staging s
            JOIN dim_station ds
                ON s.chargingStation_id = ds.chargingStation_id
               AND s.simulation_timestamp = ds.simulation_timestamp
            JOIN dim_session dv
                ON s.vehicle_id = dv.vehicle_id
               AND s.vehicle_chargingBegin = dv.vehicle_chargingBegin
               AND s.simulation_timestamp = dv.simulation_timestamp
        """)

        conn.execute("DROP VIEW _staging")

    # ------------------------------------------------------------------
    # Output loading (battery, tripinfo flat as before; chargingstations -> star)
    # ------------------------------------------------------------------
    def _load_output(self):
        self._load_output_for_timestamp(self.latest_timestamp)

    def _load_output_for_timestamp(self, timestamp):
        battery_file = (
            f"best-ebus/scenario/sumo/output/electric_bus_{timestamp}_battery.parquet"
        )
        tripinfo_file = (
            f"best-ebus/scenario/sumo/output/electric_bus_{timestamp}_tripinfo.parquet"
        )
        chargingstations_file = (
            f"best-ebus/scenario/sumo/output/electric_bus_{timestamp}_chargingstations.parquet"
        )

        with duckdb.connect(DB_PATH) as conn:
            # battery + tripinfo stay flat (unchanged behavior) unless/until
            # they also need normalizing
            for file in (battery_file, tripinfo_file):
                table_name = Path(file).stem.removeprefix(
                    f"electric_bus_{timestamp}_"
                )
                print(f"Loading data for table: {table_name}")

                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} AS
                    SELECT *,
                        '{timestamp}' AS simulation_timestamp
                    FROM read_parquet(?)
                    LIMIT 0
                """, [file])

                conn.execute(f"""
                    INSERT INTO {table_name}
                    SELECT *,
                        '{timestamp}' AS simulation_timestamp
                    FROM read_parquet(?)
                """, [file])

            # chargingstations -> star schema
            print("Loading data for tables: dim_station, dim_session, fact_charging_step")
            self._load_chargingstations_star(conn, chargingstations_file, timestamp)

    # ------------------------------------------------------------------
    # Reference / external data (unchanged)
    # ------------------------------------------------------------------
    def _load_pv(self):
        file = "best-ebus/scenario/eBuS/ext_data/solar_power_v6.csv"
        with duckdb.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS solar_power_v6 AS
                SELECT *
                FROM read_csv_auto(?, header=true)
                """,
                [file],
            )
        print("Loading data for table: solar_power_v6")

    def _load_pricing(self):
        file = "best-ebus/scenario/eBuS/ext_data/day_ahead_prices_long.csv"
        with duckdb.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS day_ahead_prices_long AS
                SELECT *
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

    # ------------------------------------------------------------------
    # Manual / backfill loading for an arbitrary past run
    # ------------------------------------------------------------------
    def _manual_update_db(self, timestamp):
        """Load a specific (non-latest) simulation run's output into the DB."""
        self._load_output_for_timestamp(timestamp)


if __name__ == "__main__":
    db = DBeBuS()
    db._update_db()
    print("Database loaded.")