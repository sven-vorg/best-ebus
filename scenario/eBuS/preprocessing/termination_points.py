import pandas as pd
from lxml import etree

class TerminationPoints():

    def __init__(self):
        route_tree = etree.parse("best-ebus/scenario/ebus/files/cicero_mueller_routes.rou.xml")
        self.ROUTE_ROOT = route_tree.getroot()
        self.OUTPUT_PATH = "best-ebus/scenario/ebus/files/"

    def get_final_stop_ids(self):
        # Store unique final stop IDs
        final_stop_ids = set()

        # Collect unique final stop IDs
        for route in self.ROUTE_ROOT.findall("route"):
            stops = route.findall("stop")
            if stops:
                final_stop_ids.add(stops[0].get("busStop"))
                final_stop_ids.add(stops[-1].get("busStop"))
        return final_stop_ids

    def txt_for_heuristic(self):
        df = pd.DataFrame(self.get_final_stop_ids())
        # Prepend a row containing 1
        df = pd.concat([pd.DataFrame([[1]]), df], ignore_index=True)
        df.to_csv(f"{self.OUTPUT_PATH}termination_points.txt", index=False, sep=";", header= False)

    def main(self):
        self.get_final_stop_ids()
        self.txt_for_heuristic()
    
if __name__ == "__main__":
    tp = TerminationPoints()
    tp.main()

