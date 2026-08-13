import pandas as pd

records = []
current = None
file = r"C:\Users\svens\Documents\FU-Berlin\BeST-eBuS\best-ebus\scenario\eBuS\files\796_29329_212_450.txt"
wanted_lines = pd.read_csv(r"")


with open(file) as f:
    for line in f:
        line = line.rstrip()

        if line.startswith("$"):
            if current is not None:
                records.append(current)

            current = {
                "header": line[1:].split(";"),
                "lines": []
            }
        elif current is not None:
            current["lines"].append(line)

if current is not None:
    records.append(current)

for record in records:
    print(record["header"])
    if record["header"] == ["LINE:ID", "Code", "Name"]:
        lines = record["lines"]

for line in lines:
    if 