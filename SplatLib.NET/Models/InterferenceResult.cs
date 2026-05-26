namespace SplatLib;

/// <summary>Interference / jamming result at a single receiver point.</summary>
public sealed class InterferenceResult
{
    /// <summary>Received desired signal (dBm).</summary>
    public double SignalDbm { get; init; }

    /// <summary>Received jammer power (dBm).</summary>
    public double JammerDbm { get; init; }

    /// <summary>
    /// Jamming-to-Signal ratio in dB.  Positive = jammer stronger than signal.
    /// </summary>
    public double JsRatioDb { get; init; }

    /// <summary>True if <see cref="JsRatioDb"/> meets or exceeds the supplied threshold.</summary>
    public bool Jammed { get; init; }
}
