#include "splatlib.h"
#include "propagation/itwom3.0.h"   // contains both point_to_point_ITM and point_to_point (ITWOM)

#include <cmath>
#include <cstring>
#include <new>

/* -------------------------------------------------------------------------
 * Internal helpers
 * ---------------------------------------------------------------------- */

static bool g_initialized = false;

/*
 * Build the elevation array in the format expected by ITM / ITWOM:
 *   elev[0]       = number of terrain intervals (count - 1)
 *   elev[1]       = interval spacing, metres
 *   elev[2..n+1]  = terrain heights, metres ASL
 *
 * elev_t is double when ITM_ELEV_DOUBLE is defined (set in CMakeLists.txt).
 */
static elev_t* build_itm_elev(const splat_profile_t* p)
{
    elev_t* elev = new (std::nothrow) elev_t[p->count + 2];
    if (!elev) return nullptr;
    elev[0] = static_cast<elev_t>(p->count - 1);
    elev[1] = static_cast<elev_t>(p->spacing_m);
    for (int i = 0; i < p->count; ++i)
        elev[i + 2] = static_cast<elev_t>(p->heights_m[i]);
    return elev;
}

/* Typical default atmospheric / ground parameters for terrestrial RF. */
static constexpr double EPS_DIELECT       = 15.0;   /* earth dielectric constant */
static constexpr double SGM_CONDUCTIVITY  = 0.005;  /* earth conductivity, S/m   */
static constexpr double ENO_NS_SURFREF    = 301.0;  /* surface refractivity, N-units */
static constexpr int    RADIO_CLIMATE     = 5;      /* 5 = continental temperate */
static constexpr int    POL_VERTICAL      = 1;
static constexpr double CONF_MEDIAN       = 0.50;
static constexpr double REL_MEDIAN        = 0.50;

static const char* const ERROR_STRINGS[] = {
    "OK",
    "Invalid argument",
    "Terrain profile error",
    "Unsupported propagation model",
};

/* -------------------------------------------------------------------------
 * Haversine great-circle distance (metres)
 * ---------------------------------------------------------------------- */
static double haversine_m(double lat1, double lon1, double lat2, double lon2)
{
    constexpr double R  = 6'371'000.0;
    constexpr double PI = 3.14159265358979323846;
    double dlat = (lat2 - lat1) * PI / 180.0;
    double dlon = (lon2 - lon1) * PI / 180.0;
    double a = std::sin(dlat / 2) * std::sin(dlat / 2)
             + std::cos(lat1 * PI / 180.0) * std::cos(lat2 * PI / 180.0)
             * std::sin(dlon / 2) * std::sin(dlon / 2);
    return 2.0 * R * std::asin(std::sqrt(a));
}

/* -------------------------------------------------------------------------
 * Library lifecycle
 * ---------------------------------------------------------------------- */

int splat_init(void)
{
    g_initialized = true;
    return SPLAT_OK;
}

void splat_shutdown(void)
{
    g_initialized = false;
}

const char* splat_error_string(int code)
{
    int idx = -code;
    if (idx < 0 || idx > 3) return "Unknown error";
    return ERROR_STRINGS[idx];
}

/* -------------------------------------------------------------------------
 * Point-to-point propagation
 * ---------------------------------------------------------------------- */

int splat_point_to_point(
    const splat_site_t*    tx,
    const splat_site_t*    rx,
    const splat_profile_t* terrain,
    double                 freq_mhz,
    splat_model_t          model,
    splat_path_result_t*   result)
{
    if (!tx || !rx || !terrain || !result)          return SPLAT_ERR_INVALID;
    if (!g_initialized)                             return SPLAT_ERR_INVALID;
    if (terrain->count < 2 || !terrain->heights_m) return SPLAT_ERR_TERRAIN;
    if (model != SPLAT_MODEL_ITM && model != SPLAT_MODEL_ITWOM)
        return SPLAT_ERR_MODEL;

    elev_t* elev = build_itm_elev(terrain);
    if (!elev) return SPLAT_ERR_INVALID;

    double path_loss = 0.0;
    char   mode_str[256] = {};
    int    errnum = 0;

    if (model == SPLAT_MODEL_ITWOM)
    {
        /* ITWOM v3.0 — better diffraction modelling, preferred above ~100 MHz */
        point_to_point(elev,
            tx->antenna_height_m, rx->antenna_height_m,
            EPS_DIELECT, SGM_CONDUCTIVITY, ENO_NS_SURFREF,
            freq_mhz, RADIO_CLIMATE, POL_VERTICAL,
            CONF_MEDIAN, REL_MEDIAN,
            path_loss, mode_str, errnum);
    }
    else
    {
        /* Legacy Longley-Rice ITM */
        point_to_point_ITM(elev,
            tx->antenna_height_m, rx->antenna_height_m,
            EPS_DIELECT, SGM_CONDUCTIVITY, ENO_NS_SURFREF,
            freq_mhz, RADIO_CLIMATE, POL_VERTICAL,
            CONF_MEDIAN, REL_MEDIAN,
            path_loss, mode_str, errnum);
    }

    delete[] elev;

    double dist = haversine_m(tx->lat, tx->lon, rx->lat, rx->lon);

    result->path_loss_db       = path_loss;
    result->received_power_dbm = tx->erp_dbm - path_loss + tx->gain_dbi + rx->gain_dbi;
    result->distance_m         = dist;
    result->elevation_angle_deg = 0.0; /* TODO: derive from terrain profile */
    result->line_of_sight       = (errnum == 0) ? 1 : 0;
    result->fresnel_clearance_m = 0.0; /* TODO: compute first Fresnel zone */

    return SPLAT_OK;
}

/* -------------------------------------------------------------------------
 * Interference / jamming at a single point
 * ---------------------------------------------------------------------- */

int splat_interference_point(
    const splat_site_t*          signal_tx,
    const splat_site_t*          jammer_tx,
    const splat_site_t*          rx,
    const splat_profile_t*       signal_terrain,
    const splat_profile_t*       jammer_terrain,
    double                       freq_mhz,
    double                       js_threshold_db,
    splat_model_t                model,
    splat_interference_result_t* result)
{
    if (!signal_tx || !jammer_tx || !rx || !result) return SPLAT_ERR_INVALID;
    if (!signal_terrain || !jammer_terrain)         return SPLAT_ERR_TERRAIN;

    splat_path_result_t sig_path = {}, jam_path = {};

    int rc = splat_point_to_point(signal_tx, rx, signal_terrain, freq_mhz, model, &sig_path);
    if (rc != SPLAT_OK) return rc;

    rc = splat_point_to_point(jammer_tx, rx, jammer_terrain, freq_mhz, model, &jam_path);
    if (rc != SPLAT_OK) return rc;

    result->signal_dbm  = sig_path.received_power_dbm;
    result->jammer_dbm  = jam_path.received_power_dbm;
    result->js_ratio_db = result->jammer_dbm - result->signal_dbm;
    result->jammed      = (result->js_ratio_db >= js_threshold_db) ? 1 : 0;

    return SPLAT_OK;
}
