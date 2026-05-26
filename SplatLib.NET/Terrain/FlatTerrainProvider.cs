namespace SplatLib.Terrain;

/// <summary>
/// Terrain provider that returns a constant elevation everywhere.
/// Useful for unit testing and free-space path-loss baselines.
/// </summary>
public sealed class FlatTerrainProvider : ITerrainProvider
{
    private readonly double _elevationM;

    /// <param name="elevationM">Constant elevation in metres ASL (default 0).</param>
    public FlatTerrainProvider(double elevationM = 0.0) => _elevationM = elevationM;

    public Task<TerrainProfile> SampleProfileAsync(
        GeoPoint from,
        GeoPoint to,
        int numSamples,
        CancellationToken cancellationToken = default)
    {
        if (numSamples < 2) throw new ArgumentOutOfRangeException(nameof(numSamples), "Must be >= 2.");

        double distance = GeoMath.GreatCircleDistanceM(from, to);
        double spacing  = distance / (numSamples - 1);
        double[] heights = new double[numSamples];
        Array.Fill(heights, _elevationM);

        return Task.FromResult(new TerrainProfile(heights, spacing));
    }
}
