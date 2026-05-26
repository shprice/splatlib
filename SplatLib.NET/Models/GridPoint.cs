namespace SplatLib;

/// <summary>A point on a coverage analysis grid together with its interference result.</summary>
public sealed class GridPoint
{
    public double Lat { get; init; }
    public double Lon { get; init; }
    public required InterferenceResult Interference { get; init; }
}
