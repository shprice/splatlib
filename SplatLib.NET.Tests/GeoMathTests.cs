using SplatLib.Terrain;
using Xunit;

namespace SplatLib.Tests;

public sealed class GeoMathTests
{
    [Fact]
    public void GreatCircleDistance_SamePoint_ReturnsZero()
    {
        var pt = new GeoPoint(51.5, -0.1);
        Assert.Equal(0.0, GeoMath.GreatCircleDistanceM(pt, pt), precision: 1);
    }

    [Fact]
    public void GreatCircleDistance_KnownPair_ReturnsApproxCorrectDistance()
    {
        // London → Paris ≈ 340 km
        var london = new GeoPoint(51.5074, -0.1278);
        var paris  = new GeoPoint(48.8566,  2.3522);
        double dist = GeoMath.GreatCircleDistanceM(london, paris);
        Assert.InRange(dist, 335_000, 345_000);
    }

    [Fact]
    public void InterpolateGreatCircle_FirstAndLastPointsMatchEndpoints()
    {
        var from = new GeoPoint(51.0, -1.0);
        var to   = new GeoPoint(52.0,  1.0);
        var pts  = GeoMath.InterpolateGreatCircle(from, to, 10);

        Assert.Equal(10, pts.Count);
        Assert.Equal(from.Lat, pts[0].Lat,  precision: 6);
        Assert.Equal(from.Lon, pts[0].Lon,  precision: 6);
        Assert.Equal(to.Lat,   pts[9].Lat,  precision: 6);
        Assert.Equal(to.Lon,   pts[9].Lon,  precision: 6);
    }
}
