from pythonnet import load
load("coreclr")

# Import System for Type.GetType and Array manipulation
import System
from System.Collections.Generic import List
from System import String, Double, Array

import clr

import automation1 as a1
import sys
import contextlib
import os
import time
import numpy as np
import tkinter as tk
from tkinter import SEL, messagebox, filedialog
import math
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.offline as pyo
from datetime import datetime
import zipfile
import xml.etree.ElementTree as ET
import shutil


class EncoderTuning():
    """
    Class to handle encoder tuning for a controller.

    This class manages the tuning of encoder values for a given axis based
    on encoder sine and cosine values gathered during a move.

    It also provides methods to interact with the controller for commanding motion, 
    gathering data, and modifying parameters.
    """
    _dlls_loaded = False # Class attribute to ensure DLLs are loaded only once per session

    def __init__(self, controller, axes):
        """
        Initializes the EncoderTuning class with a controller and axes.
        
        Args:
        controller (a1.Controller): A1 controller object.
        axes (list): List of axes being tested.
        """
        self.controller = controller
        self.axes = axes
        self.EllipseFit = None
        
        try:
            type_name1 = "Aerotech.Automation1.Applications.Shared.EllipseFit, Aerotech.Automation1.Applications.Shared"
            type_name2 = "Aerotech.Automation1.Applications.Shared.EllipseData, Aerotech.Automation1.Applications.Shared"
            self.EllipseFit = System.Type.GetType(type_name1, True) # True throws exception if not found
            self.EllipseData = System.Type.GetType(type_name2, True)
        except Exception as e:
            print("\nFATAL: Could not retrieve required Aerotech types.")
            print("Ensure that the main application has loaded the Aerotech.Automation1.Applications.Shared.dll.")
            print(f"Error: {e}")
            # Set to None so other methods can fail gracefully
            self.EllipseFit = None
            self.EllipseData = None

    def initialize_dll(self):
        """
        Set up and initialize DLL paths

        Args:
        None

        Returns:
        None
        """
        # Add Aerotech DLL directory to PATH
        #self.AEROTECH_DLL_PATH = os.path.join(os.path.dirname(__file__), "extern", "Automation1")
        #if not os.path.exists(self.AEROTECH_DLL_PATH):
            #print(f"ERROR: Aerotech DLL path not found: {self.AEROTECH_DLL_PATH}")
            #return
        
        # Add ConfigurationManager path
        self.CONFIG_MANAGER_PATH = os.path.join(os.path.dirname(__file__), "System.Configuration.ConfigurationManager.8.0.0", "lib", "netstandard2.0")
        if not os.path.exists(self.CONFIG_MANAGER_PATH):
            print(f"ERROR: ConfigurationManager not found at {self.CONFIG_MANAGER_PATH}")
            return
    
    def load_dll(self):
        """
        Loads the required Aerotech DLLs and gets the necessary types for tuning.
        """
        try:
            # Load ConfigurationManager
            print("\nLoading ConfigurationManager...")
            clr.AddReference(os.path.join(self.CONFIG_MANAGER_PATH, "System.Configuration.ConfigurationManager.dll"))

        except Exception as e:
            print("\nERROR: An exception occurred:")
            print(str(e))
            print("\nException type:", type(e).__name__)
            if hasattr(e, 'InnerException') and e.InnerException:
                print("\nInner Exception:")
                print(str(e.InnerException))
    
    def apply_gains(self, final_gains):
        """
        Applies the calculated gains to the controller configuration.   
        This method retrieves the current configuration, modifies the encoder gains,
        and then saves the updated configuration back to the controller.
        """
        configured_parameters = self.controller.configuration.parameters.get_configuration()

        for axis, gains in final_gains.items():
            
            # Update the gains
            configured_parameters.axes[axis].feedback.primaryencoder0sinegain.value = gains['SineGain']
            configured_parameters.axes[axis].feedback.primaryencoder0sineoffset.value = gains['SineOffset(mV)']
            configured_parameters.axes[axis].feedback.primaryencoder0cosinegain.value = gains['CosineGain']
            configured_parameters.axes[axis].feedback.primaryencoder0cosineoffset.value = gains['CosineOffset(mV)']
            
            # Set the phase correction if available
            if 'Phase(degrees)' in gains:
                configured_parameters.axes[axis].feedback.primaryencoder0phase.value = gains['Phase(degrees)']
        
        self.controller.configuration.parameters.set_configuration(configured_parameters)
        print("✅ Successfully applied encoder tuning parameters")

        self.controller.reset()  # Reset the controller to apply changes

    def calculate_motion_parameters(self, axis, number_of_encoder_cycles=50, constant_velocity_buffer_time_ms=200):
        """
        Calculates the motion parameters based on the decompiled Aerotech logic.

        Args:
            axis (str): The name of the axis to calculate for.
            number_of_encoder_cycles (int): The number of electrical cycles to capture.
            constant_velocity_buffer_time_ms (int): Buffer time in milliseconds.

        Returns:
            tuple: (travel_distance, travel_speed, distance_to_analyze)
        """
        
        # Get necessary parameters from the controller
        # Using a default task index of 1, as is common.
        task_index = 1
        params = self.controller.runtime.parameters
        status_item_configuration = a1.StatusItemConfiguration()
        status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis)
        results = self.controller.runtime.status.get_status_items(status_item_configuration)

        encoder_multiplication_factor = params.axes[axis].feedback.primaryencodermultiplicationfactor.value
        counts_per_unit = params.axes[axis].units.countsperunit.value
        velocitycommandfault = int(params.axes[axis].protection.faultmask.value)

        velocitycommandthreshold = params.axes[axis].protection.velocitycommandthreshold.value
        velocitycommandbeforehome = params.axes[axis].protection.velocitycommandthresholdbeforehome.value
        if (velocitycommandfault & 1 << 10) == 0:
            velocity_command_threshold = float('inf')
        elif velocitycommandthreshold == 0 and velocitycommandbeforehome == 0:
            velocity_command_threshold = float('inf')
        else:
            axis_status = int(results.axis.get(a1.AxisStatusItem.AxisStatus, axis).value)
            is_homed = (axis_status & a1.AxisStatus.Homed) == a1.AxisStatus.Homed
            velocity_command_threshold = velocitycommandthreshold if not is_homed else velocitycommandthreshold

        ramp_mode = a1.RampMode(params.tasks[task_index].motion.defaultcoordinatedrampmode.value)
        ramp_time = params.tasks[task_index].motion.defaultcoordinatedramptime.value
        ramp_rate = params.tasks[task_index].motion.defaultcoordinatedramprate.value


        # Calculate distance_to_analyze (num2 in C# code)
        units_per_cycle = encoder_multiplication_factor / counts_per_unit
        distance_to_analyze = float(number_of_encoder_cycles) * units_per_cycle

        # Calculate travel_speed (num3 in C# code)
        travel_speed = min(distance_to_analyze * 4.0, velocity_command_threshold * 0.9)

        # Calculate ramping_distance (num4 in C# code)
        ramping_distance = 0.0
        if ramp_mode == a1.RampMode.Time:
            # For time-based ramping, distance = 0.5 * v * t
            ramping_distance = 0.5 * travel_speed * ramp_time
        elif ramp_mode == a1.RampMode.Rate:
            # For rate-based ramping, distance = 0.5 * v^2 / a
            if ramp_rate > 0:
                ramping_distance = 0.5 * (travel_speed**2) / ramp_rate
        
        # The total ramp distance is for both acceleration and deceleration
        total_ramping_distance = 2 * ramping_distance

        # Calculate constant velocity buffer distance (num5 in C# code)
        buffer_distance = (constant_velocity_buffer_time_ms / 1000.0) * travel_speed

        # Calculate total travel_distance (num6 in C# code)
        travel_distance = total_ramping_distance + distance_to_analyze + buffer_distance

        return travel_distance, travel_speed, distance_to_analyze

    def data_config(self, n: int, freq: a1.DataCollectionFrequency, axis: str) -> a1.DataCollectionConfiguration:
        """
        Data configurations. These are how to configure data collection parameters

        Args:
        n (int): Number of points to collect (sample rate * time).
        freq (a1 object): Data collection frequency (limited to the available frequencies listed in the Studio dropdown).

        Returns:
        data_config: A1 data collection object used for data collection in A1
        """
        # Create a data collection configuration with sample count and frequency
        data_config = a1.DataCollectionConfiguration(n, freq)

        # Add items to collect data on the entire system
        data_config.system.add(a1.SystemDataSignal.DataCollectionSampleTime)

        
        # Add items to collect data on the specified axis
        data_config.axis.add(a1.AxisDataSignal.VelocityCommand, axis) # Added for filtering
        data_config.axis.add(a1.AxisDataSignal.EncoderCosine, axis)
        data_config.axis.add(a1.AxisDataSignal.EncoderSine, axis)
        data_config.axis.add(a1.AxisDataSignal.EncoderCosineRaw, axis)
        data_config.axis.add(a1.AxisDataSignal.EncoderSineRaw, axis)
        
        return data_config

    def generate_axis_specs(self):
        """
        Generates specifications for each axis including type, encoder type, resolution, and max velocity.
        Returns: 
        axis_specs (dict): A dictionary containing axis specifications.
        axes_to_tune (list): A list of axes that can be tuned.
        """
        axis_specs = {}
        axes_to_tune = []
        for axis in self.axes:
            axis_specs[axis] = {}
            # Determine if rotary or linear axes
            units_value = self.controller.runtime.parameters.axes[axis].units.unitsname.value
            if units_value == 'deg':
                axis_specs[axis]['Stage Type'] = 'rotary'
            else:
                axis_specs[axis]['Stage Type'] = 'linear'

            # Determine if sine or square wave
            wave_type = int(self.controller.runtime.parameters.axes[axis].feedback.primaryfeedbacktype.value)

            # Check for various sine-based encoder types
            if (wave_type in [2, 3, 10]): # 2=Sine, 3=EnDat+Sine, 10=BiSS+Sine
                axis_specs[axis]['Encoder Type'] = 'sine'
                axes_to_tune.append(axis)
        
            # Get resolution for distance
            resolution = self.controller.runtime.parameters.axes[axis].feedback.primaryfeedbackresolution.value
            axis_specs[axis]['Resolution'] = resolution

            # Get max velocity
            max_velocity = self.controller.runtime.parameters.axes[axis].motion.maxspeedclamp.value
            axis_specs[axis]['Max Velocity'] = max_velocity

        return axis_specs, axes_to_tune

    def fit_ellipse(self, signal_dict):
        """
        Use raw encoder data to fit an ellipse.

        Args:
            signal_dict (dict): Dictionary of encoder signals organized by axis and signal name.

        Returns:
            axis_ellipse_data (dict): Dictionary containing the ellipse fit result for each axis.
        """
        axis_ellipse_data = {}
        print('\nFitting ellipse for collected data...')
        for axis, signals in signal_dict.items():
            # Use the raw signals for fitting the ellipse
            if 'EncoderSineRaw' in signals and 'EncoderCosineRaw' in signals:
                # Extract raw sine and cosine data
                sine_data_raw = signals['EncoderSineRaw']
                cosine_data_raw = signals['EncoderCosineRaw']
                
                # Convert Python lists to .NET System.Array[System.Double]
                # The EllipseFit method signature is Fit(sineData, cosineData).
                # This means the first argument (x-axis) is sine, second (y-axis) is cosine.
                sine_array = Array[Double]([Double(x) for x in sine_data_raw])
                cosine_array = Array[Double]([Double(x) for x in cosine_data_raw])

                # Get the static 'Fit' method from the EllipseFit class type
                fit_method = self.EllipseFit.GetMethod("Fit")
                
                # Invoke the 'Fit' method with the correct argument order
                fit_result = fit_method.Invoke(None, [sine_array, cosine_array])
                
                # Store the resulting EllipseData object
                axis_ellipse_data[axis] = fit_result
                print(f"Ellipse fit complete for {axis}.")
            else:
                print(f"Warning: Raw sine/cosine data not found for axis {axis}. Skipping ellipse fit.")

        return axis_ellipse_data

    def _unwrap_arc_tan(self, phase_data, threshold):
        """
        Replicates the unwrapArcTan C# method to remove phase wraps.
        """
        unwrapped = np.copy(phase_data)
        for i in range(1, len(unwrapped)):
            diff = unwrapped[i] - unwrapped[i-1]
            if diff > threshold:
                unwrapped[i:] -= 2 * math.pi
            elif diff < -threshold:
                unwrapped[i:] += 2 * math.pi
        return unwrapped.tolist()

    def calculate_final_gains(self, ellipse_data_dict, signal_dict):
        """
        Calculates the final encoder gains from the ellipse data by replicating
        the iterative search algorithm found in the Aerotech.Automation1.Applications.Wpf.EncoderTuningService.

        Args:
            ellipse_data_dict (dict): A dictionary containing the EllipseData object for each axis.
            signal_dict (dict): The dictionary containing the raw signal data for each axis.
        """
        print("\nCalculating final gains from ellipse data using iterative search method...")
        final_gains_dict = {}
        
        # This constant is derived from the decompiled source. It appears to be related to
        # the nominal amplitude of a perfect Lissajous figure in the Aerotech system.
        IDEAL_LISSAJOUS_AMPLITUDE = 0.5
        
        # Define the valid range for the gain parameters based on controller limits.
        MIN_GAIN = 0.4
        MAX_GAIN = 1.75

        for axis, initial_ellipse_data in ellipse_data_dict.items():
            if initial_ellipse_data is None:
                continue

            print(f"\n--- Processing Axis: {axis} ---")
            
            # --- 1. Get initial data and center it ---
            # The original raw data is needed for the iterative process
            sine_data_raw = signal_dict[axis]['EncoderSineRaw']
            cosine_data_raw = signal_dict[axis]['EncoderCosineRaw']

            center_x = initial_ellipse_data.CenterX
            center_y = initial_ellipse_data.CenterY
            
            centered_sine = [s - center_x for s in sine_data_raw]
            centered_cosine = [c - center_y for c in cosine_data_raw]

            # --- Helper function to apply phase correction and re-fit ellipse ---
            def _calculate_new_ellipse(phase_deg, sine_pts, cos_pts):
                """ Replicates the calculateNewEllipse C# method. """
                half_phase_deg = phase_deg / 2.0
                if abs(half_phase_deg - 45.0) < 1e-9:
                    return None # Or handle as an error case

                half_phase_rad = math.radians(half_phase_deg)
                
                cos_2_half_rad = math.cos(2.0 * half_phase_rad)
                if abs(cos_2_half_rad) < 1e-9:
                    return None # Avoid division by zero

                c1 = math.cos(half_phase_rad) / cos_2_half_rad
                c2 = -math.sin(half_phase_rad) / cos_2_half_rad

                corrected_sine = [(c1 * s) + (c2 * c) for s, c in zip(sine_pts, cos_pts)]
                corrected_cosine = [(c1 * c) + (c2 * s) for s, c in zip(sine_pts, cos_pts)]
                
                # Convert to .NET arrays for the Fit method
                sine_array = Array[Double]([Double(s) for s in corrected_sine])
                cosine_array = Array[Double]([Double(c) for c in corrected_cosine])
                
                fit_method = self.EllipseFit.GetMethod("Fit")
                return fit_method.Invoke(None, [sine_array, cosine_array])

            # --- 2. Coarse Scan to find the approximate phase correction ---
            print("Performing coarse phase scan (-30 to +30 degrees)...")
            coarse_scan_results = {}
            for phase in range(-30, 31, 1):
                ellipse = _calculate_new_ellipse(float(phase), centered_sine, centered_cosine)
                if ellipse:
                    coarse_scan_results[float(phase)] = ellipse.Phi # Store the resulting ellipse rotation

            # Find the phase value that results in an ellipse rotation closest to zero
            best_coarse_phase = min(coarse_scan_results, key=lambda p: abs(coarse_scan_results[p]))
            print(f"Best coarse phase correction: {best_coarse_phase} degrees")

            # --- 3. Fine Scan around the best coarse value ---
            print(f"Performing fine phase scan ({best_coarse_phase - 1} to {best_coarse_phase + 1} degrees)...")
            fine_scan_results = {}
            for phase_decimal in np.arange(best_coarse_phase - 1.0, best_coarse_phase + 1.1, 0.1):
                phase = round(phase_decimal, 1)
                ellipse = _calculate_new_ellipse(phase, centered_sine, centered_cosine)
                if ellipse:
                    fine_scan_results[phase] = ellipse.Phi

            # --- 4. Unwrap and Interpolate to find the precise phase correction ---
            phases = list(fine_scan_results.keys())
            phis_raw = list(fine_scan_results.values())
            
            # Unwrap the raw Phi values to get a continuous phase curve
            phis_unwrapped = self._unwrap_arc_tan(phis_raw, math.pi * 7.0 / 8.0)

            # Find where the unwrapped phase crosses zero
            crossover_index = -1
            for i in range(len(phis_unwrapped) - 1):
                if np.sign(phis_unwrapped[i]) != np.sign(phis_unwrapped[i+1]):
                    crossover_index = i
                    break
            
            final_phase_correction = 0.0
            if crossover_index != -1:
                # Linear interpolation: y = y1 + (x - x1) * (y2 - y1) / (x2 - x1)
                # We want to find x (phase) where y (phi) is 0.
                # x = x1 - y1 * (x2 - x1) / (y2 - y1)
                phi1, phi2 = phis_unwrapped[crossover_index], phis_unwrapped[crossover_index+1]
                phase1, phase2 = phases[crossover_index], phases[crossover_index+1]
                final_phase_correction = phase1 - phi1 * (phase2 - phase1) / (phi2 - phi1)
            else:
                # If no crossover, just use the best value from the fine scan
                print("Warning: No zero crossover found in fine scan. Using best-fit value.")
                final_phase_correction = min(fine_scan_results, key=lambda p: abs(fine_scan_results[p]))
            
            print(f"Final interpolated phase correction: {final_phase_correction} degrees")

            # --- 5. Calculate final gains with the precise phase correction ---
            final_corrected_ellipse = _calculate_new_ellipse(final_phase_correction, centered_sine, centered_cosine)

            final_sine_gain = IDEAL_LISSAJOUS_AMPLITUDE / final_corrected_ellipse.Width
            final_cosine_gain = IDEAL_LISSAJOUS_AMPLITUDE / final_corrected_ellipse.Height

            # --- 6. Assemble the final values ---
            final_sine_offset = -initial_ellipse_data.CenterX * 1000.0
            final_cosine_offset = -initial_ellipse_data.CenterY * 1000.0

            # Clamp the gains to the valid range
            clamped_sine_gain = max(MIN_GAIN, min(final_sine_gain, MAX_GAIN))
            clamped_cosine_gain = max(MIN_GAIN, min(final_cosine_gain, MAX_GAIN))

            final_gains = {
                'SineGain': clamped_sine_gain,
                'SineOffset(mV)': final_sine_offset,
                'CosineGain': clamped_cosine_gain,
                'CosineOffset(mV)': final_cosine_offset,
                'Phase(degrees)': final_phase_correction
            }
            final_gains_dict[axis] = final_gains
            
        return final_gains_dict

    def collect_data(self):
        """
        Move axis and collect encoder data that will be used to fit the ellipse.
        
        Returns:
        results (dict): A dictionary of results keyed by axis name.
        speeds_used (dict): A dictionary of the commanded speed for each axis.
        """
        # Get axis specs and list of axes to tune
        axis_specs, axes_to_tune = self.generate_axis_specs()
        if not axes_to_tune:
            print("No axes with sine-based encoders found to tune.")
            return {}, {}

        self.controller.runtime.commands.motion.enable(self.axes)

        results = {}
        speeds_used = {}
        for axis in axes_to_tune:
            print(f"\n--- Starting data collection for axis: {axis} ---")
            
            # Calculate the ideal motion parameters for this axis
            distance, speed, _ = self.calculate_motion_parameters(axis)
            speeds_used[axis] = speed # Store the speed for this axis
        
            move_time = distance / speed if speed > 0 else 0
            
            # Setup Data Collection
            sample_rate = 1000
            n = int(sample_rate * (move_time + 1)) # Add a buffer
            freq = a1.DataCollectionFrequency.Frequency1kHz

            # Check if axis is enabled
            self.controller.runtime.commands.motion.enable(axis)
            time.sleep(3)
            # Collect data
            config = self.data_config(n, freq, axis)
            print("Starting data collection and motion...")
            self.controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, config)
            self.controller.runtime.commands.motion.moveincremental([axis], [distance], [speed])
            self.controller.runtime.commands.motion.waitformotiondone(axis)
            time.sleep(1) # Wait for buffers to fill
            self.controller.runtime.data_collection.stop()
            print("Motion and data collection complete.")
            time.sleep(5)
            results[axis] = self.controller.runtime.data_collection.get_results(config, n)

            # Return to start position
            print("Returning to start position...")
            self.controller.runtime.commands.motion.moveabsolute([axis], [0], [speed])
            self.controller.runtime.commands.motion.waitformotiondone(axis)

        return results, speeds_used

    def gather_results(self, results, speeds_used):
        """
        Gathers and filters data for all axes tested, populating a dictionary organized by signal name and axis.

        Args:
        results (dict): A dictionary of data collection results organized by axis name.
        speeds_used (dict): A dictionary of the commanded speed for each axis.

        Returns:
        signal_data_dict (dict): A dictionary of all filtered encoder data signals organized by signal name and axis.
        """
        # Define the signals we want to extract
        signals_to_extract = [
            a1.AxisDataSignal.VelocityCommand,
            a1.AxisDataSignal.EncoderSineRaw,
            a1.AxisDataSignal.EncoderCosineRaw
        ]

        axis_data_dict = {}
        for axis, data in results.items():
            print(f"📈 Processing and filtering {axis} encoder data...")
            axis_data_dict[axis] = {}
            
            # --- Retrieve all necessary signals first ---
            raw_signals = {}
            for signal_type in signals_to_extract:
                try:
                    signal_data = data.axis.get(signal_type, axis).points
                    raw_signals[signal_type.name] = np.array(signal_data)
                except Exception as e:
                    print(f"Could not retrieve {signal_type.name} for axis {axis}. Error: {e}")
                    continue
            
            if 'VelocityCommand' not in raw_signals:
                print(f"Warning: VelocityCommand not found for {axis}. Cannot filter data.")
                continue

            # --- Create the filter mask ---
            target_speed = speeds_used[axis]
            velocity_command = raw_signals['VelocityCommand']
            # Use np.isclose for robust floating-point comparison
            constant_velocity_mask = np.isclose(velocity_command, target_speed)
            
            num_points_before = len(velocity_command)
            num_points_after = np.sum(constant_velocity_mask)
            
            if num_points_after == 0:
                print(f"  - Warning: No data points at constant velocity found for axis {axis}. Using unfiltered data.")
                constant_velocity_mask = np.ones_like(velocity_command, dtype=bool)


            # --- Apply the mask to the signals we care about ---
            axis_data_dict[axis]['EncoderSineRaw'] = raw_signals['EncoderSineRaw'][constant_velocity_mask].tolist()
            axis_data_dict[axis]['EncoderCosineRaw'] = raw_signals['EncoderCosineRaw'][constant_velocity_mask].tolist()

        return axis_data_dict

    def test(self):
        """
        Entry function to begin encoder tuning logic.

        :returns: None
        """
        print('Beginning Encoder Tuning Sequence')

        # Initialize and load DLLs
        self.initialize_dll()
        self.load_dll()

        # Execute data collection
        results, speeds_used = self.collect_data()
        if not results:
            print("Encoder tuning sequence finished: No data collected.")
            return

        # Compile and organize signals, filtering for constant velocity
        signal_dict = self.gather_results(results, speeds_used)

        # Fit ellipse to the raw data
        axis_ellipse_data = self.fit_ellipse(signal_dict)

        # Calculate the final gains from the ellipse data
        final_gains = self.calculate_final_gains(axis_ellipse_data, signal_dict)

        # Apply new gains to the controller
        self.apply_gains(final_gains)