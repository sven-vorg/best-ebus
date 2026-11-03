# AI-generated code — 2026-11-01
"""Skript to match the stations selected in the solution to their bus stops.

Provides the desired charging stations (bus stops and depots) as a list of Station,
used first for the PV estimation (PVGISApiCall) and then to build the charging stations
(ChargingStations)."""
from dataclasses import dataclass
from lxml import etree
import pandas as pd
from pathlib import Path
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class Station:
    id: str
    name: str
    lane: str
    startPos: str
    endPos: str
    coordinates: str | None = None
    area: float | None = None
    parkingLength: str | None = None
    depot: bool = False


# Placed in this order in front of the bus stop charging stations
DEPOTS = (
    Station(
        id="cd_muellerstrasse_01",
        name="Depot Müllerstraße",
        lane="-E19_0",
        startPos="5",
        endPos="1000",
        coordinates="13.33776446744273,52.56058715781662",
        depot=True,
    ),
    Station(
        id="cd_cicerostrasse_01",
        name="Depot Cicerostraße",
        lane="E1.51_0",
        startPos="5",
        endPos="950",
        coordinates="13.303440333503405,52.492583731258065",
        depot=True,
    ),
)


class StationIdMatching:

    def __init__(
            self,
            station_root: Path,
            area_path: Path,
            solution_path: Path,
            station_id_path: Path,
            inactive_list: list | None = None,
            ):
        self.STATION_ROOT = etree.parse(station_root).getroot()
        self.AREA_LOOKUP = self.area_lookup(pd.read_csv(area_path, sep=";"))
        self.SOLUTION = solution_path
        self.station_id_mapping = self.station_id_lookup(station_id_path)
        self.inactive_list = inactive_list or []

    def station_id_lookup(self, station_id_mapping_path: str) -> dict:
        """
        Loads the station ID mapping file (station_id_mapping.txt) and
        returns its "stops" section: a dict mapping short station IDs
        (as strings, e.g. "1", "16") to their long canonical IDs
        (e.g. "agg_10045_25_11089_9_12475_23").
        """
        with open(station_id_mapping_path, "r") as file:
            data = json.load(file)
        return data["stops"]

    def area_lookup(self, area_df: pd.DataFrame):
        return area_df.set_index("chargingStation_id")["free_area"].to_dict()

    def charging_stations_from_solution(self):
        charging_locations = set()
        with open(self.SOLUTION, "r") as file:
            data = json.load(file)
            for station_decision in data["station_decisions"]:
                if station_decision["investment_period"] is not None:
                    short_id = str(station_decision["station_id"])
                    long_id = self.station_id_mapping.get(short_id)
                    if long_id is None:
                        raise KeyError(
                            f"station_id '{short_id}' not found in station_id_mapping "
                            f"(loaded from station_id_mapping.txt 'stops' section)"
                        )
                    if long_id not in self.inactive_list:
                        charging_locations.add(long_id)
        return charging_locations

    def main(self) -> list[Station]:
        """Return the depots followed by the bus stops selected in the solution."""
        charging_stop_ids = self.charging_stations_from_solution()
        logger.info("Found %s stops to create charging stations at.", len(charging_stop_ids))

        stations = [
            Station(
                id=depot.id,
                name=depot.name,
                lane=depot.lane,
                startPos=depot.startPos,
                endPos=depot.endPos,
                coordinates=depot.coordinates,
                area=self.AREA_LOOKUP.get(depot.id),
                depot=True,
            )
            for depot in DEPOTS
        ]

        for bus_stop in self.STATION_ROOT.findall("busStop"):
            if bus_stop.get("id") in charging_stop_ids:
                param = bus_stop.find("param[@key='coordinates']")
                station_id = f"cs_{bus_stop.get('id')}"
                stations.append(Station(
                    id=station_id,
                    name=f"{bus_stop.get('name')}_Charger",
                    lane=bus_stop.get("lane"),
                    startPos=bus_stop.get("startPos"),
                    endPos=bus_stop.get("endPos"),
                    coordinates=param.get("value") if param is not None else None,
                    area=self.AREA_LOOKUP.get(station_id),
                    parkingLength=bus_stop.get("parkingLength"),
                ))
        return stations


if __name__ == "__main__":
    HERE = Path(__file__).resolve().parent
    station_root = Path(HERE / "../../sumo/berlin_bus_stops.add.xml").resolve()
    area_path = Path(HERE / "../files/postprocessing_input/pv_area_estimation.csv").resolve()
    solution_path = Path(HERE / "../files/postprocessing_input/solution.json").resolve()
    station_id_path = Path(HERE / "../files/postprocessing_input/station_id_mapping.txt").resolve()
    for station in StationIdMatching(station_root, area_path, solution_path, station_id_path).main():
        print(station)
