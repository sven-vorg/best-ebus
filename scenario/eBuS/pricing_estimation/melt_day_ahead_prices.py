"""
Reshape SMARD day-ahead spot price export into a tidy long-format
hourly time series.

Source shape: one row per hour, one column per bidding zone/country,
values in EUR/MWh, missing values marked "-".

Output: one row per (start_time, end_time, zone), price converted to
EUR/kWh to match the units used in pricing_data_annual.csv and the
simulation's energy fields.
"""

import pandas as pd

INPUT_PATH = "C:/Users/svens/Documents/FU-Berlin/BeST-eBuS/best-ebus/scenario/eBuS/ext_data/smard_day_ahead_prices.csv"   # <-- update to your actual file
OUTPUT_PATH = "C:/Users/svens/Documents/FU-Berlin/BeST-eBuS/best-ebus/scenario/eBuS/ext_data/day_ahead_prices_long.csv"

df = pd.read_csv(INPUT_PATH, sep=";", decimal=".", na_values=["-"])

df["start_time"] = pd.to_datetime(df["Start date"], format="%b %d, %Y %I:%M %p")
df["end_time"] = pd.to_datetime(df["End date"], format="%b %d, %Y %I:%M %p")

zone_cols = [c for c in df.columns if c not in ("Start date", "End date", "start_time", "end_time")]

long_df = df.melt(
    id_vars=["start_time", "end_time"],
    value_vars=zone_cols,
    var_name="zone_raw",
    value_name="price_eur_per_mwh",
)

# Clean up zone label, e.g. "Germany/Luxembourg [€/MWh] Calculated resolutions" -> "Germany/Luxembourg"
long_df["zone"] = (
    long_df["zone_raw"]
    .str.replace(r"\s*\[.*", "", regex=True)
    .str.strip()
)
long_df = long_df.drop(columns="zone_raw")

long_df["price_eur_per_kwh"] = long_df["price_eur_per_mwh"] / 1000.0

long_df["hour_of_day"] = long_df["start_time"].dt.hour
long_df["date"] = long_df["start_time"].dt.date
long_df["weekday"] = long_df["start_time"].dt.day_name()

long_df = long_df.dropna(subset=["price_eur_per_mwh"]).sort_values(["zone", "start_time"]).reset_index(drop=True)

print("Zones found:", long_df["zone"].unique())
print("\nFinal shape:", long_df.shape)
print(long_df.head(10))

long_df.to_csv(OUTPUT_PATH, index=False)
print(f"\nSaved to {OUTPUT_PATH}")

# ---------------------------------------------------------------
# Quick preview: DE/LU only, ready to join against chargingstations
# on hour_of_day (or start_time, if your simulation timestamps
# align to real calendar dates rather than a generic day).
# ---------------------------------------------------------------
de_lu = long_df[long_df["zone"] == "Germany/Luxembourg"].copy()
print("\nDE/LU average price by hour of day (across all days in file):")
print(de_lu.groupby("hour_of_day")["price_eur_per_kwh"].mean().round(4))