using SplatLib.Terrain;
using Xunit;

namespace SplatLib.Tests;

public sealed class FlatTerrainProviderTests
{
    [Fact]
    public async Task SampleProfile_ReturnsCorrectSampleCount()
    {
        var provider = new FlatTerrainProvider(100.0);
        var profile  = await provider.SampleProfileAsync(
            new GeoPoint(51.0, -1.0), new GeoPoint(52.0, 1.0), 512);

        Assert.Equal(512, profile.HeightsM.Length);
    }

    [Fact]
    public async Task SampleProfile_AllHeightsMatchConstantElevation()
    {
        const double elevation = 250.0;
        var provider = new FlatTerrainProvider(elevation);
        var profile  = await provider.SampleProfileAsync(
            new GeoPoint(51.0, -1.0), new GeoPoint(52.0, 1.0), 64);

        Assert.All(profile.HeightsM, h => Assert.Equal(elevation, h));
    }

    [Fact]
    public async Task SampleProfile_SpacingIsConsistentWithDistance()
    {
        var from = new GeoPoint(51.5, -0.1);
        var to   = new GeoPoint(51.5,  1.0);
        const int samples = 100;

        var provider = new FlatTerrainProvider();
        var profile  = await provider.SampleProfileAsync(from, to, samples);

        double expectedTotal = GeoMath.GreatCircleDistanceM(from, to);
        double actualTotal   = profile.SpacingM * (samples - 1);
        Assert.InRange(actualTotal, expectedTotal * 0.999, expectedTotal * 1.001);
    }

    [Theory]
    [InlineData(1)]
    [InlineData(0)]
    [InlineData(-5)]
    public async Task SampleProfile_TooFewSamples_Throws(int samples)
    {
        var provider = new FlatTerrainProvider();
        await Assert.ThrowsAsync<ArgumentOutOfRangeException>(() =>
            provider.SampleProfileAsync(
                new GeoPoint(51.0, -1.0), new GeoPoint(52.0, 1.0), samples));
    }
}
