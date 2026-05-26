using SplatLib.Native;
using SplatLib.Terrain;

namespace SplatLib;

/// <summary>Point-to-point RF propagation analysis.</summary>
public sealed class PropagationAnalysis
{
    private const int DefaultProfileSamples = 1024;

    private readonly ITerrainProvider _terrain;

    internal PropagationAnalysis(ITerrainProvider terrain) => _terrain = terrain;

    /// <summary>
    /// Analyses the propagation path between <paramref name="tx"/> and
    /// <paramref name="rx"/> at the given frequency.
    /// </summary>
    public async Task<PathResult> AnalyseAsync(
        Site tx,
        Site rx,
        double freqMhz,
        PropagationModel model = PropagationModel.Itwom,
        int profileSamples = DefaultProfileSamples,
        CancellationToken cancellationToken = default)
    {
        var profile = await _terrain.SampleProfileAsync(
            new GeoPoint(tx.Lat, tx.Lon),
            new GeoPoint(rx.Lat, rx.Lon),
            profileSamples, cancellationToken);

        return CallNative(tx, rx, profile, freqMhz, model);
    }

    private static unsafe PathResult CallNative(
        Site tx, Site rx, TerrainProfile profile,
        double freqMhz, PropagationModel model)
    {
        var nativeTx = ToNative(tx);
        var nativeRx = ToNative(rx);
        var nativeResult = new NativePathResult();

        fixed (double* heights = profile.HeightsM)
        {
            var nativeProfile = new NativeProfile
            {
                HeightsM = (IntPtr)heights,
                Count    = profile.HeightsM.Length,
                SpacingM = profile.SpacingM,
            };

            int rc = NativeMethods.splat_point_to_point(
                ref nativeTx, ref nativeRx, ref nativeProfile,
                freqMhz, (int)model, ref nativeResult);

            if (rc != 0)
                throw new SplatException($"splat_point_to_point failed: {rc}", rc);
        }

        return new PathResult
        {
            PathLossDb        = nativeResult.PathLossDb,
            ReceivedPowerDbm  = nativeResult.ReceivedPowerDbm,
            DistanceM         = nativeResult.DistanceM,
            ElevationAngleDeg = nativeResult.ElevationAngleDeg,
            LineOfSight       = nativeResult.LineOfSight != 0,
            FresnelClearanceM = nativeResult.FresnelClearanceM,
        };
    }

    internal static NativeSite ToNative(Site s) => new()
    {
        Lat             = s.Lat,
        Lon             = s.Lon,
        AntennaHeightM  = s.AntennaHeightM,
        ErpDbm          = s.ErpDbm,
        GainDbi         = s.GainDbi,
    };
}
