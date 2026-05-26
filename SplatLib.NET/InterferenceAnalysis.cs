using SplatLib.Native;
using SplatLib.Terrain;

namespace SplatLib;

/// <summary>RF interference and jamming analysis.</summary>
public sealed class InterferenceAnalysis
{
    private const int DefaultProfileSamples = 1024;

    private readonly ITerrainProvider _terrain;

    internal InterferenceAnalysis(ITerrainProvider terrain) => _terrain = terrain;

    /// <summary>
    /// Computes the Jamming-to-Signal (J/S) ratio at a single receiver point.
    /// Both propagation paths (signal TX → RX and jammer TX → RX) are evaluated
    /// using the same propagation model and frequency.
    /// </summary>
    /// <param name="signalTx">The legitimate transmitter.</param>
    /// <param name="jammerTx">The interferer / jammer.</param>
    /// <param name="rx">The receiver under analysis.</param>
    /// <param name="freqMhz">Operating frequency in MHz.</param>
    /// <param name="jsThresholdDb">
    /// J/S threshold in dB above which the link is considered jammed.
    /// A common value is +6 dB (jammer 4× stronger than signal).
    /// </param>
    public async Task<InterferenceResult> AnalysePointAsync(
        Site signalTx,
        Site jammerTx,
        Site rx,
        double freqMhz,
        double jsThresholdDb = 6.0,
        PropagationModel model = PropagationModel.Itwom,
        int profileSamples = DefaultProfileSamples,
        CancellationToken cancellationToken = default)
    {
        var rxPoint = new GeoPoint(rx.Lat, rx.Lon);

        // Sample both terrain profiles concurrently.
        var signalTask = _terrain.SampleProfileAsync(
            new GeoPoint(signalTx.Lat, signalTx.Lon), rxPoint, profileSamples, cancellationToken);
        var jammerTask = _terrain.SampleProfileAsync(
            new GeoPoint(jammerTx.Lat, jammerTx.Lon), rxPoint, profileSamples, cancellationToken);

        await Task.WhenAll(signalTask, jammerTask);

        return CallNative(signalTx, jammerTx, rx, signalTask.Result, jammerTask.Result,
                          freqMhz, jsThresholdDb, model);
    }

    /// <summary>
    /// Computes the J/S ratio at every point in a coverage grid.
    /// Grid points are evaluated in parallel; degree of parallelism is controlled
    /// by <see cref="ParallelOptions"/> if needed.
    /// </summary>
    public async Task<IReadOnlyList<GridPoint>> AnalyseCoverageAsync(
        Site signalTx,
        Site jammerTx,
        CoverageGrid grid,
        double freqMhz,
        double jsThresholdDb = 6.0,
        PropagationModel model = PropagationModel.Itwom,
        int profileSamples = DefaultProfileSamples,
        CancellationToken cancellationToken = default)
    {
        var gridPositions = grid.GeneratePoints();
        var results = new GridPoint[gridPositions.Count];

        await Parallel.ForEachAsync(gridPositions, cancellationToken, async (pos, ct) =>
        {
            var rxSite = new Site
            {
                Lat             = pos.Lat,
                Lon             = pos.Lon,
                AntennaHeightM  = 2.0,   // typical receiver height
            };

            var interference = await AnalysePointAsync(
                signalTx, jammerTx, rxSite,
                freqMhz, jsThresholdDb, model, profileSamples, ct);

            results[pos.Index] = new GridPoint
            {
                Lat           = pos.Lat,
                Lon           = pos.Lon,
                Interference  = interference,
            };
        });

        return results;
    }

    private static unsafe InterferenceResult CallNative(
        Site signalTx, Site jammerTx, Site rx,
        TerrainProfile signalTerrain, TerrainProfile jammerTerrain,
        double freqMhz, double jsThresholdDb, PropagationModel model)
    {
        var nativeSignalTx = PropagationAnalysis.ToNative(signalTx);
        var nativeJammerTx = PropagationAnalysis.ToNative(jammerTx);
        var nativeRx       = PropagationAnalysis.ToNative(rx);
        var nativeResult   = new NativeInterferenceResult();

        fixed (double* sigH = signalTerrain.HeightsM)
        fixed (double* jamH = jammerTerrain.HeightsM)
        {
            var nativeSignalProfile = new NativeProfile
            {
                HeightsM = (IntPtr)sigH,
                Count    = signalTerrain.HeightsM.Length,
                SpacingM = signalTerrain.SpacingM,
            };
            var nativeJammerProfile = new NativeProfile
            {
                HeightsM = (IntPtr)jamH,
                Count    = jammerTerrain.HeightsM.Length,
                SpacingM = jammerTerrain.SpacingM,
            };

            int rc = NativeMethods.splat_interference_point(
                ref nativeSignalTx, ref nativeJammerTx, ref nativeRx,
                ref nativeSignalProfile, ref nativeJammerProfile,
                freqMhz, jsThresholdDb, (int)model,
                ref nativeResult);

            if (rc != 0)
                throw new SplatException($"splat_interference_point failed: {rc}", rc);
        }

        return new InterferenceResult
        {
            SignalDbm  = nativeResult.SignalDbm,
            JammerDbm  = nativeResult.JammerDbm,
            JsRatioDb  = nativeResult.JsRatioDb,
            Jammed     = nativeResult.Jammed != 0,
        };
    }
}
