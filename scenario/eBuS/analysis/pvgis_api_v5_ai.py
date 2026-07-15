# AI-generated on 2026-07-15

from pathlib import Path
import ast

import pandas as pd
import requests
from lxml import etree


class PVGISApiCall:
    API_URL = "https://re.jrc.ec.europa.eu/api/seriescalc"

    def __init__(
        self,
        stations_xml: str | Path,
        output_dir: str | Path,
    ):
        self.stations_xml = Path(stations_xml)
        self.output_dir = Path(output_dir)

    def run(self, save_csv: bool = False) -> pd.DataFrame:
        stations = self._load_station_locations()

        results = []

        for x, station in enumerate(stations):
            print(f"Still going... {x+1}/{len(stations)}")
            solar = self._request_pvgis(
                latitude=station["lat"],
                longitude=station["lon"],
            )

            results.append(
                {
                    "station_id": station["id"],
                    "solar_data": solar,
                }
            )
        df = pd.DataFrame(results)

        if save_csv:
            outfile = self.output_dir / "pv_data.csv"
            df.to_csv(outfile, index=False)

        print(f"\nProcessed {len(df)} stations.")
        return df

    def _load_station_locations(self) -> list[dict]:
        root = etree.parse(self.stations_xml).getroot()

        stations = []

        for station in root.findall(".//chargingStation"):
            coordinates = station.get("coordinates")

            if not coordinates:
                continue

            lon, lat = map(float, coordinates.split(","))

            stations.append(
                {
                    "id": station.get("id"),
                    "lat": lat,
                    "lon": lon,
                }
            )

        return stations

    def _request_pvgis(
        self,
        latitude: float,
        longitude: float,
    ) -> dict | None:

        params = {
            "lat": latitude,
            "lon": longitude,
            "startyear": 2022,
            "endyear": 2023,
            "pvcalculation": 1,
            "peakpower": 500,
            "loss": 14,
            "angle": 90,
            "outputformat": "csv",
        }

        try:
            response = requests.get(
                self.API_URL,
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            return response

        except requests.RequestException as exc:
            print(exc)

            if exc.response is not None:
                print(exc.response.text)

            return None

if __name__ == "__main__":
    api = PVGISApiCall(
        stations_xml="best-ebus/scenario/sumo/electric/e_stations.add.xml",
        output_dir="best-ebus/scenario/eBuS/files",
    )

    solar_df = api.run(save_csv=True)