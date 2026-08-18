# AI-generated file
# Generated on 2026-07-29

#!/usr/bin/env python3

import argparse
import os
import time
import xml.etree.ElementTree as ET
from collections import defaultdict


# Accumulator attributes: summed across every timestep in the interval.
SUM_ATTRS = (
    "energyConsumed",
    "totalEnergyConsumed",
    "totalEnergyRegenerated",
    "energyChargedInTransit",
    "energyChargedStopped",
    "timeStopped",
)

# State attributes: not additive, so we keep the last value seen in the interval.
LAST_NUMERIC_ATTRS = (
    "actualBatteryCapacity",
    "maximumBatteryCapacity",
    "speed",
    "acceleration",
    "x",
    "y",
    "posOnLane",
)
LAST_STRING_ATTRS = ("lane",)


def new_vehicle():
    d = {a: 0.0 for a in SUM_ATTRS}
    d.update({a: 0.0 for a in LAST_NUMERIC_ATTRS})
    d.update({a: "" for a in LAST_STRING_ATTRS})
    d["chargingStationId"] = "NULL"
    d["aggregateNumber"] = 0
    return d


def format_time(seconds):
    seconds = int(seconds)

    if seconds < 60:
        return f"{seconds}s"

    minutes, seconds = divmod(seconds, 60)

    if minutes < 60:
        return f"{minutes}m {seconds}s"

    hours, minutes = divmod(minutes, 60)

    return f"{hours}h {minutes}m {seconds}s"

def write_interval(outfile, time_value, data):

    outfile.write(f'    <timestep time="{time_value:.2f}">\n')

    for vid, values in data.items():

        outfile.write(
            f'        <vehicle '
            f'id="{vid}" '
            f'energyConsumed="{values["energyConsumed"]:.6f}" '
            f'totalEnergyConsumed="{values["totalEnergyConsumed"]:.6f}" '
            f'totalEnergyRegenerated="{values["totalEnergyRegenerated"]:.6f}" '
            f'actualBatteryCapacity="{values["actualBatteryCapacity"]:.2f}" '
            f'maximumBatteryCapacity="{values["maximumBatteryCapacity"]:.2f}" '
            f'chargingStationId="{values["chargingStationId"]}" '
            f'energyCharged="{values["energyChargedInTransit"] + values["energyChargedStopped"]:.6f}" '
            f'energyChargedInTransit="{values["energyChargedInTransit"]:.6f}" '
            f'energyChargedStopped="{values["energyChargedStopped"]:.6f}" '
            f'speed="{values["speed"]:.2f}" '
            f'acceleration="{values["acceleration"]:.2f}" '
            f'x="{values["x"]:.2f}" '
            f'y="{values["y"]:.2f}" '
            f'lane="{values["lane"]}" '
            f'posOnLane="{values["posOnLane"]:.2f}" '
            f'timeStopped="{values["timeStopped"]:.6f}" '
            f'aggregateNumber="{values["aggregateNumber"]}"/>\n'
        )

    outfile.write("    </timestep>\n")


def aggregate(input_file, output_file, interval):

    filesize = os.path.getsize(input_file)

    vehicles = defaultdict(new_vehicle)

    current_interval = None
    current_start = None
    current_end = None

    start_time = time.perf_counter()
    last_report = start_time

    with open(input_file, "rb") as fin, \
         open(output_file, "w", encoding="utf8") as fout:

        fout.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        fout.write("<battery-export>\n")

        context = ET.iterparse(fin, events=("end",))

        for event, elem in context:

            if elem.tag != "timestep":
                continue

            timestep = float(elem.attrib["time"])
            interval_index = int(timestep // interval)

            if current_interval is None:

                current_interval = interval_index
                current_start = interval_index * interval
                current_end = current_start + interval - 1

            elif interval_index != current_interval:

                write_interval(fout, current_start + interval / 2, vehicles)

                vehicles.clear()

                current_interval = interval_index
                current_start = interval_index * interval
                current_end = current_start + interval - 1

            for vehicle in elem.findall("vehicle"):

                stats = vehicles[vehicle.attrib["id"]]

                for attr in SUM_ATTRS:
                    stats[attr] += float(vehicle.attrib[attr])

                for attr in LAST_NUMERIC_ATTRS:
                    stats[attr] = float(vehicle.attrib[attr])

                for attr in LAST_STRING_ATTRS:
                    stats[attr] = vehicle.attrib[attr]

                charging_station_id = vehicle.attrib["chargingStationId"]
                if charging_station_id != "NULL":
                    stats["chargingStationId"] = charging_station_id

                stats["aggregateNumber"] += 1

            now = time.perf_counter()

            if now - last_report >= 5:

                pos = fin.tell()

                percent = pos / filesize * 100

                elapsed = now - start_time

                speed = pos / elapsed

                remaining = filesize - pos

                eta = remaining / speed if speed else 0

                print(
                    f"{percent:6.2f}% | "
                    f"{pos/1024**3:6.2f} / {filesize/1024**3:.2f} GB | "
                    f"{speed/1024**2:6.1f} MB/s | "
                    f"Elapsed {format_time(elapsed)} | "
                    f"ETA {format_time(eta)}",
                    flush=True,
                )

                last_report = now

            elem.clear()

        if vehicles:
            write_interval(fout, current_start + interval / 2, vehicles)

        fout.write("</battery-export>\n")

    total = time.perf_counter() - start_time

    print(f"\nFinished in {format_time(total)}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("-i", "--input", required=True)
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("-t", "--time", required=True, type=int)

    args = parser.parse_args()

    aggregate(
        args.input,
        args.output,
        args.time,
    )