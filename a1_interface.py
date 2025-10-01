import control
from datetime import datetime
import json
import math
import numpy as np
import os
import shutil
import sys

from Blocks import *
import Block_Layout
from FRD_Data import Loop_Type
import Globals
import Utils


# NOTE: If you attempt to set a property that does not have a setter in the DLL, the set may silently fail.

def get_dll_version(dll_path:str) -> str:
    """ Retrieves the version associated with a DLL.

    Args:
        dll_path (str): The filepath to the DLL to get the version from.

    Returns:
        str: The version of the DLL.
    """
    import win32api

    try:
        info = win32api.GetFileVersionInfo(dll_path, "\\")
        ms = info['FileVersionMS']
        ls = info['FileVersionLS']
        version = "%d.%d.%d.%d" % (win32api.HIWORD(ms), win32api.LOWORD(ms), win32api.HIWORD(ls), win32api.LOWORD(ls))
        return version
    except Exception as e:
        print(f"Error retrieving version information: {e}")
        return None

#region RUNTIME_SETUP
""" Sets up the runtime .NET environment used when executing .NET DLLs in Python.
"""
DLL_DIRECTORY = "Automation1 DLLs"
RUNTIME_ENVIRONMENT_FILE = "runtime_environment.json"

if not os.path.isdir(DLL_DIRECTORY):
    raise ValueError("The DLL directory ({}) which contains the required Automation1 DLLs is invalid!".format(DLL_DIRECTORY))

# Load the configuration file which allows us to specify that we will use the .NET 8.0 runtime
from clr_loader import get_coreclr
from pythonnet import set_runtime, get_runtime_info

try:
    runtime_environment_json_path = os.path.join(os.getcwd(), RUNTIME_ENVIRONMENT_FILE)
    if os.path.exists(runtime_environment_json_path):
        runtime_environment = get_coreclr(runtime_config=runtime_environment_json_path)
    else:
        raise ValueError("The runtime environment file ({}) does not exist! This is required so that we can use the correct .NET runtime!" \
                        .format(runtime_environment_json_path))
except Exception as e:
    print("The specified version of .NET does not exist on your system according to the {} file!\n".format(runtime_environment_json_path))
    raise

# Set the runtime that we specified.
try:
    set_runtime(runtime_environment)
except RuntimeError as e:
    # RuntimeError: The runtime <clr_loader.netfx.NetFx object at 0x000002013BCFE1C0> has already been loaded
    print("The module 'clr' already exists! This must be imported after the set_runtime() function! " \
          "If you are using Spyder, you can avoid this by either:\n1.) Starting a new kernel.\n2.) Disabling UMR (User Module Reloader)\n3.) Add pythonnet to the UMR exclusion list.\n"\
          "See: https://github.com/spyder-ide/spyder/issues/21269 for more details.")
    raise
except Exception as e:
    raise

# Printout runtime info.
#print(get_runtime_info(), "\n")

# Import CLR (Common Language Runtime) AFTER setting up the runtime environment.
# NOTE: https://github.com/pythonnet/pythonnet/discussions/2421
import clr

# In our working Python environment, add a list of directories that the Python interpreter can search through when importing modules.
sys.path.append(DLL_DIRECTORY)

# Add all references to the DLLs by name.
dll_files = os.listdir(DLL_DIRECTORY)
a1_versions = {}
for dll in dll_files:
    if dll.startswith("Aerotech.Automation1") and dll.endswith(".dll"):
        try:
            # Remove the .dll file extension.
            clr.AddReference(dll[:-4])
            a1_versions[dll[:-4]] = get_dll_version(dll)
        except Exception as e:
            print("Failed to import .dll: {} because {}".format(dll, str(e).split("\n")[0]))

# Finally, import the classes we need from the DLLs.
# NOTE: Because these are imported from a DLL at runtime, Python Intellisense will not work but you can use the dir()
# function to print the properties and methods that a class contains.
#region Imports
from Aerotech.Automation1.Applications.Wpf import PlotFileXmlSerializer, FrequencyResponseModel, FrequencyResponseResult, \
    FrequencyResponseAxisResult, FrequencyResponseFrequencyResult, FrequencyResponseConfiguration
from Aerotech.Automation1.Applications.Shared import Filter, FilterCoeffs, LoopShapingConfiguration, ServoGains, \
    ServoLoopConfiguration, EnhancedTrackingSetup, EnhancedTrackingControlConfig, DeviceInformation, FRInput, FRType
from Aerotech.Automation1.Applications.Wpf import EasyTuneService, TuningService, FrequencyResponseModel
from Aerotech.Automation1.Applications.Shared import TuningMotionConfiguration, OptimizeFilterOption, PIDController,\
        ServoController, FrequencyResponseAnalyzer, CurrentLoopController, \
            ObjectiveFunctionOptimizationOptions, TuningStageType, CurrentLoopGains, EncoderGains, SoftwareLimitSystemInformation,\
            TuningMotionConfiguration, MotionUnits, AutoFocusGains, AxisCommandOutputType
from Aerotech.Automation1.CustomWrapper import Wrapper_Tasks, Wrapper_Utils
from Aerotech.Automation1.DotNet import MotorType, AxisFault, PrimaryFeedbackType, AuxiliaryFeedbackType, TaskMode
from Aerotech.Automation1.DotNetInternal import GantryMechanicalDesign
from Aerotech.Automation1.Applications.Interfaces import OptimizationLoggingLevel
#endregion

# Import .NET objects.
clr.AddReference("System")
clr.AddReference("System.Collections")
from System.Collections.Generic import List
from System import Array, Version

def get_a1_dll_version():
    # Get the Automation1 DLL version. NOTE: not all dlls have the same version due to ABE (Aerotech Build Engine).

    #unique_versions = list(set(versions))
    #a1_version = "0.0.0.0"
    #occurrences = 0
    #for version in unique_versions:
    #    if versions.count(version) > occurrences:
    #        a1_version = version
    #        occurrences = versions.count(version)
    return a1_versions

A1_VERSION = a1_versions["Aerotech.Automation1.Applications.Wpf"] # The file version will default to WPF's DLL version.

#endregion ============================================================================================================

def get_loop_type_from_fr_result(data):
    loop_type = Loop_Type.Servo
    loop_name = data.Configuration.Type.ToString()
    if loop_name == "ServoLoop":
        loop_type = Loop_Type.Servo
    elif loop_name == "CurrentLoop":
        loop_type = Loop_Type.Current
    elif loop_name == "AutofocusLoop":
        raise NotImplementedError("Autofocus is not supported!")
    else:
        raise NotImplementedError("The loop type: {} is unknown!".format(loop_name))
    
    return loop_type

def get_servo_controller_from_servo_loop_configuration(servo_controller:Servo_Controller, servo_loop_configuration: ServoLoopConfiguration):
    """ Generates a Servo_Controller object from an Automation1 ServoLoopConfiguration object. This fills out
    all gains and filters, but this does not fill out Enhanced Tracking Control.

    Args:
        servo_controller (Servo_Controller): 
        servo_loop_configuration (ServoLoopConfiguration): _description_

    Returns:
        _type_: _description_
    """
    # Frequency.
    servo_controller.properties.Drive_Frequency__hz = servo_loop_configuration.ServoGains.ServoFrequency

    # Alpha.
    servo_controller.properties.Alpha = servo_loop_configuration.ServoGains.Alpha

    # Forward Path.
    servo_controller.properties.K = servo_loop_configuration.ServoGains.K
    servo_controller.properties.Kip = servo_loop_configuration.ServoGains.Kip
    servo_controller.properties.Kip2 = servo_loop_configuration.ServoGains.Kip2
    servo_controller.properties.Kv = servo_loop_configuration.ServoGains.Kv
    servo_controller.properties.Kpv = servo_loop_configuration.ServoGains.Kpv
    servo_controller.properties.Kiv = servo_loop_configuration.ServoGains.Kiv
    servo_controller.properties.Ksi1 = servo_loop_configuration.ServoGains.Ksi1
    servo_controller.properties.Ksi2 = servo_loop_configuration.ServoGains.Ksi2
    servo_controller.properties.Servo_Loop_Gain_Normalization_Factor = servo_loop_configuration.ServoGains.ServoLoopGainNormalizationFactor

    # Feedforward Path.
    servo_controller.properties.Pff = servo_loop_configuration.ServoGains.Pff
    servo_controller.properties.Vff = servo_loop_configuration.ServoGains.Vff
    servo_controller.properties.Aff = servo_loop_configuration.ServoGains.Aff
    servo_controller.properties.Jff = servo_loop_configuration.ServoGains.Jff
    servo_controller.properties.Sff = servo_loop_configuration.ServoGains.Sff
    servo_controller.properties.Feedforward_Gain_Normalization_Factor = servo_loop_configuration.ServoGains.FeedForwardGainNormalizationFactor
    servo_controller.properties.Feedforward_Advance__ms = servo_loop_configuration.ServoGains.FeedForwardAdvance

    # Servo Loop Filters.
    servo_loop_filters = servo_loop_configuration.FilterCoeffs
    for i in range(len(servo_loop_filters)):
        servo_controller.properties.Servo_Filters[i].properties.sampling_frequency = servo_controller.properties.Drive_Frequency__hz
        servo_controller.properties.Servo_Filters[i].properties.N0 = servo_loop_filters[i].N0
        servo_controller.properties.Servo_Filters[i].properties.N1 = servo_loop_filters[i].N1
        servo_controller.properties.Servo_Filters[i].properties.N2 = servo_loop_filters[i].N2
        servo_controller.properties.Servo_Filters[i].properties.D1 = servo_loop_filters[i].D1
        servo_controller.properties.Servo_Filters[i].properties.D2 = servo_loop_filters[i].D2
        backward_calculate_filter(servo_controller.properties.Servo_Filters[i].properties, recompute_type=True)

    # Feedforward Filters.
    feedforward_filters = servo_loop_configuration.FeedforwardFilters
    for i in range(len(feedforward_filters)):
        servo_controller.properties.Feedforward_Filters[i].properties.sampling_frequency = servo_controller.properties.Drive_Frequency__hz
        servo_controller.properties.Feedforward_Filters[i].properties.N0 = feedforward_filters[i].N0
        servo_controller.properties.Feedforward_Filters[i].properties.N1 = feedforward_filters[i].N1
        servo_controller.properties.Feedforward_Filters[i].properties.N2 = feedforward_filters[i].N2
        servo_controller.properties.Feedforward_Filters[i].properties.D1 = feedforward_filters[i].D1
        servo_controller.properties.Feedforward_Filters[i].properties.D2 = feedforward_filters[i].D2
        backward_calculate_filter(servo_controller.properties.Feedforward_Filters[i].properties, recompute_type=True)

    return servo_controller

def get_servo_loop_configuration_from_servo_controller(servo_controller:Servo_Controller):
    servo_gains = ServoGains()

    servo_gains.ServoFrequency = servo_controller.properties.Drive_Frequency__hz
    servo_gains.FeedforwardFrequency = servo_controller.properties.Drive_Frequency__hz
    
    servo_gains.Alpha = servo_controller.properties.Alpha
    servo_gains.K = servo_controller.properties.K
    servo_gains.Kip = servo_controller.properties.Kip
    servo_gains.Kip2 = servo_controller.properties.Kip2
    servo_gains.Kiv = servo_controller.properties.Kiv
    servo_gains.Kpv = servo_controller.properties.Kpv
    servo_gains.Kv = servo_controller.properties.Kv
    servo_gains.Ksi1 = servo_controller.properties.Ksi1
    servo_gains.Ksi2 = servo_controller.properties.Ksi2
    servo_gains.ServoLoopGainNormalizationFactor = servo_controller.properties.Servo_Loop_Gain_Normalization_Factor

    servo_gains.Pff = servo_controller.properties.Pff
    servo_gains.Vff = servo_controller.properties.Vff
    servo_gains.Aff = servo_controller.properties.Aff
    servo_gains.Jff = servo_controller.properties.Jff
    servo_gains.Sff = servo_controller.properties.Sff
    servo_gains.FeedforwardAdvance = servo_controller.properties.Feedforward_Advance__ms
    servo_gains.FeedforwardGainNormalizationFactor = servo_controller.properties.Feedforward_Gain_Normalization_Factor

    # Servo Filters.
    num_filters = len(servo_controller.properties.Servo_Filters)
    servo_filter_coefficients = Array[FilterCoeffs](num_filters)
    for i in range(num_filters):
        if servo_controller.properties.Servo_Filters[i].properties.filter_type != FilterType.Empty:
            filter = FilterCoeffs()
            filter.N0 = servo_controller.properties.Servo_Filters[i].properties.N0
            filter.N1 = servo_controller.properties.Servo_Filters[i].properties.N1
            filter.N2 = servo_controller.properties.Servo_Filters[i].properties.N2
            filter.D1 = servo_controller.properties.Servo_Filters[i].properties.D1
            filter.D2 = servo_controller.properties.Servo_Filters[i].properties.D2
            servo_filter_coefficients[i] = filter
        else:
            servo_filter_coefficients[i] = FilterCoeffs.Defaults

    # Feedforward Filters.
    num_filters = len(servo_controller.properties.Feedforward_Filters)
    feedforward_filter_coefficients = Array[FilterCoeffs](num_filters)
    for i in range(num_filters):
        if servo_controller.properties.Feedforward_Filters[i].properties.filter_type != FilterType.Empty:
            filter = FilterCoeffs()
            filter.N0 = servo_controller.properties.Feedforward_Filters[i].properties.N0
            filter.N1 = servo_controller.properties.Feedforward_Filters[i].properties.N1
            filter.N2 = servo_controller.properties.Feedforward_Filters[i].properties.N2
            filter.D1 = servo_controller.properties.Feedforward_Filters[i].properties.D1
            filter.D2 = servo_controller.properties.Feedforward_Filters[i].properties.D2
            feedforward_filter_coefficients[i] = filter
        else:
            feedforward_filter_coefficients[i] = FilterCoeffs.Defaults

    # The servo filter enabled mask is generated automatically whenever the ServoLoopConfiguration is constructed.
    servo_loop_configuration = ServoLoopConfiguration(servo_gains, \
                                                      servo_filter_coefficients, \
                                                      feedforward_filter_coefficients)
    return servo_loop_configuration

def replace_open_loop_response_data(data:FrequencyResponseResult, frd:control.FRD):
    if frd is None:
        raise RuntimeError("can't save response because the open loop is none")
    
    

    # Generate the frequency response list.
    frequency_results = List[FrequencyResponseFrequencyResult]()
    frequency_hz = Utils.radian_to_hertz(frd.frequency)
    magnitude_dB = Utils.to_dB(frd.magnitude[0][0])
    phase_degrees = np.degrees(frd.phase[0][0])
    for i in range(len(frequency_hz)):
        frequency_results.Add(FrequencyResponseFrequencyResult(frequency_hz[i], magnitude_dB[i], phase_degrees[i], True))

    # The response data is read-only, re-construct AxisData with the new response.
    axis_data = data.AxisData
    axis_data = FrequencyResponseAxisResult(axis_data.AxisIndex, axis_data.AxisName, axis_data.IsServoControlOn, axis_data.MaxOutput, \
                                            axis_data.ServoLoopConfiguration, frequency_results, axis_data.AxisConfiguration, \
                                            axis_data.DeviceInformation, axis_data.LoopShapingConfiguration)
    data = FrequencyResponseResult(data.Configuration, data.InputMode, axis_data)
    return data

def get_block_layout_from_a1_data(data):
    block_layout = Block_Layout.Block_Layout()
    for key in block_layout.block_dictionary.keys():
        block = block_layout.block_dictionary[key]
        if key == Servo_Controller:
            block: Servo_Controller

            # Drive Type.
            if data.AxisData.DeviceInformation.MotorType == MotorType.PiezoActuator:
                block.properties.Drive_Type = DriveType.Piezo
            elif data.AxisData.DeviceInformation.MotorType == MotorType.Galvo:
                block.properties.Drive_Type = DriveType.Galvo
            else:
                block.properties.Drive_Type = DriveType.Servo
                
            # The main controller.
            get_servo_controller_from_servo_loop_configuration(block, data.AxisData.DeviceInformation.OriginalServoLoopConfiguration)

            # Dual Loop.
            block.properties.Is_Dual_loop = data.AxisData.DeviceInformation.IsDualLoop

            # Counts Per Unit.
            block.properties.Counts_Per_Unit = float(data.AxisData.DeviceInformation.RuntimeParameters["CountsPerUnit"])

            # Enhanced Tracking Control.
            block.properties.Enhanced_Tracking_Control.properties.Bandwidth = data.AxisData.DeviceInformation.EnhancedTrackingControlConfig.Bandwidth
            block.properties.Enhanced_Tracking_Control.properties.Scale = data.AxisData.DeviceInformation.EnhancedTrackingControlConfig.Scale
            if data.AxisData.DeviceInformation.EnhancedTrackingControlConfig.Setup.EnhancedTrackingControlEnabled:
                if data.AxisData.DeviceInformation.EnhancedTrackingControlConfig.Setup.Value & 0x2:
                    # Before filters.
                    block.properties.Enhanced_Tracking_Control.properties.Setup = ETC_Setup.Enabled_Before_Filters
                else:
                    # After filters.
                    block.properties.Enhanced_Tracking_Control.properties.Setup = ETC_Setup.Enabled_After_Filters
            else:
                block.properties.Enhanced_Tracking_Control.properties.Setup = ETC_Setup.Disabled

        elif key == Digital_Current_Loop:
            block: Digital_Current_Loop
            
            # Electrical axes may not always exist and there can be multiple. Process only the 1st axis.
            try:
                for i in range(len(data.AxisData.AxisConfiguration.ElectricalProduct.ElectricalAxes)):
                    axis = data.AxisData.AxisConfiguration.ElectricalProduct.ElectricalAxes[i]
                    json_data = json.loads(str(axis.Drive.GetJson()))

                    try:
                        block.properties.Bus_Voltage__V = json_data["BusVoltage"]
                    except:
                        pass

                    break
            except:
                pass

            #block.properties.Back_Emf = float(data.AxisData.DeviceInformation.RuntimeParameters["CurrentLoopFeedforwardBackEmf"])
            
            try:
                # NOTE: This is not set by Machine Setup for linear amplifiers because these are not used by the drive firmware.
                bus_voltage = float(data.AxisData.DeviceInformation.RuntimeParameters["CurrentLoopFeedforwardBusVoltage"])
                if bus_voltage:
                    block.properties.Bus_Voltage__V = bus_voltage
            except:
                pass

            try:
                block.properties.K = float(data.AxisData.DeviceInformation.RuntimeParameters["CurrentLoopGainK"])
            except:
                pass

            try:
                block.properties.Ki = float(data.AxisData.DeviceInformation.RuntimeParameters["CurrentLoopGainKi"])
            except:
                pass

            try:
                block.properties.Lff__mH = float(data.AxisData.DeviceInformation.RuntimeParameters["CurrentLoopFeedforwardGainLff"])
            except:
                pass

            try:
                block.properties.Rff__ohm = float(data.AxisData.DeviceInformation.RuntimeParameters["CurrentLoopFeedforwardGainRff"])
            except:
                pass

        elif key == Amplifier_Plant:
            block: Amplifier_Plant

            # Electrical axes may not always exist and there can be multiple. Process only the 1st axis.
            try:
                for i in range(len(data.AxisData.AxisConfiguration.ElectricalProduct.ElectricalAxes)):
                    axis = data.AxisData.AxisConfiguration.ElectricalProduct.ElectricalAxes[i]
                    json_data = json.loads(str(axis.Drive.GetJson()))

                    try:
                        # Multiply by two because we are scaling the FF path by 
                        block.properties.K = json_data["CurrentLoopAmplifierGain"] * 2.0
                    except:
                        pass
                    
                    try:
                        block.properties.Delay__us = json_data["CurrentLoopAmplifierDelay"]
                    except:
                        pass

                    break
            except:
                pass

        elif key == Amplifier_Rolloff_Filter:
            block: Amplifier_Rolloff_Filter

            # Electrical axes may not always exist and there can be multiple. Process only the 1st axis.
            try:
                for i in range(len(data.AxisData.AxisConfiguration.ElectricalProduct.ElectricalAxes)):
                    axis = data.AxisData.AxisConfiguration.ElectricalProduct.ElectricalAxes[i]
                    json_data = json.loads(str(axis.Drive.GetJson()))
                    
                    try:
                        block.properties.C__uF = json_data["CurrentLoopAmplifierRolloffFilterCapacitance"]
                    except:
                        pass

                    try:
                        block.properties.R__ohm = json_data["CurrentLoopAmplifierRolloffFilterResistance"]
                    except:
                        pass

                    break
            except:
                pass

        elif key == Current_Feedback_Low_Pass_Filter:
            block: Current_Feedback_Low_Pass_Filter

            # Electrical axes may not always exist and there can be multiple. Process only the 1st axis.
            try:
                for i in range(len(data.AxisData.AxisConfiguration.ElectricalProduct.ElectricalAxes)):
                    axis = data.AxisData.AxisConfiguration.ElectricalProduct.ElectricalAxes[i]
                    json_data = json.loads(str(axis.Drive.GetJson()))

                    try:
                        block.properties.C__uF = json_data["CurrentLoopLowPassFilterCapacitance"]
                    except:
                        pass

                    try:
                        block.properties.R__ohm = json_data["CurrentLoopLowPassFilterResistance"]
                    except:
                        pass

                    break
            except:
                pass

        elif key == Motor_Plant:
            block: Motor_Plant

            # Mechanical axes may not always exist and there can be multiple. Process only the 1st axis.
            try:
                for i in range(len(data.AxisData.AxisConfiguration.MechanicalProduct.MechanicalAxes)):
                    axis = data.AxisData.AxisConfiguration.MechanicalProduct.MechanicalAxes[i]
                    json_data = json.loads(str(axis.Motor.GetJson()))                

                    try:
                        block.properties.L__mH = json_data["Inductance"]
                    except:
                        pass

                    try:
                        block.properties.R__ohm = json_data["Resistance"]
                    except:
                        pass

                    break
            except:
                pass

    return block_layout
    


def get_a1_data_from_block_layout(block_layout:Block_Layout.Block_Layout, data:FrequencyResponseResult=None, to_original=False):
    drive_frequency_hz = block_layout.block_dictionary[Servo_Controller].properties.Drive_Frequency__hz
    for key in block_layout.block_dictionary.keys():
        block = block_layout.block_dictionary[key]
        if key == Servo_Controller:
            block: Servo_Controller

            # Servo Gains.
            servo_gains = ServoGains()
            servo_gains.ServoFrequency = block.properties.Drive_Frequency__hz
            servo_gains.FeedforwardFrequency = block.properties.Drive_Frequency__hz
            servo_gains.Alpha = block.properties.Alpha
            servo_gains.K = block.properties.K
            servo_gains.Kip = block.properties.Kip
            servo_gains.Kip2 = block.properties.Kip2
            servo_gains.Kiv = block.properties.Kiv
            servo_gains.Kpv = block.properties.Kpv
            servo_gains.Kv = block.properties.Kv
            servo_gains.Ksi1 = block.properties.Ksi1
            servo_gains.Ksi2 = block.properties.Ksi2
            servo_gains.ServoLoopGainNormalizationFactor = block.properties.Servo_Loop_Gain_Normalization_Factor
            servo_gains.Pff = block.properties.Pff
            servo_gains.Vff = block.properties.Vff
            servo_gains.Aff = block.properties.Aff
            servo_gains.Jff = block.properties.Jff
            servo_gains.Sff = block.properties.Sff
            servo_gains.FeedforwardAdvance = block.properties.Feedforward_Advance__ms
            servo_gains.FeedforwardGainNormalizationFactor = block.properties.Feedforward_Gain_Normalization_Factor

            # Servo Filters.
            num_filters = len(block.properties.Servo_Filters)
            servo_filter_coefficients = Array[FilterCoeffs](num_filters)
            for i in range(num_filters):
                if block.properties.Servo_Filters[i].properties.filter_type != FilterType.Empty:
                    filter = FilterCoeffs()
                    filter.N0 = block.properties.Servo_Filters[i].properties.N0
                    filter.N1 = block.properties.Servo_Filters[i].properties.N1
                    filter.N2 = block.properties.Servo_Filters[i].properties.N2
                    filter.D1 = block.properties.Servo_Filters[i].properties.D1
                    filter.D2 = block.properties.Servo_Filters[i].properties.D2
                    servo_filter_coefficients[i] = filter
                else:
                    servo_filter_coefficients[i] = FilterCoeffs.Defaults

            # Feedforward Filters.
            num_filters = len(block.properties.Feedforward_Filters)
            feedforward_filter_coefficients = Array[FilterCoeffs](num_filters)
            for i in range(num_filters):
                if block.properties.Feedforward_Filters[i].properties.filter_type != FilterType.Empty:
                    filter = FilterCoeffs()
                    filter.N0 = block.properties.Feedforward_Filters[i].properties.N0
                    filter.N1 = block.properties.Feedforward_Filters[i].properties.N1
                    filter.N2 = block.properties.Feedforward_Filters[i].properties.N2
                    filter.D1 = block.properties.Feedforward_Filters[i].properties.D1
                    filter.D2 = block.properties.Feedforward_Filters[i].properties.D2
                    feedforward_filter_coefficients[i] = filter
                else:
                    feedforward_filter_coefficients[i] = FilterCoeffs.Defaults

            # The servo filter enabled mask is generated automatically whenever the ServoLoopConfiguration is constructed.
            servo_loop_configuration = ServoLoopConfiguration(servo_gains, servo_filter_coefficients, feedforward_filter_coefficients)
            
            # Enhanced Tracking Control.
            enhanced_tracking_control_configuration = EnhancedTrackingControlConfig()
            enhanced_tracking_control_configuration.Bandwidth = block.properties.Enhanced_Tracking_Control.properties.Bandwidth
            enhanced_tracking_control_configuration.Scale = block.properties.Enhanced_Tracking_Control.properties.Scale
            enhanced_tracking_control_configuration.Setup = EnhancedTrackingSetup(block.properties.Enhanced_Tracking_Control.properties.etc_setup_to_integer())
        elif key == Digital_Current_Loop:
            block: Digital_Current_Loop
            current_loop_gain_configuration = CurrentLoopGains(block.properties.K, block.properties.Ki, 0.0, drive_frequency_hz)

    # TODO: Add Autofocus support.
    auto_focus_gain_configuration = AutoFocusGains(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, drive_frequency_hz)

    # NOTE: If you want to change the runtime parameters, fill them out below.

    # If data is provided, we will use that data to fill in device information. Otherwise, make up some information
    # and treat this as the original configuration.
    if data is None:
        if True:
            # Read in some initial .fr file as the default model.
            [version, data] = read_frequency_response_result_from_a1_file("Initial_Model.fr")
            return data
        else:
            start_frequency = 10
            end_frequency = 2500
            number_of_divisions = 10

            frequency_response_configuration = FrequencyResponseConfiguration(description="A response configured by the System Modeling Tool",\
                                                                                inputMode=FRInput.Sinusoid, \
                                                                                type=FRType.ServoLoop, \
                                                                                startFrequency=start_frequency, \
                                                                                endFrequency=end_frequency, \
                                                                                amplitude=5, \
                                                                                numberOfDivisions=number_of_divisions, \
                                                                                directPlantIdentification=False)

            frequency_results = Array[FrequencyResponseFrequencyResult](number_of_divisions)
            for i in range(number_of_divisions):
                frequency_results[i] = FrequencyResponseFrequencyResult((end_frequency-start_frequency)/number_of_divisions)
            from System.Collections.Generic import Dictionary
            from System import String
            d= Dictionary[String, String]()

            #device_information = DeviceInformation()

            import inspect
            v =Version(get_a1_dll_version())
            e=EncoderGains()
            m=MotionUnits()
            sl=SoftwareLimitSystemInformation()
            tm=TuningMotionConfiguration()
            if False:
                device_information = DeviceInformation( \
                    controllerName="System Modeling Tool", \
                    taskIndex=1, \
                    taskMode=TaskMode.Secondary, \
                    axixIndex=0, \
                    axisName="X", \
                    amplifierPeakCurrent=0.0, \
                    amplifierMaxVoltage=0.0, \
                    axisCommandOutputType=AxisCommandOutputType.Current, \
                    driveType="Unknown", \
                    driveVersion=v, \
                    servoFrequency=20000.0, \
                    isHomed=False, \
                    isCalibrated=False, \
                    originalServoControl=False, \
                    motorType=MotorType.ACBrushlessLinear, \
                    motorTypeName="Unknown", \
                    stageType=TuningStageType.StandardStage, \
                    originalPositionErrorThreshold=0.0, \
                    positionFeedbackType=PrimaryFeedbackType.IncrementalEncoderSquareWave, \
                    velocityFeedbackType=AuxiliaryFeedbackType.IncrementalEncoderSquareWave, \
                    averageCurrentThreshold=0.0, \
                    countsPerUnit=0.0, \
                    isHighResolutionPositionFeedbackType=False, \
                    isHighResolutionVelocityFeedbackType=False, \
                    isBrakeControlEnabled=False, \
                    brakeEnableDelay=0, \
                    brakeDisableDelay=0, \
                    applyFeedforwardBeforeFilters=False, \
                    originalCurrentLoopGains=current_loop_gain_configuration, \
                    originalServoLoopConfiguration=servo_loop_configuration, \
                    originalAutoFocusGains=auto_focus_gain_configuration, \
                    originalPrimaryEncoderGains=e, \
                    originalSecondaryEncoderGains=e, \
                    numberOfSupportedFilters=0, \
                    isBrushlessMotorType=False, \
                    commutationInitializationSetup=0, \
                    countsPerRev=0.0, \
                    cyclesPerRev=0.0, \
                    maxJogSpeed=0.0, \
                    maxJogDistance=0.0, \
                    defaultSpeed=0.0, \
                    activeUnits=m, \
                    decimalPlaces=0, \
                    piezoVoltageClampLow=0.0, \
                    piezoVoltageClampHigh=0.0, \
                    piezoVoltsPerUnit=0.0, \
                    softwareLimitSettings=sl, \
                    defaultTuningMotionConfiguration=tm, \
                    enhancedTrackingControlConfig=enhanced_tracking_control_configuration, \
                    isDualLoop=False, \
                    runtimeParameters=d, \
                    isSignalLogEnabled=False, \
                    reverseMotionDirection=False, \
                    secondaryUnitsScaleFactor=0.0, \
                    secondaryUnitsName="inch", \
                    faultMask=AxisFault.PositionError, \
                    isGantry=False, \
                    gantryMechanicalDesign=GantryMechanicalDesign.Rigid)
            else:
                device_information = DeviceInformation( \
                    "System Modeling Tool", \
                    1, \
                    TaskMode.Secondary, \
                    1, \
                    "X", \
                    1.0, \
                    1.0, \
                    AxisCommandOutputType.Current, \
                    "XC4", \
                    v, \
                    20000.0, \
                    False, \
                    False, \
                    False, \
                    MotorType.ACBrushlessLinear, \
                    "ACBrushlessLinear", \
                    TuningStageType.StandardStage, \
                    1.0, \
                    PrimaryFeedbackType.IncrementalEncoderSquareWave, \
                    AuxiliaryFeedbackType.IncrementalEncoderSquareWave, \
                    1.0, \
                    1.0, \
                    False, \
                    False, \
                    False, \
                    1, \
                    1, \
                    False, \
                    current_loop_gain_configuration, \
                    servo_loop_configuration, \
                    auto_focus_gain_configuration, \
                    e, \
                    e, \
                    1, \
                    False, \
                    1, \
                    1.0, \
                    1.0, \
                    1.0, \
                    1.0, \
                    1.0, \
                    m, \
                    1, \
                    1.0, \
                    1.0, \
                    1.0, \
                    sl, \
                    tm, \
                    enhanced_tracking_control_configuration, \
                    False, \
                    d, \
                    False, \
                    False, \
                    1.0, \
                    "inch", \
                    AxisFault.PositionError, \
                    False, \
                    GantryMechanicalDesign.Rigid)

            frequency_response_axis_data = FrequencyResponseAxisResult(axisIndex=0, \
                                                                        axisName='X', \
                                                                        isServoControlOn=True, \
                                                                        maxOutput=999999.9, \
                                                                        servoLoopConfiguration=servo_loop_configuration, \
                                                                        frequencyResponseFrequencyResults=frequency_results, \
                                                                        deviceInformation=device_information)
            
            
            data = FrequencyResponseResult(frequency_response_configuration, FRInput.Sinusoid, frequency_response_axis_data)
        return data

    else:
        data = data.MemberwiseClone()

        #servo_loop_configuration = data.AxisData.DeviceInformation.OriginalServoLoopConfiguration.MemberwiseClone()
        #enhanced_tracking_control_configuration = data.AxisData.DeviceInformation.EnhancedTrackingControlConfig.MemberwiseClone()
        #current_loop_configuration = data.AxisData.DeviceInformation.OriginalCurrentLoopGains.MemberwiseClone()
        #autofocus_configuration = data.AxisData.DeviceInformation.OriginalAutoFocusGains.MemberwiseClone()

        # Write out to the original or shaped locations.
        old = data.AxisData.DeviceInformation
        if to_original:
            # DeviceInformation and ServoLoopConfiguration need to be updated but LoopShapingConfiguration remains empty.
            device_information = DeviceInformation(old.ControllerName, old.TaskIndex, old.TaskMode, old.AxisIndex, old.AxisName, old.AmplifierPeakCurrent, old.AmplifierMaxVoltage, \
                                    old.AxisCommandOutputType, old.DriveType, old.DriveVersion, old.ServoFrequency, old.IsHomed, old.IsCalibrated, old.OriginalServoControl, \
                                    old.MotorType, old.MotorTypeName, old.StageType, old.OriginalPositionErrorThreshold, old.PrimaryFeedbackType, old.AuxiliaryFeedbackType, \
                                    old.AverageCurrentThreshold, old.CountsPerUnit, old.IsHighResolutionPositionFeedbackType, old.IsHighResolutionVelocityFeedbackType, \
                                    old.IsBrakeControlEnabled, old.BrakeEnableDelay, old.BrakeDisableDelay, old.ApplyFeedforwardBeforeFilters, \
                                    current_loop_gain_configuration, servo_loop_configuration, auto_focus_gain_configuration, \
                                    old.OriginalPrimaryEncoderGains, old.OriginalSecondaryEncoderGains, old.NumberOfSupportedFilters, old.IsBrushlessMotorType, \
                                    old.CommutationInitializationSetup, old.CountsPerRev, old.CyclesPerRev, old.MaxJogSpeed, old.MaxJogDistance, old.DefaultSpeed, \
                                    old.ActiveUnitsName, old.DecimalPlaces, old.PiezoVoltageClampLow, old.PiezoVoltageClampHigh, old.PiezoVoltsPerUnit, \
                                    old.SoftwareLimitSettings, old.DefaultTuningMotionConfiguration, enhanced_tracking_control_configuration, \
                                    old.IsDualLoop, old.RuntimeParameters, old.IsSignalLogEnabled, old.ReverseMotionDirection, old.SecondaryUnitsScaleFactor, \
                                    old.SecondaryUnitsName, old.FaultMask, old.IsGantry, old.GantryMechanicalDesign)
            original_servo_loop_configuration = servo_loop_configuration
            loop_shaping_configuration = None
        else:
            # DeviceInformation and ServoLoopConfiguration remain the same but LoopShapingConfiguration is added or is changed.
            device_information = old
            original_servo_loop_configuration = old.OriginalServoLoopConfiguration
            loop_shaping_configuration = LoopShapingConfiguration(servo_loop_configuration, enhanced_tracking_control_configuration, \
                                                            auto_focus_gain_configuration, current_loop_gain_configuration)
        
        # Fill in runtime parameters.
        for key in block_layout.block_dictionary.keys():
            block = block_layout.block_dictionary[key]
            if key == Servo_Controller:
                block: Servo_Controller

                device_information.RuntimeParameters["ServoLoopGainAlpha"] = str(block.properties.Alpha)
                device_information.RuntimeParameters["ServoLoopGainK"] = str(block.properties.K)
                device_information.RuntimeParameters["CountsPerUnit"] = str(block.properties.Counts_Per_Unit)
            elif key == Digital_Current_Loop:
                block: Digital_Current_Loop

                device_information.RuntimeParameters["CurrentLoopFeedforwardBusVoltage"] = str(block.properties.Bus_Voltage__V)
                device_information.RuntimeParameters["CurrentLoopGainK"] = str(block.properties.K)
                device_information.RuntimeParameters["CurrentLoopGainKi"] = str(block.properties.Ki)
                device_information.RuntimeParameters["CurrentLoopFeedforwardGainLff"] = str(block.properties.Lff__mH)
                device_information.RuntimeParameters["CurrentLoopFeedforwardGainRff"] = str(block.properties.Rff__ohm)

        axis_data = FrequencyResponseAxisResult(data.AxisData.AxisIndex, data.AxisData.AxisName, data.AxisData.IsServoControlOn, data.AxisData.MaxOutput, \
                                                original_servo_loop_configuration, data.AxisData.FrequencyResponseFrequencyResults, \
                                                data.AxisData.AxisConfiguration, device_information, loop_shaping_configuration)
        
        return FrequencyResponseResult(data.Configuration, data.InputMode, axis_data)

def run_easy_tune(block_layout:Block_Layout.Block_Layout, data:FrequencyResponseResult, verification=False, performance_target=None) -> dict:
    def get_max_sensitivity():
        # NOTE: This function re-implements:
        # https://scm2.aerotech.com/projects/CTRL/repos/automation1/browse/pc/libs/ApplicationWpfLibrary/Source/Services/TuningService/EasyTune/EasyTuneService.cs?at=refs%2Ftags%2FRelease_2.10.0#25,75,77,80,82
        from Modules.Easy_Tune_Module import OPTIMIZATION_TARGET_RANGE_MIN, OPTIMIZATION_TARGET_RANGE_MAX
        if performance_target is None:
            optimization_target = 0
        else:
            optimization_target = performance_target
        stage_type = data.AxisData.DeviceInformation.StageType
        sensitivity_min = 2 if stage_type == TuningStageType.StandardStage else 2
        sensitivity_max = 8 if stage_type == TuningStageType.StandardStage else 6

        optimization_target_range = OPTIMIZATION_TARGET_RANGE_MAX - OPTIMIZATION_TARGET_RANGE_MIN
        optimization_target_percent = (optimization_target - OPTIMIZATION_TARGET_RANGE_MIN) / optimization_target_range
        return sensitivity_min + (sensitivity_max - sensitivity_min) * optimization_target_percent
    
    result = None
    exception = None
    try:
        # Galvos cannot run EasyTune. If they do, they get some unrelated index out of bounds error.
        if block_layout.block_dictionary[Servo_Controller].properties.Drive_Type == DriveType.Galvo:
            raise NotImplementedError("Galvos are not supported by EasyTune.")

        # Get the max sensitivity based off of optimization target.
        max_sensitivity = get_max_sensitivity()

        # Based off of the current, shaped block layout, get the data object to run the response off of in the original response form.
        data = get_a1_data_from_block_layout(block_layout, data, to_original=True)

    #region FrequencyResponseAnalyzer
        # The FrequencyResponseAnalyzer is re-implemented using the following (based off of the shaped response):
        # NOTE: https://scm2.aerotech.com/projects/CTRL/repos/automation1/browse/pc/libs/ApplicationWpfLibrary/Source/Services/TuningService/EasyTune/EasyTuneService.cs?at=refs%2Ftags%2FRelease_2.10.0#1700
        device_information = data.AxisData.DeviceInformation
        servo_loop_configuration = data.AxisData.ServoLoopConfiguration
        enhanced_tracking_control_configuration = device_information.EnhancedTrackingControlConfig

        pid_controller = PIDController(servoGains=servo_loop_configuration.ServoGains, \
                                maxOutput=data.AxisData.MaxOutput, \
                                countsPerUnit=device_information.CountsPerUnit, \
                                useJffSff=data.IsGalvoMotorResponse())
        
        if data.AxisData.IsServoControlOn:
            frequency_response_analyzer = FrequencyResponseAnalyzer.CreateFromOpenLoop( \
                openloopResponse=data.GetFrequencyResponse(), \
                controller=pid_controller, \
                filterCoeffs=servo_loop_configuration.EnabledFilterCoeffs, \
                feedforwardFilters=servo_loop_configuration.EnabledFeedforwardFilters, \
                etcConfig=enhanced_tracking_control_configuration, \
                isPiezo=device_information.IsPiezo, \
                isDualLoop=device_information.IsDualLoop)
        else:
            frequency_response_analyzer = FrequencyResponseAnalyzer.CreateFromPlant( \
                plantResponse=data.GetFrequencyResponse(), \
                controller=pid_controller, \
                filterCoeffs=servo_loop_configuration.EnabledFilterCoeffs, \
                feedforwardFilters=servo_loop_configuration.EnabledFeedforwardFilters, \
                etcConfig=enhanced_tracking_control_configuration, \
                isPiezo=device_information.IsPiezo, \
                isDualLoop=device_information.IsDualLoop)
    #endregion

    #region EasyTune Parameters
        # NOTE: The following is re-implemented from:
        # https://scm2.aerotech.com/projects/CTRL/repos/automation1/browse/pc/libs/ApplicationWpfLibrary/Source/Services/TuningService/TuningService.cs?at=Release_2.10.0#1636
        fr_input = data.InputMode
        apply_feedforward_before = device_information.ApplyFeedforwardBeforeFilters
        counts_per_unit = device_information.CountsPerUnit
        is_piezo = device_information.IsPiezo
        if verification:
            sensitivity_optimization_options = ObjectiveFunctionOptimizationOptions( \
            maxSensitivity=max_sensitivity, \
            minCrossoverFrequency=frequency_response_analyzer.GetOpenLoopResponse().Frequency[0], \
            maxCrossoverFrequency=min(250, device_information.ServoFrequency/2.0), \
            minZeroLocWrtCO=0.1, \
            maxZeroLocWrtCO=0.5, \
            minLowpassCutoffWrtCO=-1, \
            maxLowpassCutoffWrtCO=-1, \
            allowPhaseStableResonanceCO=False, \
            maxNumResonances=16, \
            notchCenterFreqVariation=0.1, \
            notchWidthMinWRTCenterFreq=0.10, \
            notchWidthMaxWRTCenterFreq=1.99, \
            notchDepthMin=4.0, \
            notchDepthMax=30.0, \
            alpha=2.0, \
            optimizeFilterOption=OptimizeFilterOption.AddOnly, # Always overwrite the existing filters.     AddOnly     DoNothing
            validatePlant=False)
        else:
            sensitivity_optimization_options = ObjectiveFunctionOptimizationOptions( \
                maxSensitivity=max_sensitivity, \
                minCrossoverFrequency=frequency_response_analyzer.GetOpenLoopResponse().Frequency[0], \
                maxCrossoverFrequency=min(250, device_information.ServoFrequency/2.0), \
                minZeroLocWrtCO=0.1, \
                maxZeroLocWrtCO=0.5, \
                minLowpassCutoffWrtCO=-1, \
                maxLowpassCutoffWrtCO=-1, \
                allowPhaseStableResonanceCO=False, \
                maxNumResonances=16, \
                notchCenterFreqVariation=0.1, \
                notchWidthMinWRTCenterFreq=0.10, \
                notchWidthMaxWRTCenterFreq=1.99, \
                notchDepthMin=4.0, \
                notchDepthMax=30.0, \
                alpha=2.0, \
                optimizeFilterOption=OptimizeFilterOption.OverwriteExisting, # Always overwrite the existing filters.     AddOnly     DoNothing
                validatePlant=False)
    #endregion

        #input("hold. press to continue")

        # Finally, run EasyTune. FrequencyResponseAnalyzer updates with any tuning results.
        # Can fail with "System.AggregateException: One or more errors occurred. (Could not optimize the axis.)"
        
        try:
            result = Wrapper_Tasks.OptimizeSensitivityObjectiveFunction(fr_input, apply_feedforward_before, counts_per_unit, \
                                                                is_piezo, sensitivity_optimization_options, frequency_response_analyzer)
        except Exception as e:
            exception = e
    except Exception as e:
        exception = e

    if result is None:
        return [False, 0, 0, 0, "", exception]
    else:
        did_converge = result.DidConverge
        optimization_options = result.OptimizationOptions
        number_of_generations = result.NumberOfGenerations
        best_result = result.BestResult
        optimization_time = result.OptimizationTime
        number_of_threads_used = result.NumberOfThreadsUsed
        population_log = result.PopulationLog
        generation_log = result.GenerationLog

        # Make log directory if it does not already exist.
        username = os.getlogin()
        working_directory = os.path.join(f"O:\\EasyTune Plus Analysis", "EasyTune Logs")
        if not os.path.exists(working_directory):
            os.makedirs(working_directory)

        current_time = datetime.now()
        time_string = current_time.strftime("%Y.%m.%d %H.%M.%S")
        log_folder = "{}_EasyTune {}".format(device_information.AxisName, time_string)
        log_directory = os.path.join(working_directory, log_folder)
        if not os.path.exists(log_directory):
            os.mkdir(log_directory)
        
        # Add log files.
        population_log_path = os.path.join(log_directory, "Optimization Population Log.csv")
        generation_log_path = os.path.join(log_directory, "Optimization Generation Log.csv")
        result.SerializePopulationCSV(population_log_path, OptimizationLoggingLevel.Verbose)
        result.SerializeGenerationCSV(generation_log_path, OptimizationLoggingLevel.Verbose)

        # Zip directory.
        zip_directory = shutil.make_archive(log_directory, 'zip', root_dir=log_directory, base_dir=".")

        # Delete original directory and leave only the zipped directory.
        #shutil.rmtree(log_directory)
        
        # Generate the filter coefficient list.
        servo_filters = Wrapper_Utils.GetFilterCoeffs(frequency_response_analyzer.get_Filters())

        # Return the tuned controller.
        servo_loop_configuration = ServoLoopConfiguration(frequency_response_analyzer.get_ControllerGains(), \
                                                        servo_filters, frequency_response_analyzer.get_FeedforwardFilters())
        servo_controller = Servo_Controller()
        get_servo_controller_from_servo_loop_configuration(servo_controller, servo_loop_configuration)

        return [did_converge, servo_controller, number_of_generations, optimization_time.Milliseconds, zip_directory, exception]


def backward_calculate_filter(properties:Filter_Model._Properties, recompute_type=False):
    # Compute the cutoff frequency, etc. based off of the N0 - N2 coefficients
    filter_coefficients = FilterCoeffs()    
    filter_coefficients.N0 = properties.N0
    filter_coefficients.N1 = properties.N1
    filter_coefficients.N2 = properties.N2
    filter_coefficients.D1 = properties.D1
    filter_coefficients.D2 = properties.D2
    a1_filter = Filter(properties.sampling_frequency, filter_coefficients)

    if recompute_type:
        type = FilterType(a1_filter.Type.value__)
        properties._filter_type = type

    try:
        if properties.filter_type == FilterType.Empty:
            return
        elif properties.filter_type == FilterType.Low_Pass:
            parameters = a1_filter.BackCalculateLowPass()
            properties._parameters = [parameters.CutoffFrequency]
        elif properties.filter_type == FilterType.High_Pass:
            parameters = a1_filter.BackCalculateHighPass()
            properties._parameters = [parameters.CutoffFrequency]
        elif properties.filter_type == FilterType.Lead_Lag:
            parameters = a1_filter.BackCalculateLeadLag()
            properties._parameters = [parameters.PhaseFrequency, parameters.Phase]
        elif properties.filter_type == FilterType.Notch:
            parameters = a1_filter.BackCalculateNotch()
            properties._parameters = [parameters.CenterFrequency, parameters.Width, parameters.Depth]
        elif properties.filter_type == FilterType.Resonant:
            parameters = a1_filter.BackCalculateResonant()
            properties._parameters = [parameters.CenterFrequency, parameters.Width, parameters.Gain]
        elif properties.filter_type == FilterType.Custom:
            properties._parameters = [properties.N0, properties.N1, properties.N2, properties.D1, properties.D2]
        else:
            raise NotImplementedError("The filter type ({}) is not handled!".format(properties.filter_type))
    except NotImplementedError:
        raise
    except:
        # If we get some computation error, just reset the user parameters.
        num_parameters = len(FILTER_PARAMETER_MAPPING[properties.filter_type])
        properties._parameters = [0.0]*num_parameters

    # Sanitize results.
    for i in range(len(properties.parameters)):
        if math.isnan(properties.parameters[i]) or math.isinf(properties.parameters[i]):
            properties._parameters[i] = 0.0

def forward_calculate_filter(properties:Filter_Model._Properties):
    # Compute the N0 - N2 coefficients based off of frequency
    a1_filter = Filter(properties.sampling_frequency)

    try:
        if properties.filter_type == FilterType.Empty:
            return
        elif properties.filter_type == FilterType.Low_Pass:
            a1_filter.CalculateLowPass(properties.parameters[0])
        elif properties.filter_type == FilterType.High_Pass:
            a1_filter.CalculateHighPass(properties.parameters[0])
        elif properties.filter_type == FilterType.Lead_Lag:
            a1_filter.CalculateLeadLag(properties.parameters[0], properties.parameters[1])
        elif properties.filter_type == FilterType.Notch:
            a1_filter.CalculateNotch(properties.parameters[0], properties.parameters[1], properties.parameters[2])
        elif properties.filter_type == FilterType.Resonant:
            a1_filter.CalculateResonant(properties.parameters[0], properties.parameters[1], properties.parameters[2])
        elif properties.filter_type == FilterType.Custom:
            return
        else:
            raise NotImplementedError("The filter type ({}) is not handled!".format(properties.filter_type))
    except NotImplementedError:
        raise
    except:
        # If we get some computation error, just reset the coefficients.
        properties.N0 = 0.0
        properties.N1 = 0.0
        properties.N2 = 0.0
        properties.D1 = 0.0
        properties.D2 = 0.0
    
    # Set coefficients.
    properties.N0 = 0.0 if math.isnan(a1_filter.Coeffs.N0) or math.isinf(a1_filter.Coeffs.N0) else a1_filter.Coeffs.N0
    properties.N1 = 0.0 if math.isnan(a1_filter.Coeffs.N1) or math.isinf(a1_filter.Coeffs.N1) else a1_filter.Coeffs.N1
    properties.N2 = 0.0 if math.isnan(a1_filter.Coeffs.N2) or math.isinf(a1_filter.Coeffs.N2) else a1_filter.Coeffs.N2
    properties.D1 = 0.0 if math.isnan(a1_filter.Coeffs.D1) or math.isinf(a1_filter.Coeffs.D1) else a1_filter.Coeffs.D1
    properties.D2 = 0.0 if math.isnan(a1_filter.Coeffs.D2) or math.isinf(a1_filter.Coeffs.D2) else a1_filter.Coeffs.D2

def read_frequency_response_result_from_a1_file(filepath:str) -> tuple[str, list]:
    oldest_compatible_version = PlotFileXmlSerializer.ReadFrequencyResponseFile(filepath).FileVersionInformation.get_OldestCompatibleSoftwareVersion()
    version = PlotFileXmlSerializer.ReadFrequencyResponseFile(filepath).FileVersionInformation.get_SoftwareVersion()
    data = PlotFileXmlSerializer.ReadFrequencyResponseFile(filepath).Data
    return [version, data]

def write_frequency_response_result_to_a1_file(filepath:str, data):
    PlotFileXmlSerializer.WriteFrequencyResponseFile(filepath, data)

def get_frd_from_a1_data(data) -> tuple[Loop_Type, control.FRD]:
    # Get the loop type.
    loop_name = data.Configuration.Type.ToString()
    if loop_name == "ServoLoop":
        loop_type = Loop_Type.Servo
    elif loop_name == "CurrentLoop":
        loop_type = Loop_Type.Current
    elif loop_name == "AutofocusLoop":
        raise NotImplementedError("Autofocus is not supported!")
    else:
        raise NotImplementedError("The loop type: {} is unknown!".format(loop_name))
    
    # Get the response.
    a1_fr_data_fr = data.GetFrequencyResponse()
    num_frequencies = len(a1_fr_data_fr.Frequency)
    frequency = [0.0]*num_frequencies
    magnitude = [0.0]*num_frequencies
    phase = [0.0]*num_frequencies
    src_idx = -1
    dest_idx = 0
    while src_idx < num_frequencies-1:
        src_idx += 1

        if not a1_fr_data_fr.DataValid[src_idx]:
            # Skip this sample
            continue
        
        frequency[dest_idx] = a1_fr_data_fr.Frequency[src_idx]
        magnitude[dest_idx] = a1_fr_data_fr.Magnitude[src_idx]
        phase[dest_idx] = a1_fr_data_fr.Phase[src_idx]
        dest_idx += 1
    
    # Data processing.
    # Need to convert the frequency to rad/s, magnitude and phase to complex number
    amplitude = control.db2mag(np.array(magnitude))
    complex_number = np.multiply(amplitude, np.exp(np.multiply(complex(0, 1), np.multiply(phase, np.pi/180))))
    frequency_radians = Utils.hertz_to_radian(frequency)
    #print(frequency_radians)

    ol_frd = control.frd(complex_number, frequency_radians, smooth=True)
    #ol = control.frequency_response(ol_frd, omega=np.array(frequency_radians)-10)

    #ol_frd.name = FrequencyResponse.FrequencyResponseType.Open_Loop.name
    return [loop_type, ol_frd]
