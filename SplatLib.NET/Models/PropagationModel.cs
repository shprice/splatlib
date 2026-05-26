namespace SplatLib;

public enum PropagationModel
{
    /// <summary>Longley-Rice ITM. Faster; well-validated over 20 MHz–20 GHz.</summary>
    Itm = 0,

    /// <summary>ITWOM v3.0. More accurate diffraction model, preferred above ~100 MHz.</summary>
    Itwom = 1,
}
