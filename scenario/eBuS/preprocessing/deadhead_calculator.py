# Imports
from lxml import etree
import sumolib
import pandas as pd
import os

class DeadheadCalculator():

    def __init__(
            self, 
            network: str = "best-ebus/scenario/sumo/berlin.net.xml", 
            stations: str = "best-ebus/scenario/sumo/berlin_bus_stops.add.xml", 
            routes: str = "best-ebus/scenario/eBuS/files/cicero_mueller_routes_trimmed.rou.xml",
            termination_points: str = "best-ebus/scenario/eBuS/files/termination_points.txt",
            depots: tuple = ("cicerostrasse", "muellerstrasse"),
            output: str = "./best-ebus/scenario/eBuS/files"):
        # Read Network
        self.net = sumolib.net.readNet(network)
        # Parse Routes
        self.routes_root = etree.parse(routes).getroot()
        # Parse Stations
        self.station_root = etree.parse(stations).getroot()
        # Load Termination Points
        self.termination_points = self._load_termination_points(termination_points)
        self.depots = depots
        # Set Output
        self.output = output



    def _load_termination_points(self, path):
        return set(pd.read_csv(path, header = None)[0].astype(str))

    def _get_stations(self):
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
        return stations

    def _write_deadhead_time(self, time_rows):
        for depot in self.depots:
            rows = []

            for row in time_rows:
                row = row.copy()

                if depot in str(row["FromStopID"]):
                    row["FromStopID"] = "1"
                if depot in str(row["ToStopID"]):
                    row["ToStopID"] = "1"

                rows.append(row)

            pd.DataFrame(rows).to_csv(
                f"{self.output}/deadhead_time_{depot}.txt",
                sep=";",
                index=False
            )
            print(f"Written deadhead_time_{depot}.txt")


    def calculate_edge_deadheads(self):
        print("Starting Network Deadhead Calculations")
        time_rows = []
        routes = []
        for route in self.routes_root.findall("route"):
            parts = route.get("edges").split(" ")
            from_edge = self.net.getEdge(parts[0])
            to_edge = self.net.getEdge(parts[-1])
            stops = route.findall("stop")
            from_stop = stops[0].get("busStop")
            to_stop = stops[-1].get("busStop")
            edges, cost = self.net.getFastestPath(from_edge, to_edge)
            time_rows.append({
                    "FromStopID": from_stop,
                    "ToStopID": to_stop,
                    "RunTime": round(cost),
                })
            routes.append({
                    "FromStopID": from_stop,
                    "ToStopID": to_stop,
                    "Edges": edges,
                })        
        print("Completed Network Deadhead Calculations")

        #self._write_deadhead_time(time_rows)
        print(routes)
        return "String"
        for route in routes:
            etree.SubElement(
                self.routes_root,
                "route",
                id=f"{route['FromStopID']}_{route['ToStopID']}",
                color="0,153,153",
                edges=route["Edges"],
            )

        etree.indent(self.routes_root, space="    ")
        tree = etree.ElementTree(self.routes_root)
        tree.write(
            f"{self.output}/merged_routes.rou.xml",
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=True,
        )
        print(f"Written {self.output} to disk")

    def calculate_station_deadheads(self):
        print("Starting Network Deadhead Calculations")
        time_rows = []
        routes = []

        selected = self._get_stations()

        for origin in selected:
            from_edge = self.net.getEdge(origin["edge"])
            from_pos = float(origin["end_pos"])
            for dest in selected:
                to_edge = self.net.getEdge(dest["edge"])
                to_pos = float(dest["start_pos"])
                edges, cost = self.net.getFastestPath(
                    from_edge, to_edge, fromPos=from_pos, toPos=to_pos
                )
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
        
        print("Completed Network Deadhead Calculations")

        self._write_deadhead_time(time_rows)

        for route in routes:
            etree.SubElement(
                self.routes_root,
                "route",
                id=f"{route['FromStopID']}_{route['ToStopID']}",
                color="0,153,153",
                edges=route["Edges"],
            )

        etree.indent(self.routes_root, space="    ")
        tree = etree.ElementTree(self.routes_root)
        tree.write(
            f"{self.output}/merged_routes.rou.xml",
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=True,
        )
        print(f"Written {self.output} to disk")

if __name__ == "__main__":
    dc = DeadheadCalculator()
    dc.calculate_edge_deadheads()