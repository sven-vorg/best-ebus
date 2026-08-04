from pathlib import Path
from lxml import etree
import pandas as pd
import requests
import ast
from math import floor

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
                print(response.text)
                # Ergebnis als Dictionary speichern
                results.append({
                    "station_id": station.get("id"),
                    "solar_data": response.text,
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
        # Convert the string into a Python dictionary
        answer_df["solar_data"] = answer_df["solar_data"].apply(ast.literal_eval)

        # Extract the power list
        columns = [(i + 1) * 3600 for i in range(24)]

        power_df = pd.DataFrame(
            answer_df["solar_data"].apply(lambda x: x["power"]).tolist(),
            columns=columns
        )

        # Combine with station_id (or keep other columns if desired)
        result = pd.concat([answer_df[["station_id"]], power_df], axis=1)

        print(result.head())

        # Save
        result.to_csv(f"{self.output_path}/solar_power_v6.csv", index=False)


@staticmethod
def manual_csv_optimization():
    df = pd.read_csv("best-ebus/scenario/eBuS/ext_data/pv_data.csv")
    # Convert the string into a Python dictionary
    df["solar_data"] = df["solar_data"].apply(ast.literal_eval)

    # Extract the power list
    columns = [(i + 1) * 3600 for i in range(24)]

    power_df = pd.DataFrame(
        df["solar_data"].apply(lambda x: x["power"]).tolist(),
        columns=columns
    )

    # Combine with station_id (or keep other columns if desired)
    result = pd.concat([df[["station_id"]], power_df], axis=1)

    print(result.head())

    # Save
    result.to_csv("best-ebus/scenario/eBuS/ext_data/solar_power_v6.csv", index=False)


if __name__ == "__main__":
    PVGISApiCall(stations_path = "best-ebus/scenario/sumo/electric/e_stations.add.xml", output_path = "best-ebus/scenario/eBuS/pv_estimation").main()
