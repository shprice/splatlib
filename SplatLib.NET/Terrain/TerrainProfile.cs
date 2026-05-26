namespace SplatLib.Terrain;

/// <summary>
/// Pre-sampled terrain elevation profile between two geographic points.
/// Samples are equally spaced along the great-circle path.
/// </summary>
public sealed class TerrainProfile
{
    /// <summary>Terrain elevations in metres ASL, from source to destination.</summary>
    public double[] HeightsM { get; }

    /// <summary>Distance between consecutive samples, metres.</summary>
    public double SpacingM { get; }

    public TerrainProfile(double[] heightsM, double spacingM)
    {
        if (heightsM.Length < 2)
            throw new ArgumentException("Profile must contain at least 2 samples.", nameof(heightsM));

        HeightsM = heightsM;
        SpacingM = spacingM;
    }
}
