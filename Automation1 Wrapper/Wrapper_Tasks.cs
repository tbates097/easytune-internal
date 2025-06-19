using Aerotech.Automation1.Applications.Interfaces;
using Aerotech.Automation1.Applications.Shared;
using Prism.Ioc;

namespace Aerotech.Automation1.CustomWrapper;

public class Wrapper_Tasks
{
    public static OptimizationResult OptimizeSensitivityObjectiveFunction(FRInput ltInput, bool applyFeedforwardBefore, double? countsPerUnit, bool isPiezo,
        ObjectiveFunctionOptimizationOptions sensitivityOptimizationOptions, FrequencyResponseAnalyzer response)
    {
        // To setup the optimization service and get around A1's registration logic. Thanks Eric D.
        Prism.Unity.UnityContainerExtension containerRegistry = new();
        containerRegistry.RegisterSingleton<IOptimizationService, OptimizationService>();
        Func<Prism.Unity.UnityContainerExtension> createcontainerextesnsion = () => containerRegistry;
        ContainerLocator.SetContainerExtension(createcontainerextesnsion);

        // Actually call this function.
        Task<OptimizationResult> task = FrequencyResponseAnalyzer.OptimizeSensitivityObjectiveFunction(ltInput, applyFeedforwardBefore, countsPerUnit, isPiezo, sensitivityOptimizationOptions, response);
        return task.Result;
    }
}
