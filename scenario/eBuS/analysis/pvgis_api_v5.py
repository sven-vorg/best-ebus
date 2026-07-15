from pathlib import Path
from lxml import etree
import pandas as pd
import requests
import ast

class PVGISApiCall():

    def __init__(
            self,
            stations: str = "best-ebus/scenario/sumo/electric/e_stations.add.xml",
            stations_df: str = "best-ebus/scenario/sumo/output/electric_bus_2026-07-15-10-18-08_chargingsstations.csv"
            ):

        self.df = self.v5_off_grid(stations, stations_df)
        self.output = "best-ebus/scenario/eBuS/files"
        pass

    def v5_off_grid(self, stations: Path, stations_df, csv: bool = False):
        root = etree.parse(stations).getroot()
        # Load station output
        # Liste für Ergebnisse initialisieren
        results = []
        # OutputStations
        station_df = pd.read_csv(stations_df, sep=";")
        print(station_df.columns.tolist())
        last_values = (
            station_df.sort_values("step_time")
            .groupby("chargingStation_id")["chargingStation_totalEnergyCharged"]
            .last()
            )
        # Alle chargingStation Elemente durchlaufen
        for station in root.findall(".//chargingStation"):
            # Koordinaten extrahieren und in Float umwandeln
            coordinates = station.get("coordinates")
            if coordinates:
                lon_str, lat_str = coordinates.split(",")
                latitude = float(lat_str.strip())
                longitude = float(lon_str.strip())

                # API-Request an Photovoltaic GIS
                response = requests.get(
                    "https://re.jrc.ec.europa.eu/api/SHScalc?",
                    params={
                        "lat": latitude,
                        "lon": longitude,
                        "userhorizon": 1,
                        "raddatabase": "PVGIS-SARAH3",
                        "peakpower": 500,
                        "angle": "90",
                        "batterysize": 500,
                        "cutoff": 10,
                        "consumptionday": f"{last_values[station.get("id")]}",
                    },
                    timeout=10  # Timeout für bessere Stabilität
                )
                print(response.url)
                print(response.status_code)
                print(response.text)
                # Ergebnis als Dictionary speichern
                results.append({
                    "station_id": station.get("id"),
                    "solar_data": response.json(),
                })
        df = pd.DataFrame(results)
        if csv:
            df.to_csv("best-ebus/scenario/eBuS/files/pv_data.csv")
        print(f"/nVerarbeitung abgeschlossen. {len(results)} Stationen verarbeitet.")
        return df

    def optimize_csv(self):
        df = pd.read_csv("best-ebus/scenario/eBuS/files/pv_data.csv")
        # Convert the string into a Python dictionary
        df["solar_data"] = df["solar_data"].apply(ast.literal_eval)

        # Extract the power list
        columns = [(i + 1) * 3600 for i in range(24)]

        power_df = pd.DataFrame(
            df["solar_data"].apply(lambda x: x["Power ⌁"]).tolist(),
            columns=columns
        )

        # Combine with station_id (or keep other columns if desired)
        result = pd.concat([df[["station_id"]], power_df], axis=1)

        print(result.head())

        # Save
        result.to_csv(f"{self.output}/solar_expanded.csv", index=False)

if __name__ == "__main__":
    pac = PVGISApiCall()
    #pac.optimize_csv()