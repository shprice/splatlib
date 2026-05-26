namespace SplatLib.Terrain;

/// <summary>
/// Provides terrain elevation profiles between geographic points.
/// Implement this interface to plug in any elevation data source (Cesium,
/// SRTM files, flat earth for testing, etc.).
/// </summary>
public interface ITerrainProvider
{
    /// <summary>
    /// Returns a terrain elevation profile sampled at <paramref name="numSamples"/>
    /// equally-spaced points along the great-circle path from <paramref name="from"/>
    /// to <paramref name="to"/>.
    /// </summary>
    /// <param name="from">Source point (typically a transmitter).</param>
    /// <param name="to">Destination point (typically a receiver).</param>
    /// <param name="numSamples">Number of elevation samples (>= 2).</param>
    Task<TerrainProfile> SampleProfileAsync(
        GeoPoint from,
        GeoPoint to,
        int numSamples,
        CancellationToken cancellationToken = default);
}
