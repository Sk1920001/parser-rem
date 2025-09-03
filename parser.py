import os
import re
from typing import Dict, Tuple, Optional, List

import numpy as np
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from dotenv import load_dotenv
from categories import CATEGORIES  # ensure this module is available


class RemParser:
    """
    Parse the REM XLS/HTML file, assemble a tidy DataFrame and export CSV/Map.

    Constructor:
      - file_path: Path to the 'XLS' (actually HTML) file.

    Public attributes:
      - df_formatted: pandas.DataFrame with columns:
          ['gender','age_group','location','latitude','longitude','category','subcategory','factor','subtype']

    Public methods:
      - export_csv(output_csv="data.csv")
      - export_map(output_html="map.html", center=None, zoom_start=13, max_zoom=19, disable_clustering_at_zoom=19)
    """

    def __init__(self, file_path: str, country_suffix: str = ", Chile"):
        load_dotenv()
        self.file_path = file_path
        self.country_suffix = country_suffix
        self.locations: List[str] = []
        self.locations_coords: Dict[str, Tuple[Optional[float], Optional[float]]] = {}
        self.df_formatted: Optional[pd.DataFrame] = None

        # Build sanitized categories cache
        self._SANITIZED_CATEGORIES: Optional[Dict[Tuple[str, str], Dict[str, str]]] = None

        # Prepare Google Maps client (optional)
        self._gmaps = None
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if api_key:
            try:
                import googlemaps
                self._gmaps = googlemaps.Client(key=api_key)
            except Exception:
                self._gmaps = None  # continue without geocoding

        # Run the full pipeline
        self._read_tables()
        self._split_blocks()
        self._collect_locations()
        self._geocode_locations()
        self._build_df()

    # ------------------------------
    # Reading and preprocessing
    # ------------------------------
    def _read_tables(self):
        # The file is HTML disguised as XLS
        self._tables = pd.read_html(self.file_path, encoding="utf-8")
        self._df = self._tables[0]

    def _split_blocks(self):
        c0 = self._df.iloc[:, 0].astype(str).str.strip().str.upper()
        c1 = self._df.iloc[:, 1].astype(str).str.strip().str.upper()
        sep = (c0 == "OTRAS") & (c1 == "OTRAS")
        idx_sep = np.where(sep.to_numpy())[0]
        cuts = (idx_sep + 1).tolist()
        self._blocks = [chunk.reset_index(drop=True) for chunk in np.split(self._df, cuts) if len(chunk) > 0]

    def _collect_locations(self):
        # Skip block 0 and last block; skip "Comuna" aggregates
        locs = []
        for i in range(1, len(self._blocks) - 1):
            first_cell = str(self._blocks[i].iloc[0, 0])
            if "Comuna" in first_cell:
                continue
            loc = first_cell.replace("Establecimiento: ", "")
            locs.append(loc)
        self.locations = locs

    def _geocode_locations(self):
        coords = {}
        for loc in self.locations:
            if self._gmaps:
                try:
                    result = self._gmaps.geocode(loc + self.country_suffix)
                except Exception:
                    result = []
            else:
                result = []
            if result:
                g = result[0]["geometry"]["location"]
                coords[loc] = (g.get("lat"), g.get("lng"))
            else:
                coords[loc] = (None, None)
        self.locations_coords = coords

    # ------------------------------
    # String sanitizing + category lookup
    # ------------------------------
    @staticmethod
    def _sanitize_string(s):
        if s is None:
            return None
        s = str(s)
        for ch in ("\ufeff", "\u200b", "\u200c", "\u200d"):
            s = s.replace(ch, "")
        s = s.replace("\u00A0", " ")
        s = s.replace("（", "(").replace("）", ")")
        s = re.sub(r"\)\s*\)+", ")", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _build_sanitized_categories(self):
        mapping = {}
        for (k0, k1), value in CATEGORIES.items():
            sk = (self._sanitize_string(k0), self._sanitize_string(k1))
            mapping[sk] = value
        self._SANITIZED_CATEGORIES = mapping

    def _get_category_for_row(self, cause_tuple: Tuple[str, str]):
        # 1) exact
        cat = CATEGORIES.get(cause_tuple)
        if cat is not None:
            return cat
        # 2) sanitized exact
        sanitized = (self._sanitize_string(cause_tuple[0]), self._sanitize_string(cause_tuple[1]))
        if sanitized != cause_tuple:
            cat = CATEGORIES.get(sanitized)
            if cat is not None:
                return cat
        # 3) cached normalized mapping
        if self._SANITIZED_CATEGORIES is None:
            self._build_sanitized_categories()
        return self._SANITIZED_CATEGORIES.get(sanitized)

    # ------------------------------
    # Block -> tidy rows
    # ------------------------------
    def _process_block(self, df_block: pd.DataFrame) -> pd.DataFrame:
        location_name = str(df_block.iloc[0, 0]).replace("Establecimiento: ", "")
        lat, lng = self.locations_coords.get(location_name, (None, None))

        rows = []
        for i, (idx, row) in enumerate(df_block.iloc[3:].iterrows(), start=3):
            if i == 8:
                continue  # skip subtotal row if present

            for col, val in zip(df_block.columns[5:39], row.iloc[5:39]):
                if pd.isna(val) or (isinstance(val, str) and not val.strip()):
                    continue

                cause_tuple = (row[0], row[1])
                cat = self._get_category_for_row(cause_tuple)

                # safe integer
                try:
                    count = int(val)
                except Exception:
                    try:
                        count = int(float(val))
                    except Exception:
                        count = 1

                for _ in range(max(0, count)):
                    rows.append({
                        "gender": col[1],
                        "age_group": col[0],
                        "location": location_name,
                        "latitude": lat,
                        "longitude": lng,
                        "category": cat["Categoria General"] if cat else None,
                        "subcategory": cat["Subcategoria"] if cat else None,
                        "factor": cat["Factor/Patología"] if cat else None,
                        "subtype": cat["Subtipo"] if cat else None,
                    })
        return pd.DataFrame(rows)

    def _build_df(self):
        df_list = [
            self._process_block(block)
            for block in self._blocks[1:-1]
            if "Comuna" not in str(block.iloc[0, 0])
        ]
        self.df_formatted = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame(
            columns=["gender", "age_group", "location", "latitude", "longitude", "category", "subcategory", "factor", "subtype"]
        )

    # ------------------------------
    # Exports
    # ------------------------------
    def export_csv(self, output_csv: str = "data.csv"):
        if self.df_formatted is None:
            raise RuntimeError("Data not built.")
        self.df_formatted.to_csv(output_csv, index=False, encoding="utf-8")

    def export_map(
        self,
        output_html: str = "map.html",
        center: Optional[Tuple[float, float]] = None,
        zoom_start: int = 13,
        max_zoom: int = 19,
        disable_clustering_at_zoom: int = 19,
    ):
        if self.df_formatted is None:
            raise RuntimeError("Data not built.")

        df = self.df_formatted
        df = df.dropna(subset=["latitude", "longitude"])
        if center is None and not df.empty:
            center = (df["latitude"].astype(float).mean(), df["longitude"].astype(float).mean())
        if center is None:
            center = (-33.024565894230584, -71.55182778531538)  # fallback

        m = folium.Map(location=center, zoom_start=zoom_start, max_zoom=max_zoom)
        cluster = MarkerCluster(name="points", disableClusteringAtZoom=disable_clustering_at_zoom).add_to(m)

        for _, row in df.iterrows():
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            popup_text = str(row.get("location", ""))
            folium.Marker(location=[lat, lon], popup=popup_text).add_to(cluster)

        m.save(output_html)