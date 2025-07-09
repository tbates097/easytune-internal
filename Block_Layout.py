
import copy
import os
from PyQt5.QtWidgets import QMessageBox

import a1_interface
from Blocks import *
from FRD_Data import DEFAULT_FRD_DATA, LOOP_RESPONSES, Loop_Type, FR_Type
from Utils import enforce_frequency_rules

#region Classes
class Block_Layout():
    """ The block layout that represents the top level loop.
    """
    def __init__(self):
        self.top_level_loop = Servo_Loop()
        self.user_facing_layout = self.get_user_facing_layout(self.top_level_loop)
        self.loop_dictionary = self.get_loop_dictionary(self.top_level_loop)
        self.block_dictionary = self.get_block_dictionary(self.top_level_loop)

        #print("NEW BLOCK LAYOUT", self.top_level_loop, "\n\nLOOP DICTIONARY", self.loop_dictionary, "\n\n", self.top_level_loop, " | ", self.top_level_loop.blocks.Current_Loop, \
        #       "\n\nBLOCK DICTIONARY", self.block_dictionary, "\n\nUSER FACING DICTIONARY", self.user_facing_layout)

        if id(self.top_level_loop) != id(self.loop_dictionary[Servo_Loop]):
            raise MemoryError("The memory location of the servo loop does not match the location stored in the loop dictionary!")
        
        if id(self.top_level_loop.blocks.Servo_Plant.blocks.Current_Loop) != id(self.loop_dictionary[Current_Loop]):
            raise MemoryError("The memory location of the current loop does not match the location stored in the loop dictionary!")
        
    def get_loop_dictionary(self, loop:Abstract_Loop) -> dict:
        """ Gets all loops including itself as a flat dictionary (no nested dictionaries) for easier access to loop information.

        Args:
            loop (Abstract_Loop): The loop to start searching from.

        Returns:
            dict: A flat dictionary containing all loops that make up the block layout. The loops are keyed by their loop type and return a
                  reference to the loop of that type.
        """
        loops = {}
        if is_loop(loop):  
            loops[type(loop)] = loop

            # Search for any additional nested blocks.
            if "blocks" not in dir(loop):
                raise ReferenceError("The {} block does not contain any blocks!".format(loop))
            else:
                # The loop has blocks. Check their type.
                for property_name in dir(loop.blocks):
                    property_value = getattr(loop.blocks, property_name)

                    # Ignore special properties.
                    if property_name.startswith("__") and property_name.endswith("__"):
                        continue
                    elif is_loop(property_value):
                        # Continue with recursion because we found another loop.
                        loops |= self.get_loop_dictionary(property_value)
                    elif is_block(property_value):
                        # Is a block, do nothing.
                        pass
        else:
            raise NotImplementedError("The passed object is not a loop!")
        
        return loops
        
    def get_block_dictionary(self, loop_or_block) -> dict:
        """ Gets all blocks including itself as a flat dictionary (no nested dictionaries) for easier access to block information.

        Args:
            block (Abstract_Block): The block to start searching from.

        Returns:
            dict: A flat dictionary containing all blocks that make up the block layout. The blocks are keyed by their block type and return a
                  reference to the block of that type.
        """
        blocks = {}
        if is_loop(loop_or_block):
            # Search for any additional nested blocks.
            if "blocks" not in dir(loop_or_block):
                raise ReferenceError("The {} block does not contain any blocks!".format(loop_or_block))
            else:
                # The loop has blocks. Check their type.
                for property_name in dir(loop_or_block.blocks):
                    property_value = getattr(loop_or_block.blocks, property_name)

                    # Ignore special properties.
                    if property_name.startswith("__") and property_name.endswith("__"):
                        continue
                    elif is_loop(property_value):
                        # Continue with recursion because we found another loop.
                        blocks |= self.get_block_dictionary(property_value)
                    elif is_block(property_value):
                        # Is a block.
                        blocks[type(property_value)] = property_value
        else:
            raise NotImplementedError("The passed object is not a loop!")
        
        return blocks
        
    def get_user_facing_layout(self, loop:Abstract_Loop) -> dict:
        """ Gets a dictionary of the user facing layout that is used by the block explorer.

        Args:
            loop (Abstract_Loop): The loop to start generating the layout from.

        Returns:
            dict: A nested dictionary of all of the loops and blocks that make up the top level loop. The dictionaries are keyed by the loop or block type's name.
        """
        def get_layout(loop:Abstract_Loop) -> dict:
            """ Get a dictionary (can be nested) of this loop and below. This is user facing and is recursively called to generate the block explorer.

            Args:
                loop (Abstract_Loop): The loop to start searching from._

            Returns:
                dict: A nested dictionary of all of the loops and blocks that make up this loop. The dictionaries are keyed by the loop or block type's name.
            """
            layout = {}
            if is_loop(loop):
                # Search for any additional nested blocks.
                if "blocks" not in dir(loop):
                    raise ReferenceError("The {} block does not contain any blocks!".format(loop))
                else:
                    # The loop has blocks. Check their type.
                    for property_name in dir(loop.blocks):
                        property_value = getattr(loop.blocks, property_name)

                        # Ignore special properties.
                        if property_name.startswith("__") and property_name.endswith("__"):
                            continue
                        elif is_loop(property_value):
                            # Continue with recursion because we found another loop.
                            layout[type(property_value).__name__] = get_layout(property_value)
                        elif is_block(property_value):
                            # Add the block into the dictionary.
                            layout[type(property_value).__name__] = property_value
            else:
                raise NotImplementedError("The passed object is not a loop!")
            
            return layout
        
        user_facing_layout = { type(loop).__name__:get_layout(loop) }
        return user_facing_layout
        
    def get_all_blocks_as_list(self) -> list[Abstract_Block]:
        """ Gets a list of all blocks in the block layout.

        Returns:
            list[Abstract_Block]: A list of block objects.
        """
        def get_all_blocks(loop: Abstract_Loop) -> list[Abstract_Block]:
            """ Gets a list of all blocks in this loop.

            Args:
                loop (Abstract_Loop): The loop to search through.

            Returns:
                list[Abstract_Block]: A list of blocks found in this loop.
            """
            if is_loop(loop):
                blocks = []
                for property_name in dir(loop.blocks):
                    property_value = getattr(loop.blocks, property_name)

                    # Ignore special properties.
                    if property_name.startswith("__") and property_name.endswith("__"):
                        continue
                    elif is_loop(property_value):
                        blocks += get_all_blocks(property_value)
                    elif is_block(property_value):
                        blocks.append(property_value)

                return blocks
            else:
                return []

        loop = self.top_level_loop
        all_blocks = get_all_blocks(loop)
        return all_blocks
    
    def find_loop_or_block_by_name(self, name:str) -> Abstract_Block:
        """ Finds the loop or block by name.

        Args:
            name (str): The name of the block to search for.

        Returns:
            Abstract_Block: The block.
        """
        import sys
        name = name.replace(' ', '_')
        return self.find_loop_or_block_by_type(getattr(sys.modules[__name__], name))

    def find_loop_or_block_by_type(self, type) -> Abstract_Block:
        """ Finds the loop or block by type.

        Args:
            type (Abstract_Loop or Abstract_Block): The type of the loop or block to search for.

        Returns:
            Abstract_Loop or Abstract_Block: The loop or block.
        """
        if is_loop(type):
            return self.loop_dictionary[type]
        elif is_block(type):
            return self.block_dictionary[type]
        else:
            return None
        
    def is_in_loop(self, loop:Abstract_Loop, loop_or_block) -> bool:
        """ Checks to see if the loop or block is actually nested or contained within the loop.

        Args:
            loop (Abstract_Loop): The loop to search in.
            loop_or_block (_type_): The loop or block to search for.

        Returns:
            bool: True, if found. False, otherwise.
        """
        def find_loop_dictionary(dictionary) -> dict:
            """ Finds the dictionary that corresponds to a loop.

            Args:
                dictionary (_type_): Recursively used to search through.

            Returns:
                dict: The dictionary for that loop.
            """
            dictionary_to_return = {}

            for key in dictionary.keys():
                is_loop = True if hasattr(dictionary[key], "keys") else False

                if key == loop.__name__:
                    # Loop matches.
                    return dictionary[key]

                if is_loop:
                    dictionary_to_return = find_loop_dictionary(dictionary[key])

                    if len(dictionary_to_return) != 0:
                        break
  
            return dictionary_to_return

        def search_in_dictionary(dictionary:dict) -> bool:
            """ Search through this dictionary to see if the loop or block exists in this dictionary.

            Args:
                dictionary (_type_): Recursively used to search through.

            Returns:
                bool: True, if found. False, otherwise.
            """
            for key in dictionary.keys():
                is_loop = True if hasattr(dictionary[key], "keys") else False

                if key == loop_or_block.__name__:
                    return True
                else:
                    if is_loop:
                        found = search_in_dictionary(dictionary[key])

                        if found:
                            return True
                    
            return False
        
        # Find the loop dictionary first.
        loop_dictionary = find_loop_dictionary(self.user_facing_layout)
        return search_in_dictionary(loop_dictionary)

class Block_Layout_With_Data():
    """ Represents the block layout with additional metadata used to make the A1 frequency response files and
    holds a copy of the shaped and original responses associated with the layout.
    """
    def __str__(self) -> str:
        """Returns a readable string representation of the block layout"""
        return f"Block Layout (filename: {self.filename}, primary: {self.is_primary}, locked: {self.is_locked})"
    
    def __repr__(self) -> str:
        """Returns a detailed representation of the block layout"""
        return f"Block_Layout_With_Data(filename='{self.filename}', is_primary={self.is_primary}, is_locked={self.is_locked}, is_default={self.is_default_file})"
    
    def __init__(self, a1_data=None, filename="", is_secondary=False, is_locked=False):
        # Determine if we need to generate all FRDs from scratch.
        generate_from_scratch = True if a1_data is None else False
        self.is_default_file = generate_from_scratch

        # Primary Response? That means use this controller's gains when modifying and exporting.
        self.is_primary = not is_secondary

        # Is Locked. Do calls to update this block layout's frequency responses update the shaped response or not?
        self.is_locked = is_locked

        # Filename (if any).
        self.filename = filename

        # A1 Data.
        if a1_data is None:
            self.a1_data = a1_interface.get_a1_data_from_block_layout(Block_Layout())
        else:
            self.a1_data = a1_data

        # FRD Data.
        self.frd_data = copy.deepcopy(DEFAULT_FRD_DATA)

        # Block Layouts.
        self.shaped = a1_interface.get_block_layout_from_a1_data(self.a1_data)
        self.copy_shaped_to_original()

        # Prepare to generate or process frequency response data.
        servo_controller: Servo_Controller = self.shaped.find_loop_or_block_by_type(Servo_Controller)
        servo_plant: Servo_Plant = self.shaped.find_loop_or_block_by_type(Servo_Plant)
        current_controller: Digital_Current_Loop = self.shaped.find_loop_or_block_by_type(Digital_Current_Loop)
        current_plant: Current_Plant = self.shaped.find_loop_or_block_by_type(Current_Plant)

        if generate_from_scratch:
            # Starting from scratch loads in "Initial Model.fr" to fill in the block layout. Everything else is filled out after that.
            # NOTE: If there are values missing from the initial .fr files, this is where we can set the remaining initial values for all of the blocks.
            # NOTE: Make sure that the values set here are set according to its type! For example, for integers specify 1 and for floats specify 1.0. This
            # is important because the property table will generate different line edit types based off of if it is an int or float.
            amplifier_plant: Amplifier_Plant = self.shaped.find_loop_or_block_by_type(Amplifier_Plant)
            amplifier_plant.properties.K = current_controller.properties.Bus_Voltage__V / 2.0

            amplifier_rolloff_filter: Amplifier_Rolloff_Filter = self.shaped.find_loop_or_block_by_type(Amplifier_Rolloff_Filter)
            amplifier_rolloff_filter.properties.R__ohm = 1.0
            amplifier_rolloff_filter.properties.C__uF = 1.0

            #current_feedback_low_pass_filter: Current_Feedback_Low_Pass_Filter = self.shaped.find_loop_or_block_by_type(Current_Feedback_Low_Pass_Filter)
            #current_feedback_low_pass_filter.properties.R__ohm = 1.0
            #current_feedback_low_pass_filter.properties.C__uF = 1.0

            #motor_plant: Motor_Plant = self.shaped.find_loop_or_block_by_type(Motor_Plant)
            #motor_plant.properties.R__ohm = 1.0
            #motor_plant.properties.L__mH = 1.0
            #motor_plant.properties.Kt__N__A = 1.0

            # Set the overall servo plant to use the models.
            servo_plant.properties.Block_Representation = BlockRepresentation.Parameters
            current_plant.properties.Block_Representation = BlockRepresentation.Parameters

            self.loop_type = Loop_Type.Servo

            # Generate the default frequency range.
            # TODO: Add the ability to customize this range.
            self.frequency_radians = np.linspace(10*2*PI, 10000*2*PI, 1000)
        else:
            # Process real frequency response data.
            [self.loop_type, open_loop_frd] = a1_interface.get_frd_from_a1_data(self.a1_data)
            self.frequency_radians = open_loop_frd.frequency

            if self.loop_type == Loop_Type.Servo:
                self.frd_data[Loop_Type.Servo][FR_Type.Servo_Open_Loop].shaped = open_loop_frd

                # Set the overall servo plant to use the frequency response, not the models.
                servo_plant.properties.Block_Representation = BlockRepresentation.FrequencyResponse
                current_plant.properties.Block_Representation = BlockRepresentation.Parameters

                self.frd_data[Loop_Type.Servo][FR_Type.Servo_Plant].shaped = control.frd(self.frd_data[Loop_Type.Servo][FR_Type.Servo_Open_Loop].shaped \
                                                                                / servo_controller.get_frd(self.frequency_radians), smooth=True)
                self.frd_data[Loop_Type.Servo][FR_Type.Servo_Plant].original = copy.deepcopy(self.frd_data[Loop_Type.Servo][FR_Type.Servo_Plant].shaped)      
            elif self.loop_type == Loop_Type.Current:
                self.frd_data[Loop_Type.Current][FR_Type.Current_Open_Loop].shaped = open_loop_frd

                # Set the overall servo plant to use the frequency response, not the models.
                servo_plant.properties.Block_Representation = BlockRepresentation.Parameters
                current_plant.properties.Block_Representation = BlockRepresentation.FrequencyResponse

                self.frd_data[Loop_Type.Current][FR_Type.Current_Plant].shaped = control.frd(self.frd_data[Loop_Type.Current][FR_Type.Current_Open_Loop].shaped \
                                                                                / current_controller.get_frd(self.frequency_radians, servo_controller.properties.Drive_Frequency__hz), smooth=True)
                self.frd_data[Loop_Type.Current][FR_Type.Current_Plant].original = copy.deepcopy(self.frd_data[Loop_Type.Current][FR_Type.Current_Plant].shaped)

        # Store copy of imported A1 frequencies.
        self.original_frequency_radians = copy.deepcopy(self.frequency_radians)

        # Update FRDs.
        self.update_shaped_frds()

        # Save a copy of the shaped FRDs as original.
        self.copy_shaped_to_original()

    def copy_in(self, obj, copy_shaped=True, copy_original=True, copy_a1_data=False):
        """ Copies in the layout to this object.
        Args:
            obj (_type_): A block layout with data to copy into this object.
            copy_shaped (bool, optional): Whether to copy in the shaped layout and responses. Defaults to True.
            copy_original (bool, optional): Whether to copy in the original layout and responses.. Defaults to True.
            copy_a1_data (bool, optional): Whether to copy in the a1 data associated with this layout. Defaults to False.
        """
        obj: Block_Layout_With_Data = obj
        if copy_shaped:
            self.shaped = copy.deepcopy(obj.shaped)
            for loop in Loop_Type:
                for fr_type in LOOP_RESPONSES[loop]:
                    self.frd_data[loop][fr_type].shaped = copy.deepcopy(obj.frd_data[loop][fr_type].shaped)
        if copy_original:
            self.original = copy.deepcopy(obj.original)
            for loop in Loop_Type:
                for fr_type in LOOP_RESPONSES[loop]:
                    self.frd_data[loop][fr_type].original = copy.deepcopy(obj.frd_data[loop][fr_type].original)
        if copy_a1_data:
            self.a1_data = obj.a1_data.MemberwiseClone()

    def copy_shaped_to_original(self):
        """ Copies the shaped layout to the original layout.
        """
        self.original = copy.deepcopy(self.shaped)
        for loop in Loop_Type:
            for fr_type in LOOP_RESPONSES[loop]:
                self.frd_data[loop][fr_type].original = copy.deepcopy(self.frd_data[loop][fr_type].shaped)

    def copy_original_to_shaped(self):
        """ Copies the original layout to the shaped layout.
        """
        self.shaped = copy.deepcopy(self.original)
        for loop in Loop_Type:
            for fr_type in LOOP_RESPONSES[loop]:
                self.frd_data[loop][fr_type].shaped = copy.deepcopy(self.frd_data[loop][fr_type].original)

    def clear_shaped_frd_data(self):
        """ Clears the shaped FRD data stored.
        """
        for loop in Loop_Type:
            for fr_type in LOOP_RESPONSES[loop]:
                self.frd_data[loop][fr_type].shaped = None

    def update_shaped_frds(self, servo_controller:Servo_Controller=None) -> None:
        """ Updates all shaped FRDs. If a controller is provided, use that instead.

        Args:
            servo_controller (Servo_Controller, optional): The controller to use instead of the one in this block layout. Defaults to None.
        """
        if self.is_locked:
            return
        
        frequencies = self.frequency_radians

        servo_plant: Servo_Plant = self.shaped.find_loop_or_block_by_type(Servo_Plant)
        if servo_plant.properties.Block_Representation == BlockRepresentation.FrequencyResponse:
            # A1 plant response. There's nothing to check for.
            pass
        else:
            # Mechanical Plant check.
            use_mechanical_plant_frequency_instead_of_default = False
            mechanical_plant: Mechanical_Plant = self.shaped.find_loop_or_block_by_type(Mechanical_Plant)
            plant_frd = mechanical_plant.properties.Frequency_Response.imported_frd
            if (mechanical_plant.properties.Block_Representation == BlockRepresentation.FrequencyResponse):
                if (plant_frd is not None):
                    if self.is_default_file:
                        # If this is the default file, allow for the 1st real plant to define the frequency range.
                        is_valid = True
                        valid_frequencies = plant_frd.frequency
                        use_mechanical_plant_frequency_instead_of_default = True
                    else:
                        [is_valid, _, _, valid_frequencies] = enforce_frequency_rules(frequencies, plant_frd.frequency)

                    if not is_valid:
                        plant_file = os.path.basename(mechanical_plant.properties.Frequency_Response.filepath)
                        popup = QMessageBox()
                        popup.setWindowTitle("Mechanical Plant Import Error")
                        popup.setIcon(QMessageBox.Critical)
                        popup.setText("{} does not overlap or exactly match the frequencies defined by the primary response.".format(plant_file))
                        popup.setDefaultButton(QMessageBox.Ok)
                        popup.setInformativeText
                        popup.exec_()
                        return
                    else:
                        frequencies = valid_frequencies
            
            current_plant: Current_Plant = self.shaped.find_loop_or_block_by_type(Current_Plant)
            if current_plant.properties.Block_Representation == BlockRepresentation.Parameters:
                # Amplifier Plant check.
                amplifier_plant: Amplifier_Plant = self.shaped.find_loop_or_block_by_type(Amplifier_Plant)
                plant_frd = amplifier_plant.properties.Frequency_Response.imported_frd
                if amplifier_plant.properties.Block_Representation == BlockRepresentation.FrequencyResponse:
                    if plant_frd is not None:
                        if self.is_default_file and not use_mechanical_plant_frequency_instead_of_default:
                            # Default file and the mechanical plant DNE. Use the amplifier plant.
                            is_valid = True
                            valid_frequencies = plant_frd.frequency
                            use_mechanical_plant_frequency_instead_of_default = True
                        else:
                            [is_valid, _, _, valid_frequencies] = enforce_frequency_rules(frequencies, plant_frd.frequency)

                        if not is_valid:
                            plant_file = os.path.basename(amplifier_plant.properties.Frequency_Response.filepath)
                            popup = QMessageBox()
                            popup.setWindowTitle("Amplifier Plant Import Error")
                            popup.setIcon(QMessageBox.Critical)
                            popup.setText("{} does not overlap or exactly match the frequencies defined by the primary response.".format(plant_file))
                            popup.setDefaultButton(QMessageBox.Ok)
                            popup.exec_()
                            return
                        else:
                            frequencies = valid_frequencies

        # Update frequency range.
        self.frequency_radians = frequencies

        # Clear all shaped responses.
        self.clear_shaped_frd_data()

        """ If the servo plant is set to frequency response, then re-compute only the servo controller. """
        lock_servo_plant = False
        if servo_controller is None:
            # If no servo controller is provided (default case), then use this layout's controller.
            servo_controller: Servo_Controller = self.shaped.find_loop_or_block_by_type(Servo_Controller)
        else:
            # Servo controller was provided, lock this layout's servo plant.
            lock_servo_plant = True
        
        servo_plant: Servo_Plant = self.shaped.find_loop_or_block_by_type(Servo_Plant)
        current_controller: Digital_Current_Loop = self.shaped.find_loop_or_block_by_type(Digital_Current_Loop)
        current_plant: Current_Plant = self.shaped.find_loop_or_block_by_type(Current_Plant)

        # Compute these responses since these are always computed and displayed.
        self.frd_data[Loop_Type.Servo][FR_Type.Servo_Controller].shaped = servo_controller.get_frd(frequencies)
        self.frd_data[Loop_Type.Servo][FR_Type.Servo_Controller_Only].shaped = servo_controller.get_pid_controller_frd(frequencies)
        self.frd_data[Loop_Type.Servo][FR_Type.Servo_Filters].shaped = servo_controller.get_servo_filters_frd(frequencies)
        self.frd_data[Loop_Type.Servo][FR_Type.Servo_Feedforward].shaped = servo_controller.get_feedforward_frd(frequencies)
        self.frd_data[Loop_Type.Servo][FR_Type.Servo_Inverse_Feedforward].shaped = 1.0 / self.frd_data[Loop_Type.Servo][FR_Type.Servo_Feedforward].shaped
        
        if (servo_plant.properties.Block_Representation == BlockRepresentation.FrequencyResponse) or \
           (lock_servo_plant and (self.frd_data[Loop_Type.Servo][FR_Type.Servo_Plant].original is not None)):
            # Lock the servo plant and restore the response that was stored originally for this layout.
            self.frd_data[Loop_Type.Servo][FR_Type.Servo_Plant].shaped = copy.deepcopy(self.frd_data[Loop_Type.Servo][FR_Type.Servo_Plant].original)

            # Re-sample plant in-case the frequencies changed.
            #print(self.frd_data[LoopType.Servo][FR_Type.Servo_Plant].shaped.frequency, frequencies)
            #servo_plant = self.frd_data[LoopType.Servo][FR_Type.Servo_Plant].shaped.eval(frequencies)
            servo_plant = control.frd(self.frd_data[Loop_Type.Servo][FR_Type.Servo_Plant].shaped.response, \
                                      self.frd_data[Loop_Type.Servo][FR_Type.Servo_Plant].shaped.frequency, smooth=True)
            servo_plant = control.frequency_response(servo_plant, frequencies)

            # Servo Open-Loop.
            self.frd_data[Loop_Type.Servo][FR_Type.Servo_Open_Loop].shaped = \
                self.frd_data[Loop_Type.Servo][FR_Type.Servo_Controller].shaped * servo_plant

            # Servo Closed Loop.
            a = servo_plant * self.frd_data[Loop_Type.Servo][FR_Type.Servo_Feedforward].shaped * \
                self.frd_data[Loop_Type.Servo][FR_Type.Servo_Filters].shaped
            b = self.frd_data[Loop_Type.Servo][FR_Type.Servo_Open_Loop].shaped
            c = 1 + self.frd_data[Loop_Type.Servo][FR_Type.Servo_Open_Loop].shaped
            self.frd_data[Loop_Type.Servo][FR_Type.Servo_Closed_Loop].shaped = (a + b) / c

            # Servo Sensitivity.
            self.frd_data[Loop_Type.Servo][FR_Type.Servo_Sensitivity].shaped = \
                1.0 / (1.0 + self.frd_data[Loop_Type.Servo][FR_Type.Servo_Open_Loop].shaped)

            # Servo Complementary Sensitivity.
            self.frd_data[Loop_Type.Servo][FR_Type.Servo_Complementary_Sensitivity].shaped = \
                self.frd_data[Loop_Type.Servo][FR_Type.Servo_Sensitivity].shaped * self.frd_data[Loop_Type.Servo][FR_Type.Servo_Open_Loop].shaped

            # Servo Process Sensitivity.
            self.frd_data[Loop_Type.Servo][FR_Type.Servo_Process_Sensitivity].shaped = \
                self.frd_data[Loop_Type.Servo][FR_Type.Servo_Sensitivity].shaped * servo_plant
        else:
            # The servo plant is unlocked and so we need to compute the blocks starting from the innermost loop out.
            
            # Mechanical Plant.
            self.frd_data[Loop_Type.Servo][FR_Type.Mechanical_Plant].shaped = self.shaped.find_loop_or_block_by_type(Mechanical_Plant).get_frd(frequencies)
            
            """ Current Loop. """
            # Current Controller.
            self.frd_data[Loop_Type.Current][FR_Type.Current_Controller].shaped = current_controller.get_frd(frequencies, servo_controller.properties.Drive_Frequency__hz)

            # Current Feedforward.
            self.frd_data[Loop_Type.Current][FR_Type.Current_Feedforward].shaped = current_controller.get_feedforward_frd(frequencies, servo_controller.properties.Drive_Frequency__hz)

            # Current Inverse Feedforward.
            self.frd_data[Loop_Type.Current][FR_Type.Current_Inverse_Feedforward].shaped = 1.0 / self.frd_data[Loop_Type.Current][FR_Type.Current_Feedforward].shaped

            # Current Plant.
            if current_plant.properties.Block_Representation == BlockRepresentation.FrequencyResponse:
                self.frd_data[Loop_Type.Current][FR_Type.Current_Plant].shaped = self.frd_data[Loop_Type.Current][FR_Type.Current_Plant].original

                # Re-sample the current plant in case frequencies changed.
                current_plant = control.frequency_response(self.frd_data[Loop_Type.Current][FR_Type.Current_Plant].shaped, omega=frequencies)
            else:
                self.frd_data[Loop_Type.Current][FR_Type.Current_Plant].shaped = current_plant.get_frd(frequencies)
                current_plant = self.frd_data[Loop_Type.Current][FR_Type.Current_Plant].shaped

                # Amplifier Rolloff Filter.
                self.frd_data[Loop_Type.Current][FR_Type.Amplifier_Rolloff_Filter].shaped = \
                    self.shaped.find_loop_or_block_by_type(Amplifier_Rolloff_Filter).get_frd(frequencies)
                
                # Amplifier Plant.
                self.frd_data[Loop_Type.Current][FR_Type.Amplifier_Plant].shaped = \
                    self.shaped.find_loop_or_block_by_type(Amplifier_Plant).get_frd(frequencies)
                
                # Current Feedback Low Pass Filter.
                self.frd_data[Loop_Type.Current][FR_Type.Current_Feedback_Low_Pass_Filter].shaped = \
                    self.shaped.find_loop_or_block_by_type(Current_Feedback_Low_Pass_Filter).get_frd(frequencies)
                
                # Motor Plant.
                self.frd_data[Loop_Type.Current][FR_Type.Motor_Plant].shaped = \
                    self.shaped.find_loop_or_block_by_type(Motor_Plant).get_frd(frequencies)
                
            # Current Open-Loop.
            self.frd_data[Loop_Type.Current][FR_Type.Current_Open_Loop].shaped = \
                self.frd_data[Loop_Type.Current][FR_Type.Current_Controller].shaped * current_plant

            # Current Closed-Loop.
            a = current_plant * self.frd_data[Loop_Type.Current][FR_Type.Current_Feedforward].shaped
            b = self.frd_data[Loop_Type.Current][FR_Type.Current_Open_Loop].shaped
            c = 1 + self.frd_data[Loop_Type.Current][FR_Type.Current_Open_Loop].shaped
            self.frd_data[Loop_Type.Current][FR_Type.Current_Closed_Loop].shaped = (a + b) / c
            #self.frd_data[LoopType.Current][FR_Type.Current_Closed_Loop].shaped = \
            #    self.frd_data[LoopType.Current][FR_Type.Current_Open_Loop].shaped / \
            #        (1+self.frd_data[LoopType.Current][FR_Type.Current_Open_Loop].shaped)

            # Current Sensitivity.
            self.frd_data[Loop_Type.Current][FR_Type.Current_Sensitivity].shaped = \
                1.0 / (1.0 + self.frd_data[Loop_Type.Current][FR_Type.Current_Open_Loop].shaped)

            # Current Complementary Sensitivity.
            self.frd_data[Loop_Type.Current][FR_Type.Current_Complementary_Sensitivity].shaped = \
                self.frd_data[Loop_Type.Current][FR_Type.Current_Sensitivity].shaped * self.frd_data[Loop_Type.Current][FR_Type.Current_Open_Loop].shaped

            # Current Process Sensitivity.
            self.frd_data[Loop_Type.Current][FR_Type.Current_Process_Sensitivity].shaped = \
                self.frd_data[Loop_Type.Current][FR_Type.Current_Sensitivity].shaped * current_plant

            """ Servo Loop. """

            # Servo Plant.
            self.frd_data[Loop_Type.Servo][FR_Type.Servo_Plant].shaped = \
                self.frd_data[Loop_Type.Current][FR_Type.Current_Closed_Loop].shaped * \
                    self.shaped.find_loop_or_block_by_type(Motor_Plant).properties.Kt__N__A * self.frd_data[Loop_Type.Servo][FR_Type.Mechanical_Plant].shaped
            
            # Store a copy of the servo plant as the original iff we were able to import a current OL response
            # so that we have some plant to fallback on.
            if self.frd_data[Loop_Type.Servo][FR_Type.Servo_Plant].original is None:
                self.frd_data[Loop_Type.Servo][FR_Type.Servo_Plant].original = copy.deepcopy(self.frd_data[Loop_Type.Servo][FR_Type.Servo_Plant].shaped)

            # Servo Open-Loop.
            self.frd_data[Loop_Type.Servo][FR_Type.Servo_Open_Loop].shaped = \
                self.frd_data[Loop_Type.Servo][FR_Type.Servo_Controller].shaped * self.frd_data[Loop_Type.Servo][FR_Type.Servo_Plant].shaped

            # Servo Closed Loop.
            a = self.frd_data[Loop_Type.Servo][FR_Type.Servo_Plant].shaped * self.frd_data[Loop_Type.Servo][FR_Type.Servo_Feedforward].shaped * \
                self.frd_data[Loop_Type.Servo][FR_Type.Servo_Filters].shaped
            b = self.frd_data[Loop_Type.Servo][FR_Type.Servo_Open_Loop].shaped
            c = 1 + self.frd_data[Loop_Type.Servo][FR_Type.Servo_Open_Loop].shaped
            self.frd_data[Loop_Type.Servo][FR_Type.Servo_Closed_Loop].shaped = (a + b) / c

            # Servo Sensitivity.
            self.frd_data[Loop_Type.Servo][FR_Type.Servo_Sensitivity].shaped = \
                1.0 / (1.0 + self.frd_data[Loop_Type.Servo][FR_Type.Servo_Open_Loop].shaped)

            # Servo Complementary Sensitivity.
            self.frd_data[Loop_Type.Servo][FR_Type.Servo_Complementary_Sensitivity].shaped = \
                self.frd_data[Loop_Type.Servo][FR_Type.Servo_Sensitivity].shaped * self.frd_data[Loop_Type.Servo][FR_Type.Servo_Open_Loop].shaped

            # Servo Process Sensitivity.
            self.frd_data[Loop_Type.Servo][FR_Type.Servo_Process_Sensitivity].shaped = \
                self.frd_data[Loop_Type.Servo][FR_Type.Servo_Sensitivity].shaped * self.frd_data[Loop_Type.Servo][FR_Type.Servo_Plant].shaped
#end region