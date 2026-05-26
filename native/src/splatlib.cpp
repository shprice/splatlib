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

/* Library-default propagation environment. */
static constexpr double ENO_NS_SURFREF    = 301.0;  /* surface refractivity, N-units (fixed) */
static constexpr double CONF_DEFAULT      = 0.50;
static constexpr double REL_DEFAULT       = 0.50;
static constexpr int    CLIMATE_DEFAULT   = 5;      /* continental temperate */
static constexpr int    POL_DEFAULT       = 0;      /* 0 = vertical (ITM convention) */

/* Ground type table: { eps_dielect, sgm_conductivity }                   */
struct ground_params { double eps; double sigma; };
static constexpr ground_params GROUND_TABLE[] = {
    { 15.0,  0.005  },  /* 0 = SPLAT_GROUND_AVERAGE      */
    { 80.0,  5.0    },  /* 1 = SPLAT_GROUND_SEA          */
    { 80.0,  0.01   },  /* 2 = SPLAT_GROUND_FRESH_WATER  */
    {  5.0,  0.001  },  /* 3 = SPLAT_GROUND_URBAN        */
    {  3.0,  0.001  },  /* 4 = SPLAT_GROUND_DESERT       */
    { 12.0,  0.01   },  /* 5 = SPLAT_GROUND_WOODLAND     */
};
static constexpr int GROUND_TABLE_SIZE =
    static_cast<int>(sizeof(GROUND_TABLE) / sizeof(GROUND_TABLE[0]));

/* Resolve a (possibly-NULL) splat_propagation_t pointer to concrete values. */
static void resolve_prop(const splat_propagation_t* p,
                         double& eps, double& sigma,
                         int& climate, int& polarz,
                         double& conf, double& rel)
{
    if (!p) {
        eps = GROUND_TABLE[0].eps;  sigma  = GROUND_TABLE[0].sigma;
        climate = CLIMATE_DEFAULT;  polarz = POL_DEFAULT;
        conf    = CONF_DEFAULT;     rel    = REL_DEFAULT;
        return;
    }
    int gi = static_cast<int>(p->ground);
    if (gi < 0 || gi >= GROUND_TABLE_SIZE) gi = 0;
    eps     = GROUND_TABLE[gi].eps;
    sigma   = GROUND_TABLE[gi].sigma;
    climate = (p->radio_climate >= 1 && p->radio_climate <= 7) ? p->radio_climate : CLIMATE_DEFAULT;
    polarz  = (p->polarz == 1) ? 1 : 0;
    conf    = (p->conf > 0.0 && p->conf < 1.0) ? p->conf : CONF_DEFAULT;
    rel     = (p->rel  > 0.0 && p->rel  < 1.0) ? p->rel  : REL_DEFAULT;
}

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
    const splat_site_t*          tx,
    const splat_site_t*          rx,
    const splat_profile_t*       terrain,
    double                       freq_mhz,
    splat_model_t                model,
    const splat_propagation_t*   prop,
    splat_path_result_t*         result)
{
    if (!tx || !rx || !terrain || !result)          return SPLAT_ERR_INVALID;
    if (!g_initialized)                             return SPLAT_ERR_INVALID;
    if (terrain->count < 2 || !terrain->heights_m) return SPLAT_ERR_TERRAIN;
    if (model != SPLAT_MODEL_ITM && model != SPLAT_MODEL_ITWOM)
        return SPLAT_ERR_MODEL;

    double eps, sigma, conf, rel;
    int    climate, polarz;
    resolve_prop(prop, eps, sigma, climate, polarz, conf, rel);

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
            eps, sigma, ENO_NS_SURFREF,
            freq_mhz, climate, polarz,
            conf, rel,
            path_loss, mode_str, errnum);
    }
    else
    {
        /* Legacy Longley-Rice ITM */
        point_to_point_ITM(elev,
            tx->antenna_height_m, rx->antenna_height_m,
            eps, sigma, ENO_NS_SURFREF,
            freq_mhz, climate, polarz,
            conf, rel,
            path_loss, mode_str, errnum);
    }

    delete[] elev;

    double dist = haversine_m(tx->lat, tx->lon, rx->lat, rx->lon);

    result->path_loss_db        = path_loss;
    result->received_power_dbm  = tx->erp_dbm - path_loss + tx->gain_dbi + rx->gain_dbi;
    result->distance_m          = dist;
    result->elevation_angle_deg = 0.0;   /* TODO: derive from terrain profile */
    result->line_of_sight       = (errnum == 0) ? 1 : 0;
    result->fresnel_clearance_m = 0.0;   /* TODO: compute first Fresnel zone */

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
    const splat_propagation_t*   prop,
    splat_interference_result_t* result)
{
    if (!signal_tx || !jammer_tx || !rx || !result) return SPLAT_ERR_INVALID;
    if (!signal_terrain || !jammer_terrain)         return SPLAT_ERR_TERRAIN;

    splat_path_result_t sig_path = {}, jam_path = {};

    int rc = splat_point_to_point(signal_tx, rx, signal_terrain, freq_mhz, model, prop, &sig_path);
    if (rc != SPLAT_OK) return rc;

    rc = splat_point_to_point(jammer_tx, rx, jammer_terrain, freq_mhz, model, prop, &jam_path);
    if (rc != SPLAT_OK) return rc;

    result->signal_dbm  = sig_path.received_power_dbm;
    result->jammer_dbm  = jam_path.received_power_dbm;
    result->js_ratio_db = result->jammer_dbm - result->signal_dbm;
    result->jammed      = (result->js_ratio_db >= js_threshold_db) ? 1 : 0;

    return SPLAT_OK;
}
