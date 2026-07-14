from pathlib import Path
from lxml import etree
import pandas as pd
import requests

class PVGISApiCall():

    def __init__(
            self,
            stations: str = "best-ebus/scenario/sumo/electric/e_stations.add.xml",
            ):
        self.df = self.v6(stations)

    def v6(self, stations: Path, pv: Path, csv: bool = True):
        root = etree.parse(stations).getroot()
        # Load station output
        # Liste für Ergebnisse initialisieren
        results = []
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
                    "http://photovoltaic-geographic-information-system.ec.europa.eu/api/v6/power/broadband",
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "installation_height": 4, # Assumption is module installation above phantograph heigth, e.g. above heigth of bus roof
                        "start_time": "2024-07-10 00:00:00",
                        "end_time": "2024-07-10 23:59:59",
                        "surface_position_optimisation_mode": "Orientation & Tilt",
                        "frequency": "Minutely",
                        "timezone": "Europe/Berlin",
                        "peak-power": 500,
                    },
                    timeout=10  # Timeout für bessere Stabilität
                )
                print(response.url)
                print(response.status_code)
                print(response.text)
                # Ergebnis als Dictionary speichern
                results.append({
                    "station_id": station.get("id"),
                    "solar_data": response.json() if response.status_code == 200 else None,
                })
        df = pd.DataFrame(results)
        if csv:
            df.to_csv("best-ebus/scenario/eBuS/files/pv_data.csv")
        print(f"/nVerarbeitung abgeschlossen. {len(results)} Stationen verarbeitet.")
        return df
