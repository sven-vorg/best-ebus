# Notes and Snippets for Documentation Creation
It performs the definition of depots and belonging service lines. For that it assumes a *[heuristic_preprocessing.lines]* table in *ebus_config.toml*, mapping each line to its depot and vehicle type. \
Available lines are taken from *berlin_bus.rou.xml*, where there is a *to* and *from* for each.
For eBuS this data has been taken from the website [berliner-lininchronik.de](https://www.berliner-linienchronik.de/fahrzeuge-bvg.html) (Sawall, Fabian; 2026) \
While manual definition of routes is possible, and adjustments can be made to fine-tune simulation behaviour, the assignment of vehciles to services is computed by a heuristic solving method (Janus, Robert; n.y.)

While **BeST** operates on the **SUMO** flow-functionality, which generates and destroys vehicles for a given route periodically, **eBuS** requieres the use of persistent vehicles.

Excluded Buses:
X10
M85
184
215
312