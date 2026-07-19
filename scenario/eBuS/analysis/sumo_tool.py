"""
sumo_inbuilds.py

An extendable wrapper around SUMO's bundled command-line tools
(tools/visualization/plotXMLAttributes.py, tripinfo statistics, etc).

Design:
- `SumoTool` is a small base class that knows how to locate SUMO_HOME
  and run a python script from SUMO's `tools/` directory, capturing
  output so failures are actually debuggable.
- `SumoInbuilds` inherits from it and adds one method per SUMO tool
  you want to call. Add new tools by adding new methods that call
  `self._run_tool(...)`.
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import Iterable, Optional

from dotenv import load_dotenv


class SumoToolError(RuntimeError):
    """Raised when a SUMO tool subprocess exits non-zero."""


class SumoTool:
    """Base class: knows how to find and run scripts under $SUMO_HOME/tools."""

    def __init__(self, sumo_home: Optional[str] = None):
        self.sumo_home = Path(sumo_home or os.environ["SUMO_HOME"])
        if not self.sumo_home.exists():
            raise FileNotFoundError(f"SUMO_HOME does not exist: {self.sumo_home}")

    def _tool_path(self, *parts: str) -> Path:
        """Build a path to a script under $SUMO_HOME/tools, e.g.
        self._tool_path('visualization', 'plotXMLAttributes.py')
        """
        path = self.sumo_home.joinpath("tools", *parts)
        if not path.exists():
            raise FileNotFoundError(f"SUMO tool script not found: {path}")
        return path

    def _run_tool(self, script: Path, args: Iterable[str]) -> subprocess.CompletedProcess:
        """Run `python script *args`, capturing stdout/stderr so failures
        are actually readable instead of a bare 'exit status 1'."""
        cmd = [sys.executable, str(script), *args]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise SumoToolError(
                f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
                f"--- stdout ---\n{result.stdout}\n"
                f"--- stderr ---\n{result.stderr}"
            )
        return result


class SumoInbuilds(SumoTool):
    """Project-specific SUMO tool calls. Add one method per tool."""

    # Adjust this once, instead of hardcoding absolute paths in every method.
    PROJECT_ROOT = Path(
        os.environ.get(
            "PROJECT_ROOT",
            r"c:/Users/Ralop/Documents/FU Berlin/BeST-eBuS/best-ebus/scenario/",
        )
    )

    def __init__(self, sumo_home: Optional[str] = None):
        super().__init__(sumo_home)
        load_dotenv()

    @property
    def latest_timestamp(self) -> str:
        ts = os.getenv("latest_timestamp")
        if not ts:
            raise EnvironmentError("latest_timestamp is not set in the environment/.env")
        return ts

    # ------------------------------------------------------------------
    # Individual tool wrappers
    # ------------------------------------------------------------------

    def run_tripstatistics(
        self,
        input_file: Optional[str] = None,
        output_file: Optional[str] = None,
        ) -> subprocess.CompletedProcess:
        script = self._tool_path("output","tripStatistics.py")
        date_of_run = self.latest_timestamp
        input_ = input_file or str(
            self.PROJECT_ROOT
            / "sumo"
            / "output"
            / f"electric_bus_{date_of_run}_tripInfo.xml"
        )
        output = output_file or str(
            self.PROJECT_ROOT / "eBuS" / "files" / "tripStatistics.xml"
        )
        
        if not Path(input_).exists():
            raise FileNotFoundError(f"Input file not found: {input_}")

        args = [
            "-t", input_,
            "-o", output,
        ]

        return self._run_tool(script, args)
    


    def run_delayovertime(
        self,
        input_file: Optional[str] = None,
        output_file: Optional[str] = None,
    ) -> subprocess.CompletedProcess:
        script = self._tool_path("visualization", "plotXMLAttributes.py")
        date_of_run = self.latest_timestamp
        input_ = input_file or str(
            self.PROJECT_ROOT
            / "sumo"
            / "output"
            / f"electric_bus_{date_of_run}_tripinfo.xml"
        )

        if not Path(input_).exists():
            raise FileNotFoundError(f"Input file not found: {input_}")

        args = [
            "-i", "id",              # idattr: groups/labels series
            "-x", "depart",
            "-y", "departDelay",
            "--scatterplot",
            "--xlabel", "depart time [s]",
            "--ylabel", "depart delay [s]",
            "--ylim", "0,40",
            "--xticks", "0,1200,200,10",
            "--yticks", "0,40,5,10",
            "--xgrid",
            "--ygrid",
            "--title", "depart delay over depart time",
            "--titlesize", "16",
        ]
        if output_file:
            args += ["--output", output_file]
        args.append(input_)  # positional input file goes last

        return self._run_tool(script, args)

    def run_generateITetrisNetworkMetrics(
        self,
        net_file: Optional[str] = None,
        output_dir: Optional[str] = None,
        vehicle_type: str = "Ebusco2.2electric12m",
    ) -> subprocess.CompletedProcess:
        script = self._tool_path("output", "generateITetrisNetworkMetrics.py")

        net_file_ = net_file or str(self.PROJECT_ROOT / "sumo" / "berlin.net.xml")
        output_dir_ = output_dir or str(self.PROJECT_ROOT / "sumo" / "output")

        if not Path(net_file_).exists():
            raise FileNotFoundError(f"Net file not found: {net_file_}")
        if not Path(output_dir_).is_dir():
            raise FileNotFoundError(f"Output directory not found: {output_dir_}")

        args = [
            "-n", net_file_,
            "-p", output_dir_,
            "-t", vehicle_type,
        ]
        return self._run_tool(script, args)

    def run_aggregateBatteryOutput(
        self,
        input_file: Optional[str] = None,
        output_file: Optional[str] = None,
        time_window: str = "3600",
    ) -> subprocess.CompletedProcess:
        script = self._tool_path("output", "aggregateBatteryOutput.py")

        date_of_run = self.latest_timestamp
        input_ = input_file or str(
            self.PROJECT_ROOT
            / "sumo"
            / "output"
            / f"electric_bus_{date_of_run}_battery.xml"
        )
        output = output_file or str(
            self.PROJECT_ROOT / "eBuS" / "files" / "aggregated_battery.xml"
        )

        if not Path(input_).exists():
            raise FileNotFoundError(f"Input file not found: {input_}")

        args = [
            "-i", input_,
            "-t", time_window,
            "-o", output,
        ]
        return self._run_tool(script, args)

    # ------------------------------------------------------------------
    # To add a new tool:
    #   def run_something(self, ...):
    #       script = self._tool_path("some_subdir", "some_script.py")
    #       args = [...]
    #       return self._run_tool(script, args)
    # ------------------------------------------------------------------


if __name__ == "__main__":
    si = SumoInbuilds()
    try:
        pass
    except (SumoToolError, FileNotFoundError, EnvironmentError) as exc:
        print(f"Failed: {exc}")