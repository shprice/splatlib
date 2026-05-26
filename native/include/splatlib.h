#pragma once

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------
 * Platform export macros
 * ---------------------------------------------------------------------- */
#ifdef _WIN32
  #ifdef SPLATLIB_EXPORTS
    #define SPLATLIB_API __declspec(dllexport)
  #else
    #define SPLATLIB_API __declspec(dllimport)
  #endif
#else
  #define SPLATLIB_API __attribute__((visibility("default")))
#endif

/* -------------------------------------------------------------------------
 * Error codes
 * ---------------------------------------------------------------------- */
#define SPLAT_OK           0
#define SPLAT_ERR_INVALID -1   /* null pointer or out-of-range argument */
#define SPLAT_ERR_TERRAIN -2   /* terrain profile is malformed */
#define SPLAT_ERR_MODEL   -3   /* unsupported propagation model */

/* -------------------------------------------------------------------------
 * Propagation model selection
 * ---------------------------------------------------------------------- */
typedef enum splat_model
{
    SPLAT_MODEL_ITM   = 0,  /* Longley-Rice ITM (faster, well-validated) */
    SPLAT_MODEL_ITWOM = 1   /* ITWOM v3.0 (more accurate at short ranges) */
} splat_model_t;

/* -------------------------------------------------------------------------
 * Ground / terrain type
 * ---------------------------------------------------------------------- */
typedef enum splat_ground
{
    SPLAT_GROUND_AVERAGE    = 0,  /* Average ground:       eps=15,  sigma=0.005  */
    SPLAT_GROUND_SEA        = 1,  /* Salt water / sea:     eps=80,  sigma=5.0    */
    SPLAT_GROUND_FRESH_WATER= 2,  /* Fresh water / lakes:  eps=80,  sigma=0.01   */
    SPLAT_GROUND_URBAN      = 3,  /* Urban / industrial:   eps=5,   sigma=0.001  */
    SPLAT_GROUND_DESERT     = 4,  /* Desert / poor ground: eps=3,   sigma=0.001  */
    SPLAT_GROUND_WOODLAND   = 5,  /* Woodland / wet ground:eps=12,  sigma=0.01   */
} splat_ground_t;

/* -------------------------------------------------------------------------
 * Propagation environment parameters
 *
 * Pass NULL to any function that accepts this struct to use library defaults
 * (average ground, vertical polarisation, continental temperate climate,
 *  50% confidence / 50% reliability).
 * ---------------------------------------------------------------------- */
typedef struct splat_propagation
{
    splat_ground_t ground;        /* ground / surface type                         */
    int            polarz;        /* 0 = vertical polarisation, 1 = horizontal      */
    int            radio_climate; /* ITM climate zone 1–7 (5 = continental temperate)
                                     1=equatorial  2=continental subtropical
                                     3=maritime subtropical  4=desert
                                     5=continental temperate (default)
                                     6=maritime temperate inland
                                     7=maritime temperate oceanic                   */
    double         conf;          /* confidence level  0.01–0.99 (0.50 = median)    */
    double         rel;           /* time reliability  0.01–0.99 (0.50 = median)    */
} splat_propagation_t;

/* -------------------------------------------------------------------------
 * Core types
 * ---------------------------------------------------------------------- */

/* A transmitter, receiver, or jammer site. */
typedef struct splat_site
{
    double lat;               /* WGS-84 latitude,  decimal degrees */
    double lon;               /* WGS-84 longitude, decimal degrees */
    double antenna_height_m;  /* height above ground level, metres */
    double erp_dbm;           /* effective radiated power, dBm (TX/jammer only) */
    double gain_dbi;          /* antenna gain, dBi */
} splat_site_t;

/*
 * Pre-sampled terrain elevation profile between two points.
 * Populated by the caller (C# layer) from whatever terrain source is in use
 * (Cesium, SRTM, etc.).  The library never allocates or frees this data.
 */
typedef struct splat_profile
{
    const double* heights_m; /* terrain elevations, metres ASL, equally spaced */
    int           count;     /* number of samples (>= 2) */
    double        spacing_m; /* distance between consecutive samples, metres */
} splat_profile_t;

/* Result of a point-to-point propagation analysis. */
typedef struct splat_path_result
{
    double path_loss_db;         /* median path loss (dB) */
    double received_power_dbm;   /* received power at RX antenna (dBm) */
    double distance_m;           /* great-circle distance TX→RX (metres) */
    double elevation_angle_deg;  /* depression angle at TX looking toward RX */
    int    line_of_sight;        /* 1 = unobstructed LOS exists */
    double fresnel_clearance_m;  /* clearance of first Fresnel zone at tightest point */
} splat_path_result_t;

/* Interference / jamming result at a single receiver point. */
typedef struct splat_interference_result
{
    double signal_dbm;    /* received desired signal (dBm) */
    double jammer_dbm;    /* received jammer power (dBm) */
    double js_ratio_db;   /* J/S = jammer_dbm - signal_dbm (dB) */
    int    jammed;        /* 1 if js_ratio_db >= supplied threshold */
} splat_interference_result_t;

/* -------------------------------------------------------------------------
 * Library lifecycle
 * ---------------------------------------------------------------------- */

/* Initialise the library.  Must be called before any analysis function. */
SPLATLIB_API int splat_init(void);

/* Release any library-level resources. */
SPLATLIB_API void splat_shutdown(void);

/* Returns a human-readable string for an error code (never NULL). */
SPLATLIB_API const char* splat_error_string(int error_code);

/* -------------------------------------------------------------------------
 * Analysis functions
 *
 * All functions are thread-safe when called with independent data.
 * The caller must ensure terrain profile arrays remain valid for the
 * duration of the call.
 * ---------------------------------------------------------------------- */

/*
 * Point-to-point propagation analysis.
 * terrain: pre-sampled elevation profile along the TX→RX great-circle path.
 * prop:    propagation environment parameters; pass NULL for library defaults.
 */
SPLATLIB_API int splat_point_to_point(
    const splat_site_t*          tx,
    const splat_site_t*          rx,
    const splat_profile_t*       terrain,
    double                       freq_mhz,
    splat_model_t                model,
    const splat_propagation_t*   prop,     /* NULL = defaults */
    splat_path_result_t*         result
);

/*
 * Interference / jamming analysis at a single receiver point.
 * signal_terrain: elevation profile along signal_tx → rx.
 * jammer_terrain: elevation profile along jammer_tx → rx.
 * js_threshold_db: J/S ratio (dB) at which the link is considered jammed.
 * prop:           propagation environment parameters; pass NULL for defaults.
 */
SPLATLIB_API int splat_interference_point(
    const splat_site_t*          signal_tx,
    const splat_site_t*          jammer_tx,
    const splat_site_t*          rx,
    const splat_profile_t*       signal_terrain,
    const splat_profile_t*       jammer_terrain,
    double                       freq_mhz,
    double                       js_threshold_db,
    splat_model_t                model,
    const splat_propagation_t*   prop,     /* NULL = defaults */
    splat_interference_result_t* result
);

#ifdef __cplusplus
}
#endif
