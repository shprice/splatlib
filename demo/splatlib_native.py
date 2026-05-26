"""
ctypes bindings for splatlib.dll / libsplatlib.so.

Mirrors the C API in native/include/splatlib.h.
The shared library is resolved from:
  1. The same directory as this file (splatlib.dll / libsplatlib.so)
  2. System library path
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load the shared library
# ---------------------------------------------------------------------------

def _load_library() -> ctypes.CDLL:
    here = Path(__file__).parent
    if sys.platform == "win32":
        candidates = [here / "splatlib.dll"]
    elif sys.platform == "darwin":
        candidates = [here / "libsplatlib.dylib", here / "libsplatlib.so"]
    else:
        candidates = [here / "libsplatlib.so"]

    for path in candidates:
        if path.exists():
            return ctypes.CDLL(str(path))

    raise FileNotFoundError(
        "splatlib shared library not found. "
        "Build it with CMake and copy splatlib.dll/.so into the demo/ directory."
    )


_lib = _load_library()

# ---------------------------------------------------------------------------
# Struct definitions (must match splatlib.h exactly)
# ---------------------------------------------------------------------------

class SplatSite(ctypes.Structure):
    """Mirrors splat_site_t."""
    _fields_ = [
        ("lat",               ctypes.c_double),
        ("lon",               ctypes.c_double),
        ("antenna_height_m",  ctypes.c_double),
        ("erp_dbm",           ctypes.c_double),
        ("gain_dbi",          ctypes.c_double),
    ]


class SplatProfile(ctypes.Structure):
    """
    Mirrors splat_profile_t.
    64-bit layout: ptr(8) + int(4) + pad(4) + double(8) = 24 bytes.
    """
    _fields_ = [
        ("heights_m", ctypes.POINTER(ctypes.c_double)),
        ("count",     ctypes.c_int),
        ("spacing_m", ctypes.c_double),    # natural alignment adds 4-byte pad before this
    ]


class SplatPathResult(ctypes.Structure):
    """Mirrors splat_path_result_t."""
    _fields_ = [
        ("path_loss_db",        ctypes.c_double),
        ("received_power_dbm",  ctypes.c_double),
        ("distance_m",          ctypes.c_double),
        ("elevation_angle_deg", ctypes.c_double),
        ("line_of_sight",       ctypes.c_int),
        ("fresnel_clearance_m", ctypes.c_double),
    ]


class SplatInterferenceResult(ctypes.Structure):
    """Mirrors splat_interference_result_t."""
    _fields_ = [
        ("signal_dbm",  ctypes.c_double),
        ("jammer_dbm",  ctypes.c_double),
        ("js_ratio_db", ctypes.c_double),
        ("jammed",      ctypes.c_int),
    ]


class SplatPropagation(ctypes.Structure):
    """
    Mirrors splat_propagation_t.
    Propagation environment parameters — ground type, polarisation, climate,
    confidence and reliability percentiles.
    Pass ctypes.byref(SplatPropagation(...)) or None (→ NULL) for library defaults.
    """
    _fields_ = [
        ("ground",        ctypes.c_int),     # splat_ground_t enum
        ("polarz",        ctypes.c_int),     # 0=vertical, 1=horizontal
        ("radio_climate", ctypes.c_int),     # 1–7
        ("conf",          ctypes.c_double),  # confidence  0.01–0.99
        ("rel",           ctypes.c_double),  # reliability 0.01–0.99
    ]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Propagation model
SPLAT_MODEL_ITM   = 0
SPLAT_MODEL_ITWOM = 1

# Ground type (splat_ground_t)
SPLAT_GROUND_AVERAGE     = 0
SPLAT_GROUND_SEA         = 1
SPLAT_GROUND_FRESH_WATER = 2
SPLAT_GROUND_URBAN       = 3
SPLAT_GROUND_DESERT      = 4
SPLAT_GROUND_WOODLAND    = 5

# Radio climate zones
SPLAT_CLIMATE_EQUATORIAL              = 1
SPLAT_CLIMATE_CONTINENTAL_SUBTROPICAL = 2
SPLAT_CLIMATE_MARITIME_SUBTROPICAL    = 3
SPLAT_CLIMATE_DESERT                  = 4
SPLAT_CLIMATE_CONTINENTAL_TEMPERATE   = 5   # default
SPLAT_CLIMATE_MARITIME_TEMPERATE_INL  = 6
SPLAT_CLIMATE_MARITIME_TEMPERATE_OCE  = 7

# Error codes
SPLAT_OK          =  0
SPLAT_ERR_INVALID = -1
SPLAT_ERR_TERRAIN = -2

# ---------------------------------------------------------------------------
# Function prototypes
# ---------------------------------------------------------------------------

_lib.splat_init.restype  = ctypes.c_int
_lib.splat_init.argtypes = []

_lib.splat_shutdown.restype  = None
_lib.splat_shutdown.argtypes = []

_lib.splat_error_string.restype  = ctypes.c_char_p
_lib.splat_error_string.argtypes = [ctypes.c_int]

_lib.splat_point_to_point.restype  = ctypes.c_int
_lib.splat_point_to_point.argtypes = [
    ctypes.POINTER(SplatSite),           # tx
    ctypes.POINTER(SplatSite),           # rx
    ctypes.POINTER(SplatProfile),        # terrain
    ctypes.c_double,                     # freq_mhz
    ctypes.c_int,                        # model
    ctypes.POINTER(SplatPropagation),    # prop (NULL = defaults)
    ctypes.POINTER(SplatPathResult),     # result (out)
]

_lib.splat_interference_point.restype  = ctypes.c_int
_lib.splat_interference_point.argtypes = [
    ctypes.POINTER(SplatSite),              # signal_tx
    ctypes.POINTER(SplatSite),              # jammer_tx
    ctypes.POINTER(SplatSite),              # rx
    ctypes.POINTER(SplatProfile),           # signal_terrain
    ctypes.POINTER(SplatProfile),           # jammer_terrain
    ctypes.c_double,                        # freq_mhz
    ctypes.c_double,                        # js_threshold_db
    ctypes.c_int,                           # model
    ctypes.POINTER(SplatPropagation),       # prop (NULL = defaults)
    ctypes.POINTER(SplatInterferenceResult),# result (out)
]

# ---------------------------------------------------------------------------
# High-level Python wrappers
# ---------------------------------------------------------------------------

_initialized = False


def ensure_init() -> None:
    global _initialized
    if not _initialized:
        rc = _lib.splat_init()
        if rc != SPLAT_OK:
            raise RuntimeError(f"splat_init failed: {rc}")
        _initialized = True


def shutdown() -> None:
    global _initialized
    if _initialized:
        _lib.splat_shutdown()
        _initialized = False


def make_site(lat: float, lon: float,
              antenna_height_m: float = 10.0,
              erp_dbm: float = 43.0,
              gain_dbi: float = 2.15) -> SplatSite:
    return SplatSite(lat=lat, lon=lon,
                     antenna_height_m=antenna_height_m,
                     erp_dbm=erp_dbm,
                     gain_dbi=gain_dbi)


def make_propagation(
    ground: int = SPLAT_GROUND_AVERAGE,
    polarz: int = 0,
    radio_climate: int = SPLAT_CLIMATE_CONTINENTAL_TEMPERATE,
    conf: float = 0.50,
    rel: float = 0.50,
) -> SplatPropagation:
    """Build a SplatPropagation struct.  Pass ctypes.byref(result) to point_to_point."""
    return SplatPropagation(
        ground=ground,
        polarz=polarz,
        radio_climate=radio_climate,
        conf=conf,
        rel=rel,
    )


def point_to_point(
    tx: SplatSite,
    rx_lat: float, rx_lon: float,
    heights_m: "np.ndarray",
    spacing_m: float,
    freq_mhz: float,
    rx_height_m: float = 2.0,
    rx_gain_dbi: float = 0.0,
    model: int = SPLAT_MODEL_ITWOM,
    prop: "SplatPropagation | None" = None,
) -> SplatPathResult:
    """
    Run a single point-to-point propagation analysis.

    heights_m:   numpy float64 array of terrain elevations along the TX→RX path.
    spacing_m:   distance between consecutive samples in metres.
    rx_height_m: receiver antenna height above ground (m).
    rx_gain_dbi: receiver antenna gain (dBi); added to received_power_dbm by the DLL.
    prop:        SplatPropagation instance (ground type, polarisation, climate,
                 confidence, reliability).  None → library defaults.
    """
    ensure_init()
    import numpy as np
    h = np.ascontiguousarray(heights_m, dtype=np.float64)
    rx = SplatSite(lat=rx_lat, lon=rx_lon,
                   antenna_height_m=rx_height_m,
                   gain_dbi=rx_gain_dbi)
    profile = SplatProfile(
        heights_m=h.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        count=len(h),
        spacing_m=spacing_m,
    )
    result = SplatPathResult()
    prop_ptr = ctypes.byref(prop) if prop is not None else None
    rc = _lib.splat_point_to_point(
        ctypes.byref(tx), ctypes.byref(rx), ctypes.byref(profile),
        freq_mhz, model, prop_ptr, ctypes.byref(result),
    )
    if rc != SPLAT_OK:
        raise RuntimeError(f"splat_point_to_point failed: {rc}")
    return result


def interference_point(
    signal_tx: SplatSite,
    jammer_tx: SplatSite,
    rx_lat: float, rx_lon: float,
    signal_heights_m: "np.ndarray", signal_spacing_m: float,
    jammer_heights_m: "np.ndarray", jammer_spacing_m: float,
    freq_mhz: float,
    js_threshold_db: float = 6.0,
    model: int = SPLAT_MODEL_ITWOM,
    prop: "SplatPropagation | None" = None,
) -> SplatInterferenceResult:
    ensure_init()
    import numpy as np
    sh = np.ascontiguousarray(signal_heights_m, dtype=np.float64)
    jh = np.ascontiguousarray(jammer_heights_m, dtype=np.float64)
    rx = SplatSite(lat=rx_lat, lon=rx_lon, antenna_height_m=2.0)
    sig_profile = SplatProfile(
        heights_m=sh.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        count=len(sh), spacing_m=signal_spacing_m,
    )
    jam_profile = SplatProfile(
        heights_m=jh.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        count=len(jh), spacing_m=jammer_spacing_m,
    )
    result = SplatInterferenceResult()
    prop_ptr = ctypes.byref(prop) if prop is not None else None
    rc = _lib.splat_interference_point(
        ctypes.byref(signal_tx), ctypes.byref(jammer_tx), ctypes.byref(rx),
        ctypes.byref(sig_profile), ctypes.byref(jam_profile),
        freq_mhz, js_threshold_db, model, prop_ptr,
        ctypes.byref(result),
    )
    if rc != SPLAT_OK:
        raise RuntimeError(f"splat_interference_point failed: {rc}")
    return result
