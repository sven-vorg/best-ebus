import pandas as pd
from lxml import etree
from pathlib import Path

class TerminationPoints():

    def __init__(
            self, 
            routes: str = "best-ebus/scenario/eBuS/files/cicero_mueller_routes.rou.xml",
            depots: tuple = ("cicerostrasse", "muellerstrasse"),
            output: str = "best-ebus/scenario/eBuS/files"):
        self.ROUTE_ROOT = etree.parse(Path(routes)).getroot()
        self.depots = depots
        self.OUTPUT_PATH = Path(output)

    def get_final_stop_ids(self):
        # Store unique final stop IDs
        final_stop_ids = set()

        # Collect unique final stop IDs
        for route in self.ROUTE_ROOT.findall("route"):
            stops = route.findall("stop")
            if stops:
                final_stop_ids.add(stops[0].get("busStop"))
                final_stop_ids.add(stops[-1].get("busStop"))
        for depot in self.depots:
            final_stop_ids.add(f"bs_{depot}")
        return final_stop_ids

    def txt_for_heuristic(self):
        df = pd.DataFrame(self.get_final_stop_ids())
        df.to_csv(f"{self.OUTPUT_PATH}/termination_points.txt", index=False, sep=";", header= False)

    def main(self):
        self.get_final_stop_ids()
        self.txt_for_heuristic()
    
if __name__ == "__main__":
    tp = TerminationPoints()
    tp.main()

