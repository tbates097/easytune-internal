import control
from enum import Enum, auto


#region Enums
class Loop_Type(Enum):
    # Autofocus = auto()
    Servo = auto()
    Current = auto()

class FR_Type(Enum):
    # The enums are sorted by numeric value. This determines the ordering in which they appear in the response checklist and plot color.
    Servo_Open_Loop = auto()
    Servo_Plant = auto()
    Servo_Sensitivity = auto()
    Servo_Complementary_Sensitivity = auto()
    Servo_Process_Sensitivity = auto()
    Servo_Feedforward = auto()
    Servo_Inverse_Feedforward = auto()
    Servo_Closed_Loop = auto()
    Servo_Controller = auto()

    Current_Open_Loop = auto()
    Current_Plant = auto()
    Current_Sensitivity = auto()
    Current_Complementary_Sensitivity = auto()
    Current_Process_Sensitivity = auto()
    Current_Feedforward = auto()
    Current_Inverse_Feedforward = auto()
    Current_Closed_Loop = auto()
    Current_Controller = auto()

    Servo_Controller_Only = auto()
    Servo_Filters = auto()
    Mechanical_Plant = auto()

    Amplifier_Plant = auto()
    Amplifier_Rolloff_Filter = auto()
    Motor_Plant = auto()
    Current_Feedback_Low_Pass_Filter = auto()

    def find_response_for_loop(loop: Loop_Type, response:str):
        for fr_type in LOOP_RESPONSES[loop]:
            if fr_type.name == (loop.name + "_{}".format(response)):
                return fr_type
        return None
#end region

#region Constants
LOOP_RESPONSES = {
    Loop_Type.Servo: list(set([enum for enum in FR_Type if enum.name.startswith("Servo")] + \
        [FR_Type.Servo_Controller_Only, FR_Type.Servo_Filters, FR_Type.Mechanical_Plant])),

    Loop_Type.Current: list(set([enum for enum in FR_Type if enum.name.startswith("Current")] + \
        [FR_Type.Amplifier_Plant, FR_Type.Amplifier_Rolloff_Filter, FR_Type.Motor_Plant, FR_Type.Current_Feedback_Low_Pass_Filter]))
}
DEFAULT_FRD_DATA = {}
""" The fr types that are supported by each loop type. """
#end region

#region Classes
class FRD_Data():
    """ This is the child structure that holds the shaped and original FRD. The parent structure that uses
    this is structured: FRD_DATA[LOOP][FR_TYPE][ORIGINAL/SHAPED] -> control.FRD
    """
    def __init__(self):
        self.original: control.FRD = None
        self.shaped: control.FRD = None
#end region

#region Functions
def get_user_facing_text(loop_type:Loop_Type=None, fr_type:FR_Type=None) -> str:
    """ Gets the user facing text of the enums provided. If both are provided, then strip out hte loop name from the fr name.

    Args:
        loop_type (Loop_Type, optional): The loop to convert or strip out of the fr name. Defaults to None.
        fr_type (FR_Type, optional): The fr to convert. Defaults to None.

    Returns:
        str: The user facing text for this loop/fr combo.
    """
    text = ""

    if (loop_type is not None) and (fr_type is not None):
        text = fr_type.name
        if text.startswith(loop_type.name):
            text = text[len(loop_type.name):] # Trim out loop name
    elif loop_type is not None:
        text = loop_type.name
    elif fr_type is not None:
        text = fr_type.name
    
    return text.replace('_', ' ').strip()

def initialize_default_frd_data():
    """ Initializes the default FRD data dictionary so that we can reset to this when clearing out data.
    """
    global DEFAULT_FRD_DATA
    for loop in Loop_Type:
        DEFAULT_FRD_DATA[loop] = {}
        for fr_type in LOOP_RESPONSES[loop]:
            DEFAULT_FRD_DATA[loop][fr_type] = FRD_Data()

        # Sort to be in alphabetical order.
        LOOP_RESPONSES[loop].sort(key=lambda e: e.value)

def is_supported_by_loop(loop:Loop_Type, fr_type:FR_Type) -> bool:
    """ Determines if the fr type is supported by this loop type.

    Args:
        loop (Loop_Type): The loop type to check if the fr type is supported.
        fr_type (FR_Type): The fr type to check to see is supported.

    Returns:
        bool: If the fr type is supported by this loop type.
    """
    if fr_type in LOOP_RESPONSES[loop]:
        return True
    else:
        return False
#end region

initialize_default_frd_data()