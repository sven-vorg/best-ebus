"""Filter the complete Bus Routes of Berlin accoarding to a csv containing the desired routes."""

# Imports
import pandas as pd
from lxml import etree
import math
import os

class FilterLines():

    def __init__(self):
        self.SELECTED_LINES = pd.read_csv("best-ebus/scenario/eBuS/files/depot_line_type.csv",sep=",")
        self.LINES = set(self.SELECTED_LINES["line"])

        ROUTES = "best-ebus/scenario/sumo/berlin_bus.rou.xml"
        self.routes_tree = etree.parse(ROUTES)
        self.routes_root = self.routes_tree.getroot()

        self.route_calculations = pd.DataFrame()

    def remove_routes(self):
        for route in self.routes_root.findall("route"):
            anchor = route.get("id").split("_", 1)[0]
            if anchor not in self.LINES:
                self.routes_root.remove(route)

    def remove_flows(self):
        for flow in self.routes_root.findall("flow"):
            anchor = flow.get("id").split("_", 1)[0]
            if anchor not in self.LINES:
                self.routes_root.remove(flow)
    
    def extract_flow_information(self):
        rows = []
        for i, route in enumerate(self.routes_root.findall("route")):
            anchor = route.get("id")
            stops = route.findall("stop")
            if stops:
                start_stop_id = stops[0].get("busStop")
                end_stop_id = stops[-1].get("busStop")
            for flow in self.routes_root.findall("flow"):
                if flow.get("route") == anchor:
                    period = float(flow.get("period"))
                    duration = float(stops[-1].get("until"))
                    nr_of_buses = math.ceil(int(duration) / int(period))
                    flow_end = self.parse_time(flow.get("end"))
                    flow_begin = self.parse_time(flow.get("begin"))
                    # print(flow.get("begin"),flow_begin,flow.get("end"),flow_end)
                    nr_of_repetitions = (flow_end-flow_begin)/duration
                    nr_of_trips_pd = (flow_end-flow_begin)/period
                    # Add the repeat attribute to the route
                    # route.set("repeat", str(int(nr_of_repetitions)))
                    rows.append({
                        "route": anchor,
                        "start_stop_id": start_stop_id,
                        "end_stop_id": end_stop_id,
                        "flow_end": flow_end,
                        "flow_begin": flow_begin,
                        "period": period,
                        "duration": duration,
                        "nr_of_buses": nr_of_buses,
                        "nr_of_repetitions": int(nr_of_repetitions),
                        "nr_of_trips_pd": int(nr_of_trips_pd)
                    })
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
        merged = self.route_calculations.merge(self.SELECTED_LINES, on="line", how="left")
        merged.to_csv("best-ebus/scenario/eBuS/files/merged_routes.csv", index=False)


    def main(self):
        self.remove_routes()
        self.remove_flows()
        self.extract_flow_information()
        self.write_xml_to_file()
        self.write_merged_csv_to_file()

    # Helper functions
    def parse_time(self, t):
        h, m, s = map(int, t.split(":"))
        return h * 3600 + m * 60 + s

if __name__ == "__main__":
    fl = FilterLines()
    fl.main()