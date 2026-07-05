# Imports
from lxml import etree
import sumolib
import pandas as pd

class DeadheadCalculator():

    def __init__(self):
        self.NETWORK = "best-ebus/scenario/sumo/berlin.net.xml"
        self.ROUTES = "best-ebus/scenario/ebus/files/cicero_mueller_routes.rou.xml"
        tree = etree.parse(self.ROUTES)
        self.root = tree.getroot()

    def get_termination_points(self) -> list:
        end_edges = [
            "E19.203",
            "-E10",
        ]

        for route in self.root.findall("route"):
            edges = route.get("edges").split()
            end_edges.append(edges[0])  # departing edge
            end_edges.append(edges[-1])  # destination edge

        return end_edges
    
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
    dc.main()