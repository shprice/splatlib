"""
SplatLib demo server.

Uses native splatlib (ITM/ITWOM propagation) + SRTM terrain when available,
falling back to FSPL (free-space) if the native library or terrain data
cannot be loaded.

Usage:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import math
import uuid as _uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="SplatLib Demo")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# ---------------------------------------------------------------------------
# Native library + SRTM (optional — graceful fallback to FSPL)
# ---------------------------------------------------------------------------

_splat = None
_terrain_provider = None
_native_available = False
_terrain_available = False

# Thread pool for blocking terrain + propagation work (keeps event loop free)
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="splatlib")

# Per-request progress tracking: task_id → completion % (0–100).
# Dict writes are GIL-protected so this is safe across the thread pool.
_task_progress: dict[str, float] = {}

# Number of terrain samples per profile path (trades accuracy vs speed)
_TERRAIN_SAMPLES = 64

# ITWOM/ITM is rated for paths ≥ 1 km.  Below this distance the model can
# over-predict path loss.  We fall back to FSPL for any path shorter than
# this threshold to avoid spurious "dead rings" around transmitters.
_MIN_ITM_DIST_M = 1_000.0

try:
    import splatlib_native as _splat_mod
    _splat_mod.ensure_init()
    _splat = _splat_mod
    _native_available = True
    logger.info("Native splatlib loaded — ITM/ITWOM propagation enabled.")
except Exception as exc:
    logger.warning("Native splatlib not available (%s) — falling back to FSPL.", exc)

if _native_available:
    try:
        from terrain_srtm import SrtmProvider  # type: ignore[import]
        _terrain_provider = SrtmProvider()
        _terrain_available = True
        logger.info("SRTM terrain provider initialised.")
    except Exception as exc:
        logger.warning("SRTM terrain not available (%s).", exc)


@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str) -> dict:
    """Poll computation progress for a running task. Returns {pct: 0–100}."""
    return {"pct": _task_progress.get(task_id, 0.0)}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class EmitterConfig(BaseModel):
    lat: float
    lon: float
    antenna_height_m: float = 10.0
    erp_dbm: float = Field(43.0, description="Effective radiated power (dBm). 43 dBm ≈ 20 W.")
    gain_dbi: float = 2.15
    freq_mhz: float = 450.0


class GridConfig(BaseModel):
    center_lat: float | None = None
    center_lon: float | None = None
    radius_m: float = 50_000
    resolution: int = Field(128, ge=32, le=512)


class CoverageRequest(BaseModel):
    emitter: EmitterConfig
    grid: GridConfig = GridConfig()
    rx_sensitivity_dbm: float = -100.0
    dynamic_range_db: float = 60.0
    use_terrain: bool = Field(True, description="Use native ITM/ITWOM + SRTM terrain if available.")


class JammingRequest(BaseModel):
    jammer_txs: list[EmitterConfig] = Field(..., min_length=1, description="One or more jamming transmitters.")
    rx_height_m: float = Field(1.0, ge=0.1, le=200.0, description="Receiver antenna height above ground (m).")
    jam_threshold_dbm: float = Field(
        -100.0,
        description=(
            "Received jammer power (dBm) above which the receiver is considered jammed. "
            "Cells below this level are shown green (safe to travel to)."
        ),
    )
    grid: GridConfig = GridConfig()
    use_terrain: bool = Field(True, description="Use native ITM/ITWOM + SRTM terrain if available.")


class Bounds(BaseModel):
    west: float
    south: float
    east: float
    north: float


class CoverageResponse(BaseModel):
    image_b64: str
    image_b64_top: str | None = None   # Second (top) layer — used for J/S overlays
    bounds: Bounds
    stats: dict


# ---------------------------------------------------------------------------
# Grid / geometry helpers
# ---------------------------------------------------------------------------

def _metres_to_deg_lat(m: float) -> float:
    return m / 111_320.0


def _metres_to_deg_lon(m: float, lat: float) -> float:
    return m / (111_320.0 * math.cos(math.radians(lat)))


def _make_grid(
    grid: GridConfig,
    fallback_lat: float,
    fallback_lon: float,
) -> tuple[np.ndarray, np.ndarray, Bounds]:
    cx = grid.center_lat if grid.center_lat is not None else fallback_lat
    cy = grid.center_lon if grid.center_lon is not None else fallback_lon
    dlat = _metres_to_deg_lat(grid.radius_m)
    dlon = _metres_to_deg_lon(grid.radius_m, cx)
    bounds = Bounds(west=cy - dlon, south=cx - dlat, east=cy + dlon, north=cx + dlat)
    lats = np.linspace(bounds.north, bounds.south, grid.resolution)
    lons = np.linspace(bounds.west, bounds.east, grid.resolution)
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    return lat_grid, lon_grid, bounds


def _haversine(lat1: float, lon1: float, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    R = 6_371_000.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat / 2) ** 2
         + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2)
    return 2.0 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# ---------------------------------------------------------------------------
# FSPL fallback
# ---------------------------------------------------------------------------

def _fspl_db(distance_m: np.ndarray, freq_mhz: float) -> np.ndarray:
    """Free-space path loss: FSPL(dB) = -27.55 + 20·log10(d_m) + 20·log10(f_MHz)."""
    d = np.maximum(distance_m, 1.0)
    return -27.55 + 20.0 * np.log10(d) + 20.0 * np.log10(freq_mhz)


def _received_power_fspl(emitter: EmitterConfig, lat_grid: np.ndarray, lon_grid: np.ndarray) -> np.ndarray:
    dist = _haversine(emitter.lat, emitter.lon, lat_grid, lon_grid)
    loss = _fspl_db(dist, emitter.freq_mhz)
    return emitter.erp_dbm + emitter.gain_dbi - loss


# ---------------------------------------------------------------------------
# Native ITM/ITWOM + SRTM computation (runs in thread pool)
# ---------------------------------------------------------------------------

def _native_coverage_grid(
    emitter: EmitterConfig,
    lat_grid: np.ndarray,
    lon_grid: np.ndarray,
    task_id: str | None = None,
) -> tuple[np.ndarray, str]:
    """
    Compute received-power grid using ITWOM + SRTM terrain.
    Returns (power_dBm array of same shape as lat_grid, model label string).

    Runs synchronously — call via run_in_executor to avoid blocking the event loop.
    """
    terrain = _terrain_provider

    if task_id is not None:
        _task_progress[task_id] = 2.0

    terrain.prefetch(
        lat_min=float(lat_grid.min()), lat_max=float(lat_grid.max()),
        lon_min=float(lon_grid.min()), lon_max=float(lon_grid.max()),
    )

    if task_id is not None:
        _task_progress[task_id] = 5.0

    power = _itm_power_grid(
        emitter, lat_grid, lon_grid, terrain,
        rx_height_m=2.0,
        task_id=task_id, progress_base=5.0, progress_span=90.0,
    )
    return power, "ITM/ITWOM + SRTM terrain"


def _itm_power_grid(
    em: EmitterConfig,
    lat_grid: np.ndarray,
    lon_grid: np.ndarray,
    terrain,
    rx_height_m: float = 2.0,
    task_id: str | None = None,
    progress_base: float = 0.0,
    progress_span: float = 100.0,
) -> np.ndarray:
    """
    Helper: compute received-power grid (dBm) for a single TX using ITWOM + SRTM.
    Terrain tiles must already be prefetched before calling.

    task_id / progress_base / progress_span: optional progress reporting.
    The function updates _task_progress[task_id] from progress_base to
    progress_base + progress_span as it sweeps the grid.
    """
    H, W = lat_grid.shape
    profiles = terrain.sample_profiles_grid(
        em.lat, em.lon, lat_grid, lon_grid, n_samples=_TERRAIN_SAMPLES,
    )
    dist_m = _haversine(em.lat, em.lon, lat_grid, lon_grid)
    spacing_m = dist_m / max(_TERRAIN_SAMPLES - 1, 1)
    tx = _splat.make_site(
        lat=em.lat, lon=em.lon,
        antenna_height_m=em.antenna_height_m,
        erp_dbm=em.erp_dbm,
        gain_dbi=em.gain_dbi,
    )
    power = np.full((H, W), -200.0, dtype=np.float64)
    total = H * W
    update_every = max(total // 50, 1)   # ~50 progress ticks across the grid
    done = 0
    for i in range(H):
        for j in range(W):
            spc = float(spacing_m[i, j])
            d_m = float(dist_m[i, j])
            if spc < 1.0:
                power[i, j] = em.erp_dbm + em.gain_dbi
            elif d_m < _MIN_ITM_DIST_M:
                # Too close for reliable ITWOM — substitute FSPL to avoid
                # the spurious high-loss "dead ring" around the transmitter.
                fspl = -27.55 + 20.0 * math.log10(max(d_m, 1.0)) + 20.0 * math.log10(em.freq_mhz)
                power[i, j] = em.erp_dbm + em.gain_dbi - fspl
            else:
                try:
                    res = _splat.point_to_point(
                        tx,
                        float(lat_grid[i, j]), float(lon_grid[i, j]),
                        profiles[i, j], spc, em.freq_mhz,
                        rx_height_m=rx_height_m,
                    )
                    power[i, j] = res.received_power_dbm
                except Exception:
                    pass
            done += 1
            if task_id is not None and done % update_every == 0:
                _task_progress[task_id] = progress_base + (done / total) * progress_span
    return power


def _native_jam_grid(
    jammer_ems: list[EmitterConfig],
    lat_grid: np.ndarray,
    lon_grid: np.ndarray,
    rx_height_m: float,
    task_id: str | None = None,
) -> tuple[np.ndarray, str]:
    """
    Compute incoherent combined jammer power (dBm) at every grid cell using
    ITWOM + SRTM terrain.  Each cell represents a potential receiver position
    at height rx_height_m; cells below the jam threshold are safe to travel to.

    Jammers combine as an incoherent power sum (linear mW then back to dBm).
    Progress is reported across [5 %, 95 %], split evenly among jammers.
    """
    terrain = _terrain_provider

    if task_id is not None:
        _task_progress[task_id] = 2.0

    terrain.prefetch(
        lat_min=float(lat_grid.min()), lat_max=float(lat_grid.max()),
        lon_min=float(lon_grid.min()), lon_max=float(lon_grid.max()),
    )

    if task_id is not None:
        _task_progress[task_id] = 5.0

    n = len(jammer_ems)
    span_each = 90.0 / n   # each jammer gets an equal slice of the 5→95 % range
    jam_mw = np.zeros(lat_grid.shape, dtype=np.float64)
    for idx, em in enumerate(jammer_ems):
        p = _itm_power_grid(
            em, lat_grid, lon_grid, terrain, rx_height_m,
            task_id=task_id,
            progress_base=5.0 + idx * span_each,
            progress_span=span_each,
        )
        jam_mw += np.power(10.0, p / 10.0)
    with np.errstate(divide='ignore'):
        combined = 10.0 * np.log10(np.maximum(jam_mw, 1e-30))
    label = (f"ITM/ITWOM + SRTM  "
             f"({n} jammer{'s' if n > 1 else ''}, RX {rx_height_m:.1f} m)")
    return combined, label


def _fspl_jam_grid(
    jammer_ems: list[EmitterConfig],
    lat_grid: np.ndarray,
    lon_grid: np.ndarray,
) -> tuple[np.ndarray, str]:
    """FSPL fallback: combined jammer power grid (rx_height_m has no effect on FSPL)."""
    jam_mw = np.zeros(lat_grid.shape, dtype=np.float64)
    for em in jammer_ems:
        jam_mw += np.power(10.0, _received_power_fspl(em, lat_grid, lon_grid) / 10.0)
    with np.errstate(divide='ignore'):
        combined = 10.0 * np.log10(np.maximum(jam_mw, 1e-30))
    n = len(jammer_ems)
    label = f"FSPL  ({n} jammer{'s' if n > 1 else ''})"
    return combined, label


# ---------------------------------------------------------------------------
# Image generation
# ---------------------------------------------------------------------------

def _signal_to_rgba(
    power: np.ndarray,
    rx_sensitivity_dbm: float,
    dynamic_range_db: float,
) -> np.ndarray:
    """Map signal strength to RGBA. Transparent below sensitivity threshold."""
    above = power >= rx_sensitivity_dbm
    norm = np.clip((power - rx_sensitivity_dbm) / dynamic_range_db, 0.0, 1.0)
    # Red (at threshold) → yellow → green (strong)
    r = np.where(above, np.clip(255 * (1.0 - norm * 0.85), 20, 255), 0).astype(np.uint8)
    g = np.where(above, np.clip(255 * (norm * 0.9 + 0.1), 20, 255), 0).astype(np.uint8)
    b = np.zeros(power.shape, dtype=np.uint8)
    a = np.where(above, 175, 0).astype(np.uint8)
    return np.stack([r, g, b, a], axis=2)


def _rag_rgba(power: np.ndarray, threshold_db: float) -> np.ndarray:
    """
    Red-Amber-Green colormap centred on threshold_db.

    The 40 dB window around the threshold is mapped to five colour stops:

      ≤ −20 dB rel. threshold  →  deep green   (definitely safe)
        −10 dB rel. threshold  →  yellow-green
          0 dB  (at threshold) →  amber / orange
        +10 dB rel. threshold  →  orange-red
      ≥ +20 dB rel. threshold  →  deep red      (heavily jammed)

    np.interp handles arbitrary-shape arrays natively.
    """
    span = 40.0  # total dB window (−20 … +20 around threshold)
    norm = np.clip((power - threshold_db + span / 2.0) / span, 0.0, 1.0)

    xp = [0.00, 0.25, 0.50, 0.75, 1.00]
    r = np.interp(norm, xp, [ 35, 120, 255, 255, 200]).astype(np.uint8)
    g = np.interp(norm, xp, [200, 210, 155,  55,  20]).astype(np.uint8)
    b = np.interp(norm, xp, [ 60,  30,   0,   0,   0]).astype(np.uint8)
    a = np.full(power.shape, 185, dtype=np.uint8)
    return np.stack([r, g, b, a], axis=2)


def _rgba_to_b64(rgba: np.ndarray) -> str:
    img = Image.fromarray(rgba, "RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/coverage", response_model=CoverageResponse)
async def compute_coverage(
    req: CoverageRequest,
    task_id: str | None = None,
) -> CoverageResponse:
    lat_grid, lon_grid, bounds = _make_grid(req.grid, req.emitter.lat, req.emitter.lon)

    use_native = req.use_terrain and _native_available and _terrain_available

    if use_native:
        if task_id:
            _task_progress[task_id] = 0.0
        logger.info(
            "Coverage: ITM/ITWOM %dx%d grid, %d terrain samples/path",
            req.grid.resolution, req.grid.resolution, _TERRAIN_SAMPLES,
        )
        loop = asyncio.get_running_loop()
        power, model_name = await loop.run_in_executor(
            _executor,
            lambda: _native_coverage_grid(req.emitter, lat_grid, lon_grid, task_id),
        )
    else:
        power = _received_power_fspl(req.emitter, lat_grid, lon_grid)
        model_name = "FSPL (free-space)"
        if req.use_terrain and not _native_available:
            model_name += " — native splatlib not loaded"
        elif req.use_terrain and not _terrain_available:
            model_name += " — SRTM terrain not available"

    if task_id:
        _task_progress.pop(task_id, None)
    rgba = _signal_to_rgba(power, req.rx_sensitivity_dbm, req.dynamic_range_db)
    above = power >= req.rx_sensitivity_dbm
    stats = {
        "model": model_name,
        "coverage_pct": float(above.mean() * 100),
        "max_signal_dbm": float(power.max()),
        "edge_signal_dbm": float(power[above].min()) if above.any() else None,
    }
    return CoverageResponse(image_b64=_rgba_to_b64(rgba), bounds=bounds, stats=stats)


@app.post("/api/interference", response_model=CoverageResponse)
async def compute_interference(
    req: JammingRequest,
    task_id: str | None = None,
) -> CoverageResponse:
    """
    Compute a jammer-coverage map.

    Each grid cell represents a potential receiver location at rx_height_m above
    ground.  The combined (incoherent) received power from all jammers is computed
    at every cell; cells above jam_threshold_dbm are shown red (jammed), those
    below are shown green (safe to travel to).
    """
    # Centre the grid on the midpoint of all jammers
    avg_lat = sum(e.lat for e in req.jammer_txs) / len(req.jammer_txs)
    avg_lon = sum(e.lon for e in req.jammer_txs) / len(req.jammer_txs)
    lat_grid, lon_grid, bounds = _make_grid(req.grid, avg_lat, avg_lon)

    use_native = req.use_terrain and _native_available and _terrain_available
    n_j = len(req.jammer_txs)

    if use_native:
        if task_id:
            _task_progress[task_id] = 0.0
        logger.info(
            "Jamming: ITM/ITWOM %dx%d grid, %d jammer(s), RX %.1f m, %d terrain samples/path",
            req.grid.resolution, req.grid.resolution, n_j, req.rx_height_m, _TERRAIN_SAMPLES,
        )
        loop = asyncio.get_running_loop()
        jammer_power, model_name = await loop.run_in_executor(
            _executor,
            lambda: _native_jam_grid(req.jammer_txs, lat_grid, lon_grid, req.rx_height_m, task_id),
        )
    else:
        jammer_power, model_name = _fspl_jam_grid(req.jammer_txs, lat_grid, lon_grid)
        if req.use_terrain and not _native_available:
            model_name += " — native lib not loaded"
        elif req.use_terrain and not _terrain_available:
            model_name += " — SRTM not available"

    if task_id:
        _task_progress.pop(task_id, None)

    # Single Red-Amber-Green image: green = safe, amber = marginal, red = jammed.
    rgba = _rag_rgba(jammer_power, req.jam_threshold_dbm)
    jammed   = jammer_power >= req.jam_threshold_dbm
    marginal = (jammer_power >= req.jam_threshold_dbm - 10.0) & ~jammed
    stats = {
        "model": model_name,
        "jammed_area_pct":   float(jammed.mean()   * 100),
        "marginal_area_pct": float(marginal.mean()  * 100),
        "max_jam_dbm":  float(jammer_power.max()),
        "min_jam_dbm":  float(jammer_power.min()),
        "threshold_dbm": req.jam_threshold_dbm,
    }
    return CoverageResponse(
        image_b64=_rgba_to_b64(rgba),
        bounds=bounds,
        stats=stats,
    )


# ---------------------------------------------------------------------------
# Evaporation duct (pywaveprop / parabolic equation)
# ---------------------------------------------------------------------------

_duct_available = False
try:
    from rwp.environment import Troposphere, evaporation_duct  # type: ignore[import]
    from rwp.sspade import (  # type: ignore[import]
        TroposphericRadioWaveSSPadePropagator,
        HelmholtzPropagatorComputationalParams,
        GaussAntenna,
    )
    import matplotlib  # type: ignore[import]
    matplotlib.use("Agg")          # non-interactive backend — must be set before pyplot import
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    _duct_available = True
    logger.info("pywaveprop (rwp) loaded — evaporation duct propagation enabled.")
except Exception as _duct_exc:
    logger.warning("pywaveprop not available (%s) — duct endpoint will return 503.", _duct_exc)


class DuctRequest(BaseModel):
    freq_mhz:      float = Field(3000.0, ge=100.0,  le=30_000.0, description="Carrier frequency (MHz).")
    tx_height_m:   float = Field(10.0,   ge=0.5,    le=500.0,    description="Transmitter antenna height (m).")
    duct_height_m: float = Field(15.0,   ge=1.0,    le=200.0,    description="Evaporation duct height (m).")
    max_range_km:  float = Field(100.0,  ge=5.0,    le=500.0,    description="Maximum propagation range (km).")
    max_height_m:  float = Field(300.0,  ge=50.0,   le=2_000.0,  description="Maximum display height (m).")
    polarz:        str   = Field("H",    pattern="^[HVhv]$",     description="Polarisation: H or V.")


class DuctResponse(BaseModel):
    image_b64: str
    stats: dict


def _compute_duct(req: DuctRequest) -> DuctResponse:
    """Run a 2-D parabolic-equation propagation and return a path-loss heatmap."""
    freq_hz   = req.freq_mhz * 1e6
    wavelength = 3e8 / freq_hz

    # Environment: evaporation duct M-profile (homogeneous along range)
    env = Troposphere()
    env.M_profile = lambda x, z: evaporation_duct(height=req.duct_height_m, z_grid_m=z)

    # Source: narrow Gaussian beam aimed at horizon
    antenna = GaussAntenna(
        freq_hz=freq_hz,
        height=req.tx_height_m,
        beam_width=3,
        elevation_angle=0,
        polarz=req.polarz.upper(),
    )

    max_range_m = req.max_range_km * 1e3

    # Grid resolution: ~500 m range steps; ≤2 m vertical steps (capped at 500 points)
    dx_wl  = max(500.0   / wavelength, 50.0)
    dz_wl  = max(req.max_height_m / 500.0 / wavelength, 1.0)

    params = HelmholtzPropagatorComputationalParams(
        max_height_m=req.max_height_m,
        dx_wl=dx_wl,
        dz_wl=dz_wl,
    )

    prop = TroposphericRadioWaveSSPadePropagator(
        antenna=antenna,
        env=env,
        max_range_m=max_range_m,
        comp_params=params,
    )
    f  = prop.calculate()
    pl = f.path_loss()

    # pl.field shape: (n_range, n_height) — transpose so rows=height for imshow
    x_km = pl.x_grid / 1_000.0
    z_m  = pl.z_grid
    data = pl.field.T  # (n_height, n_range)

    # Clip to 2nd–98th percentile to avoid extreme outliers near TX distorting colours
    p2, p98 = float(np.nanpercentile(data, 2)), float(np.nanpercentile(data, 98))
    data_clamp = np.clip(data, p2, p98)

    # ---- Matplotlib figure (dark theme to match UI) -------------------------
    # Larger figure + higher DPI so text stays crisp when displayed at panel width
    fig, ax = plt.subplots(figsize=(14, 5), facecolor="#0c101e")
    ax.set_facecolor("#0c101e")

    # RdYlGn_r: green=low loss (ducting), red=high loss (blocked)
    im = ax.imshow(
        data_clamp,
        origin="lower",
        aspect="auto",
        extent=[float(x_km[0]), float(x_km[-1]), float(z_m[0]), float(z_m[-1])],
        cmap="RdYlGn_r",
        interpolation="bilinear",
        vmin=p2,
        vmax=p98,
    )

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Path loss (dB)", color="#d8e0f0", fontsize=9)
    cbar.ax.yaxis.set_tick_params(color="#d8e0f0", labelcolor="#d8e0f0")
    plt.setp(plt.getp(cbar.ax.axes, "yticklabels"), color="#d8e0f0")

    ax.set_xlabel("Range (km)",  color="#d8e0f0", fontsize=10)
    ax.set_ylabel("Height (m)", color="#d8e0f0", fontsize=10)
    ax.tick_params(colors="#d8e0f0")
    for spine in ax.spines.values():
        spine.set_color("#46485a")

    ax.set_title(
        f"Evaporation duct — {req.freq_mhz:.0f} MHz  |  "
        f"Duct {req.duct_height_m:.0f} m  |  TX {req.tx_height_m:.0f} m  |  Pol {req.polarz.upper()}",
        color="#4a9eff", fontsize=10, pad=8,
    )

    # Reference lines
    ax.axhline(req.tx_height_m,   color="#ffffff", linewidth=0.8,
               linestyle="--", alpha=0.55, label=f"TX height ({req.tx_height_m:.0f} m)")
    ax.axhline(req.duct_height_m, color="#ffa040", linewidth=1.0,
               linestyle=":",  alpha=0.85, label=f"Duct ceiling ({req.duct_height_m:.0f} m)")
    ax.legend(fontsize=8, facecolor="#0c101e", labelcolor="#d8e0f0",
              edgecolor="#46485a", loc="upper right")

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, facecolor="#0c101e")
    plt.close(fig)

    image_b64 = base64.b64encode(buf.getvalue()).decode()

    stats = {
        "freq_mhz":      req.freq_mhz,
        "duct_height_m": req.duct_height_m,
        "tx_height_m":   req.tx_height_m,
        "max_range_km":  req.max_range_km,
        "polarz":        req.polarz.upper(),
        "pl_min_db":     round(p2,  1),
        "pl_max_db":     round(p98, 1),
        "pl_range_db":   round(p98 - p2, 1),
    }
    return DuctResponse(image_b64=image_b64, stats=stats)


@app.get("/api/capabilities")
async def capabilities() -> dict:  # type: ignore[override]  # shadows earlier def
    return {
        "native_propagation": _native_available,
        "srtm_terrain":       _terrain_available,
        "duct_propagation":   _duct_available,
    }


@app.post("/api/duct", response_model=DuctResponse)
async def compute_duct(req: DuctRequest) -> DuctResponse:
    """
    Compute a 2-D range × height path-loss field using a parabolic equation
    (pywaveprop / SSPadé) with an evaporation duct M-profile.

    Returns a dark-themed PNG heatmap (base64) showing the duct trapping effect.
    """
    if not _duct_available:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="pywaveprop not installed")

    logger.info(
        "Duct: %.0f MHz  duct %.0f m  tx %.0f m  range %.0f km  pol %s",
        req.freq_mhz, req.duct_height_m, req.tx_height_m, req.max_range_km, req.polarz.upper(),
    )
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, lambda: _compute_duct(req))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
