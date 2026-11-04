from datetime import date, datetime, timedelta
from math import floor
from pathlib import Path

import pandas as pd
import requests

import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

class PVGISApiCall:

    def __init__(
            self,
            stations: list,
            start_date: date | str,
            raw_data_file: Path,
            raw_power_file: Path,
            scaled_power_file: Path,
            ):
        """stations as provided by StationIdMatching (postprocessing.station_id_matching.Station).
        raw_data_file holds the complete PVGIS answers and tells which stations were already fetched,
        raw_power_file the PV power per station and hour as returned by PVGIS,
        scaled_power_file the PV energy per station and hour [Wh] scaled by the peak power.
        All three are appended to, so stations fetched before are kept."""
        self.stations = stations
        self.raw_data_file = Path(raw_data_file)
        self.raw_power_file = Path(raw_power_file)
        self.scaled_power_file = Path(scaled_power_file)

        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        elif isinstance(start_date, datetime):
            start_date = start_date.date()
        self.start_date = start_date
        end_date = start_date + timedelta(days=1)

        self.start_time = f"{self.start_date} 00:00:00"
        self.end_time = f"{end_date} 04:59:59"

    def main(self):
        answer_df = self.v6(self.stations)
        if answer_df.empty:
            logger.info("No new stations found, nothing to add.")
            return
        self.optimize_csv(answer_df)

    def get_existing_station_ids(self) -> set:
        if not self.raw_data_file.exists():
            return set()
        existing_df = pd.read_csv(self.raw_data_file, usecols=["station_id"])
        return set(existing_df["station_id"])

    def v6(self, stations: list, csv: bool = True) -> pd.DataFrame:
        existing_station_ids = self.get_existing_station_ids()
        # Liste für Ergebnisse initialisieren
        results = []
        # Alle Stationen durchlaufen
        for station in stations:
            if station.id in existing_station_ids:
                continue
            if station.area is None:
                logger.warning("No area for station %s, skipping PV.", station.id)
                continue
            # Koordinaten extrahieren und in Float umwandeln
            coordinates = station.coordinates
            peak_power = self.calculate_kWp(station.area)
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
                        "installation_height": 5, # Assumption is module installation above phantograph heigth, e.g. above heigth of bus roof
                        "start_time": self.start_time,
                        "end_time": self.end_time,
                        "surface_position_optimisation_mode": "Orientation & Tilt",
                        #"surface_orientation": "180",
                        #"surface_tilt": "45",
                        "frequency": "Hourly",
                        "timezone": "Europe/Berlin",
                        "peak_power": peak_power, # in kWp
                    },
                    timeout=60  # Timeout für bessere Stabilität
                )

         
                # Ergebnis als Dictionary speichern
                response.raise_for_status()

                raw_data = response.json()

                # PVGIS returns hourly production normalized per installed kWp.
                # Workaround: scale by installed capacity and convert W/Wh -> kW/kWh
                # (numerically equivalent for 1-hour timesteps).
                scaled_data = {
                    **raw_data,
                #   "power": [(p * peak_power) / 1000 for p in raw_data["power"]],
                    "power": [(p * peak_power) for p in raw_data["power"]],
                }

                results.append({
                    "station_id": station.id,
                    "peak_power": peak_power,
                    "raw_solar_data": raw_data,
                    "scaled_solar_data": scaled_data,
                })
        df = pd.DataFrame(results)
        if csv and not df.empty:
            df.to_csv(self.raw_data_file, mode="a", header=not self.raw_data_file.exists(), index=False)
        logger.info(f"\nPV call and scaling completed. {len(results)} new stations processed.")
        return df

    def calculate_kWp(self, area) -> int:
        power_per_panel = 500
        area_per_panel = 2.4

        nr_of_panels = floor(int(area) / area_per_panel)
        peak_wattage = floor((nr_of_panels * power_per_panel) / 1000)
        return peak_wattage

    def optimize_csv(self, answer_df: pd.DataFrame):
        columns = [(i + 1) * 3600 for i in range(29)]

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
            self.raw_power_file,
            mode="a",
            header=not self.raw_power_file.exists(),
            index=False,
        )

        scaled_result.to_csv(
            self.scaled_power_file,
            mode="a",
            header=not self.scaled_power_file.exists(),
            index=False,
        )
