# Dashboard creation
# Pulls Data from database
import duckdb
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import f_oneway
from pprint import pprint

class TextDashboard:

    def __init__(
            self,
            database: Path,
            output: Path
        ):
        self.output = output
        self.con = duckdb.connect(str(database), read_only=True)

    # Context Manager Helpers
    def close(self):
        # Verbindung explizit schliessen
        self.con.close()

    def __enter__(self):
        # Ermöglicht: with TextDashboard(...) as dash:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False  # Exceptions nicht verschlucken

    # DB access functions

    def infrastructure_details(self):
        result = self.con.execute(
            """
            WITH stations AS (
                SELECT scenario,
                    COUNT(DISTINCT chargingEvent_chargingStationId) AS num_stations
                FROM multirun_chargingstations
                GROUP BY scenario
            ),
            trips AS (
                SELECT scenario,
                    COUNT(DISTINCT tripinfo_id) AS num_trips
                FROM multirun_tripinfo
                GROUP BY scenario
            )
            SELECT
                s.scenario,
                s.num_stations,
                t.num_trips
            FROM stations s
            JOIN trips t USING (scenario)
            ORDER BY s.scenario
            """
        ).fetchall()

        for scenario, num_stations, num_trips in result:
            print(f"Scenario {scenario}: {num_stations} Stations, {num_trips} Vehicles")

"""
    def vehicle_delay():
        pass

    def vehicle_soc():
        pass

    def vehicle_depletions():
        pass
"""

if __name__ == "__main__":
    with TextDashboard(database= Path("best-ebus/scenario/eBuS/database/ebus.duckdb"), output= Path("best-ebus/scenario/dashboards")) as dash:
        dash.infrastructure_details()