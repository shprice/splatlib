"""
SRTM terrain elevation provider for the SplatLib demo.

Downloads SRTM 3-arcsecond HGT tiles (1° × 1°, 1201 × 1201 points, ~90 m resolution)
via the srtm.py package and exposes fast vectorised numpy lookups.

Tiles are cached in %TEMP%/srtm/ on Windows, /tmp/srtm/ on Linux.
"""

from __future__ import annotations

import math
import tempfile
import threading
from pathlib import Path

import numpy as np
import srtm as _srtm_lib   # pip install srtm.py


class SrtmProvider:
    """
    Thread-safe SRTM tile loader with vectorised bilinear interpolation.

    Typical usage
    -------------
    provider = SrtmProvider()
    provider.prefetch(lat_min=51, lat_max=54, lon_min=-3, lon_max=1)
    heights = provider.sample_profile(52.48, -1.89, 53.48, -2.24, n_samples=128)
    """

    def __init__(self) -> None:
        self._cache_dir = Path(tempfile.gettempdir()) / "srtm"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        # Force SRTM3 (3 arc-second, 1201×1201) — our tile reader assumes this resolution.
        # srtm1=False prevents accidentally downloading 3601×3601 SRTM1 tiles.
        self._downloader = _srtm_lib.get_data(
            srtm1=False, srtm3=True,
            local_cache_dir=str(self._cache_dir),
        )
        self._tiles: dict[tuple[int, int], np.ndarray | None] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Tile management
    # ------------------------------------------------------------------

    def _tile_filename(self, lat_floor: int, lon_floor: int) -> str:
        ns = "N" if lat_floor >= 0 else "S"
        ew = "E" if lon_floor >= 0 else "W"
        return f"{ns}{abs(lat_floor):02d}{ew}{abs(lon_floor):03d}.hgt"

    def _load_tile(self, lat_floor: int, lon_floor: int) -> np.ndarray | None:
        key = (lat_floor, lon_floor)
        with self._lock:
            if key in self._tiles:
                return self._tiles[key]

        # Trigger download via srtm.py (single lookup forces the file to be fetched)
        self._downloader.get_elevation(lat_floor + 0.5, lon_floor + 0.5)

        fname = self._tile_filename(lat_floor, lon_floor)
        fpath = self._cache_dir / fname

        if fpath.exists():
            raw = np.fromfile(fpath, dtype=">i2").reshape(1201, 1201).astype(np.float32)
            raw[raw == -32768] = 0  # void-fill SRTM no-data
            tile: np.ndarray | None = raw
        else:
            tile = None  # ocean tile or not available

        with self._lock:
            self._tiles[key] = tile
        return tile

    def prefetch(self, lat_min: float, lat_max: float,
                 lon_min: float, lon_max: float) -> None:
        """Pre-download every tile that covers the given bounding box."""
        for lat in range(math.floor(lat_min), math.ceil(lat_max)):
            for lon in range(math.floor(lon_min), math.ceil(lon_max)):
                self._load_tile(lat, lon)

    # ------------------------------------------------------------------
    # Vectorised elevation lookup
    # ------------------------------------------------------------------

    def get_elevations(self, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
        """
        Return terrain elevations (metres ASL) at arbitrary lat/lon arrays.
        Uses bilinear interpolation within each 1° × 1° SRTM tile.
        """
        lats = np.asarray(lats, dtype=np.float64)
        lons = np.asarray(lons, dtype=np.float64)
        result = np.zeros(lats.shape, dtype=np.float32)

        lat_floors = np.floor(lats).astype(int)
        lon_floors = np.floor(lons).astype(int)

        for key in set(zip(lat_floors.ravel(), lon_floors.ravel())):
            tlf, tlg = key
            mask = (lat_floors == tlf) & (lon_floors == tlg)
            tile = self._load_tile(tlf, tlg)
            if tile is None:
                continue  # ocean — leave as 0

            tlats = lats[mask]
            tlons = lons[mask]

            # Row 0 = north edge (lat_floor + 1), row 1200 = south edge (lat_floor)
            rows = np.clip((1.0 - (tlats - tlf)) * 1200.0, 0.0, 1200.0)
            cols = np.clip((tlons - tlg) * 1200.0, 0.0, 1200.0)

            r0 = rows.astype(int).clip(0, 1200)
            c0 = cols.astype(int).clip(0, 1200)
            r1 = (r0 + 1).clip(0, 1200)
            c1 = (c0 + 1).clip(0, 1200)
            dr = (rows - r0).astype(np.float32)
            dc = (cols - c0).astype(np.float32)

            result[mask] = (
                tile[r0, c0] * (1 - dr) * (1 - dc)
                + tile[r0, c1] * (1 - dr) * dc
                + tile[r1, c0] * dr * (1 - dc)
                + tile[r1, c1] * dr * dc
            )

        return result

    # ------------------------------------------------------------------
    # Profile sampling
    # ------------------------------------------------------------------

    def sample_profile(
        self,
        from_lat: float, from_lon: float,
        to_lat: float, to_lon: float,
        n_samples: int,
    ) -> np.ndarray:
        """
        Sample terrain elevations at n_samples equally-spaced points along
        the straight-line (lat/lon interpolated) path from → to.
        Returns float32 array of length n_samples.
        """
        lats = np.linspace(from_lat, to_lat, n_samples)
        lons = np.linspace(from_lon, to_lon, n_samples)
        return self.get_elevations(lats, lons)

    def sample_profiles_grid(
        self,
        from_lat: float, from_lon: float,
        to_lat_grid: np.ndarray, to_lon_grid: np.ndarray,
        n_samples: int,
    ) -> np.ndarray:
        """
        Vectorised: sample terrain profiles from a single origin to every
        point on a 2-D grid.

        Returns an array of shape (*grid_shape, n_samples).
        """
        shape = to_lat_grid.shape
        n_points = to_lat_grid.size

        flat_to_lats = to_lat_grid.ravel()
        flat_to_lons = to_lon_grid.ravel()

        # Build all sample-point coordinates at once:
        #   axis 0 = grid point index  (n_points)
        #   axis 1 = sample index      (n_samples)
        t = np.linspace(0.0, 1.0, n_samples)  # (n_samples,)

        all_lats = from_lat + np.outer(flat_to_lats - from_lat, t)  # (n_points, n_samples)
        all_lons = from_lon + np.outer(flat_to_lons - from_lon, t)

        heights = self.get_elevations(all_lats, all_lons)   # (n_points, n_samples)
        return heights.reshape(*shape, n_samples)
