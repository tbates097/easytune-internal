using Aerotech.Automation1.Applications.Shared;

namespace Aerotech.Automation1.CustomWrapper;

public class Wrapper_Utils
{
    public static FilterCoeffs[] GetFilterCoeffs(Filter[] filters)
    {
        return filters.Select(filter => filter.Coeffs).ToArray();
    }

    public static IEnumerable<T> ListToEnumerable<T>(T[] list)
    {
        return list.AsEnumerable();
    }
}
