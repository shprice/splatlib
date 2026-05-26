namespace SplatLib.Terrain;

/// <summary>
/// Terrain provider that delegates height sampling to CesiumJS via an
/// <see cref="ICesiumBridge"/> implementation.  The bridge is responsible
/// for marshalling requests to <c>Cesium.sampleTerrainMostDetailed</c> in
/// the host application's WebView2 instance.
/// </summary>
public sealed class CesiumTerrainProvider : ITerrainProvider
{
    private readonly ICesiumBridge _bridge;

    public CesiumTerrainProvider(ICesiumBridge bridge)
        => _bridge = bridge ?? throw new ArgumentNullException(nameof(bridge));

    public async Task<TerrainProfile> SampleProfileAsync(
        GeoPoint from,
        GeoPoint to,
        int numSamples,
        CancellationToken cancellationToken = default)
    {
        if (numSamples < 2) throw new ArgumentOutOfRangeException(nameof(numSamples), "Must be >= 2.");

        var points = GeoMath.InterpolateGreatCircle(from, to, numSamples);
        double[] heights = await _bridge.SampleHeightsAsync(points, cancellationToken);

        if (heights.Length != numSamples)
            throw new InvalidOperationException(
                $"Cesium returned {heights.Length} height values; expected {numSamples}.");

        double distance = GeoMath.GreatCircleDistanceM(from, to);
        double spacing  = distance / (numSamples - 1);

        return new TerrainProfile(heights, spacing);
    }
}
