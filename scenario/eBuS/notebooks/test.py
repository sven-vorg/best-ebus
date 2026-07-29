import lxml.etree as etree

tree = etree.parse(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\sumo\output\electric_bus_2026-07-29-20-13-37_chargingstations.xml")
root = tree.getroot()
count = len(root.findall("chargingEvent"))
print(count)