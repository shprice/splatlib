using SplatLib.Terrain;

namespace SplatLib;

/// <summary>
/// Defines the area for a coverage or interference analysis grid.
/// The grid is a square centred on <see cref="Center"/> with half-width <see cref="RadiusM"/>.
/// </summary>
public sealed class CoverageGrid
{
    /// <summary>Geographic centre of the analysis area.</summary>
    public required GeoPoint Center { get; init; }

    /// <summary>Half-width of the analysis area in metres (i.e. the grid extends this far in each cardinal direction).</summary>
    public double RadiusM { get; init; } = 50_000;

    /// <summary>Number of grid points per side. Total points = Resolution².</summary>
    public int Resolution { get; init; } = 256;

    /// <summary>Generates all lat/lon grid positions with their flat array index.</summary>
    internal IReadOnlyList<GridPosition> GeneratePoints()
    {
        var points = new List<GridPosition>(Resolution * Resolution);
        double latDelta = MetresToDegLat(RadiusM);
        double lonDelta = MetresToDegLon(RadiusM, Center.Lat);

        for (int row = 0; row < Resolution; row++)
        {
            double lat = Center.Lat - latDelta + 2.0 * latDelta * row / (Resolution - 1);
            for (int col = 0; col < Resolution; col++)
            {
                double lon = Center.Lon - lonDelta + 2.0 * lonDelta * col / (Resolution - 1);
                points.Add(new GridPosition(row * Resolution + col, lat, lon));
            }
        }
        return points;
    }

    private static double MetresToDegLat(double metres) => metres / 111_320.0;
    private static double MetresToDegLon(double metres, double lat)
        => metres / (111_320.0 * Math.Cos(lat * Math.PI / 180.0));
}

internal record GridPosition(int Index, double Lat, double Lon);
