from pathlib import Path
import re

# The seed used as the baseline run in multi-seed dashboards; the other
# seeds under a run folder are used only to compute confidence intervals
# around the baseline's plotted values.
BASELINE_SEED = "65"

SEED_DIR_PATTERN = re.compile(r"^(\d+)_directory$")


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


class SeedOutputFiles:
    """
    Resolves output files for a single seed's run folder, as produced by
    tools.order_output.order_output (files named "<seed>_multirun_<type>.xml",
    grouped under run_<timestamp>/<seed>_directory/).
    """

    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.seed = self.find_seed()

    def find_seed(self):
        files = list(self.output_dir.glob("*_multirun_*.xml"))

        if not files:
            raise FileNotFoundError(
                f"No multi-seed run files found in: {self.output_dir}"
            )

        match = re.match(r"(\d+)_multirun_", files[0].name)

        if not match:
            raise ValueError(
                f"Could not determine seed from filename: {files[0].name}"
            )

        return match.group(1)

    def get_file(self, file_type):
        pattern = f"{self.seed}_multirun_{file_type}.xml"

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
            "statistics": self.get_file("stats"),
            "stopinfo": self.get_file("stopinfo"),
            "summary": self.get_file("summary"),
            "tripinfo": self.get_file("tripinfo"),
            "ess": self.get_file("ess"),
            "battery_aggregated": self.get_file("battery_aggregated"),
        }


def seed_dirs(run_dir) -> dict[str, Path]:
    """
    Map seed -> `<seed>_directory` path for every seed subfolder directly
    under run_dir, sorted numerically by seed.
    """
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        return {}
    found = []
    for p in run_dir.iterdir():
        if p.is_dir():
            match = SEED_DIR_PATTERN.match(p.name)
            if match:
                found.append((match.group(1), p))
    found.sort(key=lambda item: int(item[0]))
    return dict(found)


class RunFiles(dict):
    """
    A baseline seed's file dict (drop-in replacement for
    `SeedOutputFiles.get_run_files()`), plus the file dicts of the other
    seeds in the same run folder, kept around for confidence-interval
    plots that want them.
    """

    def __init__(self, baseline_files: dict, baseline_seed: str, ci_seeds: dict[str, dict]):
        super().__init__(baseline_files)
        self.baseline_seed = baseline_seed
        self.ci_seeds = ci_seeds


class MultiSeedRunFiles:
    """
    Resolves output files for an overarching `run_<timestamp>` folder
    holding one `<seed>_directory` subfolder per seed (as produced by
    tools.order_output.order_output). Seed `BASELINE_SEED` is the
    baseline; every other seed present is treated as a confidence-interval
    seed.
    """

    def __init__(self, run_dir, baseline_seed: str = BASELINE_SEED):
        self.run_dir = Path(run_dir)
        self.baseline_seed = baseline_seed
        self.seeds = seed_dirs(self.run_dir)

        if not self.seeds:
            raise FileNotFoundError(
                f"No <seed>_directory subfolders found in: {self.run_dir}"
            )

        if self.baseline_seed not in self.seeds:
            raise FileNotFoundError(
                f"Baseline seed {self.baseline_seed} not found in: {self.run_dir} "
                f"(seeds present: {', '.join(self.seeds)})"
            )

    @property
    def ci_seed_ids(self) -> list[str]:
        return [seed for seed in self.seeds if seed != self.baseline_seed]

    def get_run_files(self) -> RunFiles:
        baseline_files = SeedOutputFiles(self.seeds[self.baseline_seed]).get_run_files()

        ci_seeds = {
            seed: SeedOutputFiles(path).get_run_files()
            for seed, path in self.seeds.items()
            if seed != self.baseline_seed
        }

        return RunFiles(baseline_files, self.baseline_seed, ci_seeds)


if __name__ == "__main__":
    output_dir = r"best-ebus\scenario\sumo\output"

    files = OutputFiles(output_dir)

    print(f"Simulation timestamp: {files.timestamp}")

    for file_type, path in files.get_run_files().items():
        print(f"{file_type}: {path}")