import os
import subprocess

class SumoInbuilds():

    def __init__(self):
        self.sumo_home = os.environ["SUMO_HOME"]

    def run_tripstatistics():
        pass

    def run_plotXMLAttributes(self):
        script = os.path.join(
            self.sumo_home,
            "tools",
            "visualization",
            "plotXMLAttributes.py",
        )

        # read_configuration = "/home/sven/Dokumente/Masterarbeit/Repos/best-ebus/scenario/sumo/e_berlin-bus.sumocfg"
        input_ = f"/home/sven/Dokumente/Masterarbeit/Repos/best-ebus/scenario/sumo/output/electric_bus_2026-07-15-11-55-05_battery.xml"
        output = "/home/sven/Dokumente/Masterarbeit/Repos/best-ebus/scenario/eBuS/files/aggregated_battery.xml"
        time = "3600"

        subprocess.run(
            [
                "python",
                script,
                #"-c",
                # read_configuration,
                "-i",
                input_,
                "-t",
                time,
            ],
            check=True,
        )

    def run_delayovertime(self):
        script = os.path.join(
            self.sumo_home,
            "tools",
            "visualization",
            "plotXMLAttributes.py",
        )
        
        idattr = "id"
        xattr = "depart"
        yattr = "departDelay"
        xlabel = "depart time [s]"
        ylabel = "depart delay [s]"
        ylim = "0,40"
        xticks = "0,1200,200,10"
        yticks = "0,40,5,10"
        title = "depart delay over depart time"
        titelsize = "16"
        input_ = "/home/sven/Dokumente/Masterarbeit/Repos/best-ebus/scenario/sumo/output/electric_bus_2026-07-15-11-55-05_tripinfo.xml"


        subprocess.run(
            [
                "python",
                script,
                "-i",
                idattr,
                "-x",
                xattr,
                "-y",
                yattr,
                "--scatterplot",
                "--xlabel",
                xlabel,
                "--ylabel",
                ylabel,
                "--ylim",
                ylim,
                "--xticks",
                xticks,
                "--yticks",
                yticks,
                "--xgrid",
                "--ygrid",
                "--title",
                title,
                "--titlesize",
                titelsize,
                input_
            ],
            check=True,
        )

    def 

if __name__ == "__main__":
    si = SumoInbuilds()
    si.run_delayovertime()