import cmath
import control
import math
import numpy as np
import warnings

import Globals


def lighter(color, percent:float) -> np.array:
    """ Generates a lighter version of incoming RGB color. Assumes color is rgb between (0, 0, 0) and (255, 255, 255)

    Args:
        color (_type_): The RGB color to make lighter.
        percent (float): How much lighter to make the color.

    Returns:
        np.array: The lighter color.
    """
    color = np.array(color)
    white = np.array([255, 255, 255])
    vector = white-color
    return color + vector * percent

def make_color_more_grey(rgb, factor=0.35):
    """
    Mixes a color with grey, making it more grey.

    Args:
        rgb: A tuple representing the color in RGB format (values from 0 to 255).
        factor: A value between 0 and 1 representing the blending factor 
                (0: no change, 1: completely grey).

    Returns:
        A tuple representing the modified color in RGB format.
    """
    r, g, b = rgb
    grey_value = int(sum(rgb) / 3)
    new_r = int(r * (1 - factor) + grey_value * factor)
    new_g = int(g * (1 - factor) + grey_value * factor)
    new_b = int(b * (1 - factor) + grey_value * factor)
    return (new_r, new_g, new_b)

def hex_to_rgb(hex:str) -> tuple[int, int, int]:
    """ Converts a hex number to RGB.

    Args:
        hex (str): The hex string to convert.

    Returns:
        tuple[int, int, int]: [The RGB values]
    """
    return tuple(int(hex[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb:tuple[int,int,int]) -> str:
    """ Converts a RGB number to hex.

    Args:
        rgb (tuple[int, int, int])): The RGB tuple to convert.

    Returns:
        str: The hex string.
    """
    def clamp(x): 
        return max(0, min(int(x), 255))

    return "#{0:02x}{1:02x}{2:02x}".format(clamp(rgb[0]), clamp(rgb[1]), clamp(rgb[2]))

def hertz_to_radian(frequencies:list[float]) -> list[float]:
    """ Converts an array of frequencies from hertz to radian.

    Args:
        frequencies (list[float]): The frequencies to convert.

    Returns:
        list[float]: The converted frequencies.
    """
    return np.multiply(frequencies, 2*np.pi)

def radian_to_hertz(frequencies:list[float]) -> list[float]:
    """ Converts an array of frequencies from radian to hertz.

    Args:
        frequencies (list[float]): The frequencies to convert.

    Returns:
        list[float]: The converted frequencies.
    """
    return np.multiply(frequencies, 1/(2*np.pi))

def decibels_to_complex(magnitude:list[float], phase:list[float]) -> list[complex]:
    """ Converts the magnitude and phase to complex number.

    Args:
        magnitude (list[float]): The magnitudes to convert.
        phase (list[float]): The phases to convert.

    Returns:
        list[complex]: A list of complex numbers. 
    """
    amplitude = control.db2mag(np.array(magnitude))
    complex_number = np.multiply(amplitude, np.exp(np.multiply(complex(0, 1), np.multiply(phase, np.pi/180))))
    return complex_number

def complex_to_magnitude_and_phase(complex:list[complex]) -> tuple[list[float], list[float]]:
    """ Converts complex numbers to magnitude and phase.

    Args:
        complex (list[complex]): A list of complex numbers to convert.

    Returns:
        tuple[list[float], list[float]]: [The list of magnitudes, The list of phases]
    """
    try:
        magnitude = [0.0] * len(complex)
        phase = [0.0] * len(complex)
        for i in range(len(complex)):
            magnitude[i] = abs(complex[i])
            phase[i] = cmath.phase(complex[i])
        return [magnitude, phase]
    except:
        return [abs(complex), cmath.phase(complex)]

def to_dB(values:float) -> float:
    """ Converts one or more values to dB.

    Args:
        values (float): The values to convert.

    Returns:
        float: The converted values.
    """
    with warnings.catch_warnings():
        # Used to handle divide by zero warning.
        warnings.filterwarnings("ignore", category=RuntimeWarning)

        if (type(values) == float) or (type(values) == np.float64):
            values = [values]
        
        for i in range(len(values)):
            v = 20.0*np.log10(values[i])
            if math.isinf(v):
                v = math.nan
            values[i] = v

        if len(values) == 1:
            return values[0]
        else:
            return values
        
def wrap_phase(phase_degrees:list[float]) -> list[float]:
    """ Wraps phase around 0 and -360.

    Args:
        phase_degrees (list[float]): The phase in degrees.

    Returns:
        list[float]: The wrapped phase.
    """
    if (0 < phase_degrees) and (phase_degrees <= 180):
        phase_degrees -= 360
    return phase_degrees

def format_float(value:float, decimal_places:int=6) -> str:
    """ Formats a float to only display the number of decimal places.

    Args:
        value (float): The float to format.
        decimal_places (int, optional): The number of decimal places to display. Defaults to 6.

    Returns:
        str: The formatted string.
    """
    return str(round(value, decimal_places))

def quadratic_formula(a:float, b:float, c:float) -> tuple[complex, complex]:
    """ Performs the quadratic formula.

    Args:
        a (float): Coefficient A.
        b (float): Coefficient B.
        c (float): Coefficient C.

    Returns:
        tuple[complex, complex]: The roots.
    """
    return [(-b - cmath.sqrt(b**2 - 4*a*c))/(2*a), (-b + cmath.sqrt(b**2 - 4*a*c))/(2*a)]

def are_arrays_exactly_the_same(array1:list[float], array2:list[float]) -> bool:
    """ Checks to see if the arrays are exactly the same (length and values).

    Args:
        array1 (list[float]): Array 1 to compare.
        array2 (list[float]): Array 2 to compare.

    Returns:
        bool: True, if exactly the same. False, otherwise.
    """
    if len(array1) != len(array2):
        return False
    else:
        for i in range(len(array1)):
            if abs(array1[i] - array2[i]) > Globals.FUZZ:
                return False
        
        return True
    
def are_arrays_the_same(array1:list[float], array2:list[float]) -> bool:
    """ Checks to see if the arrays are exactly the same (length and values) according to a fuzz that changes with the number of decimal places
    thanks to floating point precision quirks.

    Args:
        array1 (list[float]): Array 1 to compare.
        array2 (list[float]): Array 2 to compare.

    Returns:
        bool: True, if exactly the same. False, otherwise.
    """
    if len(array1) != len(array2):
        return False
    else:
        for i in range(len(array1)):
            dynamic_fuzz = Globals.FUZZ * 10**places_before_decimal(array1[i])
            if abs(array1[i] - array2[i]) > dynamic_fuzz:
                #print("not the same {} = {} {}".format(i, array_to_fuzz[i], array_to_change_to[i]))
                return False
        
        return True
    
def places_before_decimal(number:float) -> int:
    """ Gets how many places are before the decimal point.

    Args:
        number (float): The number to check.

    Returns:
        int: The number of decimal places.
    """
    if number >= 1:
        return math.floor(math.log10(number)) + 1
    elif number <= -1:
        return math.floor(math.log10(abs(number))) + 1
    else:
        return 0
    
def find_float_in_array(array:list, value:float) -> int:
    """ Gets the index in the array where the float exists.

    Args:
        array (list): The array to check through.
        value (float): The value to look for.

    Returns:
        int: The index of the value. Returns -1 if not found.
    """
    # Finds the exactly index in array.
    for i in range(len(array)):
        if abs(array[i] - value) <= Globals.FUZZ:
            return i
        
    return -1

def enforce_frequency_rules(current_frequency:str, new_frequency:str) -> tuple[bool, bool, bool, list]:
    """ Enforces that the new frequencies given are compatible with the current frequencies.

    Args:
        current_frequency (str): The current frequencies in use.
        new_frequency (str): The new frequencies to use.
    Returns:
        tuple[bool, bool, bool, list]: [If the new frequencies are valid, If they are exactly the same, 
                                        If the new frequencies only overlap the current ones, The new overlapping range of frequencies]
    """
    # We don't like interpolation, must run responses with the same matching frequencies (there can be ranges that are too short).
    is_valid = False
    are_exactly_the_same = False
    overlap = False
    if (len(new_frequency) >= Globals.MIN_FREQUENCIES):
        # Seems okay so far.

        # Check the range of values that overlap exactly. The range must be contiguous.
        valid_new_freq_start = -1
        valid_new_freq_end = -1
        offset_into_main = -1
        last_valid_main_index = 0
        for i in range(len(new_frequency)):
            # Shortcut oob
            if abs(new_frequency[i] - current_frequency[0]) > Globals.FUZZ:
                if (new_frequency[i] < current_frequency[0]) or (new_frequency[i] > current_frequency[-1]):
                    continue
            
            # Check range.
            for j in range(last_valid_main_index, len(current_frequency)):
                if abs(new_frequency[i] - current_frequency[j]) <= Globals.FUZZ:
                    # Match
                    if valid_new_freq_start == -1:
                        valid_new_freq_start = i
                        offset_into_main = j
                        overlap = True

                    valid_new_freq_end = i
                    last_valid_main_index = j
                    break
                elif current_frequency[j] > new_frequency[i]:
                    # Passed the frequency we are checking for, break.
                    break
                else:
                    #print("not match", new_frequency[i])
                    pass
            
            # We did not find a match and we found a start, stop.
            if (valid_new_freq_end != i) and (valid_new_freq_start != -1):
                break

        if offset_into_main == -1:
            return [False, False, False, []]
        else:
            is_valid = True
            num_new_freq_match = valid_new_freq_end-valid_new_freq_start+1
            if (len(current_frequency) == len(new_frequency)) and (offset_into_main == 0) and (num_new_freq_match == len(current_frequency)):
                are_exactly_the_same = True
            
            overlapping_frequency = current_frequency[offset_into_main:offset_into_main+num_new_freq_match+1]
            if (len(overlapping_frequency) < Globals.MIN_FREQUENCIES):
                # Invalid.
                return [False, False, False, []]
            
            #print("valid overlapping ", len(overlapping_frequency), offset_into_main, num_new_freq_match)
            return [is_valid, are_exactly_the_same, overlap, overlapping_frequency]
    else:
        # Invalid.
        return [False, False, False, []]
