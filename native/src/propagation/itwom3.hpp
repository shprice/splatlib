#pragma once

/*
 * ITWOM v3.0 (Irregular Terrain With Obstructions Model) — stub header.
 *
 * Replace with the actual ITWOM implementation from SPLAT! source:
 *   https://github.com/hoche/splat  (GPL v2)
 *   File: itwom3.0.cpp in that repo
 *
 * The key entry point used by splatlib is:
 *
 *   void itwom_point_to_point(
 *       double   elev[],          // same convention as ITM
 *       double   tht_m,
 *       double   rht_m,
 *       double   eps_dielect,
 *       double   sgm_conductivity,
 *       double   eno_ns_surfref,
 *       double   frq_mhz,
 *       int      radio_climate,
 *       int      pol,
 *       double   conf,
 *       double   rel,
 *       double&  dbloss,
 *       char*    strmode,
 *       int&     errnum
 *   );
 *
 * ITWOM is preferred for frequencies above ~100 MHz and shorter paths where
 * its improved diffraction model gives better accuracy than ITM.
 */

void itwom_point_to_point(
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
