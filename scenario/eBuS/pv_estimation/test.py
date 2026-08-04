# AI-generated on 2026-08-03

import requests

BASE_URL = "https://photovoltaic-geographic-information-system.ec.europa.eu/api/v6/power/broadband"

params = {
    "latitude": 52.56058715781662,
    "longitude": 13.33776446744273,
    "installation_height": 4,
    "start_time": "2024-06-22 00:00:00",
    "end_time": "2024-06-22 23:59:59",
    "surface_position_optimisation_mode": "Orientation & Tilt",
    "frequency": "Hourly",
    "timezone": "Europe/Berlin",
    "power_model": "Huld 2011",
}

for peak_power in [1, 10, 100, 1000, 6289]:
    p = params.copy()
    p["peak_power"] = peak_power

    r = requests.get(BASE_URL, params=p, timeout=30)
    r.raise_for_status()

    data = r.json()["power"]

    print(f"\npeak_power = {peak_power}")
    print(f"max power = {max(data):.3f}")
    print(data)