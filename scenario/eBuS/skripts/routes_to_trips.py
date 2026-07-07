#!/usr/bin/env python
"""Skript for simplyfying rou.xml files for use in a heuristic method.
Output-Format: TRIP_ID;ORIGINAL_TRIP_ID;START_STOP_ID;END_STOP_ID;depot;START_TIMESTAMP;END_TIMESTAMP"""

__author__ = "Sven Vorgheim"
__license__ = "GPL v2 or later (In accoardance to SUMO)"
__maintainer__ = "Sven Vorgheim"
__email__ = "sven.vorgheim@fu-berlin.de"
__status__ = "Prototype"
__date__ = "02.07.2026"

# Imports
import numpy as np
import pandas as pd

class RoutesToTrips():
    
    def __init__(self, 
        merged_df = None, 
        input_path="./best-ebus/scenario/eBuS/files/merged_routes.csv", 
        output_path="./best-ebus/scenario/eBuS/files/"
    ):
        self.merged_df = merged_df
        self.input_path = input_path
        self.output_path = output_path

    def routes_to_trips(self, create_csv: bool = True) -> dict:
        """
        Creates mutliple csv / dict{df} of the desired format for each depot in the input: 
        TRIP_ID;ORIGINAL_TRIP_ID;START_STOP_ID;END_STOP_ID;START_TIMESTAMP;END_TIMESTAMP
        """
        if self.merged_df is not None:
            df = self.merged_df
        else:
            df = pd.read_csv(self.input_path)

        # explode repetitions
        df = df.loc[df.index.repeat(df["nr_of_trips_pd"])].copy()
        df["repetition"] = df.groupby(level=0).cumcount()

        # Compute timestamps
        df["trip_begin"] = df["flow_begin"] + df["repetition"] * df["period"]
        df["trip_end"] = df["trip_begin"] + df["duration"]

        # Rename columns
        df = df.rename(columns={
            "route": "ORIGINAL_TRIP_ID",
            "trip_begin": "START_TIMESTAMP",
            "trip_end": "END_TIMESTAMP",
            "start_stop_id": "START_STOP_ID",
            "end_stop_id": "END_STOP_ID",
        })

        # Remove unneeded columns
        df = df.drop(columns=[
            "nr_of_buses",
            "nr_of_repetitions",
            "nr_of_trips_pd",
            "line",
            "flow_begin",
            "flow_end",
            "bothdepots",
            "doubledecker",
            "period",
            "duration",
            "repetition",
            "type"
        ])

        df.reset_index(drop=True, inplace=True)

        depot_dict = {}
        # Split by depot
        for depot, depot_df in df.groupby("depot"):
            depot_df.drop(columns="depot")
            depot_df.insert(0, "TRIP_ID", range(1, len(depot_df) + 1))
            if create_csv:
                depot_df.to_csv(f"{self.output_path}trips_{depot}.txt", index=False, sep=";")
            depot_dict[f"{depot}"] = depot_df

        return depot_dict

if __name__ == "__main__":
    rt = RoutesToTrips()
    rt.routes_to_trips()