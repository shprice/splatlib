using System.Runtime.InteropServices;

namespace SplatLib.Native;

/* -------------------------------------------------------------------------
 * Blittable structs that mirror the C types in splatlib.h.
 * Field order and types must match exactly for correct P/Invoke marshalling.
 * ---------------------------------------------------------------------- */

[StructLayout(LayoutKind.Sequential)]
internal struct NativeSite
{
    public double Lat;
    public double Lon;
    public double AntennaHeightM;
    public double ErpDbm;
    public double GainDbi;
}

[StructLayout(LayoutKind.Sequential)]
internal struct NativeProfile
{
    public IntPtr HeightsM;   /* const double* — caller pins the managed array */
    public int    Count;
    public double SpacingM;   /* on 64-bit: 4-byte int + 4-byte pad + 8-byte double */
}

[StructLayout(LayoutKind.Sequential)]
internal struct NativePathResult
{
    public double PathLossDb;
    public double ReceivedPowerDbm;
    public double DistanceM;
    public double ElevationAngleDeg;
    public int    LineOfSight;
    public double FresnelClearanceM;
}

[StructLayout(LayoutKind.Sequential)]
internal struct NativeInterferenceResult
{
    public double SignalDbm;
    public double JammerDbm;
    public double JsRatioDb;
    public int    Jammed;
}

/* -------------------------------------------------------------------------
 * P/Invoke declarations
 * ---------------------------------------------------------------------- */
internal static partial class NativeMethods
{
    // Resolved at runtime by NativeLibraryLoader.Configure() so we can
    // handle platform-specific file names (splatlib.dll / libsplatlib.so).
    private const string LibName = "splatlib";

    [LibraryImport(LibName)]
    [UnmanagedCallConv(CallConvs = [typeof(System.Runtime.CompilerServices.CallConvCdecl)])]
    internal static partial int splat_init();

    [LibraryImport(LibName)]
    [UnmanagedCallConv(CallConvs = [typeof(System.Runtime.CompilerServices.CallConvCdecl)])]
    internal static partial void splat_shutdown();

    [LibraryImport(LibName)]
    [UnmanagedCallConv(CallConvs = [typeof(System.Runtime.CompilerServices.CallConvCdecl)])]
    internal static partial IntPtr splat_error_string(int errorCode);

    [LibraryImport(LibName)]
    [UnmanagedCallConv(CallConvs = [typeof(System.Runtime.CompilerServices.CallConvCdecl)])]
    internal static partial int splat_point_to_point(
        ref NativeSite       tx,
        ref NativeSite       rx,
        ref NativeProfile    terrain,
        double               freqMhz,
        int                  model,
        ref NativePathResult result);

    [LibraryImport(LibName)]
    [UnmanagedCallConv(CallConvs = [typeof(System.Runtime.CompilerServices.CallConvCdecl)])]
    internal static partial int splat_interference_point(
        ref NativeSite             signalTx,
        ref NativeSite             jammerTx,
        ref NativeSite             rx,
        ref NativeProfile          signalTerrain,
        ref NativeProfile          jammerTerrain,
        double                     freqMhz,
        double                     jsThresholdDb,
        int                        model,
        ref NativeInterferenceResult result);
}
