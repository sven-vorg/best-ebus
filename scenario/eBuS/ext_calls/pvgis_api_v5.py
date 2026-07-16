"""
PVGIS API client for solar potential analysis at e-bus charging stations.

Fetches solar data from the PVGIS API (https://re.jrc.ec.europa.eu/pvg_tools/)
for each charging station defined in a SUMO additional-file, using each
station's total charged energy as its estimated daily consumption.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import requests
from lxml import etree

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class PVGISConfig:
    """Tunable parameters for PVGIS API requests. Override as needed."""

    raddatabase: str = "PVGIS-SARAH3"
    timeout: int = 10

    # SHScalc (off-grid PV + battery) parameters
    peakpower_offgrid: float = 500
    angle: float = 90
    batterysize: float = 500
    cutoff: float = 10

    # PVcalc (grid-connected system economics) parameters
    peakpower_system: float = 5
    mountingplace: str = "free"
    loss: float = 14
    optimalinclination: int = 1
    optimalangles: int = 1
    pvprice: int = 1
    systemcost: float = 8000
    interest: float = 5
    lifetime: int = 25


class PVGISApiCall:
    """Client for querying the PVGIS API for a set of charging stations."""

    API_BASE_URL = "https://re.jrc.ec.europa.eu/api"
    API_OFFGRID_URL = f"{API_BASE_URL}/SHScalc"
    API_SYSTEM_URL = f"{API_BASE_URL}/PVcalc"
    API_HOURLY_URL = f"{API_BASE_URL}/seriescalc"

    def __init__(
        self,
        e_stations: str | Path = "best-ebus/scenario/sumo/electric/e_stations.add.xml",
        stations_df: str | Path = "best-ebus/scenario/sumo/output/electric_bus_2026-07-16-11-29-38_chargingsstations.csv",
        output_dir: str | Path = "best-ebus/scenario/eBuS/ext_data",
        config: PVGISConfig | None = None,
    ):
        self.e_stations = Path(e_stations)
        self.stations_df = Path(stations_df)
        self.output = Path(output_dir)
        self.output.mkdir(parents=True, exist_ok=True)
        self.config = config or PVGISConfig()

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _load_last_energy_per_station(self) -> pd.Series:
        """Return the last recorded totalEnergyCharged value per station."""
        df = pd.read_csv(self.stations_df, sep=";")
        logger.debug("Loaded station output columns: %s", df.columns.tolist())
        return (
            df.sort_values("step_time")
            .groupby("chargingStation_id")["chargingStation_totalEnergyCharged"]
            .last()
        )

    def _iter_station_coordinates(self):
        """Yield (station_id, latitude, longitude) for each station with coordinates."""
        root = etree.parse(str(self.e_stations)).getroot()
        for station in root.findall(".//chargingStation"):
            coordinates = station.get("coordinates")
            if not coordinates:
                continue
            lon_str, lat_str = coordinates.split(",")
            yield station.get("id"), float(lat_str.strip()), float(lon_str.strip())

    def _query_pvgis(self, url: str, params: dict[str, Any]) -> dict | None:
        """Perform a single PVGIS API request, returning parsed JSON or None on failure.

        PVGIS sometimes returns HTTP 200 with a plain-text/HTML error body
        (invalid parameter combination, point over water, rate limiting, etc.),
        so a non-error status code does not guarantee a JSON payload.
        """
        try:
            response = requests.get(url, params=params, timeout=self.config.timeout)
        except requests.RequestException as exc:
            logger.warning("PVGIS request failed (%s): %s", url, exc)
            return None

        logger.debug("Requested %s -> %s", response.url, response.status_code)

        if not response.ok:
            logger.warning(
                "PVGIS returned HTTP %s for %s: %s",
                response.status_code, response.url, response.text[:300],
            )
            return None

        try:
            return response.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            logger.warning(
                "PVGIS returned non-JSON body for %s (params=%s): %s",
                response.url, params, response.text[:300],
            )
            return None

    def _run(
        self,
        url: str,
        extra_params_fn: Callable[[str, pd.Series | None], dict[str, Any]],
        use_consumption: bool,
        save_as: str | None,
    ) -> pd.DataFrame:
        """Shared loop: query PVGIS for every station and collect results."""
        last_values = self._load_last_energy_per_station() if use_consumption else None
        results = []
        for station_id, lat, lon in self._iter_station_coordinates():
            params = {
                "lat": lat,
                "lon": lon,
                "raddatabase": self.config.raddatabase,
                "outputformat": "json",
                **extra_params_fn(station_id, last_values),
            }
            solar_data = self._query_pvgis(url, params)
            if solar_data is None:
                continue
            results.append({"station_id": station_id, "solar_data": solar_data})

        df = pd.DataFrame(results)
        if save_as:
            out_path = self.output / save_as
            df.to_csv(out_path, index=False)
            logger.info("Saved %d station results to %s", len(results), out_path)
        logger.info("Processed %d stations.", len(results))
        return df

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def v5_off_grid(self, save_as: str | None = "pv_data.csv") -> pd.DataFrame:
        """Query the SHScalc (off-grid PV + battery) endpoint for every station."""
        cfg = self.config

        def extra_params(station_id: str, last_values: pd.Series) -> dict[str, Any]:
            return {
                "userhorizon": 1,
                "peakpower": cfg.peakpower_offgrid,
                "angle": cfg.angle,
                "batterysize": cfg.batterysize,
                "cutoff": cfg.cutoff,
                "consumptionday": last_values[station_id],
            }

        return self._run(self.API_OFFGRID_URL, extra_params, use_consumption=True, save_as=save_as)

    def v5_system(self, save_as: str | None = "pv_system_data.csv") -> pd.DataFrame:
        """Query the PVcalc (grid-connected PV system economics) endpoint for every station."""
        cfg = self.config

        def extra_params(station_id: str, last_values: pd.Series | None) -> dict[str, Any]:
            return {
                "peakpower": cfg.peakpower_system,
                "mountingplace": cfg.mountingplace,
                "loss": cfg.loss,
                "optimalinclination": cfg.optimalinclination,
                "optimalangles": cfg.optimalangles,
                "pvprice": cfg.pvprice,
                "systemcost": cfg.systemcost,
                "interest": cfg.interest,
                "lifetime": cfg.lifetime,
            }

        return self._run(self.API_SYSTEM_URL, extra_params, use_consumption=False, save_as=save_as)

    def optimize_csv(self, source_csv: str | Path | None = None, power_key: str = "Power ⌁") -> pd.DataFrame:
        """Expand the nested solar_data JSON column into 24 hourly power columns.

        Matches the SHScalc (off-grid, v5_off_grid) result shape.
        """
        source = Path(source_csv) if source_csv else self.output / "pv_data.csv"
        df = pd.read_csv(source)
        df["solar_data"] = df["solar_data"].apply(ast.literal_eval)

        hour_columns = [(i + 1) * 3600 for i in range(24)]
        power_df = pd.DataFrame(
            df["solar_data"].apply(lambda x: x[power_key]).tolist(),
            columns=hour_columns,
        )

        result = pd.concat([df[["station_id"]], power_df], axis=1)
        out_path = self.output / "solar_expanded.csv"
        result.to_csv(out_path, index=False)
        logger.info("Saved expanded solar data to %s", out_path)
        return result

    @staticmethod
    def _sanitize_key(key: str) -> str:
        """Strip parentheses so keys like 'H(i)_d' become valid, readable column names."""
        return key.replace("(", "").replace(")", "")

    @classmethod
    def _flatten_pvcalc_result(cls, solar_data: dict) -> dict[str, Any]:
        """Flatten one PVcalc solar_data payload into a single wide row.

        Produces one column per (monthly variable, month) pair, e.g. 'E_m_m01'..'E_m_m12',
        plus one 'total_<variable>' column per entry in the totals block.
        """
        flat: dict[str, Any] = {}

        monthly_entries = solar_data.get("outputs", {}).get("monthly", {}).get("fixed", [])
        for entry in monthly_entries:
            month = entry.get("month")
            for key, value in entry.items():
                if key == "month":
                    continue
                flat[f"{cls._sanitize_key(key)}_m{month:02d}"] = value

        totals = solar_data.get("outputs", {}).get("totals", {}).get("fixed", {})
        for key, value in totals.items():
            flat[f"total_{cls._sanitize_key(key)}"] = value

        return flat

    def optimize_system_csv(self, source_csv: str | Path | None = None) -> pd.DataFrame:
        """Expand the nested solar_data JSON column from a PVcalc result into a wide table.

        Matches the PVcalc (grid-connected system, v5_system) result shape: 12 months
        of E_d/E_m/H(i)_d/H(i)_m/SD_m plus an annual totals block (E_y, LCOE_pv, etc.).
        """
        source = Path(source_csv) if source_csv else self.output / "pv_system_data.csv"
        df = pd.read_csv(source)
        df["solar_data"] = df["solar_data"].apply(ast.literal_eval)

        flat_df = pd.DataFrame(df["solar_data"].apply(self._flatten_pvcalc_result).tolist())
        result = pd.concat([df[["station_id"]], flat_df], axis=1)

        out_path = self.output / "pv_system_expanded.csv"
        result.to_csv(out_path, index=False)
        logger.info("Saved expanded PV system data to %s", out_path)
        return result


if __name__ == "__main__":
    pac = PVGISApiCall()
    #pac.v5_system()
    pac.optimize_system_csv("/home/sven/Dokumente/Masterarbeit/Repos/best-ebus/scenario/eBuS/ext_data/pv_system_data.csv")