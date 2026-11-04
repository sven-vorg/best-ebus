# AI-generated code — 2026-11-04
"""Run the SUMO simulation via libsumo (or TraCI), optionally with blocked depot charging.

With block_depot_charging the depot charging stations get a charging power of 0 at the
start of the simulation, so the buses waiting there for their first trip are not charged.
As soon as every bus has left its start depot, the original charging power is restored,
so the buses returning after operations are charged as usual.

A bus has left its start depot when its first stop (the depot) has ended. Buses which
arrive or are removed before that count as left as well, so a stuck bus cannot block
the depot charging for the rest of the simulation.

The runs write their output like SUMO's runSeeds.py ("output/<seed>_multirun_<type>"),
so output_processing.order_output.order_output can sort them afterwards."""
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from lxml import etree

# prefer the tools of the own SUMO build (with the stationary energy storage) over installed packages
sys.path.insert(0, os.path.join(os.environ["SUMO_HOME"], "tools"))
try:
    import libsumo as traci
    USING_LIBSUMO = True
except ImportError:
    import traci
    USING_LIBSUMO = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEPOT_PREFIX = "cd_"


def parse_seeds(seeds: str) -> list[int]:
    """Seeds as space-separated list ("70 67 75") or as "start:stop" range ("0:100", stop excluded)."""
    if ":" in seeds:
        start, stop = seeds.split(":")
        return list(range(int(start), int(stop)))
    return [int(seed) for seed in seeds.split()]


def count_vehicles(vehicles_file: Path) -> int:
    """Number of buses in the vehicle file, i.e. the number of buses that have to leave a depot."""
    return sum(1 for _ in etree.iterparse(str(vehicles_file), tag="vehicle"))


def block_depot_charging(prefix: str = DEPOT_PREFIX) -> dict[str, float]:
    """Set the charging power of all depot charging stations to 0 and return the original values."""
    original = {}
    for cs in traci.chargingstation.getIDList():
        if cs.startswith(prefix):
            original[cs] = traci.chargingstation.getChargingPower(cs)
            traci.chargingstation.setChargingPower(cs, 0)
    return original


def restore_depot_charging(original: dict[str, float]) -> None:
    for cs, power in original.items():
        traci.chargingstation.setChargingPower(cs, power)


def run(sumocfg: Path, seed: int, vehicles_file: Path, block_depot_charging_until_departure: bool = True,
        sumo_binary: str = "sumo") -> float | None:
    """Run one simulation; the working directory is the directory of sumocfg.
    Returns the time [s] at which the depot charging was restored, None without blocking."""
    os.chdir(Path(sumocfg).parent)
    traci.start([
        sumo_binary,
        "-c", str(sumocfg),
        "--seed", str(seed),
        "--output-prefix", f"output/{seed}_multirun_",
        "--statistic-output", "stats.xml",
    ])
    end = traci.simulation.getEndTime()
    restored_at = None

    if block_depot_charging_until_departure:
        total = count_vehicles(vehicles_file)
        # at startup: before the first step, so the buses are not charged from t=0 on
        original = block_depot_charging()
        logger.info("Seed %s: blocked charging at %s depot charging stations until %s buses have left.",
                    seed, len(original), total)

        left = set()
        while len(left) < total and traci.simulation.getTime() < end:
            traci.simulationStep()
            # the first stop of every bus is its start depot
            left.update(traci.simulation.getStopEndingVehiclesIDList())
            left.update(traci.simulation.getArrivedIDList())
        restore_depot_charging(original)
        restored_at = traci.simulation.getTime()
        logger.info("Seed %s: all buses left their depot at %s s, restored depot charging.", seed, restored_at)

    # rest of the simulation without any interaction
    if traci.simulation.getTime() < end:
        traci.simulationStep(end)
    traci.close()
    logger.info("Seed %s: simulation finished.", seed)
    return restored_at


def run_seeds(sumocfg: Path, seeds: list[int], vehicles_file: Path, threads: int = 1,
              block_depot_charging_until_departure: bool = True, sumo_binary: str = "sumo") -> dict[int, float | None]:
    """Run one simulation per seed, up to threads in parallel (one process per simulation, as libsumo allows only one).
    Returns {seed: time the depot charging was restored}. A failing seed is logged, the other seeds still finish;
    afterwards the first error is raised."""
    logger.info("Running %s seeds with %s (%s parallel), depot charging blocked until departure: %s.",
                len(seeds), "libsumo" if USING_LIBSUMO else "TraCI", threads, block_depot_charging_until_departure)
    results = {}
    errors = []
    with ProcessPoolExecutor(max_workers=threads) as pool:
        futures = {
            seed: pool.submit(run, Path(sumocfg).resolve(), seed, Path(vehicles_file).resolve(),
                              block_depot_charging_until_departure, sumo_binary)
            for seed in seeds
        }
        for seed, future in futures.items():
            try:
                results[seed] = future.result()
            except Exception as e:
                logger.error("Seed %s failed: %s", seed, e)
                errors.append(e)
    if errors:
        raise errors[0]
    return results


if __name__ == "__main__":
    SUMO_DIR = Path(__file__).resolve().parents[2] / "sumo"
    run_seeds(
        sumocfg=SUMO_DIR / "e_berlin-bus_p.sumocfg",
        seeds=[65],
        vehicles_file=SUMO_DIR / "electric/e_vehicles.rou.xml",
        threads=1,
    )
