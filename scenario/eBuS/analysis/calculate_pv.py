"""
chargingStation_chargingSteps;
chargingStation_id;
chargingStation_totalEnergyCharged;
vehicle_chargingBegin;
vehicle_chargingEnd;
vehicle_id;
vehicle_totalEnergyChargedIntoVehicle;
vehicle_type;
step_actualBatteryCapacity;
step_chargingStatus;
step_efficiency;
step_energyCharged;
step_maximumBatteryCapacity;
step_partialCharge;
step_power;step_time
"""


from lxml import etree
from pathlib import Path
import pandas as pd

class CalculatePV():

    def __init__(
            self, 
            stations: str = "best-ebus/scenario/sumo/electric/e_stations.add.xml", 
            station_output: str = "best-ebus/scenario/sumo/output/electric_bus_2026-07-14-09-31-34_chargingsstations.csv",
            pv: str = "best-ebus/scenario/eBuS/files/pv_data.csv"
        ):
        # XML-Datei mit Ladestationen laden
        self.pv = self.v6(Path(stations), Path(pv))
        #self.charged = self.total_charged(station_output)
        self.charged = self.aggregate_station_hourly(station_output)
        self.df = self.merge_stations()

    def aggregate_station_hourly(self, station_output) -> pd.DataFrame:
        """
        Aggregate charging station data into hourly intervals.

        Parameters
        ----------
        df : pd.DataFrame
            Raw charging station dataframe.

        Returns
        -------
        pd.DataFrame
            One row per charging station and hour with:
            - chargingStation_id
            - hour
            - vehicles
            - avg_power
            - max_power
            - station_energy (cumulative at end of hour)
            - energy_this_hour
        """
        df = pd.read_csv(station_output, sep=";")

        # Keep only rows with timestamps
        df = df.dropna(subset=["step_time"])

        # Numeric conversion
        numeric_cols = [
            "step_time",
            "step_power",
            "chargingStation_totalEnergyCharged",
        ]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Hour bin
        df["hour"] = (df["step_time"] // 3600).astype(int)

        # Aggregate
        hourly = (
            df.sort_values("step_time")
            .groupby(["chargingStation_id", "hour"], as_index=False)
            .agg(
                vehicles=("vehicle_id", "nunique"),
                avg_power=("step_power", "mean"),
                max_power=("step_power", "max"),
                station_energy=("chargingStation_totalEnergyCharged", "last"),
            )
        )

        # Compute hourly energy from cumulative counter
        hourly["energy_this_hour"] = (
            hourly.groupby("chargingStation_id")["station_energy"]
                .diff()
                .fillna(hourly["station_energy"])
        )

        return hourly


    def merge_stations(self) -> pd.DataFrame:
        return pd.merge(self.pv, self.charged, left_on="station_id", right_on="chargingStation_id")


    def total_charged(self, station_output) -> pd.DataFrame:
        """
        Returns the last entry for each chargingStation_id based on step_time.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame containing charging station data.

        Returns
        -------
        pd.DataFrame
            One row per chargingStation_id containing the latest entry.
        """
        df = pd.read_csv(station_output, sep=";")
        return (
            df.sort_values("step_time")
            .groupby("chargingStation_id", as_index=False)
            .tail(1)
            .reset_index(drop=True)
        )

    def totals_per_station(self):
        # Extract total PV energy for each station
        pv_totals = []

        for _, row in self.station_df.iterrows():
            station_id = row["station_id"]
            solar = row["solar_data"]

            if solar is None:
                continue

            # Sum the generated power/energy values
            # Replace "value" with the correct key if necessary.
            total_pv = sum(point["value"] for point in solar["data"])

            pv_totals.append({
                "station_id": station_id,
                "total_pv_energy": total_pv
            })

        pv_df = pd.DataFrame(pv_totals)

        # Total charged energy per charging station
        charged_df = (
            self.output_df.groupby("chargingStation_id")[
                "chargingStation_totalEnergyCharged"
            ]
            .max()  # cumulative value
            .reset_index()
            .rename(columns={
                "chargingStation_id": "station_id",
                "chargingStation_totalEnergyCharged": "total_charged_energy"
            })
        )

        # Merge
        comparison = charged_df.merge(pv_df, on="station_id")

        # Plot
        plt.figure(figsize=(10, 6))

        plt.bar(
            comparison["station_id"],
            comparison["total_charged_energy"],
            alpha=0.7,
            label="Charged Energy"
        )

        plt.bar(
            comparison["station_id"],
            comparison["total_pv_energy"],
            alpha=0.7,
            label="PV Energy"
        )

        plt.xlabel("Charging Station")
        plt.ylabel("Energy")
        plt.title("Total Charged Energy vs Total PV Energy")
        plt.xticks(rotation=45)
        plt.legend()

        plt.tight_layout()
        plt.show()

    def main(self):
        print(self.charged.head())
        print(self.df.head())

if __name__ == "__main__":
    cv = CalculatePV()
    cv.main()
        