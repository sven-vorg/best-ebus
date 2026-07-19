#!/usr/bin/env python
__author__ = "Sven Vorgheim"
__license__ = "GPL v2 or later (In accoardance to SUMO)"
__maintainer__ = "Sven Vorgheim"
__email__ = "sven.vorgheim@fu-berlin.de"
__status__ = "Prototype"
__date__ = "02.07.2026"

# Imports
import pandas as pd
import numpy as np

from filter_lines import FilterLines
from cut_lines import CutLines
from deadhead_calculator import DeadheadCalculator
from termination_points import TerminationPoints

class HeuristicPreprocessing:
    def __init__(self):
        pass

    def main(self):
        fl = FilterLines()
        fl.main()

        tp = TerminationPoints()
        tp.main()

        #cl = CutLines()
        #cl.trim_routes()

        dc = DeadheadCalculator()
        dc.calculate_edge_deadheads()

if __name__ == "__main__":
    hp = HeuristicPreprocessing()
    hp.main()