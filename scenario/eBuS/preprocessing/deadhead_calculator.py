# Imports
from lxml import etree
import sumolib
import pandas as pd
import os

class DeadheadCalculator():

    def __init__(self, network = "best-ebus/scenario/sumo/berlin.net.xml", stations = "best-ebus/scenario/sumo/berlin_bus_stops.add.xml", output = "./best-ebus/scenario/eBuS/files/merged_routes.rou.xml"):
        # Read Network
        self.net = sumolib.net.readNet(network)
        # Parse Routes
        self.routes_root = etree.parse("best-ebus/scenario/ebus/files/cicero_mueller_routes_trimmed.rou.xml").getroot()
        # Parse Stations
        self.station_root = etree.parse(stations).getroot()
        # Load Termination Points
        self.termination_points = self._load_termination_points("best-ebus/scenario/ebus/files/termination_points.txt")
        # Set Output
        self.output = output


    def _load_termination_points(self, path):
        return set(pd.read_csv(path, header = None)[0].astype(str))

    def calculate_station_deadheads(self):
        print("Starting Network Deadhead Calculations")
        stations = []
        for bus_stop in self.station_root.findall("busStop"):
            if bus_stop.attrib["id"] in self.termination_points:
                lane = bus_stop.attrib["lane"]
                edge = lane.rsplit("_", 1)[0]
                stations.append({
                    "id": bus_stop.attrib["id"],
                    "name": bus_stop.attrib["name"],
                    "edge": edge,
                    "end_pos": bus_stop.attrib["endPos"],
                    "start_pos": bus_stop.attrib["startPos"],
                })

        for skip_idx, output_file in [
            (0, "best-ebus/scenario/ebus/files/deadhead_time_cicerostrasse.txt"),
            (1, "best-ebus/scenario/ebus/files/deadhead_time_muellerstrasse.txt"),
        ]:
            selected = stations[:skip_idx] + stations[skip_idx + 1:]
            selected[0]["id"] = "1"

            time_rows = []
            routes = []

            for origin in selected:
                from_edge = self.net.getEdge(origin["edge"])
                from_pos = float(origin["end_pos"])
                for dest in selected:
                    to_edge = self.net.getEdge(dest["edge"])
                    to_pos = float(dest["start_pos"])
                    edges, cost = self.net.getFastestPath(from_edge, to_edge, fromPos=from_pos, toPos=to_pos)
                    
                    edge_ids = [edge.getID() for edge in edges]
                    time_rows.append({
                        "FromStopID": origin["id"],
                        "ToStopID": dest["id"],
                        "RunTime": round(cost),
                    })
                    routes.append({
                        "FromStopID": origin["id"],
                        "ToStopID": dest["id"],
                        "Edges": " ".join(edge_ids),
                    })

            pd.DataFrame(time_rows).to_csv(output_file, sep=";", index=False)
        # Routes
        for route in routes:
            etree.SubElement(
                self.routes_root,
                "route",
                id=f"{route['FromStopID']}_{route['ToStopID']}",
                color="0,153,153",
                edges=route["Edges"],
            )
        etree.indent(self.routes_root, space="    ")
        # Write XML
        tree = etree.ElementTree(self.routes_root)
        tree.write(
            self.output,
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=True,
        )
        print(f"Written {self.output} to disk")

if __name__ == "__main__":
    dc = DeadheadCalculator()
    dc.calculate_station_deadheads()