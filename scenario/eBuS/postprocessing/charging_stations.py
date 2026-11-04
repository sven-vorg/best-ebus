# AI-generated code — 2026-11-01
"""Skript to create the charging stations provided by StationIdMatching.

Each charging station can carry a stationary energy storage and a PV energy source,
which are simulated inside SUMO (MSStationaryEnergyStorage / MSEnergySourcePV).
Both are configured through <param> children of the <chargingStation>:
    ses.maximumStorageCapacity  capacity [Wh], enables the storage
    ses.stateOfChargeStartUp    initial state of charge as fraction of capacity [0..1]
    ses.drawTarget              passive grid draw until this fraction of capacity [0..1]
    ses.drawPower               passive grid draw power [W]
    pv.energyValueList          space separated PV energy per time frame [Wh]
    pv.timeFrame                length of one time frame [s], value k covers (k * timeFrame, (k + 1) * timeFrame]
"""
import datetime
import logging
from pathlib import Path

import pandas as pd
from lxml import etree

from .station_id_matching import Station

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def format_value(value: float) -> str:
    """Write numbers without float noise, e.g. 67612.7717175 -> "67612.772", 0.0 -> "0"."""
    return f"{value:.3f}".rstrip("0").rstrip(".")


class ChargingStations:

    def __init__(
            self,
            stations: list[Station],
            output_file: Path,
            power: int = 150000,
            total_power_factor: float = 2,
            allow_depot_charging: bool = True,
            depot_total_power_factor: float = 2,
            ses_maximumStorageCapacity: float | None = None,
            ses_factor: float | None = None,
            ses_stateOfChargeStartUp: float = 0.0,
            ses_drawTarget: float = 0.0,
            ses_drawPower: float = 0.0,
            pv_csv_path: Path | None = None,
            pv_factor: float = 1.0,
            pv_energyValueList: list[float] | None = None,
            pv_timeFrame: int = 3600,
            ):
        """stations as provided by StationIdMatching, written to output_file (e_stations.add.xml).
        ses_maximumStorageCapacity sets the same storage capacity (Wh) for every station.
        Alternatively ses_factor sizes each station's storage as ses_factor * its PV peak power (kWp),
        giving the capacity in kWh. ses_maximumStorageCapacity takes precedence.
        Without both no storage is created, unless the station has PV data, then a storage
        of capacity 0 is created so the PV energy can be used directly.
        ses_drawPower is in W.
        pv_csv_path is a "<date>_solar_power_v6_scaled.csv" as written by PVGISApiCall,
        holding the peak power and the PV energy per hour (Wh) of every station.
        pv_factor scales those PV values.
        pv_energyValueList, if given, is used for every station instead of the CSV values,
        e.g. for testing."""
        self.stations = stations
        self.OUTPUT_FILE = output_file
        self.POWER = power
        self.TOTAL_POWER_FACTOR = total_power_factor
        self.ALLOW_DEPOT_CHARGING = allow_depot_charging
        self.DEPOT_TOTAL_POWER_FACTOR = depot_total_power_factor

        if pv_factor < 0:
            raise ValueError("pv_factor must not be negative.")
        if pv_timeFrame <= 0:
            raise ValueError("pv_timeFrame must be positive.")
        self.ses_maximumStorageCapacity = ses_maximumStorageCapacity
        self.ses_factor = ses_factor
        self.ses_stateOfChargeStartUp = ses_stateOfChargeStartUp
        self.ses_drawTarget = ses_drawTarget
        self.ses_drawPower = ses_drawPower
        self.pv_factor = pv_factor
        self.pv_energyValueList = pv_energyValueList
        self.pv_timeFrame = pv_timeFrame
        self.peak_power, self.pv_data = self.pv_lookup(pv_csv_path)

    def pv_lookup(self, pv_csv_path: Path | None) -> tuple[dict[str, float], dict[str, list[float]]]:
        """Read the scaled PV CSV and return ({station_id: peak_power (kWp)}, {station_id: [Wh per hour]}).
        Returns empty dicts if no CSV is given."""
        if pv_csv_path is None:
            return {}, {}
        if not Path(pv_csv_path).exists():
            raise FileNotFoundError(f"PV file {pv_csv_path} not found, run PVGISApiCall first.")
        df = pd.read_csv(pv_csv_path).set_index("station_id")
        df.index = df.index.astype(str)
        peak_power = df["peak_power"].astype(float).to_dict()
        hour_columns = sorted((c for c in df.columns if c != "peak_power"), key=int)
        pv_data = {
            station_id: row.astype(float).tolist()
            for station_id, row in df[hour_columns].iterrows()
        }
        return peak_power, pv_data

    def storage_capacity(self, station_id: str) -> float | None:
        """Storage capacity (Wh) of a station or None if it has no storage."""
        if self.ses_maximumStorageCapacity is not None:
            return self.ses_maximumStorageCapacity
        if self.ses_factor is not None:
            if station_id not in self.peak_power:
                logger.warning("No peak power for %s, cannot size its storage by ses_factor.", station_id)
                return None
            return self.peak_power[station_id] * self.ses_factor * 1000
        return None

    def pv_values(self, station_id: str) -> list[float] | None:
        """PV energy per time frame (Wh) of a station or None if it has no PV data."""
        if self.pv_energyValueList is not None:
            return self.pv_energyValueList
        if station_id not in self.pv_data:
            return None
        return [value * self.pv_factor for value in self.pv_data[station_id]]

    def add_energy_params(self, charging_station: etree._Element):
        """Add the ses.* and pv.* params to a charging station element."""
        station_id = charging_station.get("id")
        capacity = self.storage_capacity(station_id)
        pv_values = self.pv_values(station_id)
        if capacity is None and pv_values is None:
            return
        if capacity is None:
            # SUMO ignores a PV source without storage, capacity 0 uses the PV energy directly
            capacity = 0.0
        params = {
            "ses.maximumStorageCapacity": format_value(capacity),
            "ses.stateOfChargeStartUp": format_value(self.ses_stateOfChargeStartUp),
            "ses.drawTarget": format_value(self.ses_drawTarget),
            "ses.drawPower": format_value(self.ses_drawPower),
        }
        if pv_values is not None:
            params["pv.energyValueList"] = " ".join(format_value(value) for value in pv_values)
            params["pv.timeFrame"] = str(self.pv_timeFrame)
        for key, value in params.items():
            etree.SubElement(charging_station, "param", key=key, value=value)

    def charging_station_element(self, station: Station) -> etree._Element:
        """Create a <chargingStation> with its energy params, attributes set to None are left out."""
        if station.depot:
            power = 150000 if self.ALLOW_DEPOT_CHARGING else 0
            total_power = power * self.DEPOT_TOTAL_POWER_FACTOR
            charge_delay = None
        else:
            power = self.POWER
            total_power = self.POWER * self.TOTAL_POWER_FACTOR
            charge_delay = "21"
        attributes = {
            "id": station.id,
            "name": station.name,
            "lane": station.lane,
            "startPos": station.startPos,
            "endPos": station.endPos,
            "power": power,
            "totalPower": total_power,
            "efficiency": "0.95",
            "chargeInTransit": "false",
            "friendlyPos": "true",
            "parkingLength": station.parkingLength,
            "chargeDelay": charge_delay,
            "coordinates": station.coordinates,
            "area": station.area,
        }
        charging_station = etree.Element(
            "chargingStation",
            {key: str(value) for key, value in attributes.items() if value is not None},
        )
        self.add_energy_params(charging_station)
        return charging_station

    def main(self):

        # Create the root element
        additional = etree.Element(
            "additional",
            nsmap={"xsi": "http://www.w3.org/2001/XMLSchema-instance"}
            )
        additional.append(
            etree.Comment(
                f"Generated using {type(self).__name__} Skript on {str(datetime.datetime.now())}")
                )

        for station in self.stations:
            additional.append(self.charging_station_element(station))

        with_storage = len(additional.findall("chargingStation/param[@key='ses.maximumStorageCapacity']"))
        with_pv = len(additional.findall("chargingStation/param[@key='pv.energyValueList']"))
        logger.info("Created %s charging stations, %s with storage, %s with PV.",
                    len(self.stations), with_storage, with_pv)

        # Write the XML to a file
        tree = etree.ElementTree(additional)
        tree.write(
            str(self.OUTPUT_FILE),
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
        )
