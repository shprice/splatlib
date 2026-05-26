#include "itm.hpp"

/*
 * TODO: Replace this stub with the Longley-Rice ITM implementation.
 *
 * Recommended source: https://github.com/hoche/splat (GPL v2)
 * The hoche fork has modernised CMake support and compiles cleanly on Windows.
 *
 * Steps:
 *   1. Copy itm.cpp from that repo into this directory.
 *   2. Adjust the include path to match this project's layout.
 *   3. Remove this stub file.
 */

void ITM_point_to_point(
    double   elev[],
    double   tht_m,
    double   rht_m,
    double   eps_dielect,
    double   sgm_conductivity,
    double   eno_ns_surfref,
    double   frq_mhz,
    int      radio_climate,
    int      pol,
    double   conf,
    double   rel,
    double&  dbloss,
    char*    strmode,
    int&     errnum)
{
    (void)elev; (void)tht_m; (void)rht_m; (void)eps_dielect;
    (void)sgm_conductivity; (void)eno_ns_surfref; (void)frq_mhz;
    (void)radio_climate; (void)pol; (void)conf; (void)rel; (void)strmode;

    /* Stub: returns 0 dB loss so the skeleton compiles and links. */
    dbloss = 0.0;
    errnum = 0;
}
