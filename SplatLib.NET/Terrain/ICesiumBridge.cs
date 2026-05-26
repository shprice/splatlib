namespace SplatLib.Terrain;

/// <summary>
/// Bridge to a CesiumJS terrain provider running in a WebView2 instance.
///
/// Implement this interface in your host application and pass an instance to
/// <see cref="CesiumTerrainProvider"/>.
///
/// JavaScript side — add a handler in your Cesium app:
/// <code>
/// window.chrome.webview.addEventListener('message', async (e) => {
///   const req = JSON.parse(e.data);
///   const positions = req.points.map(p =>
///     Cesium.Cartographic.fromDegrees(p.lon, p.lat));
///   await Cesium.sampleTerrainMostDetailed(viewer.terrainProvider, positions);
///   const heights = positions.map(p => p.height ?? 0);
///   window.chrome.webview.postMessage(JSON.stringify({ id: req.id, heights }));
/// });
/// </code>
///
/// C# side (WPF / WinForms with WebView2) — example implementation:
/// <code>
/// public sealed class WebView2CesiumBridge : ICesiumBridge
/// {
///     private readonly CoreWebView2 _webView;
///     private readonly ConcurrentDictionary&lt;string, TaskCompletionSource&lt;double[]&gt;&gt; _pending = new();
///
///     public WebView2CesiumBridge(CoreWebView2 webView)
///     {
///         _webView = webView;
///         _webView.WebMessageReceived += OnMessage;
///     }
///
///     public async Task&lt;double[]&gt; SampleHeightsAsync(IReadOnlyList&lt;GeoPoint&gt; points, CancellationToken ct)
///     {
///         var id  = Guid.NewGuid().ToString();
///         var tcs = new TaskCompletionSource&lt;double[]&gt;();
///         _pending[id] = tcs;
///         var payload = JsonSerializer.Serialize(new { id, points = points.Select(p => new { p.Lat, p.Lon }) });
///         await _webView.ExecuteScriptAsync($"window.splatTerrainQuery({payload})");
///         using var reg = ct.Register(() => { _pending.TryRemove(id, out _); tcs.TrySetCanceled(); });
///         return await tcs.Task;
///     }
///
///     private void OnMessage(object? sender, CoreWebView2WebMessageReceivedEventArgs e)
///     {
///         var resp = JsonSerializer.Deserialize&lt;TerrainResponse&gt;(e.WebMessageAsJson);
///         if (resp is not null &amp;&amp; _pending.TryRemove(resp.Id, out var tcs))
///             tcs.TrySetResult(resp.Heights);
///     }
/// }
/// </code>
/// </summary>
public interface ICesiumBridge
{
    /// <summary>
    /// Samples terrain heights at the supplied coordinates using the Cesium
    /// terrain provider.  Returns heights in metres ASL in the same order as
    /// <paramref name="points"/>.
    /// </summary>
    Task<double[]> SampleHeightsAsync(
        IReadOnlyList<GeoPoint> points,
        CancellationToken cancellationToken = default);
}
