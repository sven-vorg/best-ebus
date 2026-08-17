import pandas as pd
from lxml import etree

MINUTES_PER_HOUR = 60
TOTAL_MINUTES = 1440  # 1 day

class ChargingEvent:
    __slots__ = ('vehicle', 'total_energy', 'begin_sec', 'end_sec', 'energy_per_minute')
    def __init__(self, vehicle, total_energy, begin_sec, end_sec):
        self.vehicle = vehicle
        self.total_energy = total_energy   # Wh
        self.begin_sec = begin_sec
        self.end_sec = end_sec
        self.energy_per_minute = 0.0

class ChargingStation:
    def __init__(self, station_id):
        self.id = station_id
        self.charging_events = []

def parse_charging_events(xml_path):
    tree = etree.parse(xml_path)
    root = tree.getroot()
    stations = {}
    for elem in root.iter('chargingEvent'):
        sid = elem.get('chargingStationId')
        ev = ChargingEvent(
            vehicle=elem.get('vehicle'),
            total_energy=float(elem.get('totalEnergyChargedIntoVehicle')),
            begin_sec=float(elem.get('chargingBegin')),
            end_sec=float(elem.get('chargingEnd')),
        )
        stations.setdefault(sid, ChargingStation(sid)).charging_events.append(ev)
    return [stations[sid] for sid in sorted(stations)]

def parse_pv_data(csv_path):
    df = pd.read_csv(csv_path)
    df = df.set_index('station_id')
    df = df.drop(columns=["peak_power"])
    df = df[sorted(df.columns, key=lambda c: int(c))]
    return {station_id: row.astype(float).tolist() for station_id, row in df.iterrows()}

class EnergyStorageSystem:
    def __init__(self, charging_stations, ess_capacity, pv_csv_path, start_soc=0.0):
        self.charging_stations = charging_stations
        self.ess_capacity = ess_capacity
        self.pv_data = parse_pv_data(pv_csv_path)
        self.start_soc = start_soc
        self.energy_per_timestep(self.charging_stations)
        self.ess_df = self.calculate_ess(charging_stations, ess_capacity, start_soc)

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


if __name__ == "__main__":
    charging_stations = parse_charging_events(
        r"C:\Users\svens\Documents\FU-Berlin\BeST-eBuS\best-ebus\scenario\sumo\output\ebus_2026-08-13-18-26-28_chargingstations.xml"
    )

    ess = EnergyStorageSystem(
        charging_stations=charging_stations,
        ess_capacity=500_000,   # Wh — replace with your real capacity per station or spec
        pv_csv_path=r"C:\Users\svens\Documents\FU-Berlin\BeST-eBuS\best-ebus\scenario\eBuS\pv_estimation\data\solar_power_v6_scaled.csv",
        start_soc=250_000,
    )

    ess.ess_df.to_csv(r"C:\Users\svens\Documents\FU-Berlin\BeST-eBuS\best-ebus\scenario\eBuS\files\output\ess_output.csv", index=False)