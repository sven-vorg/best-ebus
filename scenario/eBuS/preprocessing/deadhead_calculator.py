# Imports
import lxml.etree as etree
import sumolib
import pandas as pd
from pathlib import Path

class DeadheadCalculator():

    def __init__(
            self, 
            network: Path, 
            stations: Path, 
            routes: Path,
            termination_points: Path,
            depots: tuple,
            output: Path,
        ):
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
            edge_ids = [edge.getID() for edge in edges]
            time_rows.append({
                    "FromStopID": from_stop,
                    "ToStopID": to_stop,
                    "RunTime": round(cost),
                })
            routes.append({
                    "FromStopID": from_stop,
                    "ToStopID": to_stop,
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
    
    HERE = Path(__file__).resolve().parent

    network: Path = (HERE / "../../sumo/berlin.net.xml").resolve()
    stations: Path = (HERE / "../../sumo/berlin_bus_stops.add.xml").resolve()
    routes: Path = (HERE / "../../sumo/berlin_bus.rou.xml").resolve()
    termination_points: Path = (HERE / "../files/termination_points.txt").resolve()
    depots: tuple = ("cicerostrasse", "muellerstrasse")
    output: Path = (HERE / "../files").resolve()
    dc = DeadheadCalculator(network, stations, routes, termination_points, depots, output)
    dc.calculate_edge_deadheads()