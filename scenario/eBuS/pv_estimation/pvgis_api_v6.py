from math import floor
from pathlib import Path

from lxml import etree
import pandas as pd
import requests

class PVGISApiCall:

    def __init__(
            self,
            stations_path: Path ,
            output_path: Path
            ):
        self.stations_path = stations_path
        self.output_path = output_path

    def main(self):
        answer_df = self.v6(self.stations_path)
        self.optimize_csv(answer_df)


    def v6(self, stations: Path, csv: bool = True) -> pd.DataFrame:
        root = etree.parse(stations).getroot()
        # Load station output
        # Liste für Ergebnisse initialisieren
        results = []
        # Alle chargingStation Elemente durchlaufen
        for station in root.findall(".//chargingStation"):
            # Koordinaten extrahieren und in Float umwandeln
            coordinates = station.get("coordinates")
            peak_power = self.calculate_kWp(station.get("area"))
            print(peak_power)
            if coordinates:
                lon_str, lat_str = coordinates.split(",")
                latitude = float(lat_str.strip())
                longitude = float(lon_str.strip())

                # API-Request an Photovoltaic GIS
                response = requests.get(
                    "http://photovoltaic-geographic-information-system.ec.europa.eu/api/v6/power/broadband",
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "installation_height": 4, # Assumption is module installation above phantograph heigth, e.g. above heigth of bus roof
                        "start_time": "2024-06-22 00:00:00",
                        "end_time": "2024-06-22 23:59:59",
                        "surface_position_optimisation_mode": "Orientation & Tilt",
                        #"surface_orientation": "180",
                        #"surface_tilt": "45",
                        "frequency": "Hourly",
                        "timezone": "Europe/Berlin",
                        "peak_power": peak_power, # in kWp
                    },
                    timeout=60  # Timeout für bessere Stabilität
                )
                print(response.url)
                #print(response.status_code)
         
                # Ergebnis als Dictionary speichern
                response.raise_for_status()

                raw_data = response.json()
                print(raw_data)

                # PVGIS returns hourly production normalized per installed kWp.
                # Workaround: scale by installed capacity and convert W/Wh -> kW/kWh
                # (numerically equivalent for 1-hour timesteps).
                scaled_data = {
                    **raw_data,
                #   "power": [(p * peak_power) / 1000 for p in raw_data["power"]],
                    "power": [(p * peak_power) for p in raw_data["power"]],
                }

                results.append({
                    "station_id": station.get("id"),
                    "peak_power": peak_power,
                    "raw_solar_data": raw_data,
                    "scaled_solar_data": scaled_data,
                })
        df = pd.DataFrame(results)
        if csv:
            df.to_csv(f"{self.output_path}/raw_pv_data.csv", index=False)
        print(f"/nVerarbeitung abgeschlossen. {len(results)} Stationen verarbeitet.")
        return df

    def calculate_kWp(self, area) -> int:
        power_per_panel = 500
        area_per_panel = 2.4

        nr_of_panels = floor(int(area) / area_per_panel)
        peak_wattage = floor((nr_of_panels * power_per_panel) / 1000)
        return peak_wattage

    def optimize_csv(self, answer_df: pd.DataFrame):
        columns = [(i + 1) * 3600 for i in range(24)]

        raw_power_df = pd.DataFrame(
            answer_df["raw_solar_data"].apply(lambda x: x["power"]).tolist(),
            columns=columns,
        )

        scaled_power_df = pd.DataFrame(
            answer_df["scaled_solar_data"].apply(lambda x: x["power"]).tolist(),
            columns=columns,
        )

        raw_result = pd.concat(
            [answer_df[["station_id", "peak_power"]], raw_power_df],
            axis=1,
        )

        scaled_result = pd.concat(
            [answer_df[["station_id", "peak_power"]], scaled_power_df],
            axis=1,
        )

        raw_result.to_csv(
            f"{self.output_path}/solar_power_v6_raw.csv",
            index=False,
        )

        scaled_result.to_csv(
            f"{self.output_path}/solar_power_v6_scaled.csv",
            index=False,
        )

if __name__ == "__main__":
    stations_path: Path = Path("best-ebus/scenario/sumo/electric/e_stations.add.xml")
    output_path: Path = Path("best-ebus/scenario/eBuS/pv_estimation/data")
    PVGISApiCall(stations_path = stations_path, output_path = output_path).main()
