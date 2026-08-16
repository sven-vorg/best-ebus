"""Filter the complete Bus Routes of Berlin accoarding to a csv containing the desired routes."""

# Imports
import pandas as pd
from lxml import etree
from pathlib import Path
import math

class FilterLines:

    def __init__(
        self,
        routes_file: Path,
        selected_lines_file: Path,
        bus_stops_file: Path,
        output_dir: Path,
    ):
        self.routes_tree = etree.parse(routes_file)
        self.routes_root = self.routes_tree.getroot()

        self.selected_lines = pd.read_csv(selected_lines_file)
        self.lines = set(self.selected_lines["line"])

        self.bus_stops_tree = etree.parse(bus_stops_file)
        self.bus_stops_root = self.bus_stops_tree.getroot()

        self.output_dir = output_dir

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


    def routes_to_trips(self, create_csv: bool = True):
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

        # Add additonal information "Name" and "Coordinates" of first and last bus stop
        stop_name_dict = self.stop_name_dict()
        df["START_STOP_NAME"] = df["start_stop_id"].map(stop_name_dict)
        df["END_STOP_NAME"] = df["end_stop_id"].map(stop_name_dict)

        stop_coord_dict = self.stop_coord_dict()
        df["START_STOP_COORDINATES"] = df["start_stop_id"].map(stop_coord_dict)
        df["END_STOP_COORDINATES"] = df["end_stop_id"].map(stop_coord_dict)

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
        df.to_csv(f"{self.output_dir}/trips_best.txt", index=False, sep=";")

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

    # Parse additional information
    def stop_name_dict(self):
        bus_stop_names = {
            stop.get("id"): stop.get("name")
            for stop in self.bus_stops_root.findall("busStop")
        }
        return bus_stop_names

    def stop_coord_dict(self):
        bus_stop_coords = {
            stop.get("id"): stop.get("coordinates")
            for stop in self.bus_stops_root.findall("busStop")
        }
        return bus_stop_coords


if __name__ == "__main__":
    
    HERE = Path(__file__).resolve().parent

    routes_file = (HERE / "../../sumo/berlin_bus.rou.xml").resolve()
    selected_lines_file = (HERE / "../files/preprocessing_input/depot_line_type.csv").resolve()
    bus_stops_file = (HERE /  "../../sumo/berlin_bus_stops.add.xml").resolve()
    output_dir = (HERE / "../postprocessing_inputs/files").resolve()
    fl = FilterLines(routes_file, selected_lines_file, bus_stops_file, output_dir)
    fl.main()