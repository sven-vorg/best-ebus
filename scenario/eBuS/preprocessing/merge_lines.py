# Imports
from lxml import etree
import os

class MergeLines():

    def __init__(self):
        self.DEADHEADS = "best-ebus/scenario/ebus/files/deadheads_cicero_mueller.rou.xml"
        self.ROUTES = "best-ebus/scenario/ebus/files/cicero_mueller_routes_trimmed.rou.xml"

    
    def main(self):
        files = [self.ROUTES,self.DEADHEADS]
        root = etree.Element("routes")

        for file in files:
            tree = etree.parse(file)
            for route in tree.getroot():
                root.append(route)

        etree.ElementTree(root).write(
            "./best-ebus/scenario/eBuS/files/merged_deadheads_routes.rou.xml",
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=True,
        )

if __name__ == "__main__":
    ml = MergeLines()
    ml.main()