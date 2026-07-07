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

                for dest in selected:
                    to_edge = self.net.getEdge(dest["edge"])
                    edges, cost = self.net.getFastestPath(from_edge, to_edge)
                    
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

    def main(self):

        net = sumolib.net.readNet(self.NETWORK)

        end_edges = self.get_termination_points()

        # Remove duplicates while preserving order
        end_edges = list(dict.fromkeys(end_edges))

        all_routes = []

        # ------------------------------------------------------------------
        # Create travel-time matrices
        # ------------------------------------------------------------------
        for skip_idx, output_file in [
            (0, "best-ebus/scenario/eBuS/files/deadhead_time_cicerostrasse.txt"),
            (1, "best-ebus/scenario/eBuS/files/deadhead_time_muellerstrasse.txt"),
        ]:

            # Remove one depot for this matrix
            selected = end_edges[:skip_idx] + end_edges[skip_idx + 1:]

            time_rows = []

            for from_edge in selected:
                for to_edge in selected:

                    path, cost = net.getFastestPath(
                        net.getEdge(from_edge),
                        net.getEdge(to_edge),
                        maxCost=10000,
                    )

                    if path is None:
                        continue

                    # Save travel time
                    time_rows.append({
                        "FromEdgeID": from_edge,
                        "ToEdgeID": to_edge,
                        "RunTime": round(cost),
                    })

                    # Save complete path for XML generation
                    all_routes.append({
                        "FromEdgeID": from_edge,
                        "ToEdgeID": to_edge,
                        "Edges": " ".join(edge.getID() for edge in path),
                    })

            pd.DataFrame(time_rows).to_csv(
                output_file,
                sep=";",
                index=False,
            )

        # ------------------------------------------------------------------
        # Generate SUMO route file containing all deadhead paths
        # ------------------------------------------------------------------
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

        etree.SubElement(
            root,
            "vType",
            id="bus",
            vClass="bus",
        )


        for route in all_routes:
            etree.SubElement(
                root,
                "route",
                id=f"{route['FromEdgeID']}_{route['ToEdgeID']}",
                color="240,215,34",
                edges=route["Edges"],
            )

        etree.ElementTree(root).write(
            "best-ebus/scenario/eBuS/files/deadhead_routes_cicero_mueller.rou.xml",
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=True,
        )

if __name__ == "__main__":
    dc = DeadheadCalculator()
    dc.caculate_station_deadheads()