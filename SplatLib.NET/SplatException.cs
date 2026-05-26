namespace SplatLib;

public sealed class SplatException : Exception
{
    public int NativeErrorCode { get; }

    public SplatException(string message) : base(message) { }

    public SplatException(string message, int nativeCode)
        : base(message) => NativeErrorCode = nativeCode;
}
