namespace SplatLib;

/// <summary>A transmitter, receiver, or jammer site.</summary>
public sealed class Site
{
    /// <summary>WGS-84 latitude, decimal degrees.</summary>
    public required double Lat { get; init; }

    /// <summary>WGS-84 longitude, decimal degrees.</summary>
    public required double Lon { get; init; }

    /// <summary>Antenna height above ground level, metres.</summary>
    public double AntennaHeightM { get; init; } = 10.0;

    /// <summary>Effective radiated power, dBm. Relevant for transmitters and jammers.</summary>
    public double ErpDbm { get; init; } = 0.0;

    /// <summary>Antenna gain, dBi.</summary>
    public double GainDbi { get; init; } = 0.0;
}
