# -*- coding: utf-8 -*-
"""
Created on Thu Mar 28 14:14:27 2024

@author: tbates
"""

import automation1 as a1
import sys
import contextlib
import os
import time
import numpy as np
#import serial.tools.list_ports
from tkinter import messagebox
from DecodeFaults import decode_faults
import math
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.offline as pyo
from datetime import datetime

from Modules.Easy_Tune_Module import Easy_Tune_Module
from Modules.Easy_Tune_Plotter import EasyTunePlotter

def connect():
    global controller, non_virtual_axes, connected_axes
    
    try:
        controller = a1.Controller.connect()
        controller.start()
    except:
        connection_type = input('Are you using a Hyperwire or a USB connection? (usb/hyperwire)')
        if connection_type == 'usb':
            try:
                controller = a1.Controller.connect_usb()
                controller.start()
            except:
                messagebox.showerror('Connection Error', 'Check connections and try again')
        else:
            messagebox.showerror('Update Software', 'Update Hyperwire firmware and try again')
    connected_axes = {}
    non_virtual_axes = []

    number_of_axes = controller.runtime.parameters.axes.count

    if number_of_axes <= 12:
        for axis_index in range(0,11):
            status_item_configuration = a1.StatusItemConfiguration()
            status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
            
            result = controller.runtime.status.get_status_items(status_item_configuration)
            axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
            if (axis_status & 1 << 13) > 0:
                connected_axes[controller.runtime.parameters.axes[axis_index].identification.axisname.value] = axis_index
        for key, value in connected_axes.items():
            non_virtual_axes.append(key)
    else:
        for axis_index in range(0,32):
            status_item_configuration = a1.StatusItemConfiguration()
            status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
            result = controller.runtime.status.get_status_items(status_item_configuration)
            axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
            if (axis_status & 1 << 13) > 0:
                connected_axes[controller.runtime.parameters.axes[axis_index].identification.axisname.value] = axis_index
        for key, value in connected_axes.items():
            print(f'Key: {key}')
            print(f'Value: {value}')
            non_virtual_axes.append(key)
    if len(non_virtual_axes) == 0:
        #try:
        controller = a1.Controller.connect_usb()
        number_of_axes = controller.runtime.parameters.axes.count
        if number_of_axes <= 12:
            for axis_index in range(0,11):
                status_item_configuration = a1.StatusItemConfiguration()
                status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
                
                result = controller.runtime.status.get_status_items(status_item_configuration)
                axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
                if (axis_status & 1 << 13) > 0:
                    connected_axes[controller.runtime.parameters.axes[axis_index].identification.axisname.value] = axis_index
            for key, value in connected_axes.items():
                non_virtual_axes.append(key)
        else:
            for axis_index in range(0,32):
                status_item_configuration = a1.StatusItemConfiguration()
                status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
                result = controller.runtime.status.get_status_items(status_item_configuration)
                axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
                if (axis_status & 1 << 13) > 0:
                    connected_axes[controller.runtime.parameters.axes[axis_index].identification.axisname.value] = axis_index
            for key, value in connected_axes.items():
                print(f'Key: {key}')
                print(f'Value: {value}')
                non_virtual_axes.append(key)
    print('Controller: ', controller.name)
    print('Axes present: ' , non_virtual_axes)
    return controller    #messagebox.showerror('No Device', 'No Devices Present. Check Connections.')

def data_config(n: int, freq: a1.DataCollectionFrequency, axis: int=None, axes: list=None) -> a1.DataCollectionConfiguration:
    """
    Data configurations. These are how to configure data collection parameters
    """
    # Create a data collection configuration with sample count and frequency
    data_config = a1.DataCollectionConfiguration(n, freq)

    # Add items to collect data on the entire system
    data_config.system.add(a1.SystemDataSignal.DataCollectionSampleTime)

    if axes:
        for axis in axes:
            # Add items to collect data on the specified axis
            data_config.axis.add(a1.AxisDataSignal.DriveStatus, axis)
            data_config.axis.add(a1.AxisDataSignal.AxisFault, axis)
            data_config.axis.add(a1.AxisDataSignal.PrimaryFeedback, axis)
            data_config.axis.add(a1.AxisDataSignal.PositionFeedback, axis)
            data_config.axis.add(a1.AxisDataSignal.VelocityFeedback, axis)
            data_config.axis.add(a1.AxisDataSignal.AccelerationFeedback, axis)
            data_config.axis.add(a1.AxisDataSignal.PositionError, axis)
            data_config.axis.add(a1.AxisDataSignal.CurrentCommand, axis)
            data_config.axis.add(a1.AxisDataSignal.CurrentFeedback, axis)
            data_config.axis.add(a1.AxisDataSignal.VelocityCommand, axis)
    if axis:
        # Add items to collect data on the specified axis
        data_config.axis.add(a1.AxisDataSignal.DriveStatus, axis)
        data_config.axis.add(a1.AxisDataSignal.AxisFault, axis)
        data_config.axis.add(a1.AxisDataSignal.PrimaryFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.PositionFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.VelocityFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.AccelerationFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.PositionError, axis)
        data_config.axis.add(a1.AxisDataSignal.CurrentCommand, axis)
        data_config.axis.add(a1.AxisDataSignal.CurrentFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.VelocityCommand, axis)

    return data_config

def check_for_faults(controller: a1.Controller, axes):
    print('Checking For Faults')
    faults = {}  # Initialize an empty dictionary to store results per axis
    
    for axis in axes:
        status_item_configuration = a1.StatusItemConfiguration()
        status_item_configuration.axis.add(a1.AxisStatusItem.AxisFault, axis)
        
        # Get the results for the current axis
        results = controller.runtime.status.get_status_items(status_item_configuration)
        
        # Extract the axis fault status as an integer
        axis_faults = int(results.axis.get(a1.AxisStatusItem.AxisFault, axis).value)
        # Store the axis_faults in the faults dictionary with the axis as the key
        faults[axis] = axis_faults  # Store the result in the dictionary with the axis as the key
        
    return faults

def calculate_lowpass_coefficients(cutoff_freq, sample_freq):
    """
    Calculate Low Pass filter coefficients based on AerLowPass.m
    
    Args:
        cutoff_freq: Cutoff frequency in Hz
        sample_freq: Sample frequency in Hz
        
    Returns:
        tuple: (N_coefficients, D_coefficients) where each is a list of 3 values
    """
    dC = 2 * math.atan(math.pi * cutoff_freq / sample_freq)
    dD = (1.0 - math.sqrt(2.0) / 2.0 * math.sin(dC)) / (1.0 + math.sqrt(2.0) / 2.0 * math.sin(dC))
    
    # Denominator coefficients
    D = [1.0, 
         -(1 + dD) * math.cos(dC), 
         dD]
    
    # Numerator coefficients
    N_1 = (1 + D[1] + D[2]) / 4.0
    N = [N_1, 
         2 * N_1, 
         N_1]
    
    return N, D

def calculate_notch_coefficients(center_freq, width, depth, sample_freq):
    """
    Calculate Notch filter coefficients based on AerNotch.m
    
    Args:
        center_freq: Center frequency in Hz
        width: Width parameter
        depth: Depth in dB
        sample_freq: Sample frequency in Hz
        
    Returns:
        tuple: (N_coefficients, D_coefficients) where each is a list of 3 values
    """
    dT = 1.0 / sample_freq
    dWidth = width * 2 * math.pi
    dWC = 2 / dT * math.tan(center_freq * math.pi * dT)
    dDelta = 10 ** (-depth / 20.0)
    dAlpha = (dWidth / dWC) + math.sqrt((dWidth / dWC) * (dWidth / dWC) + 1)
    dZeta = math.sqrt((dAlpha + 1 / dAlpha - 2) / (4 * abs(1 - 2 * dDelta * dDelta)))
    
    dA_0 = 4 + dWC * dWC * dT * dT + 4 * dZeta * dWC * dT
    
    # Denominator coefficients
    D = [1.0,
         (-8 + 2 * dWC * dWC * dT * dT) / dA_0,
         (-4 * dZeta * dWC * dT + 4 + dWC * dWC * dT * dT) / dA_0]
    
    # Numerator coefficients  
    N = [(4 + dWC * dWC * dT * dT + 4 * dDelta * dZeta * dWC * dT) / dA_0,
         (-8 + 2 * dWC * dWC * dT * dT) / dA_0,
         (-4 * dDelta * dZeta * dWC * dT + 4 + dWC * dWC * dT * dT) / dA_0]
    
    return N, D

def convert_filters_to_coefficients(shaped_params, sample_freq=None):
    """
    Convert shaped filter parameters to coefficients for controller application
    
    Args:
        shaped_params: Dictionary containing shaped filter parameters
        sample_freq: Sample frequency in Hz (default 20kHz for typical servo systems)
        
    Returns:
        dict: Filter coefficients organized by filter type and index
    """
    filter_coefficients = {}
    
    # Extract sample frequency from shaped_params if not provided
    if sample_freq is None:
        if 'Drive_Frequency__hz' in shaped_params:
            sample_freq = shaped_params['Drive_Frequency__hz']
            print(f"🔧 Using Drive Frequency as sample frequency: {sample_freq} Hz")
        else:
            sample_freq = 20000.0  # Fallback default
            print(f"⚠️  Drive_Frequency__hz not found, using default sample frequency: {sample_freq} Hz")
    else:
        print(f"🔧 Using provided sample frequency: {sample_freq} Hz")

    if 'Filters' not in shaped_params:
        print("No filter data found in shaped parameters")
        return filter_coefficients
    
    for filter_group, filter_data in shaped_params['Filters'].items():
        if 'filters' not in filter_data:
            continue
            
        filter_coefficients[filter_group] = {}
        
        # Handle both list (old format) and dict (new format with preserved indices)
        filters = filter_data['filters']
        if isinstance(filters, dict):
            # New format: dict with original indices as keys
            for original_index, filter_info in filters.items():
                filter_type = filter_info['type']
                parameters = filter_info['parameters']
                
                print(f"\nProcessing {filter_group} Filter {original_index}: {filter_type}")
                print(f"Parameters: {parameters}")
                
                if filter_type == 'Low_Pass':
                    cutoff_freq = parameters['Cutoff Frequency']
                    N, D = calculate_lowpass_coefficients(cutoff_freq, sample_freq)
                    
                    filter_coefficients[filter_group][original_index] = {  # Use original index
                        'type': 'Low_Pass',
                        'parameters': parameters,
                        'numerator': N,
                        'denominator': D
                    }
                    
                    print(f"  Cutoff Frequency: {cutoff_freq:.3f} Hz")
                    print(f"  Numerator:   [{N[0]:.6f}, {N[1]:.6f}, {N[2]:.6f}]")
                    print(f"  Denominator: [{D[0]:.6f}, {D[1]:.6f}, {D[2]:.6f}]")
                    
                elif filter_type == 'Notch':
                    center_freq = parameters['Center Frequency']
                    width = parameters['Width']
                    depth = parameters['Depth']
                    N, D = calculate_notch_coefficients(center_freq, width, depth, sample_freq)
                    
                    filter_coefficients[filter_group][original_index] = {  # Use original index
                        'type': 'Notch',
                        'parameters': parameters,
                        'numerator': N,
                        'denominator': D
                    }
                    
                    print(f"  Center Frequency: {center_freq:.3f} Hz")
                    print(f"  Width: {width:.3f}")
                    print(f"  Depth: {depth:.3f} dB")
                    print(f"  Numerator:   [{N[0]:.6f}, {N[1]:.6f}, {N[2]:.6f}]")
                    print(f"  Denominator: [{D[0]:.6f}, {D[1]:.6f}, {D[2]:.6f}]")
                    
                else:
                    print(f"  Unsupported filter type: {filter_type}")
                    filter_coefficients[filter_group][original_index] = {
                        'type': filter_type,
                        'parameters': parameters,
                        'numerator': None,
                        'denominator': None,
                        'error': f"Unsupported filter type: {filter_type}"
                    }
        else:
            # Old format: list (for backwards compatibility)
            for i, filter_info in enumerate(filters):
                filter_type = filter_info['type']
                parameters = filter_info['parameters']
                
                print(f"\nProcessing {filter_group} Filter {i}: {filter_type}")
                print(f"Parameters: {parameters}")
                
                if filter_type == 'Low_Pass':
                    cutoff_freq = parameters['Cutoff Frequency']
                    N, D = calculate_lowpass_coefficients(cutoff_freq, sample_freq)
                    
                    filter_coefficients[filter_group][i] = {
                        'type': 'Low_Pass',
                        'parameters': parameters,
                        'numerator': N,
                        'denominator': D
                    }
                    
                    print(f"  Cutoff Frequency: {cutoff_freq:.3f} Hz")
                    print(f"  Numerator:   [{N[0]:.6f}, {N[1]:.6f}, {N[2]:.6f}]")
                    print(f"  Denominator: [{D[0]:.6f}, {D[1]:.6f}, {D[2]:.6f}]")
                    
                elif filter_type == 'Notch':
                    center_freq = parameters['Center Frequency']
                    width = parameters['Width']
                    depth = parameters['Depth']
                    N, D = calculate_notch_coefficients(center_freq, width, depth, sample_freq)
                    
                    filter_coefficients[filter_group][i] = {
                        'type': 'Notch',
                        'parameters': parameters,
                        'numerator': N,
                        'denominator': D
                    }
                    
                    print(f"  Center Frequency: {center_freq:.3f} Hz")
                    print(f"  Width: {width:.3f}")
                    print(f"  Depth: {depth:.3f} dB")
                    print(f"  Numerator:   [{N[0]:.6f}, {N[1]:.6f}, {N[2]:.6f}]")
                    print(f"  Denominator: [{D[0]:.6f}, {D[1]:.6f}, {D[2]:.6f}]")
                    
                else:
                    print(f"  Unsupported filter type: {filter_type}")
                    filter_coefficients[filter_group][i] = {
                        'type': filter_type,
                        'parameters': parameters,
                        'numerator': None,
                        'denominator': None,
                        'error': f"Unsupported filter type: {filter_type}"
                    }
    
    return filter_coefficients

def extract_shaped_parameters(results):
    """Extract all shaped parameter values from EasyTune results"""
    shaped_params = {}
    
    # Extract shaped gain values
    if 'Gains' in results:
        for param_name, param_data in results['Gains'].items():
            if 'shaped' in param_data:
                shaped_params[param_name] = param_data['shaped']
    
    # Extract shaped filter configurations
    if 'Filters' in results:
        shaped_params['Filters'] = {}
        for filter_type, filter_data in results['Filters'].items():
            if 'shaped' in filter_data:
                shaped_params['Filters'][filter_type] = filter_data['shaped']
    
    # Extract enhanced tracking parameters
    if 'Enhanced_Tracking' in results:
        shaped_params['Enhanced_Tracking'] = {}
        for tracking_param, tracking_data in results['Enhanced_Tracking'].items():
            if 'shaped' in tracking_data:
                shaped_params['Enhanced_Tracking'][tracking_param] = tracking_data['shaped']
    
    return shaped_params

def apply_filter_coefficients_to_controller(axis, filter_coefficients, controller):
    """
    Apply the calculated filter coefficients to the controller
    
    Args:
        axis: Axis name
        filter_coefficients: Dictionary of calculated filter coefficients
        controller: Controller object
        
    Returns:
        bool: Success status
    """
    try:
        configured_parameters = controller.configuration.parameters.get_configuration()
        servo_filter_indices = []  # Collect all servo filter indices
        
        for filter_group, filters in filter_coefficients.items():
            print(f"\nApplying {filter_group} coefficients to axis {axis}")
            
            for filter_index, filter_data in filters.items():
                if filter_data['numerator'] is None or filter_data['denominator'] is None:
                    print(f"  Skipping Filter {filter_index}: {filter_data.get('error', 'No coefficients')}")
                    continue
                
                # Ensure filter index is within valid range (0-12)
                if filter_index > 12:
                    print(f"  ⚠️  Filter index {filter_index} exceeds maximum (12), skipping...")
                    continue
                
                N = filter_data['numerator']
                D = filter_data['denominator']
                filter_type = filter_data['type']
                
                print(f"  Applying Filter {filter_index} ({filter_type}):")
                print(f"    Numerator:   [{N[0]:.6f}, {N[1]:.6f}, {N[2]:.6f}]")
                print(f"    Denominator: [{D[0]:.6f}, {D[1]:.6f}, {D[2]:.6f}]")
                
                # Format filter index with leading zero (00, 01, 02, ..., 12)
                filter_idx_str = f"{filter_index:02d}"
                
                if filter_group == 'Servo_Filters':
                    # Apply servo loop filter coefficients dynamically
                    try:
                        # Get the parameter objects dynamically
                        n0_param = getattr(configured_parameters.axes[axis].servo, f'servoloopfilter{filter_idx_str}coeffn0')
                        n1_param = getattr(configured_parameters.axes[axis].servo, f'servoloopfilter{filter_idx_str}coeffn1')
                        n2_param = getattr(configured_parameters.axes[axis].servo, f'servoloopfilter{filter_idx_str}coeffn2')
                        d1_param = getattr(configured_parameters.axes[axis].servo, f'servoloopfilter{filter_idx_str}coeffd1')
                        d2_param = getattr(configured_parameters.axes[axis].servo, f'servoloopfilter{filter_idx_str}coeffd2')
                        
                        # Set the values
                        n0_param.value = N[0]
                        n1_param.value = N[1]
                        n2_param.value = N[2]
                        d1_param.value = D[1]
                        d2_param.value = D[2]
                        
                        # Collect this servo filter index
                        servo_filter_indices.append(filter_index)
                        
                        print(f"    ✅ Applied to ServoLoopFilter{filter_idx_str}")
                        
                    except AttributeError as e:
                        print(f"    ❌ ServoLoopFilter{filter_idx_str} parameters not found: {e}")
                        continue
                        
                elif filter_group == 'Feedforward_Filters':
                    # Apply feedforward filter coefficients dynamically
                    try:
                        # Get the parameter objects dynamically (assuming similar naming pattern)
                        n0_param = getattr(configured_parameters.axes[axis].servo, f'feedforwardfilter{filter_idx_str}coeffn0')
                        n1_param = getattr(configured_parameters.axes[axis].servo, f'feedforwardfilter{filter_idx_str}coeffn1')
                        n2_param = getattr(configured_parameters.axes[axis].servo, f'feedforwardfilter{filter_idx_str}coeffn2')
                        d1_param = getattr(configured_parameters.axes[axis].servo, f'feedforwardfilter{filter_idx_str}coeffd1')
                        d2_param = getattr(configured_parameters.axes[axis].servo, f'feedforwardfilter{filter_idx_str}coeffd2')
                        
                        # Set the values
                        n0_param.value = N[0]
                        n1_param.value = N[1]
                        n2_param.value = N[2]
                        d1_param.value = D[1]
                        d2_param.value = D[2]
                        
                        print(f"    ✅ Applied to FeedforwardFilter{filter_idx_str}")
                        
                    except AttributeError as e:
                        print(f"    ❌ FeedforwardFilter{filter_idx_str} parameters not found: {e}")
                        continue
        
        # Now calculate and set the servo filter bitmask OUTSIDE the loop
        if servo_filter_indices:
            filter_setup_bitmask = 0
            print(f"\n🔧 Enabling servo filters at indices: {servo_filter_indices}")
            
            for filter_index in servo_filter_indices:
                filter_setup_bitmask |= (1 << filter_index)
                print(f"  Adding filter {filter_index} to bitmask: bit {filter_index} = {1 << filter_index}")
            
            print(f"🔧 Final servoloopfiltersetup bitmask: {filter_setup_bitmask} (binary: {bin(filter_setup_bitmask)})")
            configured_parameters.axes[axis].servo.servoloopfiltersetup.value = float(filter_setup_bitmask)
        else:
            print("🔧 No servo filters to enable")
            configured_parameters.axes[axis].servo.servoloopfiltersetup.value = 0.0
        
        # Apply the configuration
        controller.configuration.parameters.set_configuration(configured_parameters)
        print("✅ Successfully applied all filter coefficients")
        return True
        
    except Exception as e:
        print(f"❌ Error applying filter coefficients: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def apply_new_servo_params(axis, results, controller, ff_analysis_data=None):
    """Apply the shaped servo parameters from EasyTune results"""
    print(f"Applying new servo parameters for axis {axis}")
    
    # Extract all shaped parameters
    shaped_params = extract_shaped_parameters(results)
    
    # Get configuration parameters
    configured_parameters = controller.configuration.parameters.get_configuration()
    
    # Apply all gain parameters
    if 'K' in shaped_params:
        gain_k_original = controller.runtime.parameters.axes[axis].servo.servoloopgaink.value
        print(f'Gain K Before: {gain_k_original}')
        configured_parameters.axes[axis].servo.servoloopgaink.value = shaped_params['K']
        print(f'Gain K Shaped: {shaped_params["K"]}')
    
    if 'Kip' in shaped_params:
        kip_original = controller.runtime.parameters.axes[axis].servo.servoloopgainkip.value
        print(f'Kip Before: {kip_original}')
        configured_parameters.axes[axis].servo.servoloopgainkip.value = shaped_params['Kip']
        print(f'Kip Shaped: {shaped_params["Kip"]}')
    
    if 'Kip2' in shaped_params:
        kip2_original = controller.runtime.parameters.axes[axis].servo.servoloopgainkip2.value
        print(f'Kip2 Before: {kip2_original}')
        configured_parameters.axes[axis].servo.servoloopgainkip2.value = shaped_params['Kip2']
        print(f'Kip2 Shaped: {shaped_params["Kip2"]}')
    
    if 'Kiv' in shaped_params:
        kiv_original = controller.runtime.parameters.axes[axis].servo.servoloopgainkiv.value
        print(f'Kiv Before: {kiv_original}')
        configured_parameters.axes[axis].servo.servoloopgainkiv.value = shaped_params['Kiv']
        print(f'Kiv Shaped: {shaped_params["Kiv"]}')
    
    if 'Kpv' in shaped_params:
        kpv_original = controller.runtime.parameters.axes[axis].servo.servoloopgainkpv.value
        print(f'Kpv Before: {kpv_original}')
        configured_parameters.axes[axis].servo.servoloopgainkpv.value = shaped_params['Kpv']
        print(f'Kpv Shaped: {shaped_params["Kpv"]}')
    
    if 'Kv' in shaped_params:
        kv_original = controller.runtime.parameters.axes[axis].servo.servoloopgainkv.value
        print(f'Kv Before: {kv_original}')
        configured_parameters.axes[axis].servo.servoloopgainkv.value = shaped_params['Kv']
        print(f'Kv Shaped: {shaped_params["Kv"]}')
    
    if 'Ksi1' in shaped_params:
        ksi1_original = controller.runtime.parameters.axes[axis].servo.servoloopgainksi1.value
        print(f'Ksi1 Before: {ksi1_original}')
        configured_parameters.axes[axis].servo.servoloopgainksi1.value = shaped_params['Ksi1']
        print(f'Ksi1 Shaped: {shaped_params["Ksi1"]}')
    
    if 'Ksi2' in shaped_params:
        ksi2_original = controller.runtime.parameters.axes[axis].servo.servoloopgainksi2.value
        print(f'Ksi2 Before: {ksi2_original}')
        configured_parameters.axes[axis].servo.servoloopgainksi2.value = shaped_params['Ksi2']
        print(f'Ksi2 Shaped: {shaped_params["Ksi2"]}')
    
    # Apply feedforward parameters
    if 'Pff' in shaped_params:
        pff_original = controller.runtime.parameters.axes[axis].servo.feedforwardgainpff.value
        print(f'Pff Before: {pff_original}')
        configured_parameters.axes[axis].servo.feedforwardgainpff.value = shaped_params['Pff']
        print(f'Pff Shaped: {shaped_params["Pff"]}')
    
    if 'Vff' in shaped_params:
        vff_original = controller.runtime.parameters.axes[axis].servo.feedforwardgainvff.value
        print(f'Vff Before: {vff_original}')
        configured_parameters.axes[axis].servo.feedforwardgainvff.value = shaped_params['Vff']
        print(f'Vff Shaped: {shaped_params["Vff"]}')
    
    if 'Aff' in shaped_params:
        aff_original = controller.runtime.parameters.axes[axis].servo.feedforwardgainaff.value
        aff_shaped = shaped_params['Aff']
        
        # Apply FF analysis adjustment if available
        if ff_analysis_data and 'center_magnitude_difference_db' in ff_analysis_data:
            center_mag_diff = ff_analysis_data['center_magnitude_difference_db']
            # Always apply the adjustment (positive increases, negative decreases)
            aff_adjusted = aff_original + center_mag_diff
            print(f'🔧 FF ANALYSIS ADJUSTMENT:')
            print(f'   Aff Original: {aff_original:.6f}')
            print(f'   Center Mag Diff: {center_mag_diff:+.6f} dB')
            print(f'   Aff Adjusted: {aff_adjusted:.6f}')
            configured_parameters.axes[axis].servo.feedforwardgainaff.value = aff_adjusted
        else:
            print(f'Aff Before: {aff_original}')
            print(f'Aff Shaped: {aff_shaped} (no FF analysis data)')
            configured_parameters.axes[axis].servo.feedforwardgainaff.value = aff_shaped
    
    if 'Jff' in shaped_params:
        jff_original = controller.runtime.parameters.axes[axis].servo.feedforwardgainjff.value
        print(f'Jff Before: {jff_original}')
        configured_parameters.axes[axis].servo.feedforwardgainjff.value = shaped_params['Jff']
        print(f'Jff Shaped: {shaped_params["Jff"]}')
    
    if 'Sff' in shaped_params:
        sff_original = controller.runtime.parameters.axes[axis].servo.feedforwardgainsff.value
        print(f'Sff Before: {sff_original}')
        configured_parameters.axes[axis].servo.feedforwardgainsff.value = shaped_params['Sff']
        print(f'Sff Shaped: {shaped_params["Sff"]}')
    
    if 'Feedforward_Advance__ms' in shaped_params:
        ff_advance_original = controller.runtime.parameters.axes[axis].servo.feedforwardadvance.value
        print(f'Feedforward Advance Before: {ff_advance_original}')
        configured_parameters.axes[axis].servo.feedforwardadvance.value = shaped_params['Feedforward_Advance__ms']
        print(f'Feedforward Advance Shaped: {shaped_params["Feedforward_Advance__ms"]}')
    
    # Note: Drive_Type, Is_Dual_loop, Drive_Frequency__hz, and Counts_Per_Unit 
    # are typically system-level parameters that shouldn't be changed during tuning
    
    # Apply the configuration
    try:
        controller.configuration.parameters.set_configuration(configured_parameters)
        print("✅ Successfully applied shaped servo parameters")
        
        # Print summary of applied parameters
        applied_count = len([k for k in shaped_params.keys() if k not in ['Filters', 'Enhanced_Tracking', 'Drive_Type', 'Is_Dual_loop', 'Drive_Frequency__hz', 'Counts_Per_Unit']])
        print("\n📋 PARAMETER UPDATE SUMMARY:")
        print(f"   Axis: {axis}")
        print(f"   Parameters Applied: {applied_count}")
        
        # Apply filter coefficients if present
        if 'Filters' in shaped_params:
            print("\n🔧 Processing shaped filter configurations...")
            # Assume 20kHz sample frequency - adjust as needed for your system
            filter_coefficients = convert_filters_to_coefficients(shaped_params)
            
            if filter_coefficients:
                apply_filter_coefficients_to_controller(axis, filter_coefficients, controller)
        
        return True
    except Exception as e:
        print(f"❌ Error applying parameters: {str(e)}")
        return False

def analyze_easy_tune(results):
    """Analyze EasyTune results against stability standards"""
    # Define standard target values and acceptable ranges
    standards = {
        'phase_margin': {
            'target': 45,
            'min': 38,
            'max': 52,
            'unit': 'degrees'
        },
        'gain_margin': {
            'target': 10,
            'min': 6,
            'max': 15,
            'unit': 'dB'
        },
        'sensitivity': {
            'target': 6,
            'max': 6,  # Should not exceed this value
            'unit': 'dB'
        }
    }
    
    print("\n" + "="*60)
    print("                STABILITY ANALYSIS REPORT")
    print("="*60)
    
    # Extract FF Analysis data
    ff_analysis_data = None
    center_mag_diff = 0.0
    
    if 'FF_Analysis' in results:
        ff_analysis_data = results['FF_Analysis']
        center_mag_diff = ff_analysis_data.get('center_magnitude_difference_db', 0.0)
        
        print("\n🔧 FEEDFORWARD ANALYSIS:")
        print(f"   Center Frequency: {ff_analysis_data.get('center_frequency_hz', 0):.1f} Hz")
        print(f"   Center Magnitude Difference: {center_mag_diff:.3f} dB")
        print(f"   Slope Difference: {ff_analysis_data.get('slope_difference_db_per_decade', 0):.3f} dB/decade")
    
    # Check if stability metrics exist in results
    if 'Stability_Metrics' not in results or 'original' not in results['Stability_Metrics']:
        print("❌ ERROR: No stability metrics found in results")
        return False
    
    stability_data = results['Stability_Metrics']['original']
    analysis_passed = True
    issues = []
    
    # Analyze Phase Margin
    if 'phase_margin' in stability_data:
        phase_margin = stability_data['phase_margin']['degrees']
        phase_freq = stability_data['phase_margin']['frequency_hz']
        
        print("\n📐 PHASE MARGIN ANALYSIS:")
        print(f"   Current Value: {phase_margin:.1f}° @ {phase_freq:.1f} Hz")
        print(f"   Target Range:  {standards['phase_margin']['min']}-{standards['phase_margin']['max']}°")
        print(f"   Target Value:  {standards['phase_margin']['target']}°")
        
        if standards['phase_margin']['min'] <= phase_margin <= standards['phase_margin']['max']:
            print("   ✅ PASS - Phase margin within acceptable range")
        else:
            analysis_passed = False
            if phase_margin < standards['phase_margin']['min']:
                issues.append(f"Phase margin too low ({phase_margin:.1f}° < {standards['phase_margin']['min']}°)")
                print(f"   ❌ FAIL - Phase margin too low (minimum: {standards['phase_margin']['min']}°)")
            else:
                issues.append(f"Phase margin too high ({phase_margin:.1f}° > {standards['phase_margin']['max']}°)")
                print(f"   ⚠️  WARNING - Phase margin too high (maximum: {standards['phase_margin']['max']}°)")
    
    # Analyze Gain Margin
    if 'gain_margin' in stability_data:
        gain_margin = abs(stability_data['gain_margin']['db'])
        gain_freq = stability_data['gain_margin']['frequency_hz']
        
        print("\n📊 GAIN MARGIN ANALYSIS:")
        print(f"   Current Value: {gain_margin:.1f} dB @ {gain_freq:.1f} Hz")
        print(f"   Target Range:  {standards['gain_margin']['min']}-{standards['gain_margin']['max']} dB")
        print(f"   Target Value:  {standards['gain_margin']['target']} dB")
        
        if standards['gain_margin']['min'] <= gain_margin <= standards['gain_margin']['max']:
            print("   ✅ PASS - Gain margin within acceptable range")
        else:
            analysis_passed = False
            if gain_margin < standards['gain_margin']['min']:
                issues.append(f"Gain margin too low ({gain_margin:.1f} dB < {standards['gain_margin']['min']} dB)")
                print(f"   ❌ FAIL - Gain margin too low (minimum: {standards['gain_margin']['min']} dB)")
            else:
                issues.append(f"Gain margin too high ({gain_margin:.1f} dB > {standards['gain_margin']['max']} dB)")
                print(f"   ⚠️  WARNING - Gain margin too high (maximum: {standards['gain_margin']['max']} dB)")
    
    # Analyze Sensitivity
    if 'sensitivity' in stability_data:
        sensitivity = stability_data['sensitivity']['db']
        sensitivity_freq = stability_data['sensitivity']['frequency_hz']
        
        print("\n🎯 SENSITIVITY ANALYSIS:")
        print(f"   Current Value: {sensitivity:.1f} dB @ {sensitivity_freq:.1f} Hz")
        print(f"   Maximum Limit: {standards['sensitivity']['max']} dB")
        print(f"   Target Value:  {standards['sensitivity']['target']} dB")
        
        if sensitivity <= standards['sensitivity']['max']:
            print("   ✅ PASS - Sensitivity within acceptable limit")
        else:
            analysis_passed = False
            issues.append(f"Sensitivity exceeds limit ({sensitivity:.1f} dB > {standards['sensitivity']['max']} dB)")
            print("   ❌ FAIL - Sensitivity exceeds maximum limit")
    
    # Overall Assessment
    print(f"\n{'='*60}")
    if analysis_passed:
        print("🎉 OVERALL ASSESSMENT: PASS")
        print("   All stability metrics meet the required standards.")
    else:
        print("⚠️  OVERALL ASSESSMENT: FAIL")
        print("   The following issues were identified:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    
    print("="*60)
    
    return analysis_passed, ff_analysis_data

def frequency_response(axis, controller, current_percent, verification=False, position=None, axes=None):
    """Generate frequency response file and return its path
    
    Args:
        axis: Axis name
        verification: If True, this is a verification run after parameter changes
        current_percent: Current percentage for verification run (default 50%)
    """

    params = controller.configuration.parameters.get_configuration()
    motor_pole_pitch = params.axes[axis].motor.motorpolepitch.value
    distance = motor_pole_pitch / 2
    
    speed = distance * 0.1
    if position != 'Center':
        position_str = position['name']
    else: position_str = position
    # Different filename and current percentage for verification
    if verification:
        fr_filename = f'test-{axis}-{position_str}-Verification.fr'
        print(f"🔍 Running VERIFICATION frequency response at {current_percent}% max current, {distance} mm at {speed}")

    else:
        time.sleep(2)
        fr_filename = f'test-{axis}-{position_str}.fr'
        print(f"📊 Running INITIAL frequency response at {current_percent}% max current, {distance} mm at {speed}")

    print(f"FR Filename: {fr_filename}")

    # Generate the FR file with appropriate current percentage
    fr_string = fr'AppFrequencyResponseTriggerMultisinePlus({axis}, "{fr_filename}", 10, 2500, 280, {current_percent}, TuningMeasurementType.ServoOpenLoop, {distance}, {speed})'
    #fr_string = fr'AppFrequencyResponseTriggerMultisinePlus({axis}, "{fr_filename}", 10, 2500, 280, {current_percent}, TuningMeasurementType.ServoOpenLoop, 0, 0)'
    
    controller.runtime.commands.execute(fr_string,2)
    
    # Construct full path to the generated .fr file
    username = os.getlogin()
    fr_filepath = os.path.join(f"C:\\Users\\{username}\\Documents\\Automation1", fr_filename)

    # # Automatically generate plot for this .fr file
    # print(f"📈 Automatically generating plot for {fr_filename}...")
    # try:
    #     output_dir = os.path.dirname(fr_filepath)
    #     plotter = EasyTunePlotter(output_dir)
        
    #     # Create individual bode plot for this FR file
    #     individual_plot_filename = f"bode_{os.path.splitext(fr_filename)[0]}.html"
    #     plotter.create_bode_plot([fr_filepath], individual_plot_filename)
        
    #     print(f"✅ Plot generated: {individual_plot_filename}")
        
    # except Exception as e:
    #     print(f"⚠️  Warning: Could not generate plot for {fr_filename}: {e}")
    
    return fr_filepath, verification

def optimize(fr_filepath=None):
    """Run EasyTune optimization on FR file"""
    if not fr_filepath:
        raise ValueError("No .fr file path provided")
    
    easy_tune_module = Easy_Tune_Module(gui=None, block_layout_module=None)
    easy_tune_module.run_easy_tune(fr_filepath)
    
    # Wait for optimization to complete
    while easy_tune_module.active_thread:
        time.sleep(0.1)
    
    # Get the analysis results
    results = easy_tune_module.get_results()
        
    # Analyze the results against standards
    if results:
        stability_passed, ff_analysis_data = analyze_easy_tune(results)
        print(f"\nStability Analysis: {'PASSED' if stability_passed else 'FAILED'}")
        
        # Automatically generate stability analysis plot
        # print(f"📊 Automatically generating stability analysis for {os.path.basename(fr_filepath)}...")
        # try:
        #     output_dir = os.path.dirname(fr_filepath)
        #     plotter = EasyTunePlotter(output_dir)
            
        #     # Create stability analysis plot
        #     base_name = os.path.splitext(os.path.basename(fr_filepath))[0]
        #     stability_plot_filename = f"stability_{base_name}.html"
            
        #     # We'd need to save the results to a log file first, or modify the plotter to accept results directly
        #     # For now, let's create a temporary log file with the results
        #     log_filepath = os.path.join(output_dir, f"{base_name}_temp.log")
            
        #     # Write stability results to temporary log file
        #     with open(log_filepath, 'w', encoding='utf-8') as log_file:
        #         log_file.write(f"📅 Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        #         log_file.write("="*60 + "\n")
        #         if 'Stability_Metrics' in results and 'original' in results['Stability_Metrics']:
        #             stability_data = results['Stability_Metrics']['original']
        #             if 'phase_margin' in stability_data:
        #                 pm = stability_data['phase_margin']
        #                 log_file.write(f"📐 PHASE MARGIN ANALYSIS:\n")
        #                 log_file.write(f"   Current Value: {pm['degrees']:.1f}° @ {pm['frequency_hz']:.1f} Hz\n")
        #             if 'gain_margin' in stability_data:
        #                 gm = stability_data['gain_margin'] 
        #                 log_file.write(f"📊 GAIN MARGIN ANALYSIS:\n")
        #                 log_file.write(f"   Current Value: {abs(gm['db']):.1f} dB @ {gm['frequency_hz']:.1f} Hz\n")
        #             if 'sensitivity' in stability_data:
        #                 sens = stability_data['sensitivity']
        #                 log_file.write(f"🎯 SENSITIVITY ANALYSIS:\n") 
        #                 log_file.write(f"   Current Value: {sens['db']:.1f} dB @ {sens['frequency_hz']:.1f} Hz\n")
        #         log_file.write(f"🎉 OVERALL ASSESSMENT: {'PASS' if stability_passed else 'FAIL'}\n")
            
        #     # Generate stability plot from log file
        #     plotter.create_stability_analysis_plot([log_filepath], stability_plot_filename)
            
        #     print(f"✅ Stability analysis plot generated: {stability_plot_filename}")
            
            # Clean up temporary log file
        #     os.remove(log_filepath)
            
        # except Exception as e:
        #     print(f"⚠️  Warning: Could not generate stability analysis plot: {e}")
    else:
        print("No results available for analysis")
        ff_analysis_data = None
    
    return results, stability_passed, ff_analysis_data

def single_axis_frequency_response(axis, controller, current_percent):
    """Run frequency response tests at center and 4 corners of XY workspace"""
    print(f"🔧 Starting frequency response testing for {axis}")
    fr_files = [] 
    params = controller.configuration.parameters.get_configuration()
    # Get travel limits for both axes
    axis_limits = {}
    axis_distances = {}
    pos_limit = controller.runtime.parameters.axes[axis].protection.softwarelimithigh.value
    neg_limit = controller.runtime.parameters.axes[axis].protection.softwarelimitlow.value
    axis_limits[axis] = (neg_limit, pos_limit)
    print(f"  {axis} axis limits: {neg_limit} to {pos_limit}")

    motor_pole_pitch = params.axes[axis].motor.motorpolepitch.value
    distance = motor_pole_pitch / 2
    axis_distances[axis] = distance
    
    # Calculate center positions for each axis
    center = (axis_limits[axis][0] + axis_limits[axis][1]) / 2

    # Define test positions (center + 4 corners)
    test_positions = [
        {'name': 'Center', 
         'coords': (center),
         'directions': (1, 1)},  # Center uses default positive motion
        {'name': 'NE Corner', 
         'coords': (axis_limits[axis][1] - (axis_distances[axis]+0.1)),
         'directions': (-1)}, 
        {'name': 'NW Corner', 
         'coords': (axis_limits[axis][0] + (axis_distances[axis]-0.1)),
         'directions': (1)}  
        
    ]
    
    # Home axes first
    print("\n🏠 Homing axes...")
    controller.runtime.commands.motion.enable(axis)
    controller.runtime.commands.motion.home(axis)
    time.sleep(2)

    for position in test_positions:
        x = position['coords']
        print(f"\n📍 Testing {position['name']} (X{x:.2f}")
        
        # Move to position
        controller.runtime.commands.motion.moveabsolute([axis], [x], [5])
        controller.runtime.commands.motion.waitformotiondone([axis])
        time.sleep(1)  # Allow time for movement
        
        # Check for faults after move
        
        axis_faults = check_for_faults(controller, axis)
        if axis_faults:
            fault_init = decode_faults(axis_faults, axis, controller, fault_log = None)
            decoded_faults = fault_init.get_fault()    
        
            print(f"❌ Faults detected at {position['name']}: {decoded_faults}")
   
        # Run FR for each axis
        print(f"📊 Running FR for {axis} axis at {position['name']}")
        
        # Generate FR file
        fr_filepath, _ = frequency_response(
            axis=axis,
            controller=controller,
            verification=True,
            current_percent=current_percent,
            position=position,
            axes=None
        )
        if position['name'] == 'Center':
                # Step 2: EasyTune Optimization
                print("\n🎯 STEP 2: EasyTune Optimization")
                results, stability_passed, ff_analysis_data = optimize(fr_filepath=fr_filepath)
                if not stability_passed:
                    if results:
                        success = apply_new_servo_params(axis, results, controller, ff_analysis_data)
                        controller.reset()
                        controller.runtime.commands.motion.enable(axis)
                        controller.runtime.commands.motion.home(axis)
                else:
                    print(f"⚠️  OPTIMIZATION FOR AXIS: {axis} PASSED - Parameter adjustments not needed...")
        fr_files.append(fr_filepath)

        print("✅ Initial Frequency Responses Completed")

    return fr_files

def multi_axis_frequency_response(axes, controller, current_percent):
    """Run frequency response tests at center and 4 corners of XY workspace"""
    print(f"🔧 Starting multi-axis testing for axes {axes}")
    
    params = controller.configuration.parameters.get_configuration()
    fr_files = []
    # Get travel limits for both axes
    axis_limits = {}
    axis_distances = {}
    print(f'Axes: {axes}')
    for axis in axes:
        print(f'Axis: {axis}')
        pos_limit = controller.runtime.parameters.axes[axis].protection.softwarelimithigh.value
        neg_limit = controller.runtime.parameters.axes[axis].protection.softwarelimitlow.value
        axis_limits[axis] = (neg_limit, pos_limit)
        print(f"  {axis} axis limits: {neg_limit} to {pos_limit}")
        
        motor_pole_pitch = params.axes[axis].motor.motorpolepitch.value
        distance = motor_pole_pitch / 2
        axis_distances[axis] = distance

    # Get first two axes for position calculations
    x_axis = axes[0]
    y_axis = axes[1]

    # Calculate center positions for each axis
    x_center = (axis_limits[x_axis][0] + axis_limits[x_axis][1]) / 2
    y_center = (axis_limits[y_axis][0] + axis_limits[y_axis][1]) / 2

    # Define test positions with calculated centers
    test_positions = [
        {'name': 'Center', 
         'coords': (x_center, y_center),
         'directions': (1, 1)},
        {'name': 'NE Corner', 
         'coords': (axis_limits[x_axis][1] - (axis_distances[x_axis]+0.1), axis_limits[y_axis][1] - (axis_distances[y_axis]+0.1)),
         'directions': (-1, -1)},
        {'name': 'NW Corner', 
         'coords': (axis_limits[x_axis][0] + (axis_distances[x_axis]-0.1), axis_limits[y_axis][1] - (axis_distances[y_axis]+0.1)),
         'directions': (1, -1)},
        {'name': 'SE Corner', 
         'coords': (axis_limits[x_axis][1] - (axis_distances[x_axis]+0.1), axis_limits[y_axis][0] + (axis_distances[y_axis]-0.1)),
         'directions': (-1, 1)},
        {'name': 'SW Corner', 
         'coords': (axis_limits[x_axis][0] + (axis_distances[x_axis]-0.1), axis_limits[y_axis][0] + (axis_distances[y_axis]-0.1)),
         'directions': (1, 1)}
    ]
    
    # Home axes first
    print("\n🏠 Homing axes...")
    controller.runtime.commands.motion.enable(axes)
    controller.runtime.commands.motion.home(axes)
    time.sleep(2)

    for position in test_positions:
        x, y = position['coords']
        print(f"\n📍 Testing {position['name']} (X{x:.2f}, Y{y:.2f})")
        
        # Move to position
        controller.runtime.commands.motion.moveabsolute(axes, [x, y], [25, 25])
        controller.runtime.commands.motion.waitformotiondone(axes)
        time.sleep(1)  # Allow time for movement
        
        # Check for faults after move
        
        axis_faults = check_for_faults(controller, axes)
        if axis_faults:
            fault_init = decode_faults(axis_faults, axes, controller, fault_log = None)
            decoded_faults = fault_init.get_fault()    
        
            print(f"❌ Faults detected at {position['name']}: {decoded_faults}")

        # Run FR for each axis
        for axis in axes:
            print(f"📊 Running FR for {axis} axis at {position['name']}")
            
            # Generate FR file
            fr_filepath, _ = frequency_response(
                axis=axis,
                controller=controller,
                verification=True,
                current_percent=current_percent,
                position=position,
                axes=axes
            )
            if position['name'] == 'Center':
                # Step 2: EasyTune Optimization
                print("\n🎯 STEP 2: EasyTune Optimization")
                results, stability_passed, ff_analysis_data = optimize(fr_filepath=fr_filepath)
                if not stability_passed:
                    if results:
                        success = apply_new_servo_params(axis, results, controller, ff_analysis_data)
                        controller.reset()
                        controller.runtime.commands.motion.enable(axes)
                        controller.runtime.commands.motion.home(axes)
                else:
                    print(f"⚠️  OPTIMIZATION FOR AXIS: {axis} PASSED - Parameter adjustments not needed...")

            fr_files.append(fr_filepath)
            
        print("✅ Initial Frequency Responses Completed")

    return fr_files

def generate_plots_from_results(log_files=None):
    """
    Generate interactive plots from all FR and log files in the output directory
    
    Args:
        output_dir: Directory containing FR and log files (default: current directory)
    """
    
    username = os.getlogin()
    output_dir = os.path.join(f"C:\\Users\\{username}\\Documents\\Automation1")
    
    # Initialize plotter and create analysis
    plotter = EasyTunePlotter(output_dir)
    plotter.create_combined_analysis(log_files)
    
    print("✅ Interactive plots generated successfully!")

def validate_stage_performance(controller: a1.Controller, axes_dict: dict, test_type: str, axis_limits: dict):
    """
    Validate stage performance by collecting data on the specified axes
    """
    params = controller.configuration.parameters.get_configuration()

    if test_type == 'multi':
        axis_keys = list(axes_dict.keys())
        for axis in axis_keys:
            ramp_value = axes_dict[axis][1]  # Get the max_accel for this specific axis
            ramp_value_decel = ramp_value
            controller.runtime.commands.motion_setup.setupaxisrampvalue(axis, a1.RampMode.Rate, ramp_value, a1.RampMode.Rate, ramp_value_decel)

        distance_1 = axis_limits[axis_keys[0]][1] - axis_limits[axis_keys[0]][0]
        distance_2 = axis_limits[axis_keys[1]][1] - axis_limits[axis_keys[1]][0]

        time_axis_1 = distance_1 / axes_dict[axis_keys[0]][0]
        time_axis_2 = distance_2 / axes_dict[axis_keys[1]][0]

        test_time = max(time_axis_1, time_axis_2) + 2
        sample_rate = 1000
        n = int(sample_rate * test_time)
        freq = a1.DataCollectionFrequency.Frequency1kHz

        # Calculate center positions for each axis
        x_center = (axis_limits[axis_keys[0]][0] + axis_limits[axis_keys[0]][1]) / 2
        y_center = (axis_limits[axis_keys[1]][0] + axis_limits[axis_keys[1]][1]) / 2

        # Home axes first
        print("\n🏠 Homing axes...")
        controller.runtime.commands.motion.enable(axis_keys)
        controller.runtime.commands.motion.home(axis_keys)
        time.sleep(2)

        # Execute diagonal movement sequence
        print("\n🔄 Executing diagonal movement sequence...")

        # Extract coordinates for the movements
        sw_coords = (axis_limits[axis_keys[0]][0] + 0.1, axis_limits[axis_keys[1]][0] + 0.1)
        ne_coords = (axis_limits[axis_keys[0]][1] - 0.1, axis_limits[axis_keys[1]][1] - 0.1)
        se_coords = (axis_limits[axis_keys[0]][1] - 0.1, axis_limits[axis_keys[1]][0] + 0.1)
        nw_coords = (axis_limits[axis_keys[0]][0] + 0.1, axis_limits[axis_keys[1]][1] - 0.1)
        center_coords = (x_center, y_center)
        velocity = [axes_dict[axis][0] for axis in axis_keys[:2]]

        results = {}
        # Movement 1: SW → NE → SW
        print("📍 Move 1: SW → NE → SW")
        controller.runtime.commands.motion.moveabsolute(axis_keys, list(sw_coords), velocity)
        controller.runtime.commands.motion.waitformotiondone(axis_keys)
        time.sleep(0.5)

        config = data_config(n, freq, axes=axis_keys)
        controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, config)
        controller.runtime.commands.motion.moveabsolute(axis_keys, list(ne_coords), velocity)
        controller.runtime.commands.motion.waitformotiondone(axis_keys)
        time.sleep(3)
        controller.runtime.data_collection.stop()
        results['SW_NE'] = controller.runtime.data_collection.get_results(config, n)

        config = data_config(n, freq, axes=axis_keys)
        controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, config)
        controller.runtime.commands.motion.moveabsolute(axis_keys, list(sw_coords), velocity)
        controller.runtime.commands.motion.waitformotiondone(axis_keys)
        time.sleep(3)
        controller.runtime.data_collection.stop()
        results['NE_SW'] = controller.runtime.data_collection.get_results(config, n)

        # Movement 2: SE → NW → SE
        print("📍 Move 2: SE → NW → SE")
        controller.runtime.commands.motion.moveabsolute(axis_keys, list(se_coords), velocity)
        controller.runtime.commands.motion.waitformotiondone(axis_keys)
        time.sleep(0.5)

        config = data_config(n, freq, axes=axis_keys)
        controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, config)
        controller.runtime.commands.motion.moveabsolute(axis_keys, list(nw_coords), velocity)
        controller.runtime.commands.motion.waitformotiondone(axis_keys)
        time.sleep(3)
        controller.runtime.data_collection.stop()
        results['SE_NW'] = controller.runtime.data_collection.get_results(config, n)

        config = data_config(n, freq, axes=axis_keys)
        controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, config)
        controller.runtime.commands.motion.moveabsolute(axis_keys, list(se_coords), velocity)
        controller.runtime.commands.motion.waitformotiondone(axis_keys)
        time.sleep(3)
        controller.runtime.data_collection.stop()
        results['NW_SE'] = controller.runtime.data_collection.get_results(config, n)

        # Return to center
        print("📍 Returning to center")
        controller.runtime.commands.motion.moveabsolute(axis_keys, list(center_coords), velocity)
        controller.runtime.commands.motion.waitformotiondone(axis_keys)
        time.sleep(1)

        print("✅ Diagonal movement sequence completed")

    if test_type == 'single':
        axis_keys = list(axes_dict.keys())
        axis = axis_keys[0]   # First axis name

        ramp_value = axes_dict[axis][1]
        ramp_value_decel = ramp_value
        controller.runtime.commands.motion_setup.setupaxisrampvalue(axis, a1.RampMode.Rate, ramp_value, a1.RampMode.Rate, ramp_value_decel)

        distance = axis_limits[axis][1] - axis_limits[axis][0]

        time_axis = distance / axes_dict[axis_keys[0]][0]

        test_time = (time_axis) + 2
        sample_rate = 1000
        n = int(sample_rate * test_time)
        freq = a1.DataCollectionFrequency.Frequency1kHz

        # Calculate center positions for each axis
        center = (axis_limits[axis][0] + axis_limits[axis][1]) / 2

        # Home axes first
        print("\n🏠 Homing axes...")
        controller.runtime.commands.motion.enable(axis)
        controller.runtime.commands.motion.home(axis)
        time.sleep(2)

        # Execute diagonal movement sequence
        print("\n🔄 Executing diagonal movement sequence...")

        # Extract coordinates for the movements
        neg_end = axis_limits[axis][0] + 0.1
        pos_end = axis_limits[axis][1] - 0.1
        
        center_coords = center
        velocity = axes_dict[axis][0]

        results = {}
        # Movement 1: Negative to Positive
        print("📍 Move 1: Negative to Positive")
        controller.runtime.commands.motion.moveabsolute(axis, neg_end, velocity)
        controller.runtime.commands.motion.waitformotiondone(axis)
        time.sleep(0.5)

        config = data_config(n, freq, axes=axis_keys)
        controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, config)
        controller.runtime.commands.motion.moveabsolute(axis, pos_end, velocity)
        controller.runtime.commands.motion.waitformotiondone(axis)
        time.sleep(3)
        controller.runtime.data_collection.stop()
        results['pos'] = controller.runtime.data_collection.get_results(config, n)

        config = data_config(n, freq, axes=axis_keys)
        controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, config)
        controller.runtime.commands.motion.moveabsolute(axis, neg_end, velocity)
        controller.runtime.commands.motion.waitformotiondone(axis)
        time.sleep(3)
        controller.runtime.data_collection.stop()
        results['neg'] = controller.runtime.data_collection.get_results(config, n)

        # Return to center
        print("📍 Returning to center")
        controller.runtime.commands.motion.moveabsolute(axis, center, velocity)
        controller.runtime.commands.motion.waitformotiondone(axis)
        time.sleep(1)

        print("✅ Movement sequence completed")    # Move to test positions (your existing code continues here)

    return results

def calculate_performance_stats(time_array, signal_data_dict, axis_names):
    """Calculate performance statistics from signal data"""
    stats = {}
    
    for axis in axis_names:
        stats[axis] = {}
        
        # Get signal data arrays
        pos_error = np.array(signal_data_dict['PositionError'][axis])
        velocity = np.array(signal_data_dict['VelocityFeedback'][axis])
        accel = np.array(signal_data_dict['AccelerationFeedback'][axis])
        current = np.array(signal_data_dict['CurrentFeedback'][axis])
        
        # Peak Position Error
        stats[axis]['peak_pos_error'] = np.max(np.abs(pos_error))
        
        # Current during constant velocity (where velocity change < 10% of max)
        vel_threshold = 0.01 * np.max(np.abs(velocity))
        vel_diff = np.abs(np.diff(velocity))
        const_vel_mask = vel_diff < vel_threshold
        if np.any(const_vel_mask):
            stats[axis]['current_const_vel'] = np.mean((current[1:][const_vel_mask]))
        else:
            stats[axis]['current_const_vel'] = np.mean((current))
            
        # RMS Acceleration during acceleration (where accel > 10% of max)
        accel_threshold = 0.1 * np.max(np.abs(accel))
        accel_mask = np.abs(accel) > accel_threshold
        if np.any(accel_mask):
            stats[axis]['rms_accel'] = np.sqrt(np.mean(accel[accel_mask]**2))
        else:
            stats[axis]['rms_accel'] = np.sqrt(np.mean(accel**2))
    
    return stats
    
def plot_stage_performance_results(results, test_type):
    """
    Create Plotly plots for stage performance data with 5 stacked signal plots
    
    Args:
        results: Dictionary returned from validate_stage_performance
        test_type: 'single' or 'multi' to determine result structure
    """
    
    if not results:
        print("❌ No results data to plot")
        return
    
    # Create timestamp for unique filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Get axis names from the first result (assuming we know the axes from the test)
    # For single axis test, there's only one axis
    # For multi axis test, there are typically two axes
    if test_type == 'single':
        axis_names = ['X']  # This should be dynamically determined
    else:  # multi
        axis_names = ['X', 'Y']  # This should be dynamically determined
    
    print(f"📊 Creating plots for {test_type} axis test with axes: {axis_names}")
    
    # Define the signals with separate plot titles and y-axis labels
    signals = [
        (a1.AxisDataSignal.PositionError, 'Position Error Analysis', '[units]'),
        (a1.AxisDataSignal.VelocityFeedback, 'Velocity Feedback Analysis', '[units/s]'),
        (a1.AxisDataSignal.AccelerationFeedback, 'Acceleration Feedback Analysis', '[units/s²]'),
        (a1.AxisDataSignal.CurrentCommand, 'Current Command Analysis', '[A]'),
        (a1.AxisDataSignal.CurrentFeedback, 'Current Feedback Analysis', '[A]')
    ]
    
    # Colors for different axes
    axis_colors = ['blue', 'red', 'green', 'orange', 'purple']
    
    # Determine move names based on test type
    if test_type == 'multi':
        expected_moves = ['SW_NE', 'NE_SW', 'SE_NW', 'NW_SE']
        plot_prefix = "multi_axis"
    elif test_type == 'single':
        expected_moves = ['pos', 'neg']
        plot_prefix = "single_axis"
    else:
        print(f"❌ Unknown test_type: {test_type}")
        return
    
    # Verify we have the expected moves
    available_moves = list(results.keys())
    print(f"📋 Expected moves: {expected_moves}")
    print(f"📋 Available moves: {available_moves}")
    
    # Create plots for each move
    for move_name, data in results.items():
        print(f"📈 Processing {move_name} data...")
        
        # Extract time data using the correct method
        try:
            time_array = np.array(data.system.get(a1.SystemDataSignal.DataCollectionSampleTime).points)
            time_array -= time_array[0]  # Start from 0
            time_array *= 0.001  # Convert msec to sec
            time_array = time_array.tolist()
        except Exception as e:
            print(f"⚠️  Could not extract time data for {move_name}: {e}")
            continue
        
        # Create subplots - 5 rows, 1 column (stacked)
        fig = make_subplots(
            rows=5, cols=1,
            shared_xaxes=True,
            subplot_titles=[signal[1] for signal in signals],
            vertical_spacing=0.05
        )
        
        # Initialize signal data storage for stats
        signal_data_dict = {}
        for signal_type, plot_title, y_axis_label in signals:  # <-- FIX: unpack all 3 values
            signal_data_dict[signal_type.name] = {}

        # Plot each signal
        for row, (signal_type, plot_title, y_axis_label) in enumerate(signals, 1):
            for i, axis in enumerate(axis_names):
                try:
                    # Get data for this axis and signal using the correct method
                    signal_data = data.axis.get(signal_type, axis).points
                    signal_array = np.array(signal_data).tolist()
                    
                    # Store signal data for stats calculation
                    signal_data_dict[signal_type.name][axis] = signal_data
                    
                    # Add trace to the appropriate subplot
                    fig.add_trace(
                        go.Scatter(
                            x=time_array, 
                            y=signal_array, 
                            name=f'{axis} {signal_type.name}',
                            line=dict(color=axis_colors[i % len(axis_colors)]),
                            showlegend=(row == 1)
                        ),
                        row=row, col=1
                    )
                    
                except Exception as e:
                    print(f"⚠️  Could not extract {signal_type.name} data for axis {axis}: {e}")
                    signal_data_dict[signal_type.name][axis] = []  # Empty list for failed extractions
                    continue
        
        # Add this after all the fig.update_yaxes calls but before saving:
        
        # Calculate performance statistics
        try:
            stats = calculate_performance_stats(time_array, signal_data_dict, axis_names)
            
            # Create stats table text
            stats_text = f"<b>Performance Statistics ({move_name.upper()})</b><br><br>"
            for axis in axis_names:
                stats_text += f"<b>{axis} Axis:</b><br>"
                stats_text += f"• Peak Pos Error: {stats[axis]['peak_pos_error']:.4f}<br>"
                stats_text += f"• Current @ Const Vel: {stats[axis]['current_const_vel']:.4f}A<br>"
                stats_text += f"• RMS Accel: {stats[axis]['rms_accel']:.4f}<br><br>"
            
            # Add stats table as annotation
            fig.add_annotation(
                x=0.98, y=0.98,
                xref="paper", yref="paper",
                text=stats_text,
                showarrow=False,
                bgcolor="lightblue",
                bordercolor="black",
                borderwidth=1,
                font=dict(size=10),
                align="left",
                xanchor="right",  
                yanchor="top"
            )
        except Exception as e:
            print(f"⚠️  Could not calculate stats for {move_name}: {e}")
        
        # Create descriptive title based on test type
        if test_type == 'multi':
            title_details = {
                'SW_NE': "Southwest to Northeast Move",
                'NE_SW': "Northeast to Southwest Move", 
                'SE_NW': "Southeast to Northwest Move",
                'NW_SE': "Northwest to Southeast Move"
            }
            title_detail = title_details.get(move_name, move_name)
        else:  # single
            title_details = {
                'pos': "Positive Direction Move",
                'neg': "Negative Direction Move"
            }
            title_detail = title_details.get(move_name, move_name)
        
        # Update layout
        fig.update_layout(
            title=f'Stage Performance Analysis ({test_type.upper()}): {title_detail}',
            height=800,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right", 
                x=1
            )
        )
        
        # Update x-axis labels (only show time label on bottom plot)
        for row in range(1, 6):
            if row == 5:  # Bottom subplot
                fig.update_xaxes(title_text="Time [s]", row=row, col=1)
            else:
                fig.update_xaxes(title_text="", row=row, col=1)
        
        # Update y-axis labels
        for row, (signal_type, plot_title, y_axis_label) in enumerate(signals, 1):
            fig.update_yaxes(title_text=y_axis_label, row=row, col=1)  # Use y-axis labels (index 2)    
        
        # Save plot with descriptive filename
        filename = f"stage_performance_{plot_prefix}_{move_name}_{timestamp}.html"
        pyo.plot(fig, filename=filename, auto_open=False)
        print(f"✅ Saved plot: {filename}")
    
    print(f"✅ All {test_type} axis stage performance plots created with timestamp: {timestamp}")

def main(test=None):
    """Main function with verification flow"""
    print(f"Starting main with test={test}")
    
    if test == 'FR':
        print("🚀 Starting Complete EasyTune Process with Verification")
        print("="*60)

        controller = connect()
        # Ask user if this is a single axis or multi-axis test
        test_type = input("Is this a single axis or multi-axis test? (single/multi)").strip().lower()
        # Prompt user for current percent
        while True:
            try:
                current_percent = float(input("Enter the current percent to use for all frequency response tests (e.g., 5 or 10): ").strip())
                if 0 < current_percent <= 100:
                    break
                else:
                    print("Please enter a value between 0 and 100.")
            except ValueError:
                print("Invalid input. Please enter a numeric value.")
        if test_type == 'single':
            axes_dict = {}
            # Ask user which axis to perform EasyTune on
            axis = input("Enter the axis name to perform EasyTune on (e.g., X, Y, Z): ").strip().upper()
            if not axis:
                print("❌ No axis specified. Exiting...")
                return
            print(f"📋 Selected Axis: {axis}")
            max_velocity = float(input(f"Enter the max velocity for {axis} axis: "))
            max_accel = float(input(f"Enter the max acceleration for {axis} axis: "))
            axes_dict[axis] = [max_velocity, max_accel]

            controller.runtime.commands.motion.enable(axis)
            controller.runtime.commands.motion.home(axis)
            # Get travel limits for both axes
            axis_limits = {}

            pos_limit = controller.runtime.parameters.axes[axis].protection.softwarelimithigh.value
            neg_limit = controller.runtime.parameters.axes[axis].protection.softwarelimitlow.value
            axis_limits[axis] = (neg_limit, pos_limit)
            print(f"  {axis} axis limits: {neg_limit} to {pos_limit}")

            # Calculate center positions for each axis
            center = (axis_limits[axis][0] + axis_limits[axis][1]) / 2
            controller.runtime.commands.motion.moveabsolute([axis], [center], [5])
            position = 'Center'

            fr_files = {}
            fr_filepath, _ = frequency_response(axis, controller, current_percent, verification=False, position=position, axes=None)
            fr_files[axis] = fr_filepath

        elif test_type == 'multi':
            axes_dict = {}
            # Ask user which axes to perform EasyTune on
            axes = input("Enter the axes to perform EasyTune on (e.g., XYZ): ").strip().upper()

            if not axes:
                print("❌ No axes specified. Exiting...")
                return
            else:
                axes = list(axes)
                print(f"📋 Selected Axes: {axes}")
                for axis in axes:
                    max_velocity = float(input(f"Enter the max velocity for {axis} axis: "))
                    max_accel = float(input(f"Enter the max acceleration for {axis} axis: "))
                    axes_dict[axis] = [max_velocity, max_accel]
            
            # Get travel limits for both axes
            axis_limits = {}
            for axis in axes:
                pos_limit = controller.runtime.parameters.axes[axis].protection.softwarelimithigh.value
                neg_limit = controller.runtime.parameters.axes[axis].protection.softwarelimitlow.value
                axis_limits[axis] = (neg_limit, pos_limit)
                print(f"  {axis} axis limits: {neg_limit} to {pos_limit}")

            # Get first two axes for position calculations
            x_axis = axes[0]
            y_axis = axes[1]

            # Calculate center positions for each axis
            x_center = (axis_limits[x_axis][0] + axis_limits[x_axis][1]) / 2
            y_center = (axis_limits[y_axis][0] + axis_limits[y_axis][1]) / 2
            
            controller.runtime.commands.motion.enable(axes)
            controller.runtime.commands.motion.home(axes)
            controller.runtime.commands.motion.moveabsolute(axes, [x_center, y_center], [5, 5])
            position = 'Center'

            fr_files = {}
            for axis in axes:
                fr_filepath, _ = frequency_response(axis, controller, current_percent, verification=False, position=position, axes=axes)
                fr_files[axis] = fr_filepath

        iteration = 1
        log_files = []
        # Process each FR file with individual logging
        for axis, fr_filepath in fr_files.items():
            log_filepath = os.path.splitext(fr_filepath)[0] + '.log'
            with open(log_filepath, 'w', encoding='utf-8') as log_file:
                with contextlib.redirect_stdout(log_file), contextlib.redirect_stderr(log_file):
                    print(f"🔍 Processing FR file: {os.path.basename(fr_filepath)}")
                    print(f"📅 Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    print("="*60)
                    
                    # Step 2: EasyTune Optimization
                    print("\n🎯 STEP 2: EasyTune Optimization")
                    results, stability_passed, ff_analysis_data = optimize(fr_filepath=fr_filepath)
                    if not stability_passed:
                        if results:
                            success = apply_new_servo_params(axis, results, controller, ff_analysis_data)
                            controller.reset()
                    else:
                        print(f"⚠️  OPTIMIZATION FOR AXIS: {axis} PASSED - Parameter adjustments not needed...")
            log_files.append(log_filepath)
        
        fr_files = []
        while iteration < 2:
            # Step 4: Verification Frequency Response
            print("\n🔍 STEP 4: Verification Frequency Response")
            if test_type == 'single':
                fr_files = single_axis_frequency_response(axis, controller, current_percent)
            elif test_type == 'multi':
                fr_files = multi_axis_frequency_response(axes, controller, current_percent)
            print("✅ Verification Frequency Response Completed")
            time.sleep(2)
            # Process each FR file with individual logging
            for fr_filepath in fr_files:
                log_filepath = os.path.splitext(fr_filepath)[0] + '.log'
                print(f"🔍 Processing FR file: {os.path.basename(fr_filepath)}. Please wait...")
                with open(log_filepath, 'w', encoding='utf-8') as log_file:
                    with contextlib.redirect_stdout(log_file), contextlib.redirect_stderr(log_file):
                        print(f"🔍 Processing FR file: {os.path.basename(fr_filepath)}")
                        print(f"📅 Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                        print("="*60)
                        results, stability_passed, ff_analysis_data = optimize(fr_filepath=fr_filepath)
                        if stability_passed:
                            print("🎉 OPTIMIZATION PASSED - Stability criteria met!")
                            print("✅ Process completed successfully")
                print("✅ Process completed successfully")
                log_files.append(log_filepath)
                    
            print("Please view logs to see EasyTune results.")
            iteration += 1

        print("\n" + "="*60)
        print("✅ FR file processing complete")
            
        # Console feedback about log creation
        print(f"📄 Results for {os.path.basename(fr_filepath)} saved to {log_filepath}")
        
        print("\n🎉 All FR files processed successfully!")
        
        # Generate interactive plots
        print("\n📊 Generating Interactive Plots...")
        generate_plots_from_results(log_files=log_files)
        
        print("\n" + "="*60)
        print("✅ EasyTune process completed successfully!")
        print("📊 Check the generated HTML files for interactive plots")
        print("="*60)

        print("\n" + "="*60)
        print("🔍 Performing Stage Performance Validation...")
        results =validate_stage_performance(controller, axes_dict, test_type, axis_limits)
        plot_stage_performance_results(results, test_type)  # Pass the test_type!
        print("✅ Stage Performance Validation Completed")
        print("="*60)
        
    if test == 'validate':
        controller = connect()
        test_type = 'multi'
        axes_dict = {}
        # Ask user which axes to perform EasyTune on
        axes = input("Enter the axes to perform EasyTune on (e.g., XYZ): ").strip().upper()

        if not axes:
            print("❌ No axes specified. Exiting...")
            return
        else:
            axes = list(axes)
            print(f"📋 Selected Axes: {axes}")
            for axis in axes:
                max_velocity = float(input(f"Enter the max velocity for {axis} axis: "))
                max_accel = float(input(f"Enter the max acceleration for {axis} axis: "))
                axes_dict[axis] = [max_velocity, max_accel]
        
        # Get travel limits for both axes
        axis_limits = {}
        for axis in axes:
            pos_limit = controller.runtime.parameters.axes[axis].protection.softwarelimithigh.value
            neg_limit = controller.runtime.parameters.axes[axis].protection.softwarelimitlow.value
            axis_limits[axis] = (neg_limit, pos_limit)
            print(f"  {axis} axis limits: {neg_limit} to {pos_limit}")

        # Get first two axes for position calculations
        x_axis = axes[0]
        y_axis = axes[1]

        # Calculate center positions for each axis
        x_center = (axis_limits[x_axis][0] + axis_limits[x_axis][1]) / 2
        y_center = (axis_limits[y_axis][0] + axis_limits[y_axis][1]) / 2
        
        controller.runtime.commands.motion.enable(axes)
        controller.runtime.commands.motion.home(axes)
        controller.runtime.commands.motion.moveabsolute(axes, [x_center, y_center], [5, 5])
        position = 'Center'
        
        print("\n" + "="*60)
        print("🔍 Performing Stage Performance Validation...")
        results =validate_stage_performance(controller, axes_dict, test_type, axis_limits)
        plot_stage_performance_results(results, test_type)  # Pass the test_type!
        print("✅ Stage Performance Validation Completed")
        print("="*60)
# When running the script
if __name__ == "__main__":
    print("Starting program...")  # Debug print
    main(test='FR')
    print("Program completed")  # Debug print