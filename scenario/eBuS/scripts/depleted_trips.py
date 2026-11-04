"""Find the trips a bus could no longer serve after its battery was depleted.

For every <tripinfo> whose <battery depleted> is > 0, take its arrival time,
find the last stop in the bus's route whose `until` is <= that time, and
collect all tripIds of the stops after it.

Usage from Jupyter:
    from depleted_trips import find_depleted_trips
    df = find_depleted_trips("path/to/tripinfo.xml", "path/to/e_routes.rou.xml")

Usage from the command line:
    python depleted_trips.py tripinfo.xml e_routes.rou.xml [-o out.csv]
"""
import argparse
import xml.etree.ElementTree as ET

import pandas as pd


def read_depleted_buses(tripinfo_file):
    """Return {vehicle_id: arrival_time} for all vehicles with depleted > 0."""
    depleted = {}
    for _, elem in ET.iterparse(tripinfo_file, events=("end",)):
        if elem.tag == "tripinfo":
            battery = elem.find("battery")
            if battery is not None and float(battery.get("depleted", 0)) > 0:
                depleted[elem.get("id")] = float(elem.get("arrival"))
            elem.clear()
    return depleted


def read_route_stops(route_file, route_ids):
    """Return ({route_id: [(until, tripId), ...]} for the requested routes only,
    set of all tripIds in the file)."""
    routes = {}
    all_trip_ids = set()
    for _, elem in ET.iterparse(route_file, events=("end",)):
        if elem.tag == "route":
            stops = [
                (float(s.get("until")) if s.get("until") else None, s.get("tripId"))
                for s in elem.iter("stop")
            ]
            all_trip_ids.update(t for _, t in stops if t is not None)
            if elem.get("id") in route_ids:
                routes[elem.get("id")] = stops
            elem.clear()
    return routes, all_trip_ids


def trips_after(stops, arrival):
    """Return (index of last stop with until <= arrival, unique tripIds after it)."""
    last_idx = -1
    for i, (until, _) in enumerate(stops):
        if until is not None and until <= arrival:
            last_idx = i
    trip_ids = []
    for _, trip_id in stops[last_idx + 1:]:
        if trip_id is not None and trip_id not in trip_ids:
            trip_ids.append(trip_id)
    return last_idx, trip_ids


def find_depleted_trips(tripinfo_file, route_file, route_suffix="_route"):
    """Return a DataFrame with one row per depleted bus.

    The route of a bus is looked up as `<vehicle_id><route_suffix>`.
    Overall totals are stored in `df.attrs` (total_trips, missed_trips,
    missed_pct) and printed as a summary.
    """
    depleted = read_depleted_buses(tripinfo_file)
    route_ids = {bus + route_suffix for bus in depleted}
    routes, all_trip_ids = read_route_stops(route_file, route_ids)

    rows = []
    missed = set()
    for bus, arrival in depleted.items():
        stops = routes.get(bus + route_suffix)
        if stops is None:
            print(f"Warning: no route '{bus + route_suffix}' found for {bus}")
            continue
        last_idx, trip_ids = trips_after(stops, arrival)
        missed.update(trip_ids)
        n_bus_trips = len({t for _, t in stops if t is not None})
        rows.append({
            "vehicle_id": bus,
            "arrival": arrival,
            "last_stop_index": last_idx,
            "last_stop_until": stops[last_idx][0] if last_idx >= 0 else None,
            "n_bus_trips": n_bus_trips,
            "n_missed_trips": len(trip_ids),
            "missed_pct": 100 * len(trip_ids) / n_bus_trips if n_bus_trips else 0.0,
            "missed_trip_ids": trip_ids,
        })

    df = pd.DataFrame(rows)
    df.attrs["total_trips"] = len(all_trip_ids)
    df.attrs["missed_trips"] = len(missed)
    df.attrs["missed_pct"] = 100 * len(missed) / len(all_trip_ids) if all_trip_ids else 0.0
    print(f"Missed {len(missed)} of {len(all_trip_ids)} trips "
          f"({df.attrs['missed_pct']:.2f} %) across {len(df)} depleted buses")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("tripinfo_file")
    parser.add_argument("route_file")
    parser.add_argument("-o", "--output", help="optional CSV output path")
    args = parser.parse_args()

    df = find_depleted_trips(args.tripinfo_file, args.route_file)
    print(df.to_string())
    if args.output:
        df.to_csv(args.output, index=False)
