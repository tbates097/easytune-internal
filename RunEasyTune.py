# -*- coding: utf-8 -*-
"""
Created on Thu Mar 28 14:14:27 2024

@author: tbates
"""

import automation1 as a1
import sys
import contextlib
import os
import re
import json
import subprocess
import time
import numpy as np
#import serial.tools.list_ports
import tkinter as tk
from tkinter import messagebox, filedialog
from DecodeFaults import decode_faults
import math
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.offline as pyo
from datetime import datetime
import tempfile
import zipfile
import xml.etree.ElementTree as ET
import shutil

from Modules.Easy_Tune_Module import Easy_Tune_Module
from Modules.Easy_Tune_Plotter import EasyTunePlotter
from Modules.EncoderTuning import EncoderTuning

sys.path.append(r"K:\10. Released Software\Shared Python Programs\production-2.1")
from a1_file_handler import DatFile
from GenerateMCD_v2 import AerotechController

global so_dir
so_dir = None

def check_stop_signal(stop_event):
    """Check if stop was requested and raise exception if so"""
    if stop_event and stop_event.is_set():
        print("🛑 Stop requested - exiting current operation")
        raise KeyboardInterrupt("Process stopped by user")

def cleanup_mcd_files(base_name, dir_path):
    """Clean up temporary MCD files created during the process"""
    if not base_name or not dir_path:
        return
    
    backup_path = os.path.join(dir_path, f"{base_name}-backup.mcd")
    modified_path = os.path.join(dir_path, f"{base_name}-modified.mcd")
    
    files_to_cleanup = [backup_path, modified_path]
    
    print("\n🧹 Cleaning up temporary MCD files...")
    for file_path in files_to_cleanup:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️ Deleted: {os.path.basename(file_path)}")
            else:
                print(f"ℹ️ File not found (already cleaned): {os.path.basename(file_path)}")
        except Exception as e:
            print(f"⚠️ Could not delete {os.path.basename(file_path)}: {str(e)}")
    
    print("✅ MCD file cleanup completed")

def modify_controller_name(mcd_path, mode="Loaded"):
    # Use system temp directory with write permissions
    temp_dir = tempfile.mkdtemp(prefix="mcd_extract_")

    try:
        # Extract the original MCD
        with zipfile.ZipFile(mcd_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        name_path = os.path.join(temp_dir, "config", "Names")
        if os.path.exists(name_path):
            name_tree = ET.parse(name_path)
            name_root = name_tree.getroot()

            # Find the ControllerName element
            controller_name_elem = name_root.find(".//ControllerName")
            if controller_name_elem is not None and controller_name_elem.text:
                current_name = controller_name_elem.text.strip()
                if mode.lower() == "no load":
                    # If "No Load" not present, add it
                    if re.search(r'no[\s\-]*load', current_name, flags=re.IGNORECASE):
                        new_text = current_name
                    else:
                        new_text = current_name + " No Load"
                else:  # mode == "Loaded"
                    # Replace any "No Load" with "Loaded", or add "Loaded" if not present
                    new_text = re.sub(r'[\s\-]*no[\s\-]*load[\s\-]*', ' Loaded', current_name, flags=re.IGNORECASE)
                    if 'Loaded' not in new_text:
                        new_text = new_text.strip() + ' Loaded'
                controller_name_elem.text = new_text.strip()
                print(f"Updated ControllerName: {controller_name_elem.text}")

                # Save the modified Names file
                name_tree.write(name_path, encoding='utf-8', xml_declaration=True)
            else:
                print("ControllerName element not found or empty in Names file.")

        # Create new MCD file
        with zipfile.ZipFile(mcd_path, 'w', zipfile.ZIP_DEFLATED) as new_zip:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    new_zip.write(file_path, arcname)
    except Exception as e:
        print(f"❌ Error modifying MCD: {str(e)}")
        return None

def modify_mcd_enabled_tasks(mcd_path):
    """Modifies the MCD file to ensure EnabledTasks is set correctly"""
    # Use system temp directory with write permissions
    temp_dir = tempfile.mkdtemp(prefix="mcd_extract_")
    
    # Ask user to select source MCD file
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    if not mcd_path:
        print("❌ No MCD file selected")
        return None

    # Create a backup copy first
    dir_path = os.path.dirname(mcd_path)
    base_name = os.path.splitext(os.path.basename(mcd_path))[0]
    backup_path = os.path.join(dir_path, f"{base_name}-backup.mcd")
    
    try:
        print(f"📑 Creating backup of original MCD...")
        shutil.copy2(mcd_path, backup_path)
        print(f"✅ Backup created: {os.path.basename(backup_path)}")
    except Exception as e:
        print(f"❌ Failed to create backup: {str(e)}")
        return None  # Don't proceed if we can't create a backup
    
    # Create a new filename for the modified MCD
    new_mcd_path = os.path.join(dir_path, f"{base_name}-modified.mcd")
    
    # Clean up any existing temp directory
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    
    try:
        # Extract the original MCD
        with zipfile.ZipFile(mcd_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Modify the Parameters file
        params_path = os.path.join(temp_dir, "config", "Parameters")
        if os.path.exists(params_path):
            tree = ET.parse(params_path)
            root = tree.getroot()
            
            # Find or create the System section
            params = root.find(".//Parameters")
            if params is None:
                data = root.find("Data")
                if data is None:
                    data = ET.SubElement(root, "Data")
                params = ET.SubElement(data, "Parameters")
            
            system = params.find("System")
            if system is None:
                system = ET.SubElement(params, "System")
            
            # Check if EnabledTasks already exists
            enabled_tasks = system.find('.//P[@n="EnabledTasks"]')
            needs_update = False

            if enabled_tasks is None:
                # Add EnabledTasks parameter if it doesn't exist
                enabled_tasks = ET.SubElement(system, "P")
                enabled_tasks.set("id", "278")
                enabled_tasks.set("n", "EnabledTasks")
                needs_update = True
            else:
                # Check if the value is missing or <= 2
                try:
                    value = int(enabled_tasks.text.strip())
                    if value <= 2:
                        needs_update = True
                except (TypeError, ValueError, AttributeError):
                    # If text is missing or not an integer, update it
                    needs_update = True

            if needs_update:
                enabled_tasks.text = "4"
                
                # Save the modified Parameters file with proper XML declaration
                xml_str = '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n'
                tree_str = ET.tostring(root, encoding='unicode')
                if tree_str.startswith('<?xml'):
                    tree_str = tree_str[tree_str.find('?>')+2:]
                with open(params_path, 'w', encoding='utf-8') as f:
                    f.write(xml_str + tree_str)
        
        # Create new MCD file
        with zipfile.ZipFile(new_mcd_path, 'w', zipfile.ZIP_DEFLATED) as new_zip:
            # Walk through the temporary directory and add all files
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    new_zip.write(file_path, arcname)
        
        print(f"✅ Modified MCD saved as: {new_mcd_path}")
        return new_mcd_path, base_name, dir_path
        
    except Exception as e:
        print(f"❌ Error modifying MCD: {str(e)}")
        return None
    
    finally:
        # Clean up
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            
def modify_mcd_payloads(mcd_path, payload_values):
    """
    Unpack the MCD, update LoadMass/LoadInertia in config/MachineSetupData for each axis in payload_values (order matters).
    Only updates if payload is nonzero.
    """
    import tempfile

    temp_dir = tempfile.mkdtemp(prefix="mcd_extract_")
    try:
        # Extract the MCD
        with zipfile.ZipFile(mcd_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        msd_path = os.path.join(temp_dir, "config", "MachineSetupData")
        if not os.path.exists(msd_path):
            print("❌ MachineSetupData not found in MCD")
            return None

        tree = ET.parse(msd_path)
        root = tree.getroot()

        # Find all Stage components in order
        stages = []
        for mech_axis in root.findall(".//MachineSetupConfiguration/MechanicalProducts/MechanicalProduct/MechanicalAxes/MechanicalAxis"):
            stage = mech_axis.find("./Stage/LinearStageComponent")
            if stage is None:
                stage = mech_axis.find("./Stage/RotaryStageComponent")
            if stage is not None:
                stages.append(stage)

        # Get payload values in order
        payload_keys = list(payload_values.keys())
        payload_vals = [payload_values[k] for k in payload_keys if float(payload_values[k]) != 0]

        if not payload_vals:
            print("No nonzero payloads to update.")
            return None

        # Update stages in order
        updated = False
        for i, payload in enumerate(payload_vals):
            if i >= len(stages):
                break
            stage = stages[i]
            # Try LoadMass first, then LoadInertia
            load_mass = stage.find("LoadMass")
            load_inertia = stage.find("LoadInertia")
            if load_mass is not None:
                load_mass.text = str(payload)
                updated = True
            elif load_inertia is not None:
                load_inertia.text = str(payload)
                updated = True

        if not updated:
            print("No LoadMass or LoadInertia fields updated.")
            return None

        # Save the modified MachineSetupData
        tree.write(msd_path, encoding='utf-8', xml_declaration=True)

        # Repack the MCD
        with zipfile.ZipFile(mcd_path, 'w', zipfile.ZIP_DEFLATED) as new_zip:
            for root_dir, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root_dir, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    new_zip.write(file_path, arcname)
        print(f"✅ Payloads updated and new MCD saved as: {mcd_path}")
        return mcd_path

    except Exception as e:
        print(f"❌ Error modifying MCD payloads: {e}")
        return None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def upload_mcd_to_controller(controller, mdk_path):
    """Uploads an MCD file to the controller"""
    try:
        print(f"📤 Uploading MCD file to controller...")
        controller.upload_mcd_to_controller(
            mdk_path, 
            should_include_files=True, 
            should_include_configuration=True, 
            erase_controller=False
        )
        print("✅ MCD upload completed successfully")
        return True
    except Exception as e:
        print(f"❌ Error uploading MCD: {str(e)}")
        return False

def download_mcd_from_controller(controller, mdk_path):
    """Uploads an MCD file to the controller"""
    try:
        # Remove the file if it already exists to ensure overwrite
        if os.path.exists(mdk_path):
            os.remove(mdk_path)
            print(f"ℹ️ Existing file {os.path.basename(mdk_path)} deleted before download.")

        print(f"📥 Downloading MCD file to controller...")
        controller.download_mcd_to_file(
            mdk_path, 
            should_include_files=False, 
            should_include_configuration=True
        )
        print("✅ MCD download completed successfully")
        return True
    except Exception as e:
        print(f"❌ Error downloading MCD: {str(e)}")
        return False
        
def get_file_directory(controller_name):
    """Create and return the directory path for file storage based on SO number"""
    username = os.getlogin()
    base_dir = os.path.join(f"C:\\Users\\{username}\\Documents\\Automation1")
    
    # Extract SO number (first 6 digits) from controller name
    so_number = controller_name[:6]
    
    # Create SO directory path
    so_dir = os.path.join(base_dir, f"SO_{so_number}")
    
    # Create directory if it doesn't exist
    if not os.path.exists(so_dir):
        os.makedirs(so_dir)
        print(f"📁 Created directory for SO {so_number}")
    if not os.path.exists(os.path.join(so_dir, 'Performance Analysis')):
        os.makedirs(os.path.join(so_dir, 'Performance Analysis'), exist_ok=True)
        print(f"📁 Created Performance Analysis directory for SO {so_number}")
    
    return so_dir

def extract_axis_from_fr_filepath(fr_filepath):
    """
    Extracts the axis name from a frequency response file path.
    Assumes filename format: test-{axis}-{position}.fr or test-{axis}-{position}-Verification.fr
    """
    filename = os.path.basename(fr_filepath)
    match = re.match(r"test-([A-Za-z]+)-", filename)
    if match:
        return match.group(1)
    else:
        return None

def connect(connection_type=None):
    global controller, non_virtual_axes, connected_axes
    
    if connection_type is None:
        try:
            controller = a1.Controller.connect()
            controller.start()
        except:
            if messagebox.askyesno('Could Not Connect To Hyperwire', 'Is this an iDrive?'):
                try:
                    controller = a1.Controller.connect_usb()
                    controller.start()
                except:
                    messagebox.showerror('Connection Error', 'Check connections and try again')
            else:
                messagebox.showerror('Connection Error', 'Check Firmware version and try again')
    if connection_type == 'usb':
        try:
            controller = a1.Controller.connect_usb()
            controller.start()
        except:
            messagebox.showerror('Connection Error', 'Check connections and try again')
    if connection_type == 'hyperwire':
        try:
            controller = a1.Controller.connect()
            controller.start()
        except:
            messagebox.showerror('Connection Error', 'Check connections and try again')

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

                non_virtual_axes.append(key)

    return controller, non_virtual_axes    #messagebox.showerror('No Device', 'No Devices Present. Check Connections.')

def get_limit_dec(controller, axis, limit=None):
    # Retrieve the current configuration for the axis
    electrical_limits = controller.runtime.parameters.axes[axis].protection.faultmask
    electrical_limit_value = int(electrical_limits.value)

    # Define bit positions for each limit
    CCW_SOFTWARE_LIMIT = 5
    CW_SOFTWARE_LIMIT = 4
    CCW_ELECTRICAL_LIMIT = 3
    CW_ELECTRICAL_LIMIT = 2

    # Toggle limits
    if limit == 'software on':
        electrical_limit_value |= (1 << CCW_SOFTWARE_LIMIT) | (1 << CW_SOFTWARE_LIMIT)
    elif limit == 'software off':
        electrical_limit_value &= ~((1 << CCW_SOFTWARE_LIMIT) | (1 << CW_SOFTWARE_LIMIT))
    elif limit == 'electrical on':
        electrical_limit_value |= (1 << CCW_ELECTRICAL_LIMIT) | (1 << CW_ELECTRICAL_LIMIT)
    elif limit == 'electrical off':
        electrical_limit_value &= ~((1 << CCW_ELECTRICAL_LIMIT) | (1 << CW_ELECTRICAL_LIMIT))

    return electrical_limit_value

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
            data_config.axis.add(a1.AxisDataSignal.AccelerationCommand, axis)
            data_config.axis.add(a1.AxisDataSignal.PositionError, axis)
            data_config.axis.add(a1.AxisDataSignal.CurrentCommand, axis)
            data_config.axis.add(a1.AxisDataSignal.CurrentFeedback, axis)
            data_config.axis.add(a1.AxisDataSignal.VelocityCommand, axis)
            data_config.axis.add(a1.AxisDataSignal.PositionCommand, axis)
            data_config.axis.add(a1.AxisDataSignal.CurrentFeedback, axis)
    if axis:
        # Add items to collect data on the specified axis
        data_config.axis.add(a1.AxisDataSignal.DriveStatus, axis)
        data_config.axis.add(a1.AxisDataSignal.AxisFault, axis)
        data_config.axis.add(a1.AxisDataSignal.PrimaryFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.PositionFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.VelocityFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.AccelerationFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.AccelerationCommand, axis)
        data_config.axis.add(a1.AxisDataSignal.PositionError, axis)
        data_config.axis.add(a1.AxisDataSignal.CurrentCommand, axis)
        data_config.axis.add(a1.AxisDataSignal.CurrentFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.VelocityCommand, axis)
        data_config.axis.add(a1.AxisDataSignal.PositionCommand, axis)
        data_config.axis.add(a1.AxisDataSignal.CurrentFeedback, axis)

    return data_config

def check_for_faults(controller: a1.Controller, axes=None):
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
        else:
            sample_freq = 20000.0  # Fallback default

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
                
                if filter_type == 'Low_Pass':
                    cutoff_freq = parameters['Cutoff Frequency']
                    N, D = calculate_lowpass_coefficients(cutoff_freq, sample_freq)
                    
                    filter_coefficients[filter_group][original_index] = {  # Use original index
                        'type': 'Low_Pass',
                        'parameters': parameters,
                        'numerator': N,
                        'denominator': D
                    }
                    
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
                
                if filter_type == 'Low_Pass':
                    cutoff_freq = parameters['Cutoff Frequency']
                    N, D = calculate_lowpass_coefficients(cutoff_freq, sample_freq)
                    
                    filter_coefficients[filter_group][i] = {
                        'type': 'Low_Pass',
                        'parameters': parameters,
                        'numerator': N,
                        'denominator': D
                    }
                    
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

def apply_new_servo_params(axis, results, controller, ff_analysis_data=None, verification=False):
    """Apply the shaped servo parameters from EasyTune results"""
    print(f"Applying new servo parameters for axis {axis}")
    
    # Extract all shaped parameters
    shaped_params = extract_shaped_parameters(results)
    
    # Get configuration parameters
    configured_parameters = controller.configuration.parameters.get_configuration()
    
    if verification:
        # Apply filter coefficients if present
        if 'Filters' in shaped_params:
            print("\n🔧 Processing shaped filter configurations...")
            # Assume 20kHz sample frequency - adjust as needed for your system
            filter_coefficients = convert_filters_to_coefficients(shaped_params)
            
            if filter_coefficients:
                apply_filter_coefficients_to_controller(axis, filter_coefficients, controller)

    else:            
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
            
            if ff_analysis_data and 'center_magnitude_difference_db' in ff_analysis_data:
                center_mag_diff = ff_analysis_data['center_magnitude_difference_db']
                # Convert dB to absolute units and multiply by original Aff
                center_mag_absolute = 10**(center_mag_diff/20)  # Convert from dB to absolute units
                aff_adjusted = aff_original * center_mag_absolute
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

def apply_servo_params_from_dict(servo_params, controller, available_axes):
    """
    Apply all servo loop parameters from the servo_params dictionary to the controller.
    axis_index (as string) is mapped to axis name using available_axes list.
    """
    # Get the current configuration object
    configured_parameters = controller.configuration.parameters.get_configuration()

    for axis_index_str, param_list in servo_params.items():
        # axis_index_str is a string, convert to int for indexing
        try:
            axis_index = int(axis_index_str)
        except Exception:
            print(f"⚠️ Invalid axis index: {axis_index_str}")
            continue

        # Map axis index to axis name using available_axes
        if axis_index >= len(available_axes):
            print(f"⚠️ Axis index {axis_index} out of range for available_axes")
            continue
        axis_name = available_axes[axis_index]
        print(f"\n🔧 Applying servo parameters to axis '{axis_name}' (index {axis_index})")

        for param in param_list:
            param_name = param['name']
            param_value = param['value']

            # Try to set the parameter dynamically
            try:
                servo_obj = configured_parameters.axes[axis_name].servo
                param_obj = getattr(servo_obj, param_name.lower())
                param_obj.value = type(param_obj.value)(param_value)
                print(f"    ✅ Set {param_name}.value = {param_value}")
            except AttributeError as e:
                print(f"    ⚠️ Parameter '{param_name}' not found on axis '{axis_name}': {e}")
            except Exception as e:
                print(f"    ⚠️ Error setting '{param_name}' on axis '{axis_name}': {e}")

    # Apply the configuration to the controller
    try:
        controller.configuration.parameters.set_configuration(configured_parameters)
        return True
    except Exception as e:
        print(f"❌ Error applying servo parameters: {e}")
        return False

def apply_feedforward_params_from_dict(feedforward_params, controller, available_axes):
    """
    Apply all feedforward parameters from the feedforward_params dictionary to the controller.
    axis_index (as string) is mapped to axis name using available_axes list.
    """
    # Get the current configuration object
    configured_parameters = controller.configuration.parameters.get_configuration()

    for axis_index_str, param_list in feedforward_params.items():
        # axis_index_str is a string, convert to int for indexing
        try:
            axis_index = int(axis_index_str)
        except Exception:
            print(f"⚠️ Invalid axis index: {axis_index_str}")
            continue

        # Map axis index to axis name using available_axes
        if axis_index >= len(available_axes):
            print(f"⚠️ Axis index {axis_index} out of range for available_axes")
            continue
        axis_name = available_axes[axis_index]
        print(f"\n🔧 Applying feedforward parameters to axis '{axis_name}' (index {axis_index})")

        for param in param_list:
            param_name = param['name']
            param_value = param['value']

            # Try to set the parameter dynamically
            try:
                servo_obj = configured_parameters.axes[axis_name].servo
                param_obj = getattr(servo_obj, param_name.lower())
                param_obj.value = type(param_obj.value)(param_value)
                print(f"    ✅ Set {param_name}.value = {param_value}")
            except AttributeError as e:
                print(f"    ⚠️ Parameter '{param_name}' not found on axis '{axis_name}': {e}")
            except Exception as e:
                print(f"    ⚠️ Error setting '{param_name}' on axis '{axis_name}': {e}")

    # Apply the configuration to the controller
    try:
        controller.configuration.parameters.set_configuration(configured_parameters)
        return True
    except Exception as e:
        print(f"❌ Error applying feedforward parameters: {e}")
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
            'max': 8,  # Should not exceed this value
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
    
    #print(f"Results from analyze_easy_tune: {results}")
    stability_data = results['Stability_Metrics']['original']
    #shaped_data = results['Stability_Metrics']['shaped']
    analysis_passed = True
    issues = []

    # Analyze Phase Margin
    if 'phase_margin' in stability_data:
        phase_margin = stability_data['phase_margin']['degrees']
        crossover_freq = stability_data['phase_margin']['frequency_hz']
        
        print("\n📐 CROSSOVER FREQUENCY ANALYSIS:")
        print(f"   Current Value: {crossover_freq:.1f} Hz")
        
        print("\n📐 PHASE MARGIN ANALYSIS:")
        print(f"   Current Value: {phase_margin:.1f}° @ {crossover_freq:.1f} Hz")
        print(f"   Target Range:  {standards['phase_margin']['min']}-{standards['phase_margin']['max']}°")
        print(f"   Target Value:  {standards['phase_margin']['target']}°")

        #if standards['phase_margin']['min'] <= phase_margin <= standards['phase_margin']['max']:
            #print("   ✅ PASS - Phase margin within acceptable range")
        #else:
            #analysis_passed = False
            #if phase_margin < standards['phase_margin']['min']:
                #issues.append(f"Phase margin too low ({phase_margin:.1f}° < {standards['phase_margin']['min']}°)")
                #print(f"   ❌ FAIL - Phase margin too low (minimum: {standards['phase_margin']['min']}°)")
            #else:
                #issues.append(f"Phase margin too high ({phase_margin:.1f}° > {standards['phase_margin']['max']}°)")
                #print(f"   ⚠️  WARNING - Phase margin is high (maximum: {standards['phase_margin']['max']}°)")
    
    # Analyze Gain Margin
    if 'gain_margin' in stability_data:
        gain_margin = abs(stability_data['gain_margin']['db'])
        gain_freq = stability_data['gain_margin']['frequency_hz']
        
        print("\n📊 GAIN MARGIN ANALYSIS:")
        print(f"   Current Value: {gain_margin:.1f} dB @ {gain_freq:.1f} Hz")
        print(f"   Target Range:  {standards['gain_margin']['min']}-{standards['gain_margin']['max']} dB")
        print(f"   Target Value:  {standards['gain_margin']['target']} dB")
        
        #if standards['gain_margin']['min'] <= gain_margin <= standards['gain_margin']['max']:
            #print("   ✅ PASS - Gain margin within acceptable range")
        #else:
            #analysis_passed = False
            #if gain_margin < standards['gain_margin']['min']:
                #issues.append(f"Gain margin too low ({gain_margin:.1f} dB < {standards['gain_margin']['min']} dB)")
                #print(f"   ⚠️ FAIL - Gain margin low (minimum: {standards['gain_margin']['min']} dB)")
            #else:
                #issues.append(f"Gain margin too high ({gain_margin:.1f} dB > {standards['gain_margin']['max']} dB)")
                #print(f"   ⚠️  WARNING - Gain margin high (maximum: {standards['gain_margin']['max']} dB)")
    
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
    global so_dir

    params = controller.configuration.parameters.get_configuration()
    units = params.axes[axis].units.unitsname.value
    motor_pole_pitch = params.axes[axis].motor.motorpolepitch.value
    motor = params.axes[axis].motor.motortype.value
    distance = calculate_unit_distance(motor_pole_pitch, units)
    
    pos_limit = controller.runtime.parameters.axes[axis].protection.softwarelimithigh.value
    neg_limit = controller.runtime.parameters.axes[axis].protection.softwarelimitlow.value
    travel = pos_limit + abs(neg_limit)
    
    if travel == 0 and motor == 1:
        travel = 360
        
    if distance >= travel:
        distance = travel / 2.25
    
    speed = distance * 0.1
    if position != 'Center Init':
        position_str = position['name']
    else: position_str = position
    # Different filename and current percentage for verification
    if verification:
        fr_filename = f'test-{axis}-{position_str}-Verification.fr'
        print(f"🔍 Running VERIFICATION frequency response at {current_percent}% max current, {distance} mm at {speed}")

    else:
        time.sleep(2)
        fr_filename =  f'test-{axis}-{position_str}.fr'
        print(f"📊 Running INITIAL frequency response at {current_percent}% max current, {distance} mm at {speed}")


    # Generate the FR file with appropriate current percentage
    fr_string = fr'AppFrequencyResponseTriggerMultisinePlus({axis}, "{fr_filename}", 10, 2500, 280, {current_percent}, TuningMeasurementType.ServoOpenLoop, {distance}, {speed})'
    #fr_string = fr'AppFrequencyResponseTriggerMultisinePlus({axis}, "{fr_filename}", 10, 2500, 280, {current_percent}, TuningMeasurementType.ServoOpenLoop, 0, 0)'
    
    controller.runtime.commands.execute(fr_string,2)
    axis_faults = check_for_faults(controller, axes if axes else [axis])

    if axis_faults:
        fault_init = decode_faults(axis_faults, axes, controller, fault_log = None)
        decoded_faults = fault_init.get_fault()
    if decoded_faults == 'OverCurrentFault':
        fr_string = fr'AppFrequencyResponseTriggerMultisinePlus({axis}, "{fr_filename}", 10, 2500, 280, 4, TuningMeasurementType.ServoOpenLoop, {distance}, {speed})'
        controller.runtime.commands.execute(fr_string,2)
        
    time.sleep(10)
    
    # Move file from default location to SO directory
    username = os.getlogin()
    source_path = os.path.join(f"C:\\Users\\{username}\\Documents\\Automation1", fr_filename)
    fr_filepath = os.path.join(so_dir, fr_filename)
    
    if os.path.exists(source_path):
        os.replace(source_path, fr_filepath)
    else:
        print(f"❌ Could not find {fr_filename} in default location")
        
    return fr_filepath, verification

def optimize(fr_filepath=None, verification=False, position=None, performance_target=None):
    """Run EasyTune optimization on FR file"""
    if not fr_filepath:
        raise ValueError("No .fr file path provided")
    
    axis = extract_axis_from_fr_filepath(fr_filepath)

    easy_tune_module = Easy_Tune_Module(gui=None, block_layout_module=None)
    easy_tune_module.run_easy_tune(fr_filepath, verification, performance_target)
    
    # Wait for optimization to complete
    while easy_tune_module.active_thread:
        time.sleep(0.1)
    
    # Get the analysis results
    results, original_frd = easy_tune_module.get_results()

    if results is None:
        print("❌ EasyTune optimization failed - no results available")
        return None, False, None, 0
    
    if original_frd is None:
        print("⚠️ Warning: No original FRD data available - continuing without plots")
        
    shaped_data = results['Stability_Metrics']['original']
    if 'sensitivity' in shaped_data:
        sensitivity = shaped_data['sensitivity']['db']
        print(f"Sensitivity: {sensitivity}")
        sensitivity_freq = shaped_data['sensitivity']['frequency_hz']
    
    # Analyze the results against standards
    if results:
        stability_passed, ff_analysis_data = analyze_easy_tune(results)
        print(f"\nStability Analysis: {'PASSED' if stability_passed else 'FAILED'}")
        generate_plots_from_results(log_files=None, original_frd=original_frd, position=position, axis=axis)
    else:
        print("No results available for analysis")
        ff_analysis_data = None
    
    return results, stability_passed, ff_analysis_data, sensitivity

def single_axis_frequency_response(axis, controller, current_percent, all_axes=None):
    """Run frequency response tests at center and 4 corners of XY workspace"""
    print(f"🔧 Starting frequency response testing for {axis}")
    
    rotary = False
    axis = axis[0]
    fr_files = [] 
    params = controller.configuration.parameters.get_configuration()
    # Get travel limits for both axes
    axis_limits = {}
    axis_distances = {}
    rev_motion = controller.runtime.parameters.axes[axis].motion.reversemotiondirection.value
    if rev_motion == 1:
        reverse_motion = True
    else:
        reverse_motion = False
        
    pos_limit = controller.runtime.parameters.axes[axis].protection.softwarelimithigh.value
    neg_limit = controller.runtime.parameters.axes[axis].protection.softwarelimitlow.value
    units = controller.runtime.parameters.axes[axis].units.unitsname.value
    
    if units == 'deg':
        rotary = True
        
    axis_limits[axis] = (neg_limit, pos_limit)
    
    travel = abs(axis_limits[axis][1] - axis_limits[axis][0])
    speed = params.axes[axis].motion.maxjogspeed.value
    motor_pole_pitch = params.axes[axis].motor.motorpolepitch.value
    distance = calculate_unit_distance(motor_pole_pitch, units)

    limit = 'software off'
    electrical_limit_value = get_limit_dec(controller, axis, limit)
    controller.runtime.parameters.axes[axis].protection.faultmask.value = electrical_limit_value

    if distance >= travel:
        distance = travel/2.25
        
    axis_distances[axis] = distance
    
    if rotary and axis_limits[axis][0] == 0 and axis_limits[axis][1] == 0:  
        center = 0
    else:
        # Calculate center positions for each axis
        if reverse_motion:
            center = ((axis_limits[axis][0] + axis_limits[axis][1]) / 2) * -1
        else:   
            center = (axis_limits[axis][0] + axis_limits[axis][1]) / 2

    # Define test positions (center + 4 corners)
    test_positions = [
        {'name': 'Center', 
         'coords': (center),
         'directions': (1, 1)},  # Center uses default positive motion
        {'name': 'NE Corner', 
         'coords': ((axis_limits[axis][1] - calculate_coordinate_offset(axis_limits, axis)) - axis_distances[axis]),
         'directions': (-1)}, 
        {'name': 'NW Corner', 
         'coords': ((axis_limits[axis][0] + calculate_coordinate_offset(axis_limits, axis)) + axis_distances[axis]),
         'directions': (1)}  
        
    ]
    
    # Home axes first
    print("\n🏠 Homing axes...")
    controller.runtime.commands.motion.enable(all_axes)
    
    # Check for faults after enable
    axis_faults = check_for_faults(controller, all_axes)
    if axis_faults:
        fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
        decoded_faults = fault_init.get_fault()
        print(f"❌ Faults detected after enable: {decoded_faults}")
    
    controller.runtime.commands.motion.home(axis)
    
    # Check for faults after homing
    axis_faults = check_for_faults(controller, all_axes if all_axes else [axis])
    if axis_faults:
        fault_init = decode_faults(axis_faults, all_axes if all_axes else [axis], controller, fault_log = None)
        decoded_faults = fault_init.get_fault()
        print(f"❌ Faults detected after homing: {decoded_faults}")
    
    time.sleep(2)

    for position in test_positions:
        x = position['coords']
        print(f"\n📍 Testing {position['name']} (X{x:.2f}")
        
        # Move to position
        controller.runtime.commands.motion.moveabsolute([axis], [x], [speed])
        controller.runtime.commands.motion.waitformotiondone([axis])
        time.sleep(1)  # Allow time for movement
        
        # Check for faults after move
        
        axis_faults = check_for_faults(controller, all_axes if all_axes else [axis])
        if axis_faults:
            fault_init = decode_faults(axis_faults, all_axes if all_axes else [axis], controller, fault_log = None)
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
            axes=all_axes
        )

        fr_files.append(fr_filepath)

        print("✅ Initial Frequency Responses Completed")

        if rotary:
            break

    limit = 'software off'
    electrical_limit_value = get_limit_dec(controller, axis, limit)
    controller.runtime.parameters.axes[axis].protection.faultmask.value = electrical_limit_value

    return fr_files

def multi_axis_frequency_response(axes, controller, current_percent, all_axes=None):
    """Run frequency response tests at center and 4 corners of XY workspace"""
    print(f"🔧 Starting multi-axis testing for axes {axes}")
    
    rotary = False
    params = controller.configuration.parameters.get_configuration()
    fr_files = []
    units = []
    # Get travel limits for both axes
    axis_limits = {}
    axis_distances = {}
    limit = 'software off'
    
    reverse_motion = {}
    for axis in axes:
        rev_motion = controller.runtime.parameters.axes[axis].motion.reversemotiondirection.value
        if rev_motion == 1:
            reverse_motion[axis] = True
        else:
            reverse_motion[axis] = False
            
        pos_limit = controller.runtime.parameters.axes[axis].protection.softwarelimithigh.value
        neg_limit = controller.runtime.parameters.axes[axis].protection.softwarelimitlow.value
        units_value = controller.runtime.parameters.axes[axis].units.unitsname.value
        speed = params.axes[axis].motion.maxjogspeed.value
        units.append(units_value)
        axis_limits[axis] = (neg_limit, pos_limit)

        motor_pole_pitch = params.axes[axis].motor.motorpolepitch.value
        distance = calculate_unit_distance(motor_pole_pitch, units_value)
        travel = abs(axis_limits[axis][1] - axis_limits[axis][0])
        
        if distance >= travel:
            distance = travel/2.25
            
        axis_distances[axis] = distance
    
        electrical_limit_value = get_limit_dec(controller, axis, limit)
        controller.runtime.parameters.axes[axis].protection.faultmask.value = electrical_limit_value

    if units[0] == 'deg' and units[1] == 'deg':
        rotary = True
        
    # Get first two axes for position calculations
    x_axis = axes[0]
    y_axis = axes[1]

    if rotary and axis_limits[x_axis][0] == 0 and axis_limits[y_axis][0] == 0:
        x_center = 0
        y_center = 0
    else:
        # Calculate center positions for each axis
        x_center = ((axis_limits[x_axis][0] + axis_limits[x_axis][1]) / 2) * -1 if reverse_motion[x_axis] else (axis_limits[x_axis][0] + axis_limits[x_axis][1]) / 2
        y_center = ((axis_limits[y_axis][0] + axis_limits[y_axis][1]) / 2) * -1 if reverse_motion[y_axis] else (axis_limits[y_axis][0] + axis_limits[y_axis][1]) / 2

        
    # Define test positions with calculated centers
    test_positions = [
        {'name': 'Center', 
         'coords': (x_center, y_center),
         'directions': (1, 1)},
        {'name': 'NE Corner', 
         'coords': ((axis_limits[x_axis][1] - calculate_coordinate_offset(axis_limits, x_axis)) - axis_distances[x_axis], (axis_limits[y_axis][1] - calculate_coordinate_offset(axis_limits, y_axis)) - axis_distances[y_axis]),
         'directions': (-1, -1)},
        {'name': 'NW Corner', 
         'coords': ((axis_limits[x_axis][0] + calculate_coordinate_offset(axis_limits, x_axis)) + axis_distances[x_axis], (axis_limits[y_axis][1] - calculate_coordinate_offset(axis_limits, y_axis)) - axis_distances[y_axis]),
         'directions': (1, -1)},
        {'name': 'SE Corner', 
         'coords': ((axis_limits[x_axis][1] - calculate_coordinate_offset(axis_limits, x_axis)) - axis_distances[x_axis], (axis_limits[y_axis][0] + calculate_coordinate_offset(axis_limits, y_axis)) + axis_distances[y_axis]),
         'directions': (-1, 1)},
        {'name': 'SW Corner', 
         'coords': ((axis_limits[x_axis][0] + calculate_coordinate_offset(axis_limits, x_axis)) + axis_distances[x_axis], (axis_limits[y_axis][0] + calculate_coordinate_offset(axis_limits, y_axis)) + axis_distances[y_axis]),
         'directions': (1, 1)}
    ]

    # Home axes first
    print("\n🏠 Homing axes...")

    controller.runtime.commands.motion.enable(all_axes)
    
    # Check for faults after enable
    axis_faults = check_for_faults(controller, all_axes)
    if axis_faults:
        fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
        decoded_faults = fault_init.get_fault()
        print(f"❌ Faults detected after enable: {decoded_faults}")
    
    controller.runtime.commands.motion.home(axes)
    
    # Check for faults after homing
    axis_faults = check_for_faults(controller, all_axes if all_axes else axes)
    if axis_faults:
        fault_init = decode_faults(axis_faults, all_axes if all_axes else axes, controller, fault_log = None)
        decoded_faults = fault_init.get_fault()
        print(f"❌ Faults detected after homing: {decoded_faults}")
    
    controller.runtime.commands.motion.waitformotiondone(axes)
    time.sleep(2)

    for position in test_positions:
        x, y = position['coords']
        print(f"\n📍 Testing {position['name']} (X{x:.2f}, Y{y:.2f})")
        
        # Move to position
        controller.runtime.commands.motion.moveabsolute(axes, [x, y], [speed, speed])
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

            fr_files.append(fr_filepath)
            
            if rotary:
                break
        print("✅ Initial Frequency Responses Completed")

    limit = 'software on'
    for axis in axes:
        electrical_limit_value = get_limit_dec(controller, axis, limit)
        controller.runtime.parameters.axes[axis].protection.faultmask.value = electrical_limit_value

    return fr_files

def generate_plots_from_results(log_files=None, original_frd=None, position=None, axis=None):
    """
    Generate interactive plots from all FR and log files in the output directory
    
    Args:
        output_dir: Directory containing FR and log files (default: current directory)
    """
    global so_dir

    plotter = EasyTunePlotter(so_dir)
    if log_files:
        # Initialize plotter and create analysis
        plotter.create_combined_analysis(log_files)
    if original_frd:
        plotter.create_bode_plot(original_frd, position=position, axis=axis)
    print("✅ Interactive plots generated successfully!")

# Recalculate time with proper motion profile
def calculate_trapezoidal_time(distance, max_velocity, acceleration):
    """Calculate time for trapezoidal motion profile"""
    min_distance = (max_velocity ** 2) / acceleration
    
    if distance < min_distance:
        # Triangular profile - never reaches max speed
        # Peak velocity = sqrt(accel * distance)
        peak_velocity = math.sqrt(acceleration * distance)
        time = 2 * peak_velocity / acceleration
        print(f"📊 Triangular profile: Peak speed {peak_velocity:.1f}, Time {time:.1f}s")
    else:
        # Trapezoidal profile - reaches max speed
        accel_time = max_velocity / acceleration
        const_velocity_distance = distance - min_distance
        const_velocity_time = const_velocity_distance / max_velocity
        time = 2 * accel_time + const_velocity_time
        print(f"📊 Trapezoidal profile: Accel {accel_time:.1f}s + Const {const_velocity_time:.1f}s + Decel {accel_time:.1f}s = {time:.1f}s")
    
    return time

def move_profile(controller: a1.Controller, axes: list, velocity: float, n: int, filename: str, so_dir: str, position: list):
    """
    Move the stage to the specified coordinates and collect data
    """
    with open(r'assets\programs\Move.txt') as f:
                
        program_contents = f.read()
        
    # Populate the program variables
    program_variables = f'''Program variables
    var $axes[] as axis = [{",".join(axes)}]
    var $speed[] as real = {velocity}
    var $distance[] as real = {position}
    var $numsamples as integer = {n}
    var $sampletime as real = {1}
    var $index as integer
    var $filename as string = "{filename}"'''
    
    # Insert the variables into the program
    program_contents = program_contents.replace('Program variables', program_variables)
    
    # Write the program to a controller AeroScript file
    controller.files.write_text('Move.ascript', program_contents)
    
    # Execute the program
    controller.runtime.tasks[1].program.run('Move.ascript')

    # Wait for the program to finish
    while controller.runtime.tasks[1].status.task_state != a1.TaskState.ProgramComplete.value:
        time.sleep(0.2)
        
    # Copy the output data file to the local output folder
    with open(os.path.join(so_dir, 'Performance Analysis', filename), 'wb') as f:
        f.write(controller.files.read_bytes(filename))
        
    # Create a result object from the file
    result = DatFile.create_from_file(os.path.join(so_dir, 'Performance Analysis', filename))

    return result

def validate_stage_performance(controller: a1.Controller, axes_dict: dict, test_type: str, axis_limits: dict, all_axes=None):
    """
    Validate stage performance by collecting data on the specified axes
    """
    rotary = False
    units = []
    params = controller.configuration.parameters.get_configuration()
    
    results = {}
    if test_type == 'multi':
        axis_keys = list(axes_dict.keys())
        reverse_motion = {}
        for axis in axis_keys:
            units_value = controller.runtime.parameters.axes[axis].units.unitsname.value
            units.append(units_value)
            ramp_value = axes_dict[axis][1]  # Get the max_accel for this specific axis
            ramp_value_decel = ramp_value
            controller.runtime.commands.motion_setup.setupaxisrampvalue(axis, a1.RampMode.Rate, ramp_value, a1.RampMode.Rate, ramp_value_decel)
            rev_motion = controller.runtime.parameters.axes[axis].motion.reversemotiondirection.value
            if rev_motion == 1:
                reverse_motion[axis] = True
            else:
                reverse_motion[axis] = False
                
        if units[0] == 'deg' and units[1] == 'deg':
            rotary = True
        
        if rotary and axis_limits[axis_keys[0]][0] == 0 and axis_limits[axis_keys[1]][0] == 0:
            # Calculate minimum distance needed to reach max speed for each axis
            min_distances = []
            for i, axis in enumerate(axis_keys):
                max_velocity = axes_dict[axis][0]
                acceleration = axes_dict[axis][1]
                
                # Minimum distance for trapezoidal profile: v_max² / accel
                min_distance = (max_velocity ** 2) / acceleration
                min_distances.append(min_distance)
                
                print(f"📐 Axis {axis}: Max speed {max_velocity}°/s, Accel {acceleration}°/s²")
                print(f"📐 Minimum distance to reach max speed: {min_distance:.1f}°")
            
            # Use the larger of: minimum required distance or current distance (360°)
            distance_1 = max(360, min_distances[0])
            distance_2 = max(360, min_distances[1])
            
            print(f"📐 Adjusted distances: {distance_1:.1f}°, {distance_2:.1f}°")
            
        else:
            distance_1 = axis_limits[axis_keys[0]][1] - axis_limits[axis_keys[0]][0]
            distance_2 = axis_limits[axis_keys[1]][1] - axis_limits[axis_keys[1]][0]
            
            # Also check linear axes for motion profile issues
            for i, axis in enumerate(axis_keys):
                max_velocity = axes_dict[axis][0]
                acceleration = axes_dict[axis][1]
                current_distance = distance_1 if i == 0 else distance_2
                
                min_distance = (max_velocity ** 2) / acceleration
                if current_distance < min_distance:
                    print(f"⚠️ Axis {axis}: Travel ({current_distance:.3f}) too short to reach max speed")
                    print(f"⚠️ Minimum needed: {min_distance:.3f}, will not reach {max_velocity} speed")

        time_axis_1 = calculate_trapezoidal_time(distance_1, axes_dict[axis_keys[0]][0], axes_dict[axis_keys[0]][1])
        time_axis_2 = calculate_trapezoidal_time(distance_2, axes_dict[axis_keys[1]][0], axes_dict[axis_keys[1]][1])

        distance = [distance_1, distance_2]
        test_time = max(time_axis_1, time_axis_2) + 2
        sample_rate = 1000
        n = int(sample_rate * test_time)
        freq = a1.DataCollectionFrequency.Frequency1kHz

        if rotary and axis_limits[axis_keys[0]][0] == 0 and axis_limits[axis_keys[1]][0] == 0:
            x_center = 0
            y_center = 0
        else:
            # Calculate center positions for each axis
            x_center = ((axis_limits[axis_keys[0]][0] + axis_limits[axis_keys[0]][1]) / 2) * -1 if reverse_motion[axis_keys[0]] else (axis_limits[axis_keys[0]][0] + axis_limits[axis_keys[0]][1]) / 2
            y_center = ((axis_limits[axis_keys[1]][0] + axis_limits[axis_keys[1]][1]) / 2) * -1 if reverse_motion[axis_keys[1]] else (axis_limits[axis_keys[1]][0] + axis_limits[axis_keys[1]][1]) / 2

        # Home axes first
        print("\n🏠 Homing axes...")
        controller.runtime.commands.motion.enable(all_axes)
        controller.runtime.commands.motion.home(axis_keys)
        controller.runtime.commands.motion.waitformotiondone(axis_keys)
        time.sleep(2)
        
        # Extract coordinates for the movements
        sw_coords = (axis_limits[axis_keys[0]][0] + calculate_coordinate_offset(axis_limits, axis_keys[0]), axis_limits[axis_keys[1]][0] + calculate_coordinate_offset(axis_limits, axis_keys[1]))
        ne_coords = (axis_limits[axis_keys[0]][1] - calculate_coordinate_offset(axis_limits, axis_keys[0]), axis_limits[axis_keys[1]][1] - calculate_coordinate_offset(axis_limits, axis_keys[1]))
        se_coords = (axis_limits[axis_keys[0]][1] - calculate_coordinate_offset(axis_limits, axis_keys[0]), axis_limits[axis_keys[1]][0] + calculate_coordinate_offset(axis_limits, axis_keys[1]))
        nw_coords = (axis_limits[axis_keys[0]][0] + calculate_coordinate_offset(axis_limits, axis_keys[0]), axis_limits[axis_keys[1]][1] - calculate_coordinate_offset(axis_limits, axis_keys[1]))
        center_coords = (x_center, y_center)
        velocity = [axes_dict[axis][0] for axis in axis_keys[:2]]

        if rotary and axis_limits[axis_keys[0]][0] == 0 and axis_limits[axis_keys[1]][0] == 0:
            # Execute movement sequence
            print("\n🔄 Executing movement sequence...")

            move_name = 'Positive'
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"stage_performance_{test_type}_{move_name}_{timestamp}.dat"

            # Call Studio to run move profile and save readable .dat file
            move_results = move_profile(controller, axis_keys, velocity, n, filename, so_dir, distance)
            
            axis_faults = check_for_faults(controller, all_axes)
            if axis_faults:
                fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
                decoded_faults = fault_init.get_fault()

            results['pos'] = move_results

            move_name = 'Negative'
            filename = f"stage_performance_{test_type}_{move_name}.dat"

            move_results = move_profile(controller, axis_keys, velocity, n, filename, so_dir, [0,0])

            axis_faults = check_for_faults(controller, all_axes)
            if axis_faults:
                fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
                decoded_faults = fault_init.get_fault()

            results['neg'] = move_results

        if rotary:
            # Movement 1: SW → NE → SW
            print("📍 Move 1: SW → NE → SW")
            controller.runtime.commands.motion.moveabsolute(axis_keys, list(sw_coords), velocity)
            controller.runtime.commands.motion.waitformotiondone(axis_keys)
            time.sleep(0.5)

            move_name = 'Positive'
            filename = f"stage_performance_{test_type}_{move_name}.dat"

            move_results = move_profile(controller, axis_keys, velocity, n, filename, so_dir, list(ne_coords))

            axis_faults = check_for_faults(controller, all_axes)
            if axis_faults:
                fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
                decoded_faults = fault_init.get_fault()

            results['pos'] = move_results

            move_name = 'Negative'
            filename = f"stage_performance_{test_type}_{move_name}.dat"

            move_results = move_profile(controller, axis_keys, velocity, n, filename, so_dir, list(sw_coords))

            axis_faults = check_for_faults(controller, all_axes)
            if axis_faults:
                fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
                decoded_faults = fault_init.get_fault()

            results['neg'] = move_results

        # Movement 1: SW → NE → SW
        print("📍 Move 1: SW → NE → SW")
        controller.runtime.commands.motion.moveabsolute(axis_keys, list(sw_coords), velocity)
        controller.runtime.commands.motion.waitformotiondone(axis_keys)
        time.sleep(0.5)

        move_name = 'SW_NE'
        filename = f"stage_performance_{test_type}_{move_name}.dat"
        
        move_results = move_profile(controller, axis_keys, velocity, n, filename, so_dir, list(ne_coords))

        axis_faults = check_for_faults(controller, all_axes)
        if axis_faults:
            fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
            decoded_faults = fault_init.get_fault()

        results['SW_NE'] = move_results

        move_name = 'NE_SW'
        filename = f"stage_performance_{test_type}_{move_name}.dat"
        
        move_results = move_profile(controller, axis_keys, velocity, n, filename, so_dir, list(sw_coords))

        axis_faults = check_for_faults(controller, all_axes)
        if axis_faults:
            fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
            decoded_faults = fault_init.get_fault()

        results['NE_SW'] = move_results

        # Movement 2: SE → NW → SE
        print("📍 Move 2: SE → NW → SE")
        controller.runtime.commands.motion.moveabsolute(axis_keys, list(se_coords), velocity)
        controller.runtime.commands.motion.waitformotiondone(axis_keys)
        time.sleep(0.5)

        move_name = 'SE_NW'
        filename = f"stage_performance_{test_type}_{move_name}.dat"
        
        move_results = move_profile(controller, axis_keys, velocity, n, filename, so_dir, list(nw_coords))

        axis_faults = check_for_faults(controller, all_axes)
        if axis_faults:
            fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
            decoded_faults = fault_init.get_fault()

        results['SE_NW'] = move_results

        move_name = 'NW_SE'
        filename = f"stage_performance_{test_type}_{move_name}.dat"
        
        move_results = move_profile(controller, axis_keys, velocity, n, filename, so_dir, list(se_coords))

        axis_faults = check_for_faults(controller, all_axes)
        if axis_faults:
            fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
            decoded_faults = fault_init.get_fault()

        results['NW_SE'] = move_results

        # Return to center
        print("📍 Returning to center")
        controller.runtime.commands.motion.moveabsolute(axis_keys, list(center_coords), velocity)
        controller.runtime.commands.motion.waitformotiondone(axis_keys)
        time.sleep(1)

        axis_faults = check_for_faults(controller, all_axes)
        if axis_faults:
            fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
            decoded_faults = fault_init.get_fault()

        print("✅ Diagonal movement sequence completed")

    if test_type == 'single':
        axis_keys = list(axes_dict.keys())
        axis = axis_keys[0]   # First axis name
        rev_motion = controller.runtime.parameters.axes[axis].motion.reversemotiondirection.value
        if rev_motion == 1:
            reverse_motion = True
        else:
            reverse_motion = False
            
        units_value = controller.runtime.parameters.axes[axis].units.unitsname.value
        if units_value == 'deg':
            rotary = True
            
        ramp_value = axes_dict[axis][1]
        ramp_value_decel = ramp_value
        controller.runtime.commands.motion_setup.setupaxisrampvalue(axis, a1.RampMode.Rate, ramp_value, a1.RampMode.Rate, ramp_value_decel)
        
        if rotary and axis_limits[axis][0] == 0 and axis_limits[axis][1] == 0:
            # Calculate minimum distance needed to reach max speed
            max_velocity = axes_dict[axis_keys[0]][0]
            acceleration = axes_dict[axis_keys[0]][1]
            
            # Minimum distance for trapezoidal profile: v_max² / accel
            min_distance = (max_velocity ** 2) / acceleration
            
            print(f"📐 Axis {axis}: Max speed {max_velocity}°/s, Accel {acceleration}°/s²")
            print(f"📐 Minimum distance to reach max speed: {min_distance:.1f}°")
            
            # Use the larger of: minimum required distance or current distance (360°)
            distance = max(360, min_distance)
            
            print(f"📐 Adjusted distance: {distance:.1f}°")
            distance = [distance]
            
        else:    
            distance = axis_limits[axis][1] - axis_limits[axis][0]
            
            # Check linear axes for motion profile issues
            max_velocity = axes_dict[axis_keys[0]][0]
            acceleration = axes_dict[axis_keys[0]][1]
            
            min_distance = (max_velocity ** 2) / acceleration
            if distance < min_distance:
                print(f"⚠️ Axis {axis}: Travel ({distance:.3f}) too short to reach max speed")
                print(f"⚠️ Minimum needed: {min_distance:.3f}, will not reach {max_velocity} speed")
            distance = [distance]
            
        time_axis = calculate_trapezoidal_time(distance[0], axes_dict[axis_keys[0]][0], axes_dict[axis_keys[0]][1])
        print(f"📊 Time axis: {time_axis:.1f}s")
        test_time = time_axis + 2

        sample_rate = 1000
        n = int(sample_rate * test_time)
        freq = a1.DataCollectionFrequency.Frequency1kHz

        if rotary and axis_limits[axis][0] == 0 and axis_limits[axis][1] == 0:
            center = 0
        else:
            # Calculate center positions for each axis
            if reverse_motion:
                center = ((axis_limits[axis][0] + axis_limits[axis][1]) / 2) * -1
            else:
                center = (axis_limits[axis][0] + axis_limits[axis][1]) / 2

        # Home axes first
        print("\n🏠 Homing axes...")
        controller.runtime.commands.motion.enable(all_axes)
        
        # Check for faults after enable
        axis_faults = check_for_faults(controller, all_axes)
        if axis_faults:
            fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
            decoded_faults = fault_init.get_fault()
            print(f"❌ Faults detected after enable: {decoded_faults}")
        
        controller.runtime.commands.motion.home(axis)
        
        # Check for faults after homing
        axis_faults = check_for_faults(controller, all_axes if all_axes else [axis])
        if axis_faults:
            fault_init = decode_faults(axis_faults, all_axes if all_axes else [axis], controller, fault_log = None)
            decoded_faults = fault_init.get_fault()
            print(f"❌ Faults detected after homing: {decoded_faults}")
        
        controller.runtime.commands.motion.waitformotiondone([axis])
        time.sleep(2)
        
        axis_faults = check_for_faults(controller, all_axes)
        if axis_faults:
            fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
            decoded_faults = fault_init.get_fault()

        # Execute diagonal movement sequence
        print("\n🔄 Executing diagonal movement sequence...")

        # Extract coordinates for the movements
        neg_end = axis_limits[axis][0] + calculate_coordinate_offset(axis_limits, axis)
        pos_end = axis_limits[axis][1] - calculate_coordinate_offset(axis_limits, axis)
        
        center_coords = center
        velocity = [axes_dict[axis][0]]

        if rotary and axis_limits[axis][0] == 0 and axis_limits[axis][1] == 0:
            
            move_name = 'Positive'
            filename = f"stage_performance_{test_type}_{move_name}.dat"
            
            move_results = move_profile(controller, axis_keys, velocity, n, filename, so_dir, distance)

            axis_faults = check_for_faults(controller, all_axes)
            if axis_faults:
                fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
                decoded_faults = fault_init.get_fault()

            results['pos'] = move_results

            move_name = 'Negative'
            filename = f"stage_performance_{test_type}_{move_name}.dat"
            
            move_results = move_profile(controller, axis_keys, velocity, n, filename, so_dir, [0])

            axis_faults = check_for_faults(controller, all_axes)
            if axis_faults:
                fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
                decoded_faults = fault_init.get_fault()

            results['neg'] = move_results
        else:
            # Calculate center positions for each axis
            if reverse_motion:
                center = ((axis_limits[axis][0] + axis_limits[axis][1]) / 2) * -1
            else:
                center = (axis_limits[axis][0] + axis_limits[axis][1]) / 2

            # Movement 1: Negative to Positive
            print("📍 Move 1: Negative to Positive")
            print(f" Axes = {axis}. Position = {neg_end}. Velocity = {velocity}")
            controller.runtime.commands.motion.moveabsolute(axis, [neg_end], velocity)
            controller.runtime.commands.motion.waitformotiondone(axis)
            time.sleep(0.5)

            move_name = 'Positive'
            filename = f"stage_performance_{test_type}_{move_name}.dat"
            
            move_results = move_profile(controller, axis_keys, velocity, n, filename, so_dir, [pos_end])
            axis_faults = check_for_faults(controller, all_axes)
            if axis_faults:
                fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
                decoded_faults = fault_init.get_fault()

            results['pos'] = move_results

            move_name = 'Negative'
            filename = f"stage_performance_{test_type}_{move_name}.dat"
            
            move_results = move_profile(controller, axis_keys, velocity, n, filename, so_dir, [neg_end])

            axis_faults = check_for_faults(controller, all_axes)
            if axis_faults:
                fault_init = decode_faults(axis_faults, all_axes, controller, fault_log = None)
                decoded_faults = fault_init.get_fault()

            results['neg'] = move_results

            # Return to center
            print("📍 Returning to center")
            controller.runtime.commands.motion.moveabsolute(axis, [center], velocity)
            controller.runtime.commands.motion.waitformotiondone(axis)
            time.sleep(1)

        print("✅ Movement sequence completed")

    return results

def calculate_performance_stats(time_array, signal_data_dict, axis_names):
    """Calculate performance statistics from signal data"""
    stats = {}
    
    for axis in axis_names:
        stats[axis] = {}
        
        # Get signal data arrays using new signal names
        pos_error = np.array(signal_data_dict['PosErr'][axis])
        velocity = np.array(signal_data_dict['VelFbk'][axis])
        accel = np.array(signal_data_dict['AccFbk'][axis])
        current = np.array(signal_data_dict['CurFbk'][axis])
        
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
    
def calculate_settle_time(time_array, velocity_command, position_error, controller, axis):
    """
    Calculate settle time based on InPositionDistance and InPositionTime parameters
    
    Args:
        time_array: Time data in seconds
        velocity_command: VelocityCommand signal data
        position_error: PositionError signal data
        controller: Controller object to get parameters
        axis: Axis name
        
    Returns:
        settle_time: Time to settle in seconds, or None if not settled
    """
    try:
        # Get in-position parameters from controller
        in_position_distance = controller.runtime.parameters.axes[axis].motion.inpositiondistance.value
        in_position_time = controller.runtime.parameters.axes[axis].motion.inpositiontime.value  # in milliseconds
        in_position_time_sec = in_position_time / 1000.0  # Convert to seconds
        
        print(f"📐 Axis {axis}: InPositionDistance = {in_position_distance}, InPositionTime = {in_position_time}ms")
        
        # Convert to numpy arrays for easier processing
        time_array = np.array(time_array)
        velocity_command = np.array(velocity_command)
        position_error = np.array(position_error)
        
        # Find the last occurrence of non-zero velocity command (end of move)
        non_zero_velocity_indices = np.where(np.abs(velocity_command) > 1e-6)[0]  # Small threshold for floating point
        
        if len(non_zero_velocity_indices) == 0:
            print(f"⚠️ No non-zero velocity found for axis {axis}")
            return None
            
        end_of_move_index = non_zero_velocity_indices[-1]
        end_of_move_time = time_array[end_of_move_index]
        
        print(f"📍 End of move detected at t={end_of_move_time:.3f}s (index {end_of_move_index})")
        
        # Shift time array so end of move is t=0
        shifted_time = time_array - end_of_move_time
        
        # Only consider data after end of move
        post_move_mask = shifted_time >= 0
        post_move_time = shifted_time[post_move_mask]
        post_move_position_error = position_error[post_move_mask]
        # After creating post_move_position_error:
        print(f"🔍 Post-move data points: {len(post_move_position_error)}")
        print(f"🔍 Max post-move position error: {np.max(np.abs(post_move_position_error)):.8f}")
        print(f"🔍 InPositionDistance: {in_position_distance:.8f}")

        if len(post_move_time) < 2:
            print(f"⚠️ Insufficient data after end of move for axis {axis}")
            return None
        
        # Find when position error BREAKS tolerance (last occurrence approach)
        out_of_position_mask = np.abs(post_move_position_error) > in_position_distance
        
        print(f"🔍 First 5 position errors: {post_move_position_error[:5]}")
        print(f"🔍 First 5 out-of-position status: {out_of_position_mask[:5]}")

        # Calculate sample rate for sustained period analysis
        sample_rate = 1.0 / (post_move_time[1] - post_move_time[0])  # Assuming uniform sampling
        
        if in_position_time_sec == 0:
            # Simple case: Find LAST time position error exceeds threshold
            last_bad_indices = np.where(out_of_position_mask)[0]
            if len(last_bad_indices) > 0:
                settle_time = post_move_time[last_bad_indices[-1]]  # LAST occurrence
                print(f"✅ Axis {axis}: Last out of position at t={settle_time:.3f}s after end of move")
            else:
                settle_time = None
                print(f"❌ Axis {axis}: Never exceeds InPositionDistance tolerance")
            return settle_time
        else:
            # Sustained case: Find LAST sustained period where position stays OUTSIDE tolerance
            min_samples_out = int(in_position_time_sec * sample_rate)
            
            print(f"🔍 Looking for last sustained out-of-position period of {min_samples_out} samples ({in_position_time_sec:.3f}s)")
            
            # Check each position from the end to find the last sustained bad period
            for i in range(len(out_of_position_mask) - min_samples_out, -1, -1):
                if np.all(out_of_position_mask[i:i + min_samples_out]):
                    # Found last sustained bad period
                    settle_time = post_move_time[i + min_samples_out - 1]  # End of last sustained bad period
                    print(f"✅ Axis {axis}: Last sustained out-of-position at t={settle_time:.3f}s after end of move")
                    return settle_time
            
            # No sustained bad period found
            settle_time = None
            print(f"❌ Axis {axis}: Never has sustained out-of-position period")
            return settle_time
        
    except Exception as e:
        print(f"❌ Error calculating settle time for axis {axis}: {e}")
        return None

def export_stage_performance_dat(results, test_type, axes_dict, move_name, axis_names):
    """
    Export stage performance data to .dat file format (Aerotech data collection format)
    
    Args:
        results: Dictionary returned from validate_stage_performance  
        test_type: 'single' or 'multi' to determine result structure
        axes_dict: Dictionary of axis parameters
        move_name: Name of the move (e.g., 'SW_NE', 'pos', etc.)
        axis_names: List of axis names
    """
    try:
        data = results[move_name]
        
        # Create time array using the same method as in plot function
        SAMPLE_PERIOD_S = 0.001
        first_axis = axis_names[0]
        pos_fbk_key = f'PosFbk{first_axis}'
        if pos_fbk_key in data.all_data:
            num_samples = len(data.all_data[pos_fbk_key])
            time_array = np.arange(0, num_samples * SAMPLE_PERIOD_S, SAMPLE_PERIOD_S)
        else:
            print(f"⚠️ Could not find {pos_fbk_key} in data for {move_name}")
            return None
        
        # Define the signals to extract (in order for .dat file) using new format
        dat_signals = [
            ('PosCmd', 'PosCmd'),
            ('PosFbk', 'PosFbk'), 
            ('PosErr', 'PosErr'),
            ('VelCmd', 'VelCmd'),
            ('VelFbk', 'VelFbk'),
            ('AccCmd', 'AccCmd'),
            ('AccFbk', 'AccFbk'),
            ('CurCmd', 'CurCmd'),
            ('CurFbk', 'CurFbk')
        ]
        
        # Extract data for each axis and signal
        signal_data = {}
        for signal_type, signal_name in dat_signals:
            signal_data[signal_name] = {}
            for axis in axis_names:
                try:
                    signal_key = f'{signal_type}{axis}'
                    if signal_key in data.all_data:
                        data_points = data.all_data[signal_key][:]
                        signal_data[signal_name][axis] = np.array(data_points)
                    else:
                        print(f"⚠️ Could not find {signal_key} in data for {move_name}")
                        # Fill with zeros if signal not available
                        signal_data[signal_name][axis] = np.zeros(len(time_array))
                except Exception as e:
                    print(f"⚠️ Could not extract {signal_name} for axis {axis}: {e}")
                    # Fill with zeros if signal not available
                    signal_data[signal_name][axis] = np.zeros(len(time_array))
        
        # Calculate sample rate (assuming uniform sampling)
        if len(time_array) > 1:
            sample_rate = int(1.0 / (time_array[1] - time_array[0]))
        else:
            sample_rate = 1000  # Default fallback
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Create .dat filename
        dat_filename = os.path.join(so_dir, f"stage_performance_{test_type}_{move_name}_{timestamp}.dat")
        
        # Write .dat file
        with open(dat_filename, 'w') as f:
            # Header line 1: Samples, Items, SampleRate
            num_samples = len(time_array)
            num_items = len(dat_signals) * len(axis_names)
            f.write(f"; Samples {num_samples}, Items {num_items}, SampleRate {sample_rate}\n")
            
            # Header line 2: Item numbers
            item_nums = []
            for i, (_, signal_name) in enumerate(dat_signals):
                for j, axis in enumerate(axis_names):
                    item_nums.append(str(i * len(axis_names) + j))
            f.write(f"; Item#: {' '.join(item_nums)}\n")
            
            # Header line 3: Index (all zeros typically)
            indices = ['0'] * num_items
            f.write(f"; Index: {' '.join(indices)}\n")
            
            # Header line 4: Signal names with axis identifiers
            signal_headers = []
            for signal_type, signal_name in dat_signals:
                for i, axis in enumerate(axis_names):
                    signal_headers.append(f"{signal_name}#{i:02d}[{i}]")
            f.write(f"; {' '.join(signal_headers)}\n")
            
            # Data rows
            for sample_idx in range(num_samples):
                row_data = []
                for signal_type, signal_name in dat_signals:
                    for axis in axis_names:
                        value = signal_data[signal_name][axis][sample_idx]
                        row_data.append(f"{value:.10f}")
                f.write(' '.join(row_data) + '\n')
        
        print(f"✅ Exported .dat file: {dat_filename}")
        return dat_filename
        
    except Exception as e:
        print(f"❌ Error exporting .dat file for {move_name}: {e}")
        return None

def plot_stage_performance_results(results, test_type, axes_dict, controller):
    """
    Create Plotly plots for stage performance data with 5 stacked signal plots
    
    Args:
        results: Dictionary returned from validate_stage_performance
        test_type: 'single' or 'multi' to determine result structure
        axes_dict: Dictionary of axis parameters
        controller: Controller object for getting parameters
    """
    
    if not results:
        print("❌ No results data to plot")
        return
    
    # Get axis names from the first result (assuming we know the axes from the test)
    # For single axis test, there's only one axis
    # For multi axis test, there are typically two axes
    axis_names = list(axes_dict.keys())
    axis_units = {}
    
    # Query actual units from controller for each axis
    for axis in axis_names:
        try:
            units = controller.runtime.parameters.axes[axis].units.unitsname.value
            axis_units[axis] = units
            print(f"📏 Axis {axis} units: {units}")
        except Exception as e:
            print(f"⚠️ Could not get units for axis {axis}: {e}")
            axis_units[axis] = "units"  # Fallback
    
    # Use the first axis units as primary (assuming homogeneous system)
    primary_units = axis_units[axis_names[0]]
    
    # Define the signals with their new column names and units
    signals = [
        ('PosErr', 'Position Error Analysis', f'[{primary_units}]'),
        ('VelFbk', 'Velocity Feedback Analysis', f'[{primary_units}/s]'),
        ('AccFbk', 'Acceleration Feedback Analysis', f'[{primary_units}/s²]'),
        ('CurCmd', 'Current Command Analysis', '[A]'),
        ('CurFbk', 'Current Feedback Analysis', '[A]')
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
        SAMPLE_PERIOD_S = 0.001
        try:
            # Get the number of samples from any available data signal
            # Use the first axis to get sample count
            first_axis = axis_names[0]
            pos_fbk_key = f'PosFbk{first_axis}'
            if pos_fbk_key in data.all_data:
                num_samples = len(data.all_data[pos_fbk_key])
                # Create the time array using np.arange(start, stop, step)
                time_array = np.arange(0, num_samples * SAMPLE_PERIOD_S, SAMPLE_PERIOD_S)
                time_array = time_array.tolist()
            else:
                print(f"⚠️ Could not find {pos_fbk_key} in data for {move_name}")
                continue

        except Exception as e:
            print(f"⚠️  Could not generate time array for {move_name}: {e}")
            time_array = []
            continue
        
        # Create subplots - 5 rows per axis, 1 column (stacked)
        total_rows = 5 * len(axis_names)
        fig = make_subplots(
            rows=total_rows, cols=1,
            shared_xaxes=True,
            subplot_titles=[f"{axis} {signal[1]}" for axis in axis_names for signal in signals],
            vertical_spacing=0.02
        )
        
        # Initialize signal data storage for stats
        signal_data_dict = {}
        for signal_type, plot_title, y_axis_label in signals:
            signal_data_dict[signal_type] = {}
        
        # Also extract VelocityCommand for settle time calculation (not plotted)
        signal_data_dict['VelCmd'] = {}

        # Plot each signal for each axis - group by axis
        for axis_idx, axis in enumerate(axis_names):
            for signal_idx, (signal_type, plot_title, y_axis_label) in enumerate(signals):
                try:
                    # Get data for this axis and signal using the new format
                    signal_key = f'{signal_type}{axis}'
                    if signal_key in data.all_data:
                        signal_array = data.all_data[signal_key][:]
                        
                        # Store signal data for stats calculation
                        signal_data_dict[signal_type][axis] = signal_array
                        
                        # Calculate row number: (axis_index * 5) + signal_index + 1
                        row_num = (axis_idx * 5) + signal_idx + 1
                        
                        # Add trace to the appropriate subplot
                        fig.add_trace(
                            go.Scatter(
                                x=time_array, 
                                y=signal_array, 
                                name=f'{axis} {signal_type}',
                                line=dict(color=axis_colors[axis_idx % len(axis_colors)]),
                                showlegend=(row_num == 1)
                            ),
                            row=row_num, col=1
                        )
                    else:
                        print(f"⚠️ Could not find {signal_key} in data for {move_name}")
                        signal_data_dict[signal_type][axis] = []
                    
                except Exception as e:
                    print(f"⚠️  Could not extract {signal_type} data for axis {axis}: {e}")
                    signal_data_dict[signal_type][axis] = []
                    continue
        
        # Extract VelocityCommand for settle time calculation
        for axis in axis_names:
            try:
                vel_cmd_key = f'VelCmd{axis}'
                if vel_cmd_key in data.all_data:
                    velocity_command_data = data.all_data[vel_cmd_key][:]
                    signal_data_dict['VelCmd'][axis] = velocity_command_data
                else:
                    print(f"⚠️ Could not find {vel_cmd_key} in data for {move_name}")
                    signal_data_dict['VelCmd'][axis] = []
            except Exception as e:
                print(f"⚠️  Could not extract VelCmd data for axis {axis}: {e}")
                signal_data_dict['VelCmd'][axis] = []
        
        # Calculate performance statistics
        try:
            stats = calculate_performance_stats(time_array, signal_data_dict, axis_names)
            
            # Calculate settle times for each axis
            settle_times = {}
            for axis in axis_names:
                if ('VelCmd' in signal_data_dict and axis in signal_data_dict['VelCmd'] and
                    'PosErr' in signal_data_dict and axis in signal_data_dict['PosErr']):
                    settle_time = calculate_settle_time(
                        time_array,
                        signal_data_dict['VelCmd'][axis],
                        signal_data_dict['PosErr'][axis],
                        controller,
                        axis
                    )
                    settle_times[axis] = settle_time
                else:
                    settle_times[axis] = None
            
            # Create stats table text
            stats_text = f"<b>Performance Statistics ({move_name.upper()})</b><br><br>"
            for axis in axis_names:
                stats_text += f"<b>{axis} Axis:</b><br>"
                stats_text += f"• Peak Pos Error: {stats[axis]['peak_pos_error']:.7f} {primary_units}<br>"
                stats_text += f"• Current @ Const Vel: {stats[axis]['current_const_vel']:.4f}A<br>"
                stats_text += f"• RMS Accel: {stats[axis]['rms_accel']:.4f} {primary_units}/s²<br>"
                
                # Add settle time
                if settle_times[axis] is not None:
                    stats_text += f"• Settle Time: {settle_times[axis]:.3f}s<br><br>"
                else:
                    stats_text += f"• Settle Time: Not calculated<br><br>"
            
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
            height=2000,  # Much taller for better plot visibility
            showlegend=False  # Remove legend since each subplot is clearly labeled
        )
        
        # Update x-axis labels (only show time label on the very bottom plot)
        for axis_idx in range(len(axis_names)):
            for row in range(1, 6):
                actual_row = (axis_idx * 5) + row
                if axis_idx == len(axis_names) - 1 and row == 5:  # Only the very bottom subplot
                    fig.update_xaxes(title_text="Time [s]", row=actual_row, col=1)
                else:
                    fig.update_xaxes(title_text="", row=actual_row, col=1)
        
        # Update y-axis labels
        for axis_idx, axis in enumerate(axis_names):
            for signal_idx, (signal_type, plot_title, y_axis_label) in enumerate(signals):
                actual_row = (axis_idx * 5) + signal_idx + 1
                fig.update_yaxes(title_text=y_axis_label, row=actual_row, col=1)
        
        # Save plot with descriptive filename
        filename = os.path.join(so_dir, 'Performance Analysis', f"stage_performance_{plot_prefix}_{move_name}.html")
        pyo.plot(fig, filename=filename, auto_open=False)
        print(f"✅ Saved plot: {filename}")
    
    print(f"✅ All {test_type} axis stage performance plots and .dat files created.")

def init_fr(all_axes=None, test_type=None, axes=None, controller=None, init_current=None, axes_params=None, performance_target=None):
    global so_dir
    
    rotary = False
    units = []
    
    if test_type == 'single':
        axes_dict = {}
        # Ask user which axis to perform EasyTune on
        axis = str(axes[0])
        if not axis:
            print("❌ No axis specified. Exiting...")
            return
        print(f"📋 Selected Axis: {axis}")
        if axes_params and axis in axes_params:
            max_velocity = float(axes_params[axis]['velocity'])
            max_accel = float(axes_params[axis]['acceleration'])
        else:
            max_velocity = float(input(f"Enter the max velocity for {axis} axis: "))
            max_accel = float(input(f"Enter the max acceleration for {axis} axis: "))
        axes_dict[axis] = [max_velocity, max_accel]

        controller.runtime.commands.motion.enable(all_axes)
        controller.runtime.commands.motion.home(axis)

        axis_faults = check_for_faults(controller, axes if axes else [axis])

        if axis_faults:
            fault_init = decode_faults(axis_faults, axes, controller, fault_log = None)
            decoded_faults = fault_init.get_fault()
        if decoded_faults in ('OverCurrentFault', 'PositionErrorFault'):
            messagebox.showerror('OverCurrentFault', 'OverCurrentFault detected. Increasing Gain k')
            params = controller.configuration.parameters.get_configuration()
            gain_k = params.axes[axis].servo.servoloopgaink.value
            gain_k = gain_k * 1.5
            params.axes[axis].servo.servoloopgaink.value = gain_k
            controller.configuration.parameters.set_configuration(params)
            controller.reset()
            time.sleep(1)
            init_fr(all_axes, test_type, axes, controller, init_current, axes_params)
        # Get travel limits for both axes
        axis_limits = {}
        rev_motion = controller.runtime.parameters.axes[axis].motion.reversemotiondirection.value
        if rev_motion == 1:
            reverse_motion = True
        else:
            reverse_motion = False
            
        pos_limit = controller.runtime.parameters.axes[axis].protection.softwarelimithigh.value
        neg_limit = controller.runtime.parameters.axes[axis].protection.softwarelimitlow.value
        units_value = controller.runtime.parameters.axes[axis].units.unitsname.value
        units.append(units_value)
        axis_limits[axis] = (neg_limit, pos_limit)
        
        axis_keys = list(axes_dict.keys())
        axis = axis_keys[0]   # First axis name
        
        if units[0] == 'deg':
            rotary = True

        if rotary and axis_limits[axis][0] == 0 and axis_limits[axis][1] == 0:
            center = 0
            position = 'Center Init'
        else:
            # Calculate center positions for each axis
            if reverse_motion:
                center = ((axis_limits[axis][0] + axis_limits[axis][1]) / 2) * -1
            else:
                center = (axis_limits[axis][0] + axis_limits[axis][1]) / 2
        
        controller.runtime.commands.motion.moveabsolute([axis], [center], [5])
        position = 'Center Init'

        fr_files = {}
        fr_filepath, _ = frequency_response(axis, controller, init_current, verification=False, position=position, axes=all_axes)
        fr_files[axis] = fr_filepath

    elif test_type == 'multi':
        axes_dict = {}
        # Ask user which axes to perform EasyTune on
        axes = axes

        if not axes:
            print("❌ No axes specified. Exiting...")
            return
        else:
            axes = list(axes)
            print(f"📋 Selected Axes: {axes}")
            for axis in axes:
                if axes_params and axis in axes_params:
                    max_velocity = float(axes_params[axis]['velocity'])
                    max_accel = float(axes_params[axis]['acceleration'])
                else:
                    max_velocity = float(input(f"Enter the max velocity for {axis} axis: "))
                    max_accel = float(input(f"Enter the max acceleration for {axis} axis: "))
                axes_dict[axis] = [max_velocity, max_accel]
        
        # Get travel limits for both axes
        axis_limits = {}
        reverse_motion = {}
        for axis in axes:
            rev_motion = controller.runtime.parameters.axes[axis].motion.reversemotiondirection.value
            if rev_motion == 1:
                reverse_motion[axis] = True
            else:
                reverse_motion[axis] = False
                
            pos_limit = controller.runtime.parameters.axes[axis].protection.softwarelimithigh.value
            neg_limit = controller.runtime.parameters.axes[axis].protection.softwarelimitlow.value
            units_value = controller.runtime.parameters.axes[axis].units.unitsname.value
            units.append(units_value)
            axis_limits[axis] = (neg_limit, pos_limit)

        if units[0] == 'deg' and units[1] == 'deg':
            rotary = True
            
        # Get first two axes for position calculations
        x_axis = axes[0]
        y_axis = axes[1]

        if rotary and axis_limits[x_axis][0] == 0 and axis_limits[y_axis][0] == 0:
            x_center = 0
            y_center = 0
        else:
            # Calculate center positions for each axis
            x_center = ((axis_limits[x_axis][0] + axis_limits[x_axis][1]) / 2) * -1 if reverse_motion[x_axis] else (axis_limits[x_axis][0] + axis_limits[x_axis][1]) / 2
            y_center = ((axis_limits[y_axis][0] + axis_limits[y_axis][1]) / 2) * -1 if reverse_motion[y_axis] else (axis_limits[y_axis][0] + axis_limits[y_axis][1]) / 2
            
        controller.runtime.commands.motion.enable(all_axes)
        controller.runtime.commands.motion.home(axes)
        controller.runtime.commands.motion.moveabsolute(axes, [x_center, y_center], [5, 5])
        position = 'Center Init'

        fr_files = {}
        for axis in axes:
            fr_filepath, _ = frequency_response(axis, controller, init_current, verification=False, position=position, axes=axes)
            fr_files[axis] = fr_filepath

    iteration = 1
    log_files = []
    # Process each FR file with individual logging
    for axis, fr_filepath in fr_files.items():
        log_filepath = os.path.join(so_dir, os.path.splitext(os.path.basename(fr_filepath))[0] + '.log')
        with open(log_filepath, 'w', encoding='utf-8') as log_file:
            with contextlib.redirect_stdout(log_file), contextlib.redirect_stderr(log_file):
                print(f"🔍 Processing FR file: {os.path.basename(fr_filepath)}")
                print(f"📅 Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print("="*60)
                
                # Step 2: EasyTune Optimization
                print("\n🎯 STEP 2: EasyTune Optimization")
                results, stability_passed, ff_analysis_data, sensitivity = optimize(fr_filepath=fr_filepath, verification=False, position=position, performance_target=performance_target)
                if results:
                    success = apply_new_servo_params(axis, results, controller, ff_analysis_data, verification=False)
                    controller.reset()
        log_files.append(log_filepath)

    return log_files, axes_dict, axis_limits

def verify_fr(all_axes=None, test_type=None, axes=None, controller=None, log_files=None, axes_dict=None, axis_limits=None, ver_current=None, performance_target=None):
    global so_dir

    fr_files = []
    ver_failed = False  # Initialize before the loop

    # Step 4: Verification Frequency Response
    print("\n🔍 STEP 4: Verification Frequency Response")
    if test_type == 'single':
        axis = axes
        fr_files = single_axis_frequency_response(axis, controller, ver_current, all_axes=all_axes)
    elif test_type == 'multi':
        axes = list(axes)
        fr_files = multi_axis_frequency_response(axes, controller, ver_current, all_axes=all_axes)
    print("✅ Verification Frequency Response Completed")
    time.sleep(2)
    
    # Process each FR file with individual logging
    for fr_filepath in fr_files:
        # Extract axis name and position from filename
        # Filename format is 'test-{axis}-{position}-Verification.fr'
        filename = os.path.basename(fr_filepath)
        parts = filename.split('-')  # Split into ['test', '{axis}', '{position}', 'Verification.fr']
        current_axis = parts[1]  # Get the axis name part
        position = parts[2]  # Get the position part
    
        log_filepath = os.path.join(so_dir, os.path.splitext(os.path.basename(fr_filepath))[0] + '.log')
        print(f"🔍 Processing FR file: {os.path.basename(fr_filepath)}. Please wait...")
        with open(log_filepath, 'w', encoding='utf-8') as log_file:
            with contextlib.redirect_stdout(log_file), contextlib.redirect_stderr(log_file):
                print(f"🔍 Processing FR file: {os.path.basename(fr_filepath)}")
                print(f"📅 Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print("="*60)
                results, stability_passed, ff_analysis_data, sensitivity = optimize(fr_filepath=fr_filepath, verification=True, position=position, performance_target=performance_target)
                if stability_passed:
                    print("🎉 OPTIMIZATION PASSED - Stability criteria met!")
                    print("✅ Process completed successfully")
                else:
                    if sensitivity > 8:
                        print("❌ OPTIMIZATION FAILED - Stability criteria not met for this coordinate!")
                        ver_failed = ver_failed or True  # Use OR to maintain failed state
                        if results:
                            success = apply_new_servo_params(current_axis, results, controller, ff_analysis_data, verification=True)
                        
        print("✅ Process completed successfully")
        log_files.append(log_filepath)

    if ver_failed:
        controller.reset()
        print("⚠️ Some positions failed stability check - Re-verification needed")
    else:
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
        results = validate_stage_performance(controller, axes_dict, test_type, axis_limits, all_axes=all_axes)
        plot_stage_performance_results(results, test_type, axes_dict, controller)  # Pass the test_type!
        print("✅ Stage Performance Validation Completed")
        print("="*60)

    return ver_failed

def run_fr_test(controller, axes, test_type, all_axes, axes_params=None, stop_event=None, performance_target=None):
    """Run the frequency response testing for a specific set of axes"""
    try:
        check_stop_signal(stop_event)
        print("🚀 Starting Complete EasyTune Process with Verification")
        print("="*60)

        # Set a condition that ensures currents are below average current threshold
        current_thresholds = {}
        for axis in axes:
            current_thresholds[axis] = {}
            current_thresholds[axis]['average'] = controller.runtime.parameters.axes[axis].protection.averagecurrentthreshold.value
            current_thresholds[axis]['max'] = controller.runtime.parameters.axes[axis].protection.maxcurrentclamp.value

        init_current = 5
        ver_current = 10
        
        # Check init and ver currents against thresholds
        check_stop_signal(stop_event)
        for axis in axes:
            init_current_amp = current_thresholds[axis]['max'] * (init_current / 100)
            ver_current_amp = current_thresholds[axis]['max'] * (ver_current / 100)
            if init_current_amp > (current_thresholds[axis]['average'] / 2):
                new_init_current = (0.5 * current_thresholds[axis]['average']) / current_thresholds[axis]['max'] * 100
                print(f"⚠️ Initial current {init_current} exceeds average current threshold for axis {axis}. Adjusting to {new_init_current:.2f}% of max current.")
                init_current = new_init_current
            if ver_current_amp > (current_thresholds[axis]['average'] / 2):
                new_ver_current = 5
                print(f"⚠️ Verification current {ver_current} exceeds average current threshold for axis {axis}. Adjusting to {new_ver_current:.2f}% of max current.")
                ver_current = new_ver_current

        # Set position error to 10x for axes being tuned
        check_stop_signal(stop_event)
        current_pos_error = {}
        config_params = controller.configuration.parameters.get_configuration()
        for axis in axes:
            current_pos_error[axis] = {}
            pos_error = controller.runtime.parameters.axes[axis].protection.positionerrorthreshold.value
            current_pos_error[axis] = pos_error
            config_params.axes[axis].protection.positionerrorthreshold.value = pos_error * 10
            controller.configuration.parameters.set_configuration(config_params)
        controller.reset()

        check_stop_signal(stop_event)
        log_files, axes_dict, axis_limits = init_fr(all_axes=all_axes, test_type=test_type, axes=axes, controller=controller, init_current=init_current, axes_params=axes_params, performance_target=performance_target)
        
        check_stop_signal(stop_event)
        ver_failed = verify_fr(all_axes=all_axes, test_type=test_type, axes=axes, controller=controller, log_files=log_files, axes_dict=axes_dict, axis_limits=axis_limits, ver_current=ver_current, performance_target=performance_target)
        
        # Re-verify if needed (maximum of 3 attempts)
        attempts = 1
        max_attempts = 3
        while ver_failed and attempts < max_attempts:
            check_stop_signal(stop_event)
            print(f"\n⚠️ Verification attempt {attempts + 1} of {max_attempts}")
            if attempts == 2:
                ver_failed = verify_fr(all_axes=all_axes, test_type=test_type, axes=axes, controller=controller,
                                    log_files=log_files, axes_dict=axes_dict, axis_limits=axis_limits, ver_current=ver_current, performance_target=(performance_target-1 if performance_target > -3 else performance_target))
                attempts += 1
            else:
                ver_failed = verify_fr(all_axes=all_axes, test_type=test_type, axes=axes, controller=controller,
                                    log_files=log_files, axes_dict=axes_dict, axis_limits=axis_limits, ver_current=ver_current, performance_target=performance_target)
                attempts += 1
            
        if ver_failed:
            print("\n❌ Maximum verification attempts reached without success")
        else:
            print("\n✅ Verification completed successfully")
        
        # Set position error back to original value
        check_stop_signal(stop_event)
        config_params = controller.configuration.parameters.get_configuration()
        for axis in axes:
            config_params.axes[axis].protection.positionerrorthreshold.value = current_pos_error[axis]
            controller.configuration.parameters.set_configuration(config_params)
        controller.reset()
        
        return log_files, axes_dict, axis_limits
        
    except KeyboardInterrupt:
        print(f"\n🛑 FR test stopped for axes: {axes}")
        return None, None, None

def cleanup_controller(controller, test_type):
    messagebox.askokcancel("EasyTune", "Stage performance analysis completed. Please navigate to Controller Files to view performance plots before clicking OK.")

    # Clean up files from controller
    print("🧹 Cleaning up controller files...")
    try:
        # Delete all performance analysis data files
        for move_name in ['SW_NE', 'NE_SW', 'SE_NW', 'NW_SE', 'Positive', 'Negative']:
            data_filename = f"stage_performance_{test_type}_{move_name}.dat"
            controller.files.delete(data_filename)
            print(f"✅ Deleted {data_filename}")
        
        # Delete the Move.ascript file
        controller.files.delete('Move.ascript')
        print("✅ Deleted Move.ascript")
    except Exception as e:
        print(f"⚠️ Warning: Could not delete some files from controller: {e}")

def calculate_coordinate_offset(axis_limits, axis):
    """Calculate a relative offset based on the axis range for unit-agnostic positioning"""
    min_limit, max_limit = axis_limits[axis]
    range_size = abs(max_limit - min_limit)
    # Use 0.1% of the range as offset, with a minimum threshold
    offset = max(range_size * 0.001, range_size * 0.0001)  # 0.1% to 0.01% of range
    return offset

def calculate_unit_distance(motor_pole_pitch, units):
    """Calculate distance based on motor pole pitch and units for unit-agnostic operation"""
    distance = motor_pole_pitch / 2
    
    # Convert distance based on units
    if units == 'um':
        distance = distance * 1000
    elif units == 'mm':
        distance = distance  # Already in mm
    elif units == 'm':
        distance = distance / 1000  # Convert to meters
    elif units == 'deg':
        distance = distance  # Already in degrees
    elif units == 'rad':
        distance = distance * (180 / 3.14159)  # Convert to degrees
    elif units == 'in':
        distance = distance / 25.4  # Convert to inches
    elif units == 'mil':
        distance = distance * 39.37  # Convert to mils
    else:
        # Default to mm if unit not recognized
        print(f"⚠️ Unknown unit '{units}', defaulting to mm")
        distance = distance
    
    return distance

def main(test=None, controller=None, axes=None, test_type=None, all_axes=None, ui_params=None):
    """Main function with verification flow"""
    
    # Get stop event from ui_params
    stop_event = ui_params.get('stop_event') if ui_params else None
    mcd_cleanup_info = None
    
    # Handle UI-driven execution - Initial setup phase
    if ui_params:
        try:
            # Check for stop before each major operation
            check_stop_signal(stop_event)
            
            # UI provides all parameters, set up everything
            global so_dir
            
            # 1. Connect to controller
            print("🔌 Connecting to controller...")
            check_stop_signal(stop_event)
            controller = ui_params.get('controller')
            available_axes = ui_params.get('available_axes')

            # 2. Set up directories
            check_stop_signal(stop_event)
            so_dir = get_file_directory(controller.name)
            print(f"📁 Saving all files to: {so_dir}")
            
            # 3. Handle MCD configuration
            check_stop_signal(stop_event)
            print("\n🔧 Checking MCD configuration...")

            mcd_path = filedialog.askopenfilename(
                title="Select MCD file to modify",
                filetypes=[("MCD files", "*.mcd"), ("All files", "*.*")],
                initialdir=os.path.join(f"C:\\Users\\{os.getlogin()}\\Documents\\Automation1")
            )

            # no_load_dir_path = os.path.dirname(mcd_path)
            # no_load_base_name = os.path.splitext(os.path.basename(mcd_path))[0]
            # no_load_path = os.path.join(no_load_dir_path, f"{no_load_base_name}.mcd")

            # Set servo parameters back to machine setup values.
            # try:
                # CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
                # MS_DLL_PATH = os.path.join(CURRENT_DIR, "MSDll")  # Your separate DLL path
                # CONFIG_MANAGER_PATH = os.path.join(CURRENT_DIR, "Modules", 
                    # "System.Configuration.ConfigurationManager.8.0.0", "lib", "netstandard2.0")
        
                # Run the worker script in a separate process
                # print("Calling MCD worker to apply servo parameters...")
                # proc = subprocess.run(
                    # [sys.executable, "mcd_worker.py", 
                     # no_load_path, MS_DLL_PATH, CONFIG_MANAGER_PATH],
                    # capture_output=True, 
                    # text=True
                # )
        
                # if proc.returncode != 0:
                    # print(f"❌ Worker process failed: {proc.stderr}")
                    # return None
                # else:
                    # lines = proc.stdout.strip().splitlines()
                    # servo_params = json.loads(lines[-1])

            # except Exception as e:
                # print(f"❌ Error running MCD worker: {str(e)}")
                # return None

            # apply_servo_params_from_dict(servo_params, controller, available_axes)
            # print("✅ Servo parameters applied from MCD configuration")

            # download_mcd_from_controller(controller, no_load_path)
            modify_controller_name(mcd_path, mode="No Load")

            mcd_result = modify_mcd_enabled_tasks(mcd_path)
            if mcd_result:
                modified_mcd_path, base_name, dir_path = mcd_result
                mcd_cleanup_info = (base_name, dir_path)
            else:
                print("⚠️ No MCD modifications needed or file not selected")
                return
            
            if modified_mcd_path:
                # --- PAYLOAD UPDATE LOGIC START ---
                payload_values = ui_params.get('payload_values', {})
                if any(float(v) != 0 for v in payload_values.values()):
                    print("🔧 Nonzero payloads detected, updating MCD payloads...")
                    modify_mcd_payloads(modified_mcd_path, payload_values)
                    
                    try:
                        CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
                        #MS_DLL_PATH = os.path.join(CURRENT_DIR, "MSDll")  # Your separate DLL path

                        # Run the worker script in a separate process
                        print("Calling MCD worker to apply servo parameters with payload info...")
                        proc = subprocess.run(
                            [sys.executable, "mcd_worker.py", 
                             modified_mcd_path, base_name],
                            capture_output=True, 
                            text=True
                        )
                        print("STDOUT:", proc.stdout)
                        print("STDERR:", proc.stderr)
                
                        if proc.returncode != 0:
                            print(f"❌ Worker process failed: {proc.stderr}")
                            return None
                        else:
                            lines = proc.stdout.strip().splitlines()
                            result_data = json.loads(lines[-1])
                            payload_servo_params = result_data["servo_params"]
                            payload_feedforward_params = result_data["feedforward_params"]
                    except Exception as e:
                        print(f"❌ Error running MCD worker: {str(e)}")
                        return None
                    
                    apply_servo_params_from_dict(payload_servo_params, controller, available_axes)
                    print("✅ Servo parameters with payload info applied from MCD configuration")
                    
                    # Now process feedforward_params the same way
                    apply_feedforward_params_from_dict(payload_feedforward_params, controller, available_axes)
                    print("✅ Feedforward parameters with payload info applied from MCD configuration")

                check_stop_signal(stop_event)
                print("✅ MCD configuration updated")
                if upload_mcd_to_controller(controller, modified_mcd_path):
                    if ui_params.get('cal_file_ready', True):
                        print("✅ Controller configuration updated")
                    else:
                        print("⚠️ Calibration files not ready")
                else:
                    print("⚠️ Failed to update controller configuration")
                
            else:
                print("ℹ️ No MCD modifications needed or file not selected")
            controller.reset()
            # time.sleep(300)
            # 5. Encoder tuning
            check_stop_signal(stop_event)
            all_axes = ui_params.get('all_axes', [])
            print('Performing Encoder Tuning On All Axes')
            encoder_tuning = EncoderTuning(controller=controller, axes=all_axes)
            encoder_tuning.test()
            print("✅ Encoder tuning completed")
            
            # 6. Follow the test roadmap
            check_stop_signal(stop_event)
            test_type = ui_params.get('test_type', 'single')
            axes_params = ui_params.get('axes_params')
            performance_target = ui_params.get('performance_target', 0)
            print(f"Performance Target: {performance_target}")
            if test_type == 'multi':
                # Get XY axes and other axes from UI params
                xy_axes = ui_params.get('xy_axes', [])
                other_axes = ui_params.get('other_axes', [])
                
                # Process XY axes first
                if xy_axes:
                    check_stop_signal(stop_event)
                    run_fr_test(controller=controller, axes=xy_axes, 
                               test_type='multi', all_axes=all_axes, 
                               axes_params=axes_params, stop_event=stop_event,
                               performance_target=performance_target)
                
                # Process other axes individually
                for axis in other_axes:
                    check_stop_signal(stop_event)
                    run_fr_test(controller=controller, axes=[axis], 
                               test_type='single', all_axes=all_axes, 
                               axes_params=axes_params, stop_event=stop_event,
                               performance_target=performance_target)
                
            elif test_type == 'single':
                # Get single axis from UI params
                single_axis = ui_params.get('single_axis', '')
                if isinstance(single_axis, list):
                    single_axis = single_axis[0] if single_axis else ''
                print(f'Single Axis To Test: {single_axis}')
                
                check_stop_signal(stop_event)
                run_fr_test(controller=controller, axes=[single_axis], 
                           test_type=test_type, all_axes=all_axes, 
                           axes_params=axes_params, stop_event=stop_event,
                           performance_target=performance_target)
            
            # Cleanup controller files
            cleanup_controller(controller, test_type)

            # Download Loaded MCD and move results folder to EngOnly
            check_stop_signal(stop_event)
            loaded_base_name = re.sub(r'(?i)\b(no\s*load)\b', 'Loaded', base_name)
            
            MCD_path = os.path.join(dir_path, f"{loaded_base_name}.mcd")
            download_mcd_from_controller(controller, MCD_path)
            
            controller_name_mcd = modify_controller_name(MCD_path, mode="Loaded")
            
            # Move results folder to EngOnly directory
            parent_dir = os.path.dirname(os.path.dirname(dir_path))
            engonly_dir = os.path.join(parent_dir, "EngOnly")
            
            # Create EngOnly directory if it doesn't exist
            if not os.path.exists(engonly_dir):
                os.makedirs(engonly_dir)
                print(f"📁 Created EngOnly directory: {engonly_dir}")
            
            # Move the results folder (so_dir) to EngOnly
            if os.path.exists(so_dir):
                results_folder_name = os.path.basename(so_dir)
                destination_path = os.path.join(engonly_dir, results_folder_name)
                
                try:
                    # Remove destination if it exists
                    if os.path.exists(destination_path):
                        shutil.rmtree(destination_path)
                    
                    shutil.move(so_dir, destination_path)
                    print(f"📁 Moved results folder to: {destination_path}")
                except Exception as e:
                    print(f"❌ Error moving results folder: {str(e)}")
            else:
                print(f"⚠️ Results folder not found: {so_dir}")
            
            # Clean up temporary MCD files
            if mcd_cleanup_info:
                base_name, dir_path = mcd_cleanup_info
                cleanup_mcd_files(base_name, dir_path)
                print(f"Cleaned up temporary MCD files")
            
        except KeyboardInterrupt:
            print("\n🛑 EasyTune process stopped by user")
            return
        except Exception as e:
            if stop_event and stop_event.is_set():
                print("\n🛑 Process stopped during execution")
            else:
                raise  # Re-raise if it's not a stop-related exception
        return
    
    # FR Testing section - This is for the original main() interface
    if test == 'FR':
        # Call the extracted function
        axes_params = ui_params.get('axes_params') if ui_params else None
        log_files, axes_dict, axis_limits = run_fr_test(controller, axes, test_type, all_axes, axes_params, stop_event)

    if test == 'validate':
        validate_stage_performance(controller=controller, axes_dict=axes_dict, test_type=test_type, axis_limits=axis_limits, all_axes=all_axes)

if __name__ == "__main__":
    import argparse
    import ast
    
    parser = argparse.ArgumentParser(description="Run EasyTune or just validate stage performance.")
    parser.add_argument('--validate-only', action='store_true', help='Only run validate_stage_performance')
    parser.add_argument('--test-type', type=str, default=None, help='Test type for validation (single or multi)')
    parser.add_argument('--axes-dict', type=str, default=None, help='Axes dict as a string, e.g. "{\'X\':[100,1000],\'Y\':[100,1000]}"')
    parser.add_argument('--axis-limits', type=str, default=None, help='Axis limits as a string, e.g. "{\'X\':(-10,10),\'Y\':(-10,10)}"')
    parser.add_argument('--all-axes', type=str, default=None, help='All axes as a list string, e.g. "[\'X\',\'Y\']"')
    args = parser.parse_args()

    if args.validate_only:
        if args.axes_dict:
            axes_dict = ast.literal_eval(args.axes_dict)
        else:
            axes_dict = {'X': [100, 1000]}

        if args.axis_limits:
            axis_limits = ast.literal_eval(args.axis_limits)
        else:
            axis_limits = {'X': (-50.1, 50.1)}

        if args.all_axes:
            all_axes = ast.literal_eval(args.all_axes)
        else:
            all_axes = ['X', 'Y']
        test_type = args.test_type
        # You must provide a real controller object here for actual testing
        controller, _ = connect(connection_type='usb')  # Replace with actual controller setup if needed
        so_dir = get_file_directory(controller.name)
        print("[TEST MODE] Would call validate_stage_performance with:")
        print(f"  axes_dict: {axes_dict}")
        print(f"  test_type: {test_type}")
        print(f"  axis_limits: {axis_limits}")
        print(f"  all_axes: {all_axes}")
        # Uncomment and set controller for real use:
        results = validate_stage_performance(controller, axes_dict, test_type, axis_limits, all_axes=all_axes)

        plot_stage_performance_results(results, test_type, axes_dict, controller)
    else:
        # Optionally, call main() or other entry point
        pass

    
    