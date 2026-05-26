#pragma once

/*
 * Longley-Rice Irregular Terrain Model (ITM) — stub header.
 *
 * Replace with the actual ITM implementation from the SPLAT! source:
 *   https://github.com/hoche/splat  (GPL v2)
 *   File: itm.cpp / itm.hpp in that repo
 *
 * The key entry point used by splatlib is:
 *
 *   void ITM_point_to_point(
 *       double   elev[],        // elev[0]=count-1, elev[1]=spacing_m, elev[2..]=heights
 *       double   tht_m,         // TX antenna height above ground (m)
 *       double   rht_m,         // RX antenna height above ground (m)
 *       double   eps_dielect,   // earth dielectric constant (typ. 15.0)
 *       double   sgm_conductivity, // earth conductivity (typ. 0.005)
 *       double   eno_ns_surfref,   // surface refractivity (typ. 301.0)
 *       double   frq_mhz,
 *       int      radio_climate,    // 5 = continental temperate
 *       int      pol,              // 0 = horizontal, 1 = vertical
 *       double   conf,             // confidence (0.5 = median)
 *       double   rel,              // reliability (0.5 = median)
 *       double&  dbloss,           // output: path loss (dB)
 *       char*    strmode,          // output: propagation mode description
 *       int&     errnum            // output: ITM error/warning code
 *   );
 */

void ITM_point_to_point(
    double elev[],
    double tht_m,
    double rht_m,
    double eps_dielect,
    double sgm_conductivity,
    double eno_ns_surfref,
    double frq_mhz,
    int    radio_climate,
    int    pol,
    double conf,
    double rel,
    double& dbloss,
    char*  strmode,
    int&   errnum
);
