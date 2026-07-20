"""
Reshape `pricing_data` (Destatis table 61243 — "Durchschnittspreise
fuer Strom und Gas") into a tidy table.

Important context about this dataset (confirmed from a real sample):
  - `time` is a YEAR (time_code == "JAHR"), not a timestamp. This table
    gives annual average prices, not intraday/hourly prices. Use it for
    year-over-year trend and tariff-by-consumption-volume, not for a
    "cheapest hour to charge" analysis.
  - `2_variable_attribute_label` = price COMPONENT. The two components
    ("Steuern, Abgaben und Umlagen" = taxes/levies/surcharges, and
    "Energie und Vertrieb" = energy + distribution) are parts of the
    total price and must be SUMMED, not treated as alternatives.
  - `3_variable_attribute_label` = annual consumption class bracket
    (e.g. "2 000 bis unter 20 000 MWh"). Blank / "Insgesamt" means
    "all classes combined". Pick the bracket matching your depot's
    real annual consumption once you know it.
  - `value` uses German decimal commas ("0,1132") -> must be parsed.
  - `value_q` is a quality flag (e.g. "e" = estimated).

Output: one row per (year, consumption_class) with the two components
as separate columns plus a summed total_price_eur_per_kwh column.
"""

import pandas as pd

INPUT_PATH = "pricing_data.csv"        # <-- update to your actual file
OUTPUT_PATH = "pricing_data_annual.csv"

df = pd.read_csv(INPUT_PATH, sep=";", decimal=",")
# sep=";" and decimal="," handle the German CSV format directly,
# so `value` should already load as a proper float. If it doesn't
# (e.g. mixed formatting), fall back to manual parsing:
if df["value"].dtype == object:
    df["value"] = (
        df["value"].astype(str).str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False).astype(float)
    )

# Keep only rows where time is actually a year (defensive, in case the
# export mixes granularities)
df = df[df["time_code"] == "JAHR"].copy()
df["year"] = df["time"].astype(int)

# Normalize the consumption-class label: blank -> "Insgesamt" (=all classes)
df["consumption_class"] = df["3_variable_attribute_label"].fillna("Insgesamt")
df.loc[df["consumption_class"].str.strip() == "", "consumption_class"] = "Insgesamt"

component_col = "2_variable_attribute_label"

print("Price components found:")
print(df[component_col].unique())
print("\nConsumption classes found:")
print(df["consumption_class"].unique())

# ---------------------------------------------------------------
# Pivot: one row per (year, consumption_class), one column per
# price component, then sum components -> total price.
# ---------------------------------------------------------------
pivot = df.pivot_table(
    index=["year", "consumption_class"],
    columns=component_col,
    values="value",
    aggfunc="first",   # should be exactly one value per combination
).reset_index()

pivot.columns.name = None

component_cols = [c for c in pivot.columns if c not in ("year", "consumption_class")]
pivot["total_price_eur_per_kwh"] = pivot[component_cols].sum(axis=1, min_count=1)

pivot = pivot.sort_values(["consumption_class", "year"]).reset_index(drop=True)

print("\nFinal shape:", pivot.shape)
print(pivot.head(10))

pivot.to_csv(OUTPUT_PATH, index=False)
print(f"\nSaved to {OUTPUT_PATH}")