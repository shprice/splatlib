namespace SplatLib.Terrain;

internal static class GeoMath
{
    private const double EarthRadiusM = 6_371_000.0;

    public static double GreatCircleDistanceM(GeoPoint a, GeoPoint b)
    {
        double lat1 = Rad(a.Lat), lat2 = Rad(b.Lat);
        double dLat = Rad(b.Lat - a.Lat);
        double dLon = Rad(b.Lon - a.Lon);

        double h = Math.Sin(dLat / 2) * Math.Sin(dLat / 2)
                 + Math.Cos(lat1) * Math.Cos(lat2)
                 * Math.Sin(dLon / 2) * Math.Sin(dLon / 2);

        return 2.0 * EarthRadiusM * Math.Asin(Math.Sqrt(h));
    }

    /// <summary>
    /// Generates <paramref name="count"/> equally-spaced points along the
    /// great-circle path from <paramref name="from"/> to <paramref name="to"/>.
    /// Uses linear lat/lon interpolation — accurate for paths under ~500 km.
    /// For longer paths a proper spherical interpolation (slerp) should replace this.
    /// </summary>
    public static IReadOnlyList<GeoPoint> InterpolateGreatCircle(GeoPoint from, GeoPoint to, int count)
    {
        var points = new GeoPoint[count];
        for (int i = 0; i < count; i++)
        {
            double t = count > 1 ? (double)i / (count - 1) : 0.0;
            points[i] = new GeoPoint(
                from.Lat + t * (to.Lat - from.Lat),
                from.Lon + t * (to.Lon - from.Lon));
        }
        return points;
    }

    private static double Rad(double deg) => deg * Math.PI / 180.0;
}
