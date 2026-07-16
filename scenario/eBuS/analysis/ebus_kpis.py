import os
import subprocess

class EbusKpis():

    def __init__(self):
        self.sumo_home = os.environ["SUMO_HOME"]

    def run_tripstatistics():
        pass

    def run_generateITetrisNetworkMetrics(self):
        script = os.path.join(
            self.sumo_home,
            "tools",
            "output",
            "generateITetrisNetworkMetrics.py",
        )

        net_file = "/home/sven/Dokumente/Masterarbeit/Repos/best-ebus/scenario/sumo/berlin.net.xml"
        output_dir = "/home/sven/Dokumente/Masterarbeit/Repos/best-ebus/scenario/sumo/output"
        vehicle_type = "Ebusco2.2electric12m"

        subprocess.run(
            [
                "python",
                script,
                "-n",
                net_file,
                "-p",
                output_dir,
                "-t",
                vehicle_type,
            ],
            check=True,
        )

    def run_aggregateBatteryOutput(self):
        script = os.path.join(
            self.sumo_home,
            "tools",
            "output",
            "aggregateBatteryOutput.py",
        )

#        read_configuration = "/home/sven/Dokumente/Masterarbeit/Repos/best-ebus/scenario/sumo/e_berlin-bus.sumocfg"
        input_ = "/home/sven/Dokumente/Masterarbeit/Repos/best-ebus/scenario/sumo/output/electric_bus_2026-07-15-11-55-05_battery.xml"
        output = "/home/sven/Dokumente/Masterarbeit/Repos/best-ebus/scenario/eBuS/files/aggregated_battery.xml"
        time = "3600"

        subprocess.run(
            [
                "python",
                script,
#                "-c",
#                read_configuration,
                "-i",
                input_,
                "-t",
                time,
            ],
            check=True,
        )

if __name__ == "__main__":
    ek = EbusKpis()
    ek.run_aggregateBatteryOutput()