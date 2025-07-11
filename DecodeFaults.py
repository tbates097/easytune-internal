# -*- coding: utf-8 -*-
"""
Created on Fri Oct 11 14:55:16 2024

@author: TBates
"""
import automation1 as a1
import logging
import os

class decode_faults:
    def __init__(self, faults_per_axis, connected_axes, controller: a1.Controller, fault_log):
        self.faults_per_axis = faults_per_axis
        self.connected_axes = connected_axes
        self.controller = controller
        
        if fault_log is None:
            logger = logging.getLogger(controller.name)
            logger.setLevel(logging.ERROR)
            if not logger.handlers:
                username = os.getlogin()
                logs_dir = os.path.join(f"C:\\Users\\{username}\\Documents\\Automation1")
                if not os.path.exists(logs_dir):
                    os.makedirs(logs_dir)
                log_file_path = os.path.join(logs_dir, f"{controller.name}_faults.log")
                handler = logging.FileHandler(log_file_path)
                formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')  # ← Missing this
                handler.setFormatter(formatter)                                           # ← Missing this
                logger.addHandler(handler)                                                # ← Missing this
            self.fault_log = logger
        else:
            self.fault_log = fault_log
        
    def get_fault(self):
        fault_dict = {
            'PositionErrorFault': 1 << 0,
            'OverCurrentFault': 1 << 1,
            'CwEndOfTravelLimitFault': 1 << 2,
            'CcwEndOfTravelLimitFault': 1 << 3,
            'CwSoftwareLimitFault': 1 << 4,
            'CcwSoftwareLimitFault': 1 << 5,
            'AmplifierFault': 1 << 6,
            'FeedbackInput0Fault': 1 << 7,
            'FeedbackInput1Fault': 1 << 8,
            'HallSensorFault': 1 << 9,
            'MaxVelocityCommandFault': 1 << 10,
            'EmergencyStopFault': 1 << 11,
            'VelocityErrorFault': 1 << 12,
            'ExternalFault': 1 << 15,
            'MotorTemperatureFault': 1 << 17,
            'AmplifierTemperatureFault': 1 << 18,
            'EncoderFault': 1 << 19,
            'GantryMisalignmentFault': 1 << 22,
            'FeedbackScalingFault': 1 << 23,
            'MarkerSearchFault': 1 << 24,
            'SafeZoneFault': 1 << 25,
            'InPositionTimeoutFault': 1 << 26,
            'VoltageClampFault': 1 << 27,
            'MotorSupplyFault': 1 << 28,
            'InternalFault': 1 << 30,
        }
        self.present_faults = []
        self.decoded_faults_per_axis = {}
        
        for axis, axis_faults in self.faults_per_axis.items():
            present_faults = []
            for fault_name, fault_enum in fault_dict.items():
                if axis_faults & fault_enum:  # Check if the fault bit is set
                    present_faults.append(fault_name)
            
            self.decoded_faults_per_axis[axis] = present_faults  # Store decoded faults per axis
        
        if any(self.decoded_faults_per_axis[axis] for axis in self.decoded_faults_per_axis):
            self.log_faults()
        
        return self.decoded_faults_per_axis
    
    def log_faults(self):
        for axis in self.connected_axes:
            fault_value = self.decoded_faults_per_axis.get(axis)
            if fault_value:
                self.fault_log.error(f'An axis fault occurred on axis {axis}: {fault_value}')
                print(f'An axis fault occurred on axis {axis}: {fault_value}')
        self.acknowlegde_faults()
        
    def acknowlegde_faults(self):
        self.controller.runtime.commands.fault_and_error.acknowledgeall(1)
        for axis in self.connected_axes:
            self.controller.runtime.commands.motion.enable([axis])

        self.download_mcd()

    def download_mcd(self):
        import os
        try:
            userprofile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
            mcd_path = os.path.join(
                userprofile,
                "Documents",
                "Automation1",
                f"{self.controller.name}.mcd"
            )
            self.controller.download_mcd_to_file(mcd_path, True, True)
            print('MCD file downloaded successfully.')
        except Exception as e:
            self.fault_log.error(f'Failed to download MCD file: {e}')
            print(f'Failed to download MCD file: {e}')