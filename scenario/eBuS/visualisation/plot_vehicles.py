# AI-generated on 2026-07-14

import os
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv

def plot_rand_20():
    load_dotenv()
    latest_run = os.getenv("latest_timestamp")
    df = pd.read_csv(f"best-ebus\scenario\sumo\output\electric_bus_{latest_run}_battery.csv", sep=";")
    df = df.sort_values(["vehicle_id", "timestep_time"])

    plt.figure(figsize=(12, 6))

    selected_ids = df["vehicle_id"].drop_duplicates().sample(n=20, random_state=42)

    for vehicle_id, group in df[df["vehicle_id"].isin(selected_ids)].groupby("vehicle_id"):
        cumulative = group["vehicle_energyConsumed"].cumsum()

        plt.plot(
            group["timestep_time"],
            cumulative,
            label=f"Vehicle {vehicle_id}"
        )

    plt.xlabel("Time")
    plt.ylabel("Cumulative Energy Consumed")
    plt.title("Cumulative Energy Consumption by Vehicle")
    plt.legend(title="Vehicle ID", bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.grid(True)
    plt.tight_layout()
    plt.legend().remove()
    plt.show()

def plot_top_total_energy():
        # Load the data
    df = pd.read_csv("best-ebus\scenario\sumo\output\electric_bus_2026-07-14-09-31-34_battery.csv", sep=";")

    # Ensure data is ordered by time
    df = df.sort_values(["vehicle_id", "timestep_time"])

    # Get the 20 vehicles with the highest total energy consumption
    # (using the final value of the cumulative total)
    top20_ids = (
        df.groupby("vehicle_id")["vehicle_totalEnergyConsumed"]
        .max()
        .nlargest(20)
        .index
    )

    # Keep only those vehicles
    top20_df = df[df["vehicle_id"].isin(top20_ids)]

    # Plot
    plt.figure(figsize=(14, 8))

    for vehicle_id, group in top20_df.groupby("vehicle_id"):
        plt.plot(
            group["timestep_time"],
            group["vehicle_totalEnergyConsumed"],
            linewidth=2,
            label=f"Vehicle {vehicle_id}"
        )

    plt.title("Total Energy Consumed Over Time (Top 20 Vehicles)")
    plt.xlabel("Time")
    plt.ylabel("Total Energy Consumed")
    plt.grid(True)
    plt.legend(title="Vehicle ID", bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.legend().remove()
    plt.tight_layout()
    plt.show()

plot_top_total_energy()