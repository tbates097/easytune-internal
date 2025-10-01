import sys
import os
import json

sys.path.append(r"K:\10. Released Software\Shared Python Programs\production-2.1")
from GenerateMCD_v2 import AerotechController

def extract_mcd_params(mcd_path, mcd_name):
    """Worker function to extract MCD parameters using specific DLL version"""
    try:
        ms_params = AerotechController(mcd_name)

        ms_params.initialize()

        #read_from_file = ms_params.MachineControllerDefinition.GetMethod("ReadFromFile")
        #mcd_obj = ms_params._read_mcd_from_file(mcd_path)

        ms_mcd_obj, _, _ = ms_params.calculate_from_current_mcd(mcd_path)
        print("About to call inspect_mcd_object")
        servo_params, feedforward_params = ms_params.inspect_mcd_object(ms_mcd_obj)
        print("Returned from inspect_mcd_object")

        return servo_params, feedforward_params
    except Exception as e:
        print(f'error: {str(e)}')
        return None, None

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(1)
        
    mcd_path = sys.argv[1]
    mcd_name = sys.argv[2]
    print(f"mcd_path: {mcd_path}, mcd_name: {mcd_name}")
    servo_params, feedforward_params = extract_mcd_params(mcd_path, mcd_name)
    if servo_params is None or feedforward_params is None:
        print("Failed to extract parameters from MCD.")
        sys.exit(1)
    print(json.dumps({
        "servo_params": servo_params,
        "feedforward_params": feedforward_params
    }))

