from pathlib import Path
import re


class OutputFiles:

    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.timestamp = self.find_latest_timestamp()

    def find_latest_timestamp(self):
        pattern = "*electric_bus*_stopinfo.xml"

        files = list(self.output_dir.glob(pattern))

        if not files:
            raise FileNotFoundError(
                f"No files found matching: {pattern}"
            )

        timestamps = []

        for file in files:
            match = re.search(
                r"(\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})",
                file.name
            )

            if match:
                timestamps.append(match.group(1))

        if not timestamps:
            raise ValueError(
                "No timestamps found in filenames."
            )

        return max(timestamps)

    def get_file(self, file_type):
        pattern = (
            f"*electric_bus*"
            f"{self.timestamp}"
            f"_{file_type}.xml"
        )

        files = list(self.output_dir.glob(pattern))

        if not files:
            raise FileNotFoundError(
                f"No file found matching: {pattern}"
            )

        return files[0]

    def get_run_files(self) -> dict:
        return {
            "battery": self.get_file("battery"),
            "chargingstations": self.get_file("chargingstations"),
            "fcdinfo": self.get_file("fcdinfo"),
            "statistics": self.get_file("statistics"),
            "stopinfo": self.get_file("stopinfo"),
            "summary": self.get_file("summary"),
            "tripinfo": self.get_file("tripinfo"),
            "ess": self.get_file("ess"),
            "battery_aggregated": self.get_file("battery_aggregated"),
        }


if __name__ == "__main__":
    output_dir = r"best-ebus\scenario\sumo\output"

    files = OutputFiles(output_dir)

    print(f"Simulation timestamp: {files.timestamp}")

    for file_type, path in files.get_run_files().items():
        print(f"{file_type}: {path}")