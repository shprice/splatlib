namespace SplatLib.Terrain;

/// <summary>
/// Terrain provider backed by SPLAT! SDF files derived from SRTM elevation data.
/// Useful for offline analysis when a Cesium instance is not available.
///
/// Generating SDF files:
///   1. Download SRTM .hgt tiles from https://dwtkns.com/srtm30m/
///   2. Run the <c>srtm2sdf</c> utility from SPLAT! source to convert them:
///      <c>srtm2sdf N51W002.hgt</c>  →  <c>N51W002.sdf</c>
///   3. Place all .sdf files in a single directory and pass that path here.
/// </summary>
public sealed class SrtmTerrainProvider : ITerrainProvider
{
    private readonly string _sdfDirectory;

    public SrtmTerrainProvider(string sdfDirectory)
    {
        if (!Directory.Exists(sdfDirectory))
            throw new DirectoryNotFoundException($"SDF directory not found: {sdfDirectory}");
        _sdfDirectory = sdfDirectory;
    }

    public Task<TerrainProfile> SampleProfileAsync(
        GeoPoint from,
        GeoPoint to,
        int numSamples,
        CancellationToken cancellationToken = default)
    {
        // TODO: Implement SDF file loading and terrain profile extraction.
        //
        // Reference: SPLAT! source, functions LoadSDF() and ReadPath() in
        //   https://github.com/hoche/splat/blob/master/splat.cpp
        //
        // Key steps:
        //   1. Determine which SDF tile(s) cover the path (1° × 1° tiles).
        //   2. Memory-map or read the binary SDF files.
        //   3. Walk the great-circle path, bilinearly interpolating elevation
        //      from the tile grid at each sample point.
        //   4. Return a TerrainProfile with the sampled heights.
        throw new NotImplementedException(
            "SrtmTerrainProvider is not yet implemented. " +
            "Use CesiumTerrainProvider or FlatTerrainProvider in the meantime.");
    }
}
