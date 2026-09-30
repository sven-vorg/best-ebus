# Extension of the scenario

## Adding Depots

## Adding passenger cars
The simulation can be extended by adding back the passenger vehicles from BeST. While BeST provided only 24 hours of passenger traffic, trough repeating the first five hours a passenger traffic file with 29 hours of runtime was achieved. This file, *e_berlin_extended.rou.gz*, can be added to the simulation by including it in the *e_berlin-bus.sumocfg* route files parameter.
The effects of this upon the energy consumption, punctuality, route completion and PSC aptitude would be very interesting. However, the scale and number of vehicles requires very capable hardware and may take multiple days to compute. Furthermore, depending on configuration, large amounts of output data may be generated. The recommendation is therefore to limit the output to necessary and aggregated files.
A previous run on a system using an Intel i7 14700 silently failed at an unknown time due to limited storage space, but had exceeded 18 hours. Simulation speed may drop below real time when using this option.

Option for the .sumocfg:
```xml
<route-files value="electric/e_routes.rou.xml, electric/e_vehicles.rou.xml, e_berlin_extended.rou.gz"/>
```

