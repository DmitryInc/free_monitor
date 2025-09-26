import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as ctx
import pandas as pd
import numpy as np
import matplotlib.transforms as transforms
import matplotlib.patches as patches
from shapely.geometry import Point
import os
import random
from typing import List, Tuple, Optional
from svgpath2mpl import parse_path
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from zoneinfo import ZoneInfo
from matplotlib import font_manager
from core.config import (
    COLORS, LABEL, NO_TARGETS_MESSAGE, UA_NAME_MAP, 
    EXCLUDED_CITIES, WEAPON_ICONS, 
    WEAPON_ICON_ROTATION_OFFSET_DEG, WEAPON_COLORS
)
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
load_dotenv()

class VisualMap:
    def __init__(self, full_json_data: dict):
        self.full_json_data = full_json_data
        self.shapes_path = "shapes"
        self.channel_name = os.getenv("TELEGRAM_CHANNEL")

        self._geodata_cache = {}
        self._svg_cache = {}
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            ukraine_future = executor.submit(self.load_ukraine)
            regions_future = executor.submit(self.load_regions)
            cities_future = executor.submit(self.load_ukraine_cities)
            
            self.ukraine = ukraine_future.result()
            self.regions = regions_future.result()
            self.cities = cities_future.result()
        
        self.target_data = self._get_target_data()
        self.target_point = [target['point'] for target in self.target_data]
        self.region_target_mapping = None

    def _get_target_data(self) -> List[dict]:
        """Get target data from the full JSON data with complete information
        
        Returns:
            List[dict]: Target data with coordinates, weapon type, count, and city info
        """
        target_data = []

        for region in self.full_json_data['regions']:
            for target in region['targets']:
                target_point = Point(target['longitude'], target['latitude'])
                target_info = {
                    'point': target_point,
                    'weapon_type': target.get('weapon_type', 'БпЛА'),
                    'count': target.get('count', 1),
                    'city': target.get('city', ''),
                    'region': region.get('region', '')
                }
                target_data.append(target_info)

        return target_data

    def _first_existing(self, paths: List[str]) -> str | None:
        """Find the first existing path in the list
        
        Args:
            paths: List of paths

        Returns:
            Str: First existing path | None
        """
        
        return next((p for p in paths if os.path.exists(p)), None)

    def load_ukraine(self) -> gpd.GeoDataFrame:
        """Load Ukraine from shapefile
        
        Returns:
            GeoDataFrame: Ukraine
        """
        
        out_dir = "ne_10m_admin_0_countries"
        shp_candidates = [
            os.path.join(self.shapes_path, out_dir, "ne_10m_admin_0_countries.shp"),
            os.path.join(self.shapes_path, "ne_10m_admin_0_countries.shp"),
        ]
        shp_path = self._first_existing(shp_candidates)

        admin0 = gpd.read_file(shp_path)
        ukraine = admin0[admin0["ADMIN"] == "Ukraine"].to_crs("EPSG:4326")
        if ukraine.empty:
            raise RuntimeError("Не знайдено полігон України у admin_0")
        return ukraine

    def load_regions(self) -> gpd.GeoDataFrame:
        """Load regions from shapefile
        
        Returns:
            GeoDataFrame: Regions
        """
        
        out_dir = "ne_10m_admin_1_states_provinces"
        shp_candidates = [
            os.path.join(
                self.shapes_path, out_dir, "ne_10m_admin_1_states_provinces.shp"
            ),
            os.path.join(
                self.shapes_path, "ne_10m_admin_1_states_provinces.shp"
            ),
        ]
        shp_path = self._first_existing(shp_candidates)
        admin1 = gpd.read_file(shp_path).to_crs("EPSG:4326")
        return admin1

    def add_crimea(self, ua_admin0: gpd.GeoDataFrame, admin1_all: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """Add Crimea to Ukraine dataframe
        
        Args:
            ua_admin0: Ukraine GeoDataFrame
            admin1_all: Regions GeoDataFrame

        Returns:
            tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]: Ukraine GeoDataFrame, Regions GeoDataFrame
        """
        crimea_mask = admin1_all["iso_3166_2"].astype(str).isin(["UA-43", "UA-40"]) if "iso_3166_2" in admin1_all.columns else False
        
        oblasts_ua = pd.concat([
            admin1_all[admin1_all.get("admin").astype(str) == "Ukraine"],
            admin1_all[crimea_mask]
        ]).drop_duplicates().reset_index(drop=True)

        union_geom = ua_admin0.unary_union.union(oblasts_ua.unary_union)
        ukraine_union = gpd.GeoDataFrame(geometry=[union_geom], crs=ua_admin0.crs)
        return ukraine_union, oblasts_ua

    def get_south_ukraine_point(self) -> Point:
        """Calculate the southern point of Ukraine for arrow starting point
        
        Returns:
            Point: Southern point of Ukraine
        """
        
        bounds = self.ukraine.total_bounds
        south_longitude = (bounds[0] + bounds[2]) / 2 
        south_latitude = bounds[1] + (bounds[3] - bounds[1]) * 0.15
        return Point(south_longitude, south_latitude)

    def match_targets_to_regions(self) -> List[Tuple[Point, List[dict], any]]:
        """Find which targets belong to which regions and return the centroids of regions with geometry
        
        Returns:
            List[Tuple[Point, List[dict], any]]: Region target mapping with full target info
        """
        _, oblasts = self.add_crimea(self.ukraine, self.regions)
        
        region_target_mapping = []
        
        for _, region in oblasts.iterrows():
            if region.geometry is None:
                continue
                
            region_targets = []
            for target_info in self.target_data:
                target_point = target_info['point']
                target_gdf = gpd.GeoDataFrame([1], geometry=[target_point], crs='EPSG:4326')
                
                if target_gdf.within(region.geometry).any():
                    region_targets.append(target_info)
            
            if region_targets:
                region_centroid = region.geometry.centroid
                region_target_mapping.append((region_centroid, region_targets, region.geometry))
        
        return region_target_mapping

    def load_ukraine_cities(self) -> gpd.GeoDataFrame | None:
        """Load Ukraine cities from shapefile
        
        Returns:
            GeoDataFrame: Ukraine cities | None
        """
        out_dir = "ne_10m_populated_places"
        shp_candidates = [
            os.path.join(
                self.shapes_path, out_dir, "ne_10m_populated_places.shp"
            ),
            os.path.join(
                self.shapes_path, "ne_10m_populated_places.shp"
            ),
        ]
        
        shp_path = self._first_existing(shp_candidates)
        if not shp_path:
            return None
            
        try:
            places = gpd.read_file(shp_path).to_crs("EPSG:4326")
            
            ukraine_places = places[places.get("ADM0_A3") == "UKR"].copy()
            if ukraine_places.empty:
                return None

            name_col = next((col for col in ["NAME", "NAME_EN", "NAMEascii"] if col in ukraine_places.columns), "NAME")
            ukraine_places = ukraine_places.rename(columns={name_col: 'city'})
            
            return ukraine_places[["city", "geometry"]]
        except Exception:
            return None
    
    def _setup_figure_and_axes(self) -> tuple:
        """Setup figure and axes for map
        
        Returns:
            tuple: Figure, Axes, DPI
        """
        target_w_px, target_h_px = 1920, 1080
        dpi = 200
        fig_w_in, fig_h_in = target_w_px / dpi, target_h_px / dpi

        fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in), dpi=dpi, facecolor=COLORS['background'])
        ax.set_facecolor(COLORS['background'])
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        return fig, ax, dpi

    def _setup_map_bounds_and_basemap(self, ax, ukraine_3857) -> None:
        """Setup map bounds and add base map
        
        Args:
            ax: Axes object
            ukraine_3857: Ukraine GeoDataFrame

        Returns:
            None
        """
        bounds = ukraine_3857.total_bounds
        minx, miny, maxx, maxy = bounds
        width = maxx - minx
        height = maxy - miny

        target_aspect = 1920 / 1080
        current_aspect = width / height if height != 0 else target_aspect

        pad = 0.02
        if current_aspect < target_aspect:
            needed_w = target_aspect * height
            delta = (needed_w - width) / 2
            minx -= delta
            maxx += delta

        elif current_aspect > target_aspect:
            needed_h = width / target_aspect
            delta = (needed_h - height) / 2
            miny -= delta
            maxy += delta

        ax.set_xlim(minx - width * pad, maxx + width * pad)
        ax.set_ylim(miny - height * pad, maxy + height * pad)

        ctx.add_basemap(
            ax,
            source=ctx.providers.CartoDB.DarkMatterNoLabels,
            attribution=False,
            alpha=1.0
        )

    def _draw_ukraine_and_regions(self, ax, ukraine_3857, oblasts_3857) -> None:
        """Draw Ukraine territory and region borders
        
        Args:
            ax: Axes object
            ukraine_3857: Ukraine GeoDataFrame
            oblasts_3857: Oblasts GeoDataFrame

        Returns:
            None
        """
        ukraine_3857.plot(
            ax=ax,
            color=COLORS['ukraine_fill'],
            alpha=0.6,
            edgecolor=COLORS['border_line'], 
            linewidth=1.2,
            zorder=1
        )
        oblasts_3857.boundary.plot(ax=ax, color=COLORS['region_line'], linewidth=0.6, alpha=0.9, zorder=2)

    def _draw_cities(self, ax) -> None:
        """Draw cities and their names
        
        Args:
            ax: Axes object

        Returns:
            None
        """
        if 'city' in self.cities.columns:
            self.cities['city'] = self.cities['city'].apply(lambda x: UA_NAME_MAP.get(x, x))

        cities_3857 = self.cities.to_crs(3857)
        cities_filtered = cities_3857[~cities_3857['city'].str.lower().isin(EXCLUDED_CITIES)]

        cities_filtered.plot(
            ax=ax,
            color=COLORS['city_point'],
            markersize=4,
            alpha=0.9,
            edgecolor=COLORS['city_point_edge'],
            linewidth=0.5,
        )

        for _, row in cities_filtered.iterrows():
            name = str(row['city'])
            ax.text(
                row.geometry.x,
                row.geometry.y + 15000,
                name,
                fontsize=5,
                color=COLORS['city_label'],
                ha='center',
                va='bottom',
                weight='bold',
                alpha=0.95,
            )

    def _canon_weapon_type(self, value: str) -> str:
        """Return canonical weapon type: 'БпЛА' | 'х101' | 'Балістика'
        
        Args:
            value: Weapon type

        Returns:
            Str: Canonical weapon type
        """
        if not value:
            return 'БпЛА'
        
        s = str(value).strip().lower()
        
        match s:
            case 'uav' | 'бпла' | 'дрон' | 'дрон-камікадзе' | 'шахед' | 'shahed' | 'гермес' | 'бпа' | 'бплА':
                return 'БпЛА'
            case 'x101' | 'х101' | 'крилата ракета' | 'крилатая ракета' | 'cruise' | 'cruise_missile':
                return 'х101'
            case 'balistic' | 'ballistic' | 'балістика' | 'баллистика' | 'кинжал' | 'kinzhal':
                return 'Балістика'
            case _:
                return 'БпЛА'

    def _parse_svg_to_paths(self, icon_path: str) -> Optional[List]:
        """Cached function for parsing SVG
        
        Args:
            icon_path: Path to the SVG icon

        Returns:
            List: List of paths
        """
        cache_key = f"svg_{icon_path}"
        if cache_key in self._svg_cache:
            return self._svg_cache[cache_key]
        
        try:
            tree = ET.parse(icon_path)
            root = tree.getroot()
            
            ns = '{http://www.w3.org/2000/svg}'
            path_elems = list(root.iter(ns+'path')) if root.tag.startswith('{') else list(root.iter('path'))
            
            if not path_elems:
                self._svg_cache[cache_key] = None
                return None

            min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
            mpl_paths = []
            
            for p in path_elems:
                d = p.get('d')
                if d:
                    mpl_path = parse_path(d)
                    mpl_paths.append(mpl_path)
                    verts = mpl_path.vertices
                    if verts.size > 0:
                        min_x = min(min_x, float(np.min(verts[:, 0])))
                        min_y = min(min_y, float(np.min(verts[:, 1])))
                        max_x = max(max_x, float(np.max(verts[:, 0])))
                        max_y = max(max_y, float(np.max(verts[:, 1])))

            result = {
                'paths': mpl_paths,
                'bounds': (min_x, min_y, max_x, max_y)
            }
            
            self._svg_cache[cache_key] = result
            return result
            
        except Exception as e:
            self._svg_cache[cache_key] = None
            return None

    def _add_svg_icon_patch(self, ax, weapon_type, angle_radians, arrow_color, x, y) -> None:
        """Add SVG icon as vector PathPatch with rotation and coloring under the line color.
        
        Args:
            ax: Axes object
            weapon_type: Weapon type
            angle_radians: Angle in radians
            arrow_color: Color of the arrow
            x: X coordinate of the icon
            y: Y coordinate of the icon

        Returns:
            None
        """
        icon_path = WEAPON_ICONS.get(weapon_type, WEAPON_ICONS['БпЛА'])
        
        svg_data = self._parse_svg_to_paths(icon_path)
        if not svg_data:
            return
        
        mpl_paths = svg_data['paths']
        min_x, min_y, max_x, max_y = svg_data['bounds']
        
        ax_w = ax.get_xlim()[1] - ax.get_xlim()[0]
        icon_w = ax_w * 0.015
        
        if weapon_type in ('х101', 'Балістика'):
            p0 = ax.transData.transform((0.0, 0.0))
            p1 = (p0[0] + 15.0, p0[1])
            data_dx = ax.transData.inverted().transform(p1)[0] - ax.transData.inverted().transform(p0)[0]
            icon_w += data_dx

        content_w = max(max_x - min_x, 1e-6)
        content_h = max(max_y - min_y, 1e-6)
        content_cx = (min_x + max_x) / 2.0
        content_cy = (min_y + max_y) / 2.0
        scale_ratio = icon_w / max(content_w, content_h)

        angle_deg = np.degrees(angle_radians)
        icon_offset = WEAPON_ICON_ROTATION_OFFSET_DEG.get(weapon_type, 0.0)
        
        transform = (
            transforms.Affine2D()
            .translate(-content_cx, -content_cy)
            .scale(scale_ratio)
            .rotate_deg(angle_deg + icon_offset)
            .translate(x, y)
        ) + ax.transData

        for mpl_path in mpl_paths:
            patch = patches.PathPatch(
                mpl_path,
                facecolor=arrow_color,
                edgecolor=arrow_color,
                lw=1.0,
                transform=transform,
                zorder=15
            )
            ax.add_patch(patch)
    
    def _find_icon_position(self, target_xy, base_angle, region_boundary, placed_positions) -> Tuple[float, float, float]:
        """Find the best position for the icon, avoiding overlaps
        
        Args:
            target_xy: Target coordinates
            base_angle: Base angle
            region_boundary: Region boundary
            placed_positions: Placed positions

        Returns:
            Tuple[float, float, float]: X, Y, angle
        """
        distances = (15000, 20000, 24000, 28000)
        min_separation = 18000
        
        angle_offsets = (0, 0.26, -0.26, 0.52, -0.52, 0.79, -0.79, 1.05, -1.05)
        for dist in distances:
            for offset in angle_offsets:
                angle = base_angle + offset
                x = target_xy.x - np.cos(angle) * dist
                y = target_xy.y - np.sin(angle) * dist
                
                too_close = any(
                    np.hypot(x - px, y - py) < min_separation 
                    for px, py in placed_positions
                )
                if too_close:
                    continue
                
                if region_boundary and not region_boundary.buffer(0).contains(Point(x, y)):
                    continue
                    
                return x, y, angle
        
        x = target_xy.x - np.cos(base_angle) * distances[-1]
        y = target_xy.y - np.sin(base_angle) * distances[-1]
        return x, y, base_angle

    def _draw_weapon_icon_and_line(self, ax, weapon_type, target_xy, angle, arrow_color, region_boundary, placed_positions) -> Tuple[float, float]:
        """Draw weapon icon and line on the map
        
        Args:
            ax: Axes object
            weapon_type: Weapon type
            target_xy: Target coordinates
            angle: Angle of the arrow
            arrow_color: Color of the arrow
            region_boundary: Region boundary
            placed_positions: Placed positions

        Returns:
            Tuple[float, float]: Icon coordinates (x, y)
        """
        icon_x, icon_y, used_angle = self._find_icon_position(target_xy, angle, region_boundary, placed_positions)
        placed_positions.append((icon_x, icon_y))

        self._add_svg_icon_patch(ax, weapon_type, used_angle, arrow_color, icon_x, icon_y)

        unit_dx = np.cos(used_angle)
        unit_dy = np.sin(used_angle)

        icon_size = (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.015
        if weapon_type in ('х101', 'Балістика'):
            offset = icon_size / 2.0 + 17000
        else:
            offset = icon_size / 2.0 + 10000 

        line_start_x = icon_x + unit_dx * offset
        line_start_y = icon_y + unit_dy * offset
        line_end_x = line_start_x + unit_dx * 25000
        line_end_y = line_start_y + unit_dy * 25000

        ax.plot(
            [line_start_x, line_end_x],
            [line_start_y, line_end_y],
            color=arrow_color,
            linewidth=1.0,
            alpha=0.8,
            solid_capstyle='round',
            zorder=14
        )
        

        return icon_x, icon_y

    def _draw_arrows(self, ax) -> None:
        """Draw arrows on the map
        
        Args:
            ax: Axes object

        Returns:
            None
        """
        self.region_target_mapping = self.match_targets_to_regions()
        
        for region_data in self.region_target_mapping:
            _, region_targets = region_data[:2]
            region_geometry = region_data[2] if len(region_data) > 2 else None
            
            region_boundary = None
            if region_geometry:
                region_geom_3857 = gpd.GeoDataFrame([1], geometry=[region_geometry], crs='EPSG:4326').to_crs(3857)
                region_boundary = region_geom_3857.iloc[0].geometry
            
            placed_positions = []
            
            for target_data_item in region_targets:
                if isinstance(target_data_item, dict):
                    target_point = target_data_item['point']
                    weapon_type = target_data_item['weapon_type']
                    weapon_count = target_data_item['count']
                elif isinstance(target_data_item, tuple) and len(target_data_item) == 2:
                    target_point, weapon_type = target_data_item
                    weapon_count = 1 
                else:
                    target_point = target_data_item
                    weapon_type = 'БпЛА'
                    weapon_count = 1
                
                target_gdf = gpd.GeoDataFrame([1], geometry=[target_point], crs='EPSG:4326').to_crs(3857)
                target_xy = target_gdf.iloc[0].geometry
                
                canonical_type = self._canon_weapon_type(weapon_type)
                arrow_color = WEAPON_COLORS.get(canonical_type, COLORS['arrow'])

                base_angle = np.pi * 3/4
                angle = base_angle + random.uniform(-np.pi/24, np.pi/24)
                
                icon_x, icon_y = self._draw_weapon_icon_and_line(ax, canonical_type, target_xy, angle, arrow_color, region_boundary, placed_positions)
                
                self._add_weapon_count_text(ax, icon_x, icon_y, weapon_count)

    def _add_weapon_count_text(self, ax, icon_x, icon_y, count) -> None:
        """Add weapon count text over the icon
        
        Args:
            ax: Axes object
            icon_x: Icon X coordinate
            icon_y: Icon Y coordinate
            count: Weapon count to display

        Returns:
            None
        """
        ax.text(
            icon_x, icon_y,
            str(count),
            fontsize=5,
            color='#FFE8BF',
            weight='bold',
            ha='center',
            va='center',
            zorder=20,
        )

    def _add_digital_information(self, base_img: Image.Image) -> Image.Image:
        """Add digital information to the map
        
        Args:
            base_img: Base image

        Returns:
            Image.Image: Final image with digital information
        """
        counts: dict[str, int] = {}
        try:
            for region in self.full_json_data.get('regions', []):
                for tgt in region.get('targets', []):
                    wtype = tgt.get('weapon_type')
                    c = int(tgt.get('count', 1) or 1)
                    canonical = self._canon_weapon_type(wtype)
                    counts[canonical] = counts.get(canonical, 0) + c
        except Exception:
            for target_info in self.target_data:
                wtype = target_info.get('weapon_type', 'БпЛА')
                c = int(target_info.get('count', 1) or 1)
                canonical = self._canon_weapon_type(wtype)
                counts[canonical] = counts.get(canonical, 0) + c

        dt_str = datetime.now(ZoneInfo('Europe/Kyiv')).strftime('%d.%m.%Y %H:%M')
        
        img = base_img.convert('RGBA')
        draw = ImageDraw.Draw(img)
        W, H = 1920, 1080
        
        font = ImageFont.truetype(font_manager.findfont('DejaVu Sans'), 28)
        default_color = WEAPON_COLORS.get('БпЛА', '#CE983C')
        
        x, y = 24, H - 280
        
        self._draw_source_info_above_panels(draw, x, y, W, H)
        
        y += 40 
        
        self._draw_info_panel(draw, x, y, LABEL, COLORS['info_text_color'], font, W, H)
        self._draw_info_panel(draw, x + 260, y, dt_str, COLORS['info_text_color'], font, W, H)
        
        y += 58
        
        has_targets = any(counts.get(weapon_type, 0) > 0 for weapon_type in ('БпЛА', 'х101', 'Балістика'))
        
        if has_targets:
            for weapon_type in ('БпЛА', 'х101', 'Балістика'):
                if counts.get(weapon_type, 0) > 0:
                    label = f"{counts[weapon_type]} x {weapon_type}"
                    color = WEAPON_COLORS.get(weapon_type, default_color)
                    self._draw_info_panel(draw, x, y, label, color, font, W, H)
                    y += 50
        else:
            self._draw_no_targets_message(draw, x+30, y, W, H)
                
        return img
    
    def _draw_no_targets_message(self, draw, x, y, W, H) -> None:
        """Draw simple white text message when no targets found
        
        Args:
            draw: Draw object
            x: X coordinate
            y: Y coordinate  
            W: Width of the map
            H: Height of the map

        Returns:
            None
        """
        big_font = ImageFont.truetype(font_manager.findfont('DejaVu Sans'), 30)
        
        
        current_y = y
        for line in NO_TARGETS_MESSAGE:
            draw.text(
                (x, current_y), 
                line, 
                font=big_font, 
                fill='white' 
            )
            current_y += 45
    
    def _draw_source_info_above_panels(self, draw, x, y, W, H) -> None:
        """Draw source channel information above main info panels
        
        Args:
            draw: Draw object
            x: X coordinate
            y: Y coordinate
            W: Width of the map
            H: Height of the map

        Returns:
            None
        """
        source_text = f"Data visualized based on TG channel: {self.channel_name or "@kudy_letyt"}"
        small_font = ImageFont.truetype(font_manager.findfont('DejaVu Sans'), 16)
        text_color = (255, 255, 255, 128)
        draw.text((x, y), source_text, font=small_font, fill=text_color)
        
    def _draw_info_panel(self, draw, x, y, text, color, font, W, H) -> None:
        """Draw one information panel with support for multiline text
        
        Args:
            draw: Draw object
            x: X coordinate of the panel
            y: Y coordinate of the panel
            text: Text to draw (supports \n for line breaks)
            color: Color of the text
            font: Font object
            W: Width of the map
            H: Height of the map

        Returns:
            None
        """
        lines = text.split('\n')
        
        line_heights = []
        max_width = 0
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            line_heights.append((line_height, bbox[1])) 
            max_width = max(max_width, line_width)
        
        total_height = sum(height for height, _ in line_heights) + (len(lines) - 1) * 5
        w, h = max_width + 36, total_height + 20
        
        overlay = Image.new(
            'RGBA',
            (W, H),
            (0, 0, 0, 0)
        )

        ov_draw = ImageDraw.Draw(overlay)
        ov_draw.rounded_rectangle(
            (x, y, x + w, y + h),
            radius=12, 
            fill=(11, 13, 17, 230),
            outline=(26, 32, 44, 255),
            width=2
        )
        
        current_y = y + 10
        for i, line in enumerate(lines):
            line_height, y_offset = line_heights[i]
            tx = x + 18
            ty = current_y - y_offset
            ov_draw.text((tx, ty), line, font=font, fill=color)
            current_y += line_height + 5  
        
        base_img = Image.new('RGBA', (W, H))
        base_img.alpha_composite(overlay)
        draw._image.alpha_composite(base_img)

    def _finalize_and_save_map(self, fig, ax, dpi) -> None:
        """Finalize and save the map
        
        Args:
            fig: Figure object
            ax: Axes object
            dpi: DPI of the map

        Returns:
            True if the map is saved successfully
        """
        ax.set_aspect('equal')
        ax.set_axis_off()
        ax.grid(False)
        plt.tight_layout(pad=0)

        buf = BytesIO()
        fig.savefig(buf, dpi=dpi, bbox_inches=None, pad_inches=0, facecolor=COLORS['background'], edgecolor='none', format='png')
        buf.seek(0)

        base_img = Image.open(buf)
        final_img = self._add_digital_information(base_img)
        if final_img.size != (1920, 1080):
            final_img = final_img.resize((1920, 1080), Image.Resampling.LANCZOS)
        name = datetime.now(ZoneInfo('Europe/Kyiv')).strftime('%d.%m.%Y;%H:%M')
        final_img.save(f'gened_maps/map_{name}.png')
        return True

    def create_map(self) -> None:
        """Main method for creating the map - coordinates all stages of visualization
        
        Returns:
            None
        """
        
        fig, ax, dpi = self._setup_figure_and_axes()
        
        ukraine_id = id(self.ukraine)
        regions_id = id(self.regions)
        
        cache_key_3857 = f"ukraine_3857_{ukraine_id}_{regions_id}"
        cache_key_oblasts = f"oblasts_3857_{ukraine_id}_{regions_id}"
        
        if cache_key_3857 not in self._geodata_cache:
            ukraine_area, oblasts = self.add_crimea(self.ukraine, self.regions)
            ukraine_3857 = ukraine_area.to_crs(3857)
            oblasts_3857 = oblasts.to_crs(3857)
            
            self._geodata_cache[cache_key_3857] = ukraine_3857
            self._geodata_cache[cache_key_oblasts] = oblasts_3857
        else:
            ukraine_3857 = self._geodata_cache[cache_key_3857]
            oblasts_3857 = self._geodata_cache[cache_key_oblasts]
        
        self._setup_map_bounds_and_basemap(ax, ukraine_3857)
        
        self._draw_ukraine_and_regions(ax, ukraine_3857, oblasts_3857)
        self._draw_cities(ax)
        self._draw_arrows(ax)
        
        self._finalize_and_save_map(fig, ax, dpi)