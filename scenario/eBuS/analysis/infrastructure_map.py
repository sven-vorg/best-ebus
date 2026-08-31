from pathlib import Path

import matplotlib.pyplot as plt
import geopandas as gpd
import contextily as cx
from lxml import etree
from matplotlib.lines import Line2D

# The basemap image barely changes between runs, so tiles are downloaded
# once and cached here instead of being re-fetched from the web every time.
BASEMAP_CACHE_DIR = Path(__file__).resolve().parent.parent / "files" / "basemaps"


def _add_cached_basemap(ax, cache_name, source=cx.providers.CartoDB.Positron, zoom="auto"):
    BASEMAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = BASEMAP_CACHE_DIR / f"{cache_name}.tif"

    if not cache_path.exists():
        west, east, south, north = ax.axis()
        cx.bounds2raster(west, south, east, north, path=str(cache_path), zoom=zoom, source=source)

    cx.add_basemap(ax, source=str(cache_path))


class InfrastructureMap:

    def __init__(self, busstops_path: Path, stations_path: Path, routes_path: Path):
        used_busstop_ids = self.parse_used_busstop_ids(routes_path)
        self.busstops = self.parse_busstops(busstops_path, used_busstop_ids)
        self.depots, self.chargingstations = self.parse_stations(stations_path)

    def parse_used_busstop_ids(self, xml_path):
        tree = etree.parse(xml_path)
        root = tree.getroot()
        return {elem.get('busStop') for elem in root.iter('stop') if elem.get('busStop')}

    def parse_busstops(self, xml_path, used_busstop_ids):
        tree = etree.parse(xml_path)
        root = tree.getroot()
        busstops = {}

        for elem in root.iter('busStop'):
            if elem.get('id') not in used_busstop_ids:
                continue
            param = elem.find("param[@key='coordinates']")
            if param is None:
                continue
            lon, lat = (float(v) for v in param.get('value').split(','))
            busstops[elem.get('id')] = {
                'name': elem.get('name'),
                'lon': lon,
                'lat': lat,
            }

        return busstops

    def parse_stations(self, xml_path):
        tree = etree.parse(xml_path)
        root = tree.getroot()
        depots = {}
        chargingstations = {}

        for elem in root.iter('chargingStation'):
            coords = elem.get('coordinates')
            if coords is None:
                continue
            lon, lat = (float(v) for v in coords.split(','))
            name = elem.get('name')
            station = {'name': name, 'lon': lon, 'lat': lat}

            if 'depot' in name.lower():
                depots[elem.get('id')] = station
            else:
                chargingstations[elem.get('id')] = station

        return depots, chargingstations

    def plot_infrastructure_map(self, save_path=None):
        """
        Map of Berlin showing bus stops (circles), charging stations
        (squares) and depots (diamonds).
        """
        groups = [
            (self.busstops, 'o', '#DAE8FC', '#6C8EBF', 'Bus stop', 8),
            (self.chargingstations, 's', '#F8CECC', '#B85450', 'Charging station', 60),
            (self.depots, 'D', '#E1D5E7', '#9673A6', 'Depot', 200),
        ]

        fig, ax = plt.subplots(figsize=(10, 12))

        scatters = []
        legend_handles = []

        for zorder, (stations, marker, color, edgecolor, label, size) in enumerate(groups, start=2):
            if not stations:
                continue

            lons = [s['lon'] for s in stations.values()]
            lats = [s['lat'] for s in stations.values()]
            names = [s['name'] for s in stations.values()]

            gdf = gpd.GeoDataFrame(
                {'name': names},
                geometry=gpd.points_from_xy(lons, lats),
                crs="EPSG:4326",
            ).to_crs(epsg=3857)

            sc = ax.scatter(
                gdf.geometry.x,
                gdf.geometry.y,
                s=size,
                marker=marker,
                c=color,
                alpha=0.8,
                edgecolor=edgecolor,
                linewidth=0.5,
                zorder=zorder,
            )
            scatters.append((sc, names))

            legend_handles.append(Line2D(
                [0], [0],
                marker=marker,
                color='none',
                markerfacecolor=color,
                markeredgecolor=edgecolor,
                markersize=10,
                label=label,
            ))

        annot = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(10, 10),
            textcoords='offset points',
            fontsize=8,
            zorder=10,
            bbox={'boxstyle': 'round', 'fc': 'white', 'ec': 'gray'},
        )
        annot.set_visible(False)

        def hover(event):
            visible = annot.get_visible()
            if event.inaxes != ax:
                if visible:
                    annot.set_visible(False)
                    fig.canvas.draw_idle()
                return

            for sc, names in reversed(scatters):
                contains, details = sc.contains(event)
                if contains:
                    index = details['ind'][0]
                    annot.xy = sc.get_offsets()[index]
                    annot.set_text(names[index])
                    annot.set_visible(True)
                    fig.canvas.draw_idle()
                    return

            if visible:
                annot.set_visible(False)
                fig.canvas.draw_idle()

        fig.canvas.mpl_connect('motion_notify_event', hover)

        _add_cached_basemap(ax, cache_name="infrastructure_map")

        ax.set_axis_off()
        ax.legend(handles=legend_handles, loc='lower right', frameon=True)

        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()


if __name__ == "__main__":
    busstops_path = r"best-ebus\scenario\sumo\berlin_bus_stops.add.xml"
    stations_path = r"best-ebus\scenario\sumo\electric\e_stations.add.xml"
    routes_path = r"best-ebus\scenario\sumo\electric\e_routes.rou.xml"

    im = InfrastructureMap(busstops_path, stations_path, routes_path)
    im.plot_infrastructure_map(
        save_path=r"best-ebus\scenario\sumo\output\plots\infrastructure_map.png"
    )
