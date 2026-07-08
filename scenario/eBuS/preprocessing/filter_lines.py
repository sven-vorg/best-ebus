"""Filter the complete Bus Routes of Berlin accoarding to a csv containing the desired routes."""

# Imports
import pandas as pd
from lxml import etree
from pathlib import Path
import math
import os

class FilterLines():

    def __init__(
        self,
        routes_file: str = "best-ebus/scenario/sumo/berlin_bus.rou.xml",
        selected_lines_file: str = "best-ebus/scenario/eBuS/files/depot_line_type.csv",
        output_dir: str = "./best-ebus/scenario/eBuS/files/",
    ):
        self.routes_file = Path(routes_file)
        self.selected_lines_file = Path(selected_lines_file)
        self.output_dir = Path(output_dir)

        self.selected_lines = pd.read_csv(self.selected_lines_file)
        self.lines = set(self.selected_lines["line"])

        self.routes_tree = etree.parse(self.routes_file)
        self.routes_root = self.routes_tree.getroot()

        self.route_calculations = pd.DataFrame()

    def _remove_routes(self):
        for route in self.routes_root.findall("route"):
            anchor = route.get("id").split("_", 1)[0]
            if anchor not in self.lines:
                self.routes_root.remove(route)

    def _remove_flows(self):
        for flow in self.routes_root.findall("flow"):
            anchor = flow.get("id").split("_", 1)[0]
            if anchor not in self.lines:
                self.routes_root.remove(flow)

    def _find_flow(self, route_id: str):
        for flow in self.routes_root.findall("flow"):
            if flow.get("route") == route_id:
                return flow
        return None

    def _get_terminal_stops(self, route):
        stops = route.findall("stop")

        return (
            stops[0].get("busStop"),
            stops[-1].get("busStop"),
            float(stops[-1].get("until")),
        )

    def _calculate_statistics(
        self,
        route_id: str,
        flow,
        start_stop_id: str,
        end_stop_id: str,
        duration: float,
    ):
        period = float(flow.get("period"))

        flow_begin = self.parse_time(flow.get("begin"))
        flow_end = self.parse_time(flow.get("end"))

        return {
            "route": route_id,
            "start_stop_id": start_stop_id,
            "end_stop_id": end_stop_id,
            "flow_begin": flow_begin,
            "flow_end": flow_end,
            "period": period,
            "duration": duration,
            "nr_of_buses": math.ceil(duration / period),
            "nr_of_repetitions": int((flow_end - flow_begin) / duration),
            "nr_of_trips_pd": int((flow_end - flow_begin) / period),
        }
    
    def extract_flow_information(self):
        rows = []

        for route in self.routes_root.findall("route"):
            route_id = route.get("id")

            flow = self._find_flow(route_id)
            if flow is None:
                continue

            start_stop, end_stop, duration = self._get_terminal_stops(route)

            rows.append(
                self._calculate_statistics(
                    route_id,
                    flow,
                    start_stop,
                    end_stop,
                    duration,
                )
            )

            self.routes_root.remove(flow)

        self.route_calculations = pd.DataFrame(rows)

    def write_xml_to_file(self):
        self.routes_tree.write(
            "best-ebus/scenario/eBuS/files/cicero_mueller_routes.rou.xml",
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
        )

    def write_merged_csv_to_file(self):
        # Extract the line name from the route ID
        self.route_calculations["line"] = self.route_calculations["route"].str.split("_").str[0]
        # Join on the Line column
        merged = self.route_calculations.merge(self.selected_lines, on="line", how="left")
        merged.to_csv("best-ebus/scenario/eBuS/files/merged_routes.csv", index=False)


    def routes_to_trips(self, create_csv: bool = True) -> dict:
        """
        Creates mutliple csv / dict{df} of the desired format for each depot in the input: 
        TRIP_ID;ORIGINAL_TRIP_ID;START_STOP_ID;END_STOP_ID;START_TIMESTAMP;END_TIMESTAMP
        """
        # Extract the line name from the route ID
        self.route_calculations["line"] = self.route_calculations["route"].str.split("_").str[0]
        # Join on the Line column
        df = self.route_calculations.merge(self.selected_lines, on="line", how="left")

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
                depot_df.to_csv(f"{self.output_dir}/trips_{depot}.txt", index=False, sep=";")
            depot_dict[f"{depot}"] = depot_df

        return depot_dict

    def main(self):
        self._remove_routes()
        self._remove_flows()
        self.extract_flow_information()
        self.routes_to_trips(True)
        self.write_xml_to_file()
        self.write_merged_csv_to_file()

    # Helper functions
    def parse_time(self, t):
        h, m, s = map(int, t.split(":"))
        return h * 3600 + m * 60 + s

if __name__ == "__main__":
    fl = FilterLines()
    fl.main()