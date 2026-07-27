import duckdb
import os

from dotenv import load_dotenv
import numpy as np
from pathlib import Path
import pandas as pd

"""
ESS is not part of the Sumo Simulation,
this means it can be entierly calculated after the fact.
"""

class DB_ESS:

    def __init__(self, run_timestamp: str, capacity: float = 100.0, start_fill: float = 50.0):
        db_path = "best-ebus/scenario/eBuS/database/ebus.db"
        self.run_timestamp = run_timestamp
        self.station_charging = self.station_charging_timestep(db_path, run_timestamp)
        self.station_pv = self.station_pv_timestamp(db_path)
        ess = self.calculate_ess(self.station_charging, self.station_pv, capacity, start_fill)
        self.energy_storage = ess['fill']
        self.curtailed_pv = ess['curtailed_pv']
        self.unmet_demand = ess['unmet_demand']

        self.write_to_db(run_timestamp, self.energy_storage, db_path, "energy_storage")
        self.write_to_db(run_timestamp, self.curtailed_pv, db_path, "curtailed_pv")
        self.write_to_db(run_timestamp, self.unmet_demand, db_path, "unmet_demand")

    def station_pv_timestamp(self, db_path: Path) -> pd.DataFrame:
        with duckdb.connect(db_path) as con:
            solar: pd.DataFrame = con.sql("SELECT * FROM solar_power_v6").df()

        # Long format: one row per (station, bucket_seconds, value)
        bucket_cols = [c for c in solar.columns if c != 'station_id']
        solar_long = solar.melt(
            id_vars='station_id',
            value_vars=bucket_cols,
            var_name='bucket',
            value_name='value'
        )

        # "_3600" -> 3600
        solar_long['bucket_sec'] = solar_long['bucket'].str.lstrip('_').astype(int)

        # Pivot: rows = station, columns = bucket boundary (3600, 7200, ...)
        pivot = solar_long.pivot(index='station_id', columns='bucket_sec', values='value')
        pivot = pivot.sort_index(axis=1)

        # Expand to every second 1..86400
        full_range = pd.RangeIndex(start=1, stop=86401, step=1)
        pivot_full = pivot.reindex(columns=full_range)

        # Back-fill: each second picks up the value of the next bucket boundary
        pivot_full = pivot_full.bfill(axis=1)

        # Convert hourly bucket total into a per-second rate
        pivot_full = pivot_full / 3600

        # Transpose: rows = time, columns = stations
        pivot_full = pivot_full.T
        pivot_full.index.name = "step_time"
        pivot_full.columns.name = "station_id"

        return pivot_full

    def station_charging_timestep(self, db_path: Path, run_timestamp: str) -> pd.DataFrame:
        """ Get energy charged at station for every timestep, returns df index: chargingStation_id, columns: step_time (0 - 84600)"""
        # Connect to the DuckDB database and execute the query
        with duckdb.connect(db_path) as con:
            df = con.execute(
                """
                SELECT
                    chargingStation_id,
                    step_energyCharged,
                    step_time
                FROM chargingstations
                WHERE simulation_timestamp = ?
                ORDER BY chargingStation_id, step_time
                """,
                [run_timestamp],
            ).df()
        pivoted = df.pivot_table(
            index='chargingStation_id',
            columns='step_time',
            values='step_energyCharged'
        )

        full_range = pd.RangeIndex(start=0, stop=86401, step=1)
        pivoted = pivoted.reindex(columns=full_range, fill_value=0)

        # Transpose so time is the index
        pivoted = pivoted.T
        pivoted.index.name = "step_time"
        pivoted.columns.name = "chargingStation_id"

        return pivoted

    def calculate_ess(
        self,
        station_charging: pd.DataFrame,
        station_pv: pd.DataFrame,
        capacity,
        start_fill,
    ) -> dict[str, pd.DataFrame]:
        """Simulate ESS state of charge."""

        common_stations = station_charging.index.intersection(station_pv.index)
        common_steps = sorted(set(station_charging.columns) & set(station_pv.columns))

        if len(common_stations) == 0:
            raise ValueError("No overlapping station ids.")
        if len(common_steps) == 0:
            raise ValueError("No overlapping timesteps.")

        charging = station_charging.loc[common_stations, common_steps].to_numpy(float)
        pv = station_pv.loc[common_stations, common_steps].to_numpy(float)
        net = pv - charging

        n_stations, n_steps = net.shape

        def to_array(x, name):
            if np.isscalar(x):
                return np.full(n_stations, float(x))
            s = pd.Series(x).reindex(common_stations)
            if s.isna().any():
                raise ValueError(f"Missing {name} for stations: {s[s.isna()].index.tolist()}")
            return s.to_numpy(float)

        capacity = to_array(capacity, "capacity")
        fill_prev = to_array(start_fill, "start_fill")

        fill = np.empty_like(net)
        curtailed = np.empty_like(net)
        unmet = np.empty_like(net)

        for t in range(n_steps):
            raw = fill_prev + net[:, t]
            fill_prev = np.clip(raw, 0, capacity)

            fill[:, t] = fill_prev
            curtailed[:, t] = np.clip(raw - capacity, 0, None)
            unmet[:, t] = np.clip(-raw, 0, None)

        def to_long(data):
            return (
                pd.DataFrame(data, index=common_stations, columns=common_steps)
                .rename_axis(index="station_id", columns="step_time")
                .stack()
                .reset_index(name="value")
            )

        return {
            "fill": to_long(fill),
            "curtailed_pv": to_long(curtailed),
            "unmet_demand": to_long(unmet),
        }          

    @staticmethod
    def write_to_db(run_timestamp: str, data: pd.DataFrame, db_path: Path, table_name: str) -> None:
        # Don't modify the caller's DataFrame
        df = data.copy()
        df["run_timestamp"] = run_timestamp

        with duckdb.connect(db_path) as con:
            # Register the DataFrame as a temporary view
            con.register("df", df)

            # Create the table on the first run
            con.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} AS
                SELECT * FROM df WHERE FALSE
            """)

            # Append this batch
            con.execute(f"""
                INSERT INTO {table_name}
                SELECT * FROM df
            """)

if __name__ == "__main__":
    load_dotenv()
    run_timestamp = os.getenv("latest_timestamp")
    programm = DB_ESS(run_timestamp, capacity=500000.0, start_fill=50.0 )
