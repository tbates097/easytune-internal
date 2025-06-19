""" This file defines all of the blocks that make up a block layout. """
from abc import ABC, abstractmethod
import copy
import control
import csv
from enum import Enum, auto
import math
import numpy as np
from scipy import signal

import a1_interface
from Globals import PI
from Utils import quadratic_formula, radian_to_hertz


#region Enums
class BlockRepresentation(Enum):
    """ The representation of a block.
    """
    Parameters = auto()
    FrequencyResponse = auto()

class FilterType(Enum):
    """ The filter type.
    """
    Empty = 0
    Low_Pass = 1
    Notch = 2
    Lead_Lag = 3
    Resonant = 4
    High_Pass = 5
    Custom = 6

class DriveType(Enum):
    """ The drive type of the system.
    """
    Servo = auto()
    Piezo = auto()
    Galvo = auto()

    def is_servo(motor_type):
        """ If this enum is a servo drive. """
        return motor_type == DriveType.Servo
    
    def is_piezo(motor_type):
        """ If this enum is a piezo drive. """
        return motor_type == DriveType.Piezo
    
    def is_galvo(motor_type):
        """ If this enum is a galvo drive. """
        return motor_type == DriveType.Galvo

class ETC_Setup(Enum):
    """ The setup of ETC (Enhanced Tracking Control). 
    """
    Disabled = 0
    Enabled_Before_Filters = 1
    Enabled_After_Filters = 2
#end region

#region Constants
UNIT_DELIMITER = "__" 
"""
This delimiter determines if the public property found in a block contains units or not. The unit parsing scheme is as follows:\n
1.) The 1st encounter of this delimiter determines whether or not the property has units. When this is detected, parentheses are automatically injected.\n
2.) Any encounters afterwards with a "___" (3 underscores) result in a '*' while "__" (2 underscores) result in a '/'.\n
\n
For example, consider the following Mechanical Plant property: Damping__N___s__m. This appears as "Damping (N*s/m)". This is because
the 1st "__" indicates units and results in the parentheses, the "___" afterwards results in a '*' and then any "__" remaining are
converted into a '/'.
"""

FILTER_PARAMETER_MAPPING = {
    FilterType.Custom:["N0","N1","N2","D1","D2"],
    FilterType.Empty:[],
    FilterType.Low_Pass:["Cutoff Frequency"],
    FilterType.High_Pass:["Cutoff Frequency"],
    FilterType.Lead_Lag:["Frequency", "Phase"],
    FilterType.Notch:["Center Frequency", "Width", "Depth"],
    FilterType.Resonant:["Center Frequency", "Width", "Gain"]
}
""" The user facing parameters that correspond to each filter. """

ETC_SETUP_PARAMETER_MAPPING = {
    ETC_Setup.Disabled:"Disabled",
    ETC_Setup.Enabled_Before_Filters:"Enabled (Before Servo Filters)",
    ETC_Setup.Enabled_After_Filters:"Enabled (After Servo Filters)",
}
""" The user facing text that is displayed when the ETC combo box changes."""
#end region

#region Classes
class Abstract_Loop(ABC):
    """ An abstract class that defines how each loop is structured.
    """
    @abstractmethod
    class _Blocks:
        """ Each loop must define their own version of this class!
        """
        pass

    def __init__(self):
        pass

class Abstract_Block(ABC):
    """ An abstract class that represents a single block in the loop. This shall not contain any additional nested blocks.
    """
    @abstractmethod
    class _Properties:
        """ Each loop must define their own version of this class!
        """
        pass

    def __init__(self):
        self.tf: control.TransferFunction = None
        self.frd: control.FRD = None

    @property
    @abstractmethod
    def get_zeros(self) -> list[complex]:
        """ The zeros of the transfer function according to user defined parameters.

        Returns:
            list[complex]: The zeros of the system. Can be empty.
        """
        pass

    @property
    @abstractmethod
    def get_poles(self) -> list[complex]:
        """ The poles of the transfer function according to user defined parameters.

        Returns:
            list[complex]: The poles of the system. Can be empty.
        """
        pass

    @property
    @abstractmethod
    def get_gain(self) -> float:
        """ The gain of the transfer function according to user defined parameters.

        Returns:
            list[complex]: The gain of the system. Can be empty.
        """
        pass
    
    def get_frd(self, omega:list[float]=None) -> control.FRD:
        """ Retrieves the frd that corresponds to this block at the frequencies requested.

        Args:
            omega (list[float], optional): The frequencies to evaluate and retrieve the FRD at. Defaults to None.

        Returns:
            control.FRD: The FRD that corresponds to this block.
        """
        if omega is not None:
            # If omega was provided, sample the FRD at the requested frequencies.
            # NOTE: The returned frd cannot be re-sampled with another set of frequencies if interpolation is needed.
            # NOTE: In order to multiply two FRDs, they must match in frequency exactly.
            frd = control.frequency_response(self.frd, omega=omega)
            frd = control.frd(frd, self.frd.frequency, smooth=True)
            return frd
        else:
            return self.frd

    def set_frd(self, z:list[float]=None, p:list[float]=None, k:float=None, num:list[float]=None, den:list[float]=None, fs:float=None, omega:list[float]=None, frd:control.FRD=None) -> None:
        """ Sets the FRD according to:
        - ZPK form and the frequencies to compute at
        - Numerator/Denominator form and the frequencies to compute at
        - The FRD directly

        Args:
            z (list[float], optional): The zeros of the system. Defaults to None.
            p (list[float], optional): The poles of the system. Defaults to None.
            k (float, optional): The gain of the system. Defaults to None.
            num (list[float], optional): The numerator of the transfer function. Defaults to None.
            den (list[float], optional): The denominator of the transfer function. Defaults to None.
            omega (list[float], optional): The frequencies of the system. This is used for determining the sampling time of the system. Defaults to None.
            frd (control.FRD, optional): The FRD to directly set this block to. Defaults to None.
        """
        if frd:
            self.frd = copy.deepcopy(frd)
        else:
            if omega is None:
                raise ValueError("Omega was not defined!")
            
            sample_time = None
            if fs:
                sample_time = 1.0/fs

            if (z is not None) and (p is not None) and (k is not None):
                # Compute FRD from ZPK form.
                self.tf = control.zpk(z, p, k, dt=sample_time)
                self.frd = control.frd(self.tf, omega, smooth=True)
            elif num and den:
                # Compute FRD from numerator, denominator form.
                self.tf = control.tf(num, den, dt=sample_time)
                self.frd = control.frd(self.tf, omega, smooth=True)
            else:
                # Get local variables. This is how we will check for function parameters that are set to None.
                args = locals()
                missing_args = []
                for key in args.keys():
                    if args[key] is None:
                        missing_args.append(key)
                raise ValueError("One or more arguments of the following arguments are missing: {}".format(missing_args))

class Filter_Model(Abstract_Block):
    # NOTE: https://en.wikipedia.org/wiki/Digital_biquad_filter
    class _Properties:
        def __init__(self):
            self._sampling_frequency = 1.0
            self.default_to_empty()

        @property
        def filter_type(self):
            return self._filter_type
        
        @filter_type.setter
        def filter_type(self, value:FilterType):
            num_parameters = len(FILTER_PARAMETER_MAPPING[value])
            self._filter_type = value
            self._parameters = [0.0]*num_parameters

            # Set new defaults.
            if value == FilterType.Empty:
                self.default_to_empty()
            elif value == FilterType.Low_Pass:
                self.parameters = [1000.0]
            elif value == FilterType.High_Pass:
                self.parameters = [1000.0]
            elif value == FilterType.Lead_Lag:
                self.parameters = [1000.0, 50.0]
            elif value == FilterType.Notch:
                self.parameters = [1000.0, 50.0, 20.0]
            elif value == FilterType.Resonant:
                self.parameters = [1000.0, 50.0, 20.0]

        @property
        def parameters(self):
            return self._parameters
        
        @parameters.setter
        def parameters(self, value:list[float]):
            if len(self.parameters) != len(value):
                raise ValueError("The number of parameters specified ({}) does not equal the number of parameters ({}) used for a {} filter!"\
                                .format(len(value), len(self.parameters), self.filter_type.name))
        
            self._parameters = copy.deepcopy(value)

            # Compute the coefficients based off of user parameters.
            a1_interface.forward_calculate_filter(self)

        @property
        def sampling_frequency(self):
            return self._sampling_frequency
        
        @sampling_frequency.setter
        def sampling_frequency(self, value:float):
            if value == 0:
                raise ValueError("The sampling frequency was set to an invalid value of {}!".format(value))
            
            self._sampling_frequency = value
            a1_interface.backward_calculate_filter(self)
            a1_interface.forward_calculate_filter(self)

        def default_to_empty(self):
            self._filter_type = FilterType.Empty
            self._parameters = []
            self.N0 = 1.0
            self.N1 = 0.0
            self.N2 = 0.0
            self.D1 = 0.0
            self.D2 = 0.0

    def get_zeros(self) -> list[complex]:
        a = self.properties.N0
        b = self.properties.N1
        c = self.properties.N2
        return quadratic_formula(a, b, c)
    
    def get_poles(self) -> list[complex]:
        a = 1.0
        b = self.properties.D1
        c = self.properties.D2
        return quadratic_formula(a, b, c)

    def get_gain(self) -> float:
        return 1.0
    
    def get_frd(self, omega:list[float]) -> control.FRD:
        # Use numerator and denominator form instead of ZPK form so that we don't have to bias the DC gain around unity.
        self.set_frd(num=[self.properties.N0, self.properties.N1, self.properties.N2], \
                     den=[1.0, self.properties.D1, self.properties.D2], \
                     omega=omega, fs=self.properties.sampling_frequency)
        
        return self.frd

    def __init__(self):
        self.properties = __class__._Properties()

class Enhanced_Tracking_Control():
    # This changes how the servo loop block is arranged
    class _Properties:
        def __init__(self):
            self.Setup: ETC_Setup = ETC_Setup.Disabled
            self.Bandwidth = 0.0
            self.Scale = 0.0

        def etc_setup_to_integer(self) -> int:
            if self.Setup == ETC_Setup.Disabled:
                return int("0x0", 16)
            elif self.Setup == ETC_Setup.Enabled_Before_Filters:
                return int("0x3", 16)
            elif self.Setup == ETC_Setup.Enabled_After_Filters:
                return int("0x1", 16)

    def __init__(self):
        self.properties = __class__._Properties()

class FR():
    def __init__(self):
        self.imported_frd: control.FRD = None
        self.filepath = None

    def parse_fr_file(self, filepath):
        # Allow for interpolation.
        # The main FR file will restrict what frequencies we plot.
        frequency_ang = []
        complex_num = []
        skip_header = True
        with open(filepath, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter='\t', quotechar='|')
            for row in reader:
                if skip_header:
                    skip_header = False
                    continue

                frequency_ang.append(float(row[0]) * 2*PI)
                complex_num.append(complex(float(row[3]), float(row[4])))
        
        # Generate the FRD. Allow for interpolation.
        self.imported_frd = control.frd(complex_num, frequency_ang, smooth=True)
        self.filepath = filepath

class Servo_Loop(Abstract_Loop):
    class _Blocks:
        def __init__(self):
            self.Servo_Controller = Servo_Controller()
            self.Servo_Plant = Servo_Plant()

    def __init__(self):
        self.blocks = __class__._Blocks()

class Servo_Controller(Abstract_Block):
    class _Properties:
        def __init__(self):
            # Drive Type.
            self.Drive_Type = DriveType.Servo

            # Gains.
            self.K = 1.0
            self.Kip = 1.0
            self.Kip2 = 0.0
            self.Kiv = 1.0
            self.Kpv = 0.0
            self.Kv = 1.0
            self.Ksi1 = 0.0
            self.Ksi2 = 0.0

            # Servo Filters (x16).
            self.Servo_Filters = [Filter_Model() for _ in range(16)]
            self.Servo_Loop_Gain_Normalization_Factor = 1.0 # Can't be 0 due to division.

            # ETC.
            self.Enhanced_Tracking_Control = Enhanced_Tracking_Control()

            # Feedforward.
            self.Pff = 0.0
            self.Vff = 0.0
            self.Aff = 53.5
            self.Jff = 0.0
            self.Sff = 0.0
            self.Feedforward_Advance__ms = 0.25

            # Feedforward Filters (x4).
            self.Feedforward_Filters = [Filter_Model() for _ in range(4)]
            self.Feedforward_Gain_Normalization_Factor = 1.0 # Can't be 0 due to division.

            # Dual Loop Path.
            self.Is_Dual_loop = False # Doesn't actually do anything.
            self.Alpha = 0.0

            # Drive Frequency.
            self.Drive_Frequency__hz = 20000.0

            # Counts per Unit.
            self.Counts_Per_Unit = 1000.0

    def __init__(self):
        self.properties = __class__._Properties()

    def get_position_feedback_input0_zeros(self) -> list[complex]:
        zeros = []
        
        # Zeros for Position Feedback Input 0.
        a = self.properties.Kpv * self.properties.Alpha
        b = 2*PI*(self.properties.Kiv*self.properties.Alpha + self.properties.Kip*self.properties.Kpv)
        c = 1000*self.properties.Kip2 + (2*PI)**2*self.properties.Kip*self.properties.Kiv

        a/= self.properties.Servo_Loop_Gain_Normalization_Factor
        b/=self.properties.Servo_Loop_Gain_Normalization_Factor
        c/=self.properties.Servo_Loop_Gain_Normalization_Factor

        if a != 0:
            # 2nd order Transfer Function.
            zeros += quadratic_formula(a, b, c)
        elif b != 0:
            # 1st order Transfer Function.
            zeros.append(complex(-c/b, 0))
        else:
            # 0th order Transfer Function. No zeros.
            pass

        # Ksi1.
        if self.properties.Ksi1:
            zeros.append(complex(-2*PI*self.properties.Ksi1, 0))

        # Ksi2.
        if self.properties.Ksi2:
            zeros.append(complex(-2*PI*self.properties.Ksi2, 0))

        return zeros
    
    def get_position_feedback_input0_poles(self) -> list[complex]:
        poles = [complex(0, 0)]

        # Ksi1.
        if self.properties.Ksi1:
            poles.append(complex(0, 0))

        # Ksi2.
        if self.properties.Ksi2:
            poles.append(complex(0, 0))

        return poles
    
    def get_position_feedback_input0_gain(self) -> float:
        gain = 0.0

        if (self.properties.Kpv != 0.0) and (self.properties.Alpha != 0.0):
            gain = self.properties.Kpv*self.properties.Alpha
        elif ((self.properties.Kiv != 0.0) and (self.properties.Alpha != 0.0)) or \
            ((self.properties.Kip != 0.0) and (self.properties.Kpv != 0.0)):
            gain = 2*PI*(self.properties.Kiv*self.properties.Alpha + self.properties.Kip*self.properties.Kpv)
        elif (self.properties.Kip2 != 0.0) or ((self.properties.Kip != 0.0) and (self.properties.Kiv != 0.0)):
            gain = 1000*self.properties.Kip2 + 4*PI**2*self.properties.Kip*self.properties.Kiv

        gain *= self.properties.K

        #if self.properties.Servo_Loop_Gain_Normalization_Factor:
        #    gain /= self.properties.Servo_Loop_Gain_Normalization_Factor # Divide if not using engineering units

        return gain

    def get_position_feedback_input1_zeros(self) -> list[complex]:
        zeros = []
        
        # Zeros for Position Feedback Input 1.
        a = 0
        b = self.properties.Kpv
        c = 2*PI*self.properties.Kiv

        if a != 0:
            # 2nd order Transfer Function.
            zeros += quadratic_formula(a, b, c)
        elif b != 0:
            # 1st order Transfer Function.
            zeros.append(complex(-c/b, 0))
        else:
            # 0th order Transfer Function. No zeros.
            pass

        # Ksi1.
        if self.properties.Ksi1:
            zeros.append(complex(-2*PI*self.properties.Ksi1, 0))

        # Ksi2.
        if self.properties.Ksi2:
            zeros.append(complex(-2*PI*self.properties.Ksi2, 0))

        return zeros
    
    def get_position_feedback_input1_poles(self) -> list[complex]:
        poles = []

        # Ksi1.
        if self.properties.Ksi1:
            poles.append(complex(0, 0))

        # Ksi2.
        if self.properties.Ksi2:
            poles.append(complex(0, 0))

        return poles
    
    def get_position_feedback_input1_gain(self) -> float:
        gain = 0.0

        if (self.properties.Kpv != 0.0):
            gain = self.properties.Kpv
        elif (self.properties.Kiv != 0.0):
            gain = 2*PI*self.properties.Kiv

        gain *= self.properties.K * (1.0 - self.properties.Alpha)

        if (self.properties.Kv != 0.0):
            gain /= self.properties.Kv

        #if self.properties.Servo_Loop_Gain_Normalization_Factor:
        #    gain /= self.properties.Servo_Loop_Gain_Normalization_Factor

        return gain

    def get_zeros(self) -> list[complex]:
        if self.properties.Alpha == 1.0:
            return self.get_position_feedback_input0_zeros()
        else:
            return None

    def get_poles(self) -> list[complex]:
        if self.properties.Alpha == 1.0:
            return self.get_position_feedback_input0_poles()
        else:
            return None

    def get_gain(self) -> float:
        if self.properties.Alpha == 1.0:
            return self.get_position_feedback_input0_gain()
        else:
            return 1.0
        
    def get_servo_filters_frd(self, omega:list[float]):
        # Get the response from our servo filter(s).
        filter_response = control.frd(control.tf([1], [1], 1.0/self.properties.Drive_Frequency__hz), omega, smooth=True) # Start off with unity gain
        for filter in self.properties.Servo_Filters:
            if filter.properties.filter_type != FilterType.Empty:
                filter.properties.sampling_frequency = self.properties.Drive_Frequency__hz
                frd = filter.get_frd(omega)
                if frd is not None:
                    filter_response *= frd

        return filter_response
    
    def get_feedforward_frd(self, omega:list[float]):
        def sample_delay_response(adv_samples):
            integer_advance = math.ceil(adv_samples)
            fractional_delay = integer_advance - adv_samples
            num = [0.0] * (integer_advance+1)
            den = [0.0] * (integer_advance+1)
            num[0] = 1
            den[-1] = 1
            _, advance_filter_response = signal.freqz(num, den, worN=freq_hz, fs=self.properties.Drive_Frequency__hz)
            _, fractional_delay_filter_response = signal.freqz([1-fractional_delay, fractional_delay], [1, 0], worN=freq_hz, fs=self.properties.Drive_Frequency__hz)
            return control.frd(advance_filter_response, omega, smooth=True) * control.frd(fractional_delay_filter_response, omega, smooth=True)

        freq_hz = radian_to_hertz(omega)
        sample_time = 1/self.properties.Drive_Frequency__hz
        pff = self.properties.Pff
        vff = self.properties.Vff * self.properties.Drive_Frequency__hz
        aff = self.properties.Aff * self.properties.Drive_Frequency__hz**2
        jff = self.properties.Jff * self.properties.Drive_Frequency__hz**3
        sff = self.properties.Sff * self.properties.Drive_Frequency__hz**4

        scale_ratio = self.properties.Servo_Loop_Gain_Normalization_Factor / self.properties.Feedforward_Gain_Normalization_Factor
        pff *= scale_ratio
        vff *= scale_ratio
        aff *= scale_ratio
        jff *= scale_ratio
        sff *= scale_ratio

        if self.properties.Drive_Type.is_galvo():
            # FIR Filters.
            # https://docs.scipy.org/doc/scipy-1.12.0/reference/generated/scipy.signal.freqz.html\
            _, vff_filter_response = signal.freqz([-1/12*vff, 2/3*vff, 0, -2/3*vff, 1/12*vff], [0.0, 0.0, 1.0, 0.0, 0.0], worN=freq_hz, fs=self.properties.Drive_Frequency__hz)
            _, aff_filter_response = signal.freqz([-1/12*aff, 4/3*aff, -5/2*aff, 4/3*aff, -1/12*aff], [0.0, 0.0, 1.0, 0.0, 0.0], worN=freq_hz, fs=self.properties.Drive_Frequency__hz)
            _, jff_filter_response = signal.freqz([0.5*jff, -1.0*jff, 0, jff, -0.5*jff], [0.0, 0.0, 1.0, 0.0, 0.0], worN=freq_hz, fs=self.properties.Drive_Frequency__hz)
            _, sff_filter_response = signal.freqz([sff, -4.0*sff, 6.0*sff, -4.0*sff, sff], [0.0, 0.0, 1.0, 0.0, 0.0], worN=freq_hz, fs=self.properties.Drive_Frequency__hz)

            feedforward_frd = control.frd(vff_filter_response, omega, smooth=True)
            feedforward_frd += control.frd(aff_filter_response, omega, smooth=True)
            feedforward_frd += control.frd(jff_filter_response, omega, smooth=True)
            feedforward_frd += control.frd(sff_filter_response, omega, smooth=True)

            # Convert ff advance to response.
            _, fir_filter_response = signal.freqz([0.25, 0.5, 0.25], [0.0, 1.0, 0.0], worN=freq_hz, fs=self.properties.Drive_Frequency__hz)
            samples = (self.properties.Feedforward_Advance__ms / 1000.0 * self.properties.Drive_Frequency__hz)
            fir_filter_response = control.frd(fir_filter_response, omega, smooth=True)
            fir_filter_response *= sample_delay_response(samples)
            feedforward_frd *= fir_filter_response
        else:
            pff_filter = control.tf([pff, 0.0, 0.0], [1.0, 0.0, 0.0], sample_time)

            # FIR Filters.
            # https://docs.scipy.org/doc/scipy-1.12.0/reference/generated/scipy.signal.freqz.html
            _, vff_filter_response = signal.freqz([vff, -1*vff, 0], [0.0, 0.0, 1.0, 0.0, 0.0], worN=freq_hz, fs=self.properties.Drive_Frequency__hz)
            _, aff_filter_response = signal.freqz([aff, -2*aff, aff], [0.0, 0.0, 1.0, 0.0, 0.0], worN=freq_hz, fs=self.properties.Drive_Frequency__hz)

            feedforward_frd = control.frd(pff_filter, omega, smooth=True)
            feedforward_frd += control.frd(vff_filter_response, omega, smooth=True)
            feedforward_frd += control.frd(aff_filter_response, omega, smooth=True)

            # Convert ff advance to response.
            samples = (self.properties.Feedforward_Advance__ms / 1000.0 * self.properties.Drive_Frequency__hz) + 0.5
            feedforward_frd *= sample_delay_response(samples)

        # Feedforward Filters.
        filter_response = control.frd(control.tf([1], [1], 1.0/self.properties.Drive_Frequency__hz), omega, smooth=True) # Start off with unity gain.
        for filter in self.properties.Feedforward_Filters:
            if filter.properties.filter_type != FilterType.Empty:
                filter.properties.sampling_frequency = self.properties.Drive_Frequency__hz
                frd = filter.get_frd(omega)
                if frd is not None:
                    filter_response *= frd

        return feedforward_frd * filter_response

    def get_etc_frds(self, omega:list[float]):
        # Get the response from ETC.
        sampling_frequency = self.properties.Drive_Frequency__hz
        sampling_time = 1.0/sampling_frequency
        bandwidth = self.properties.Enhanced_Tracking_Control.properties.Bandwidth
        scale = self.properties.Enhanced_Tracking_Control.properties.Scale

        etc_integrator_gain = 2*PI*sampling_time*bandwidth
        etc_filter_gain = etc_integrator_gain*scale*self.properties.Drive_Frequency__hz**2 * \
            (self.properties.Servo_Loop_Gain_Normalization_Factor / self.properties.Feedforward_Gain_Normalization_Factor)
        
        #etc_filter_gain /= self.properties.Servo_Loop_Gain_Normalization_Factor

        # Feedback path.
        backwards_difference_filter = control.tf([1.0, -1.0, 0.0], [1.0, 0.0, 0.0], sampling_time)
        #backwards_difference_filter = control.tf([1.0, -1.0], [1.0, 0.0], sampling_time)
        accumulator_filter = control.tf([etc_integrator_gain, 0.0, 0.0], [1.0, -1.0, 0.0], sampling_time)
        #accumulator_filter = control.tf([1, 0.0], [1.0, -1.0], sampling_time)
        etc_filter = control.tf([etc_filter_gain, -etc_filter_gain, 0.0], [1.0, -1.0, etc_integrator_gain], sampling_time)
        #etc_filter = control.tf([1, -1, 0.0], [1.0, -1.0, etc_integrator_gain], sampling_time)
        etc_delay_filter = control.tf([0.0, 0.0, 1.0], [1.0, 0.0, 0.0], sampling_time)

        if self.properties.Drive_Type.is_piezo():
            etc_filter_gain = scale / self.properties.Counts_Per_Unit
            etc_filter = control.tf([etc_filter_gain*etc_integrator_gain, -etc_filter_gain*etc_integrator_gain, 0.0], \
                                    [1.0, -(1.0 + (1.0 - etc_integrator_gain)), 1 - etc_integrator_gain], sampling_time)
            etc_delay_filter = control.tf([0.0, 1.0, 0.0], [1.0, 0.0, 0.0], sampling_time)

        feedback_path = control.frd(etc_filter, omega, smooth=True)

        if not self.properties.Drive_Type.is_piezo():
            feedback_path *= control.frd(backwards_difference_filter, omega, smooth=True)

        forward_path = control.frd(etc_delay_filter, omega, smooth=True) * control.frd(accumulator_filter, omega, smooth=True)
        forward_path += 1

        return [feedback_path, forward_path]
    
    def get_pid_controller_frd(self, omega:list[float]):
        # Get the response from the Position Feedback Input 0 path.
        tf = control.zpk(self.get_position_feedback_input0_zeros(), self.get_position_feedback_input0_poles(), self.get_position_feedback_input0_gain())
        position_feedback_input_0_frd = control.frd(tf, omega, smooth=True)

        # Get the response from the Position Feedback Input 1 path.
        tf = control.zpk(self.get_position_feedback_input1_zeros(), self.get_position_feedback_input1_poles(), self.get_position_feedback_input1_gain())
        position_feedback_input_1_frd = control.frd(tf, omega, smooth=True)

        pid_controller_frd = position_feedback_input_0_frd + position_feedback_input_1_frd

        delay = control.tf([0, 1], [1, 0], 1/self.properties.Drive_Frequency__hz)
        delay_frd = control.frd(delay, omega, smooth=True)
        pid_controller_frd *= delay_frd

        return pid_controller_frd
        
    def get_frd(self, omega:list[float]) -> control.FRD:
        # Override abstract FRD implementation due to dual loop and servo filter crap.
        pid_controller_frd = self.get_pid_controller_frd(omega)

        # Filter response
        filter_frd = self.get_servo_filters_frd(omega)

        # Enhanced Tracking Control (ETC).
        if self.properties.Enhanced_Tracking_Control.properties.Setup == ETC_Setup.Disabled:
            pid_controller_frd *= filter_frd
            #print(pid_controller_frd, filter_frd)
            #print("etc disabled", pid_controller_frd)
        else:
            [feedback_path, forward_path] = self.get_etc_frds(omega)
            #print("filter response", filter_frd)
            if self.properties.Enhanced_Tracking_Control.properties.Setup == ETC_Setup.Enabled_Before_Filters:
                #print("etc before filters")
                pid_controller_frd = (pid_controller_frd + feedback_path) * forward_path * filter_frd
            elif self.properties.Enhanced_Tracking_Control.properties.Setup == ETC_Setup.Enabled_After_Filters:
                #print("etc after filters")
                pid_controller_frd = ((pid_controller_frd * filter_frd) + feedback_path) * forward_path

        self.set_frd(frd=pid_controller_frd)
        return self.frd

class Servo_Plant(Abstract_Loop):
    class _Blocks:
        def __init__(self):
            self.Current_Loop = Current_Loop()
            self.Mechanical_Plant = Mechanical_Plant()

    class _Properties:
        def __init__(self):
            self.Block_Representation = BlockRepresentation.Parameters
            # The Frequency Response option uses the A1 response.

    def __init__(self):
        self.blocks = __class__._Blocks()
        self.properties = __class__._Properties()

class Current_Loop(Abstract_Loop):
    class _Blocks:
        def __init__(self):
            self.Current_Controller = Digital_Current_Loop()
            self.Current_Plant = Current_Plant()

    def __init__(self):
        self.blocks = __class__._Blocks()

class Digital_Current_Loop(Abstract_Block):
    class _Properties:
        def __init__(self):
            # Gains
            self.K = 1.0
            self.Ki = 1.0
            self.Bus_Voltage__V = 39.9

            #self.Back_Emf = 0.0
            self.Lff__mH = 1.0
            self.Rff__ohm = 1.0
            
    def get_poles(self) -> list[float]:
        return [0.0]

    def get_zeros(self) -> list[float]:
        return [complex(-2*PI*self.properties.Ki, 0)]

    def get_gain(self) -> float:
        return self.properties.K / 32768 # 32768 is some arbitrary scaling done by the drive.
    
    def get_feedforward_frd(self, omega:list[float], servo_rate):
        try:
            tf = (control.tf([1,-1],[1,0],1.0/servo_rate)*servo_rate*self.properties.Lff__mH/1000.0 + self.properties.Rff__ohm) / 2 / (self.properties.Bus_Voltage__V / 2)
        except Exception as e:
            print("An error occurred when computing the Digital Current Loop: \"{}\"\nDefaulting to unity gain.".format(e))
            tf = control.tf([1], [1])
        return control.frd(tf, omega, smooth=True)
    
    def get_frd(self, omega:list[float], servo_rate) -> control.FRD:
        ts = 1/servo_rate
        #print("Digital values", self.properties.Bus_Voltage__V, self.properties.K, self.properties.Ki)
        #tf = self.properties.K*control.tf([PI*self.properties.Ki*ts + 1, PI*self.properties.Ki*ts - 1], [32768, -32768], ts)
        tf = (1.0 + control.tf([1,1],[1,-1],ts)/(2.0*servo_rate) * self.properties.Ki * 2 * np.pi) * self.properties.K / 32768.0 #* self.properties.Bus_Voltage__V
        #print("Digital tf", tf)
        frd = control.frd(tf, omega, smooth=True)
       # print("dig frd", frd)
        return frd
    
    def __init__(self):
        self.properties = __class__._Properties()

class Current_Plant(Abstract_Loop):
    class _Blocks:
        def __init__(self):
            self.Amplifier_Plant_Block = Amplifier_Plant()
            self.Amplifier_Rolloff_Filter_Block = Amplifier_Rolloff_Filter()
            self.Motor_Plant_Block = Motor_Plant()
            self.Current_Feedback_LPF = Current_Feedback_Low_Pass_Filter()

    class _Properties:
        def __init__(self):
            self.Block_Representation = BlockRepresentation.Parameters

    def __init__(self):
        self.blocks = __class__._Blocks()
        self.properties = __class__._Properties()

    def get_frd(self, omega:list[float]) -> control.FRD:
        return self.blocks.Amplifier_Rolloff_Filter_Block.get_frd(omega) * self.blocks.Amplifier_Plant_Block.get_frd(omega) * \
            self.blocks.Motor_Plant_Block.get_frd(omega) * self.blocks.Current_Feedback_LPF.get_frd(omega)

class Amplifier_Plant(Abstract_Block):
    class _Properties:
        def __init__(self):
            self.Block_Representation = BlockRepresentation.Parameters
            self.Frequency_Response = FR()
            self.K = 39.9
            self.Delay__us = 25.4

    def get_zeros(self) -> list[complex]:
        return []

    def get_poles(self) -> list[complex]:
        return []

    def get_gain(self) -> float:
        return self.properties.K
    
    def get_frd(self, omega:list[float]) -> control.FRD:
        if self.properties.Block_Representation == BlockRepresentation.Parameters:
            self.set_frd(z=self.get_zeros(), p=self.get_poles(), k=self.get_gain(), omega=omega)
            self.frd = self.frd  #TODO: Add thiran filter all pass, group delay 
        elif self.properties.Block_Representation == BlockRepresentation.FrequencyResponse:
            if self.properties.Frequency_Response.imported_frd is not None:
                frd = control.frequency_response(self.properties.Frequency_Response.imported_frd, omega)
                frd_new = control.frd(frd.response, frd.frequency, smooth=True)
                self.set_frd(frd=frd_new)
        return self.frd

    def __init__(self):
        self.properties = __class__._Properties()

class Motor_Plant(Abstract_Block):
    class _Properties:
        def __init__(self):
            self.R__ohm = 1.0
            self.L__mH = 1.0
            self.Kt__N__A = 1.0 # units: N/A. This parameter still applies to the frequency response file.

    def get_zeros(self) -> list[complex]:
        return []

    def get_poles(self) -> list[complex]:
        try:
            return [-self.properties.R__ohm/(self.properties.L__mH/10**3)]
        except:
            return []

    def get_gain(self) -> float:
        try:
            return 2.0/(self.properties.L__mH/10**3) # 2.0 is for the line-to-line R/L conversion to phase.
        except Exception as e:
            print("An error occurred when computing the Motor Plant: \"{}\"\nDefaulting to unity gain.".format(e))
            return 1.0
    
    def get_frd(self, omega:list[float]) -> control.FRD:
        self.set_frd(z=self.get_zeros(), p=self.get_poles(), k=self.get_gain(), omega=omega)
        return self.frd
        
    def __init__(self):
        self.properties = __class__._Properties()

class Amplifier_Rolloff_Filter(Abstract_Block):
    class _Properties:
        def __init__(self):
            self.R__ohm = 1.0
            self.C__uF = 1.0

    def get_zeros(self) -> list[complex]:
        return []

    def get_poles(self) -> list[complex]:
        try:
            return [-1.0/(self.properties.R__ohm*self.properties.C__uF/10**6)]
        except:
            return []

    def get_gain(self) -> float:
        try:
            return 1.0/(self.properties.R__ohm*self.properties.C__uF/10**6)
        except Exception as e:
            print("An error occurred when computing the Amplifier Rolloff Filter: \"{}\"\nDefaulting to unity gain.".format(e))
            return 1.0
    
    def get_frd(self, omega:list[float]) -> control.FRD:
        self.set_frd(z=self.get_zeros(), p=self.get_poles(), k=self.get_gain(), omega=omega)
        return self.frd
    
    def __init__(self):
        self.properties = __class__._Properties()

class Current_Feedback_Low_Pass_Filter(Abstract_Block):
    class _Properties:
        def __init__(self):
            self.R__ohm = 1.0
            self.C__uF = 1.0

    def get_zeros(self) -> list[complex]:
        return []

    def get_poles(self) -> list[complex]:
        try:
            return [-1.0/(self.properties.R__ohm*self.properties.C__uF/10**6)]
        except:
            return []

    def get_gain(self) -> float:
        try:
            return 1.0/(self.properties.R__ohm*self.properties.C__uF/10**6)
        except Exception as e:
            print("An error occurred when computing the Current Feedback Low Pass Filter: \"{}\"\nDefaulting to unity gain.".format(e))
            return 1.0
    
    def get_frd(self, omega:list[float]) -> control.FRD:
        self.set_frd(z=self.get_zeros(), p=self.get_poles(), k=self.get_gain(), omega=omega)
        return self.frd
    
    def __init__(self):
        self.properties = __class__._Properties()

class Mechanical_Plant(Abstract_Block):
    # FR
    # https://www.uml.edu/docs/Second-Theory_tcm18-190098.pdf
    # Poles and zeros
    # 2nd order system representation with mass, damping, stiffness or plant response
    # natural frequency takes w = sqrt(stiffness/mass)
    # damping ratio = damping / (2*mass*natural_frequency)
    # https://lpsa.swarthmore.edu/SecondOrder/SOI.html
    # TF = w_n^2 / (s^2 + 2*damping_ratio*w_n*s + w_n^2)

    class _Properties:
        def __init__(self):
            self.Block_Representation = BlockRepresentation.Parameters
            self.Frequency_Response = FR()
            self.Mass__kg = 10.0
            self.Damping__N___s__m = 0.5
            self.Stiffness__N__mm = 1

    def get_zeros(self) -> list[complex]:
        return []
    
    def get_poles(self) -> list[complex]:
        if self.properties.Mass__kg == 0.0:
            return []
        else:
            try:
                w_n = math.sqrt(self.properties.Stiffness__N__mm*1000/self.properties.Mass__kg)
                damping_ratio = self.properties.Damping__N___s__m / (2.0*self.properties.Mass__kg*w_n)
                #print("Damping ratio {} w_n {} stiff {} mass {}".format(damping_ratio, w_n, self.properties.Stiffness, self.properties.Mass__kg))
                a = 1.0
                b = 2*damping_ratio*w_n**2
                c = w_n**2
                return quadratic_formula(a, b, c)
            except:
                return []

    def get_gain(self) -> float:
        try:
            return self.properties.Stiffness__N__mm*1000/self.properties.Mass__kg
        except Exception as e:
            print("An error occurred when computing the Mechanical Plant: \"{}\"\nDefaulting to unity gain.".format(e))
            return 1.0
        
    def get_frd(self, omega:list[float]) -> control.FRD:
        # Depending on the configuration, set the FRD accordingly.
        if self.properties.Block_Representation == BlockRepresentation.Parameters:
            if self.properties.Stiffness__N__mm == 0.0:
                tf = control.tf([1], [self.properties.Mass__kg, 0, 0])
                frd = control.frd(tf, omega, smooth=True)
                self.set_frd(frd=frd)
                return frd
            else:
                try:
                    w_n = math.sqrt(self.properties.Stiffness__N__mm*1000/self.properties.Mass__kg)
                    damping_ratio = self.properties.Damping__N___s__m / (2.0*self.properties.Mass__kg*w_n)
                    tf = control.tf([w_n**2], [1, 2*w_n*damping_ratio, w_n**2])
                    frd = control.frd(tf, omega, smooth=True)
                    self.set_frd(frd=frd)
                    return frd
                except:
                    # Likely a divide by zero.
                    tf = control.tf([1], [1])
                    frd = control.frd(tf, omega, smooth=True)
                    self.set_frd(frd=frd)
                    return frd
        elif self.properties.Block_Representation == BlockRepresentation.FrequencyResponse:
            if self.properties.Frequency_Response.imported_frd is not None:

                # Re-evaluate frd at the passed in frequencies.
                frd = control.frequency_response(self.properties.Frequency_Response.imported_frd, omega)
                frd_new = control.frd(frd.response, frd.frequency, smooth=True)
                self.set_frd(frd=frd_new)

        return self.frd

    def __init__(self):
        self.properties = __class__._Properties()
#end region

#region Functions
def is_loop(thing) -> bool:
    """ If the object provided is a child of Abstract_Loop.

    Args:
        thing (_type_): The thing to check the type of.

    Returns:
        bool: True, if the type matches. False, otherwise.
    """
    return is_T(thing, Abstract_Loop)

def is_block(thing) -> bool:
    """ If the object provided is a child of Abstract_Block.

    Args:
        thing (_type_): The thing to check the type of.

    Returns:
        bool: True, if the type matches. False, otherwise.
    """
    return is_T(thing, Abstract_Block)
    
def is_T(thing, class_type:type) -> bool:
    """ Checks to see if the object is of the type requested.

    Args:
        thing (_type_): The thing to check.
        class_type (type): The type to check for.

    Returns:
        bool: True, if the type matches. False, otherwise.
    """
    if isinstance(thing, type):
        return issubclass(thing, class_type)
    else:
        return issubclass(type(thing), class_type)
#end region