# AI-generated code — 2026-10-30

import pandas as pd

SECONDS_PER_HOUR = 3600


class PVGenerator:
    """Provides the PV energy generated at each charging station location.

    Reads a "<date>_solar_power_v6_scaled.csv" file as written by the PVGIS call:
    one row per station with its peak_power (kW) and one column per hour holding the
    energy generated in that hour (Wh). The column header is the end of the hour in
    seconds, so column "3600" covers [0 s, 3600 s). The profile repeats cyclically."""

    def __init__(self, csv_path, pv_factor: float = 1.0) -> None:
        if pv_factor < 0:
            raise ValueError("pv_factor must not be negative.")
        self.pv_factor = pv_factor
        df = pd.read_csv(csv_path).set_index("station_id")
        df.index = df.index.astype(str)
        self.peak_power = df["peak_power"].astype(float).to_dict()  # kW
        hour_columns = sorted((c for c in df.columns if c != "peak_power"), key=int)
        self.hourly = {
            station_id: row.astype(float).tolist()  # Wh per hour
            for station_id, row in df[hour_columns].iterrows()
        }

    @property
    def duration_sec(self) -> float:
        """Length of the profile in seconds."""
        return max((len(values) for values in self.hourly.values()), default=0) * SECONDS_PER_HOUR

    def get_peak_power(self, station_id: str) -> float:
        """PV peak power of a station in kW."""
        return self.peak_power[station_id]

    def get_energy(self, station_id: str, begin_sec: float, duration_sec: float) -> float:
        """PV energy (Wh, scaled by pv_factor) generated at a station within
        [begin_sec, begin_sec + duration_sec]. Intervals crossing an hour boundary
        are split, so any step length works."""
        if station_id not in self.hourly:
            raise KeyError(f"No PV data for charging station '{station_id}'.")
        hourly = self.hourly[station_id]
        end = begin_sec + duration_sec
        t = max(begin_sec, 0.0)
        energy = 0.0
        while t < end:
            hour = int(t // SECONDS_PER_HOUR)
            until = min(end, (hour + 1) * SECONDS_PER_HOUR)
            energy += hourly[hour % len(hourly)] * (until - t) / SECONDS_PER_HOUR
            t = until
        return energy * self.pv_factor
