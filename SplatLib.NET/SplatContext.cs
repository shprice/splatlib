using SplatLib.Native;
using SplatLib.Terrain;

namespace SplatLib;

/// <summary>
/// Entry point for the SplatLib.NET API.  Manages the native library lifecycle.
/// Dispose when done to release native resources.
/// </summary>
public sealed class SplatContext : IDisposable
{
    private bool _disposed;

    /// <summary>Point-to-point propagation analysis.</summary>
    public PropagationAnalysis Propagation { get; }

    /// <summary>Interference and jamming analysis.</summary>
    public InterferenceAnalysis Interference { get; }

    /// <summary>
    /// Initialises the library with the given terrain provider.
    /// </summary>
    /// <exception cref="SplatException">Thrown if the native library fails to initialise.</exception>
    public SplatContext(ITerrainProvider terrainProvider)
    {
        ArgumentNullException.ThrowIfNull(terrainProvider);

        int rc = NativeMethods.splat_init();
        if (rc != 0)
            throw new SplatException($"splat_init failed with code {rc}.", rc);

        Propagation  = new PropagationAnalysis(terrainProvider);
        Interference = new InterferenceAnalysis(terrainProvider);
    }

    public void Dispose()
    {
        if (_disposed) return;
        NativeMethods.splat_shutdown();
        _disposed = true;
    }
}
