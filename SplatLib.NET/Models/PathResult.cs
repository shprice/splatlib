namespace SplatLib;

/// <summary>Result of a point-to-point propagation analysis.</summary>
public sealed class PathResult
{
    /// <summary>Median path loss (dB).</summary>
    public double PathLossDb { get; init; }

    /// <summary>Received power at the RX antenna (dBm).</summary>
    public double ReceivedPowerDbm { get; init; }

    /// <summary>Great-circle distance TX→RX (metres).</summary>
    public double DistanceM { get; init; }

    /// <summary>Depression angle at TX looking toward RX (degrees).</summary>
    public double ElevationAngleDeg { get; init; }

    /// <summary>True if an unobstructed line-of-sight path exists.</summary>
    public bool LineOfSight { get; init; }

    /// <summary>First Fresnel zone clearance at the tightest obstruction (metres).</summary>
    public double FresnelClearanceM { get; init; }
}
