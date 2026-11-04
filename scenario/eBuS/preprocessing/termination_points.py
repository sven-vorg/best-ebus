import pandas as pd
from lxml import etree
from pathlib import Path

class TerminationPoints():

    def __init__(
            self,
            routes_root,
            depots: tuple,
            output_file: Path
        ):
        self.ROUTE_ROOT = routes_root
        self.depots = depots
        # read by the DeadheadCalculator
        self.output_file = output_file

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
        df.to_csv(self.output_file, index=False, sep=";", header= False)

    def main(self):
        self.get_final_stop_ids()
        self.txt_for_heuristic()
    
if __name__ == "__main__":

    HERE = Path(__file__).resolve().parent
    
    routes: Path = (HERE / "../files/cicero_mueller_routes.rou.xml").resolve()
    depots: tuple = ("cicerostrasse", "muellerstrasse")
    output_file: Path = (HERE / "../files/postprocessing_input/termination_points.txt").resolve()
    routes_root = etree.parse(routes).getroot()
    tp = TerminationPoints(routes_root, depots, output_file)
    tp.main()

