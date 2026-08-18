from pathlib import Path

import pandas as pd

from energy_storage_system.charging_station import ChargingStation

MINUTES_PER_HOUR = 60
TOTAL_MINUTES = 1440  # 1 day


def parse_pv_data(csv_path):
    df = pd.read_csv(csv_path)
    df = df.set_index('station_id')
    df = df.drop(columns=["peak_power"])
    df = df[sorted(df.columns, key=lambda c: int(c))]
    return {station_id: row.astype(float).tolist() for station_id, row in df.iterrows()}

class EnergyStorageSystem:
    def __init__(self, charging_stations, ess_capacity, pv_csv_path, output_path=None, start_soc=0.0):
        self.charging_stations = charging_stations
        self.ess_capacity = ess_capacity
        self.pv_csv_path = pv_csv_path
        self.output_path = output_path
        self.start_soc = start_soc
        self.pv_data = None
        self.ess_df = None

    def main(self):
        """Run the full ESS pipeline: load PV data, derive load/PV profiles,
        simulate the battery, and write the result to XML if an output_path was given."""
        self.pv_data = parse_pv_data(self.pv_csv_path)
        self.energy_per_timestep(self.charging_stations)
        self.ess_df = self.calculate_ess(self.charging_stations, self.ess_capacity, self.start_soc)
        if self.output_path is not None:
            self.write_xml(self.output_path)
        return self.ess_df

    def energy_per_timestep(self, charging_stations):
        for station in charging_stations:
            for ev in station.charging_events:
                duration_min = (ev.end_sec - ev.begin_sec) / 60
                ev.energy_per_minute = ev.total_energy / duration_min if duration_min > 0 else 0.0
        return charging_stations

    def build_load_profile(self, charging_station, total_minutes=TOTAL_MINUTES):
        load = [0.0] * total_minutes
        for ev in charging_station.charging_events:
            start_sec = max(ev.begin_sec, 0)
            end_sec = min(ev.end_sec, total_minutes * 60)
            if end_sec <= start_sec:
                continue
            start_min = int(start_sec // 60)
            end_min = int(end_sec // 60)
            for t in range(start_min, min(end_min + 1, total_minutes)):
                minute_start, minute_end = t * 60, t * 60 + 60
                overlap = min(end_sec, minute_end) - max(start_sec, minute_start)
                if overlap <= 0:
                    continue
                load[t] += ev.energy_per_minute * (overlap / 60)
        return load

    def get_pv_generated(self, charging_station, hour):
        hourly_values = self.pv_data[charging_station.id]
        return hourly_values[hour % len(hourly_values)]

    def build_pv_profile(self, charging_station, total_minutes=TOTAL_MINUTES):
        pv = [0.0] * total_minutes
        for t in range(total_minutes):
            hour = t // MINUTES_PER_HOUR
            pv_hourly = self.get_pv_generated(charging_station, hour)
            pv[t] = pv_hourly / MINUTES_PER_HOUR
        return pv

    def calculate_ess(self, charging_stations, ess_capacity, start_soc=0.0, total_minutes=TOTAL_MINUTES):
        rows = []
        for station in charging_stations:
            load = self.build_load_profile(station, total_minutes)
            pv = self.build_pv_profile(station, total_minutes)
            soc = start_soc
            for t in range(total_minutes):
                net = pv[t] - load[t]
                grid_draw = 0.0
                curtailed_pv = 0.0
                if net >= 0:
                    new_soc = soc + net
                    if new_soc > ess_capacity:
                        curtailed_pv = new_soc - ess_capacity
                        soc = ess_capacity
                    else:
                        soc = new_soc
                else:
                    deficit = -net
                    new_soc = soc - deficit
                    if new_soc < 0:
                        grid_draw = -new_soc
                        soc = 0.0
                    else:
                        soc = new_soc
                rows.append({
                    "station_id": station.id,
                    "timestep_min": t,
                    "pv_generated": pv[t],
                    "energy_charged": load[t],
                    "ess_soc": soc,
                    "grid_energy_drawn": grid_draw,
                    "pv_curtailed": curtailed_pv,
                })
        return pd.DataFrame(rows)

    def write_xml(self, output_path):
        """Write ess_df out as a SUMO-style timestep/station XML file."""
        df = self.ess_df.sort_values(["timestep_min", "station_id"])

        with open(Path(output_path), "w", encoding="utf8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write("<ess-export>\n")

            for timestep_min, group in df.groupby("timestep_min"):
                f.write(f'    <timestep time="{timestep_min * 60:.2f}">\n')

                for row in group.itertuples():
                    f.write(
                        f'        <station '
                        f'id="{row.station_id}" '
                        f'pvGenerated="{row.pv_generated:.6f}" '
                        f'energyCharged="{row.energy_charged:.6f}" '
                        f'essSoc="{row.ess_soc:.6f}" '
                        f'gridEnergyDrawn="{row.grid_energy_drawn:.6f}" '
                        f'pvCurtailed="{row.pv_curtailed:.6f}"/>\n'
                    )

                f.write("    </timestep>\n")

            f.write("</ess-export>\n")


if __name__ == "__main__":
    charging_stations = ChargingStation.from_xml(
        r"C:\Users\svens\Documents\FU-Berlin\BeST-eBuS\best-ebus\scenario\sumo\output\electric_bus_2026-08-17-19-10-35_chargingstations.xml"
    )

    EnergyStorageSystem(
        charging_stations=charging_stations,
        ess_capacity=500_000,   # Wh — replace with your real capacity per station or spec
        pv_csv_path=r"C:\Users\svens\Documents\FU-Berlin\BeST-eBuS\best-ebus\scenario\eBuS\pv_estimation\data\solar_power_v6_scaled.csv",
        output_path=r"C:\Users\svens\Documents\FU-Berlin\BeST-eBuS\best-ebus\scenario\sumo\output\electric_bus_2026-08-17-19-10-35_ess.xml",
        start_soc=250_000,
    ).main()