# Imports
from lxml import etree
import sumolib
import pandas as pd
import os

class DeadheadCalculator():

    def __init__(self):
        # Read Network
        NETWORK = "best-ebus/scenario/sumo/berlin.net.xml"
        self.net = sumolib.net.readNet(NETWORK)
        # Parse Routes
        self.ROUTES = "best-ebus/scenario/ebus/files/cicero_mueller_routes_trimmed.rou.xml"
        routes_tree = etree.parse(self.ROUTES)
        self.routes_root = routes_tree.getroot()
        # Parse Stations
        ADDITIONAL = "best-ebus/scenario/ebus/files/termination_points.add.xml"
        station_tree = etree.parse(ADDITIONAL)
        self.station_root = station_tree.getroot()

    def get_termination_points(self) -> list:
        end_edges = [
            "E19.203",
            "-E10",
        ]

        for route in self.routes_root.findall("route"):
            edges = route.get("edges").split()
            end_edges.append(edges[0])  # departing edge
            end_edges.append(edges[-1])  # destination edge

        return end_edges

    def caculate_station_deadheads(self):
        print("Starting Network Calculations")
        stations = []

        for cs in self.station_root.findall("chargingStation"):
            lane = cs.attrib["lane"]
            edge = lane.rsplit("_", 1)[0]
            stations.append({
                "id": cs.attrib["id"],
                "name": cs.attrib["name"],
                "edge": edge,
                "end_pos": cs.attrib["endPos"],
                "start_pos": cs.attrib["startPos"],
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

            root = etree.Element(
            "routes",
            nsmap={
                "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            },
        )

        root.set(
            "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation",
            "http://sumo.dlr.de/xsd/routes_file.xsd",
        )

        # Vehicle type
        etree.SubElement(
            root,
            "vType",
            id="bus",
            vClass="bus",
        )

        # Routes
        for route in routes:
            etree.SubElement(
                root,
                "route",
                id=f"{route['FromStopID']}_{route['ToStopID']}",
                color="240,215,34",
                edges=route["Edges"],
            )

        # Write XML
        tree = etree.ElementTree(root)
        tree.write(
            "best-ebus/scenario/eBuS/files/deadheads_cicero_mueller.rou.xml",
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=True,
        )
        print("Written deadheads_cicero_mueller.rou.xml to disk")

if __name__ == "__main__":
    dc = DeadheadCalculator()
    dc.caculate_station_deadheads()