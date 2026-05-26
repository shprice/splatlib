#include "itwom3.hpp"

/*
 * TODO: Replace this stub with the ITWOM v3.0 implementation.
 *
 * Recommended source: https://github.com/hoche/splat (GPL v2)
 * File to copy: itwom3.0.cpp (rename to itwom3.cpp to match CMakeLists.txt)
 *
 * Steps:
 *   1. Copy itwom3.0.cpp from the hoche/splat repo into this directory.
 *   2. Rename it to itwom3.cpp.
 *   3. Adjust includes if needed.
 *   4. Remove this stub file.
 */

void itwom_point_to_point(
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
