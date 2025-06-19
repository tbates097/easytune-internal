from enum import Enum
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt

import a1_interface
from Blocks import *
from Block_Layout import Block_Layout_With_Data
import Custom_QWidgets
from FRD_Data import FR_Type, Loop_Type
from Modules.File_Explorer_Module import Export_Type
from pyqt_ui import Ui_MainWindow

from Utils import enforce_frequency_rules
 

class Block_Explorer_Module():
    """ The Block Explorer Module. This is composed of the Block Explorer and the Property Table.
    """
    def __init__(self, gui:Ui_MainWindow, set_line_data_from_frd_data, temporarily_show_easy_tune_plot):
        self.gui = gui
        self.set_line_data_from_frd_data = set_line_data_from_frd_data
        self.temporarily_show_easy_tune_plot = temporarily_show_easy_tune_plot
        self.property_table_rows = []
        
        # Block layouts.
        self.temporary_block_layout: Block_Layout_With_Data = None
        self.primary_block_layout = Block_Layout_With_Data(filename="New Response.fr")
        self.secondary_block_layouts = {} # filename:block_layout for faster searching.

        # Generate GUI (default to Servo Controller).
        self.selected_block = Servo_Controller.__name__.replace('_', ' ')
        self.generate_block_explorer()
        self.refresh_selected_block()

        # Events.
        self.gui.block_explorer.itemClicked.connect(self.get_selected_block)
        self.gui.capture_as_original.pressed.connect(self.capture_shaped)
        self.gui.restore_original.pressed.connect(self.restore_original)
    
    def generate_block_explorer(self):
        """ Generate the blocks explorer according to the primary block layout.
        """
        self.gui.block_explorer.clear()
        self.gui.block_explorer.setEnabled(False)
        self.create_block_explorer_items(self.primary_block_layout.shaped.user_facing_layout, self.gui.block_explorer)
        self.gui.block_explorer.expandAll()

        # Fills the block layout with information
        self.get_selected_block()
        self.enable_or_disable_treeview_items()

        for i in range(len(self.property_table_rows)):
            row = self.property_table_rows[i]
            row.refresh()

        # Update the plot
        self.gui.block_explorer.setEnabled(True)
        self.update_modules()
        self.set_line_data_from_frd_data(self.primary_block_layout)

    def initialize_primary_block_layout_from_a1_data(self, a1_data, filename:str) -> None:
        """ Initializes a whole new primary block layout given some a1 data. This will always replace the primary block layout
        as there is only a single primary layout allowed at the moment.

        Args:
            a1_data (FrequencyResponseResult): The A1 data object to initialize a block layout with.
            filename (str): The filename that corresponds to the data object.
        """

        # Load EVERYTHING from an Automation1 FR file.
        self.primary_block_layout = Block_Layout_With_Data(a1_data, filename=filename)
        index = self.gui.loop_response.findText(self.primary_block_layout.loop_type.name, Qt.MatchFixedString)
        if index >= 0:
            self.gui.loop_response.setCurrentIndex(index) # Set either to display current or servo loop.

        # Re-create the block explorer.
        self.generate_block_explorer()

    def initialize_secondary_block_layout_from_a1_data(self, a1_data, filename:str) -> bool:
        """ Initializes a whole new secondary block layout given some a1 data. This will add or replace
        a secondary block layout that corresponds to the given filename iff the frequency range is valid.

        Args:
            a1_data (FrequencyResponseResult): The A1 data object to initialize a block layout with.
            filename (str): The filename that corresponds to the data object.

        Returns:
            bool: True, if a block layout was added or removed. False, otherwise.
        """

        # Add or replace all block layout information.
        secondary_block_layout = Block_Layout_With_Data(a1_data, filename=filename, is_secondary=True)

        [is_valid, are_the_same, overlap, overlap_freq] = \
            enforce_frequency_rules(self.primary_block_layout.frequency_radians, secondary_block_layout.frequency_radians)
        if is_valid:
            self.primary_block_layout.frequency_radians = overlap_freq
            secondary_block_layout.frequency_radians = overlap_freq
        else:
            return False

        # Update the plot
        self.secondary_block_layouts[filename] = secondary_block_layout
        self.update_modules(secondary_layout_file=filename)
        #self.set_freq(self.secondary_block_layouts[filename])

        return True

    def delete_secondary_block_layout_from_a1_data(self, filename:str) -> None:
        """ Deletes the secondary block layout if it exists.

        Args:
            filename (str): The filename to delete.
        """
        if self.does_secondary_layout_exist(filename):
            # Delete this information from the plotter.
            self.set_line_data_from_frd_data(self.secondary_block_layouts[filename], delete_secondary=True)

            # Delete block layout information.
            del self.secondary_block_layouts[filename]

    def does_secondary_layout_exist(self, filename:str) -> bool:
        """ Determines if the secondary file exists in the block layout already.

        Args:
            filename (str): The filename to check for.

        Returns:
            bool: True, if found. False, otherwise.
        """
        if filename in self.secondary_block_layouts.keys():
            return True
        else:
            return False

    def display_optimized_controller(self, servo_controller:Servo_Controller) -> None:
        """ Temporarily displays the optimized EasyTune controller by swapping out the original controller with the
        shaped controller before running EasyTune and by swapping out the shaped controller with the EasyTune shaped
        controller so that the user can compare their differences.

        Args:
            servo_controller (Servo_Controller): The controller to temporarily display as the new shaped controller.
        """
        # Takes the optimized controller and updates the gui accordingly.

        # Save a copy of the shaped and original data because we will temporarily:
        # 1.) Replace the original with shaped.
        # 2.) Replace the shaped with optimized.
        # 3.) Display the servo controller tree view and a temporary plot of the OL response.

        # Keep a copy of the current output.
        self.temporary_block_layout = Block_Layout_With_Data()
        self.temporary_block_layout.copy_in(self.primary_block_layout, copy_shaped=True, copy_original=True, copy_a1_data=True)

        # Save the shaped as original.
        self.primary_block_layout.copy_shaped_to_original()

        # Save the new optimized controller in shaped.
        self.primary_block_layout.shaped.block_dictionary[Servo_Controller] = copy.deepcopy(servo_controller)
        
        self.primary_block_layout.update_shaped_frds()

        self.temporary_selected_block = self.selected_block
        shaped_block = self.primary_block_layout.shaped.find_loop_or_block_by_type(Servo_Controller)
        original_block = self.primary_block_layout.original.find_loop_or_block_by_type(Servo_Controller)
        self.set_selected_block(shaped_block, original_block)
        self.gui.property_table_header.setText(Servo_Controller.__name__.replace('_',' '))
        self.temporarily_show_easy_tune_plot()
        self.set_line_data_from_frd_data(self.primary_block_layout)

    def accept_optimized_controller(self) -> None:
        """ If called, "accepts" the optimized EasyTune controller as the new shaped controller. This replaces
        the previous shaped controller that existed prior to running EasyTune with the EasyTuned controller.
        Do note, that the original controller will revert back to the original controller that existed prior to
        running EasyTune.
        """
        # Accept the optimized controller changes by restoring only the original controller that was stored temporarily. This
        # is when the user says yes.
        if self.temporary_block_layout is not None:
            self.primary_block_layout.copy_in(self.temporary_block_layout, copy_shaped=False, copy_original=True, copy_a1_data=True)

            self.get_selected_block()
            self.temporarily_show_easy_tune_plot(show=False)
            self.set_line_data_from_frd_data(self.primary_block_layout)

    def restore_pre_optimized_controller(self):
        """ If called, "restores" both the shaped and original controllers that existed prior to running EasyTune.
        """
        # Restore both controllers that were stored temporarily. This is when user says no.
        if self.temporary_block_layout is not None:
            self.primary_block_layout.copy_in(self.temporary_block_layout, copy_shaped=True, copy_original=True, copy_a1_data=True)

            self.get_selected_block()
            self.temporarily_show_easy_tune_plot(show=False)
            self.set_line_data_from_frd_data(self.primary_block_layout)

    def restore_original(self) -> None:
        """ Not to be confused with *_optimized_controller() functions, this function implements the "Restore" button by
        overwriting the shaped layout with the original layout.
        """
        can_continue = False
        def should_continue(button):
            nonlocal can_continue
            if button.text() == "&Yes":
                can_continue = True
            else:
                can_continue = False

        popup = QMessageBox()
        popup.setWindowTitle("Restore Original Layout")
        popup.setIcon(QMessageBox.Question)
        popup.setText("Would you like to continue? This is action is irreversible.")
        popup.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        popup.setDefaultButton(QMessageBox.Yes)
        popup.buttonClicked.connect(should_continue)
        popup.exec_()

        if can_continue:
            self.primary_block_layout.copy_original_to_shaped()
            self.refresh_selected_block()
            self.update_modules()

    def capture_shaped(self):
        """ Not to be confused with *_optimized_controller() functions, this function implements the "Capture" button by
        overwriting the original layout with the shaped layout.
        """
        can_continue = False
        def should_continue(button):
            nonlocal can_continue
            if button.text() == "&Yes":
                can_continue = True
            else:
                can_continue = False

        popup = QMessageBox()
        popup.setWindowTitle("Capture Shaped Layout as the Original Layout")
        popup.setIcon(QMessageBox.Question)
        popup.setText("Would you like to continue? This is action is irreversible.")
        popup.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        popup.setDefaultButton(QMessageBox.Yes)
        popup.buttonClicked.connect(should_continue)
        popup.exec_()

        if can_continue:
            self.primary_block_layout.copy_shaped_to_original()
            self.refresh_selected_block()
            self.set_line_data_from_frd_data(self.primary_block_layout, regen_original=True)

    def save_block_layout_to_fr_result(self, export_type:Export_Type):
        """ Saves the current block layout as an A1 data object for writing out to file.

        Args:
            export_type (Export_Type): The export type.

        Returns:
            FrequencyResponseResult: The A1 data object to write out.
        """
        if self.primary_block_layout.loop_type == Loop_Type.Servo:
            frd = self.primary_block_layout.frd_data[Loop_Type.Servo][FR_Type.Servo_Open_Loop].shaped
        elif self.primary_block_layout.loop_type == Loop_Type.Current:
            frd = self.primary_block_layout.frd_data[Loop_Type.Current][FR_Type.Current_Open_Loop].shaped

        if export_type == Export_Type.Shaped_Response:
            # Treat the shaped response as the original response.
            data = a1_interface.get_a1_data_from_block_layout(self.primary_block_layout.shaped, self.primary_block_layout.a1_data, to_original=True)

            # Replace the original response data.
            data = a1_interface.replace_open_loop_response_data(data, frd)
        else:
            # Treat the shaped response as the shaped response.
            data = a1_interface.get_a1_data_from_block_layout(self.primary_block_layout.shaped, self.primary_block_layout.a1_data)

            # Don't need to replace any response data.

        return data

    def enable_or_disable_treeview_items(self):
        """ Enables or disables the block explorer tree items based on the block representation actively selected. For example,
        if the user represents the Servo Plant with the frequency response collected, then all plants and loops below it are unable
        to be selected.
        """
        iterator = QTreeWidgetItemIterator(self.gui.block_explorer)
        loop_and_blocks = Abstract_Loop.__subclasses__() + Abstract_Block.__subclasses__()
        parent_loop: Abstract_Loop = None
        start_disabling = False
        while iterator.value():
            tree_widget_item = iterator.value()
            loop_or_block_name = tree_widget_item.text(0).replace(' ', '_')
            iterator += 1
            #print("tree item = {} parent={} start_disable={}".format(loop_or_block_name, parent_loop, start_disabling))
            disable = False
            if start_disabling:
                for loop_or_block in loop_and_blocks:
                    if loop_or_block_name == loop_or_block.__name__:
                        if self.primary_block_layout.shaped.is_in_loop(parent_loop, loop_or_block):
                            disable = True
                        break
            
            if disable:
                tree_widget_item.setFlags(Qt.ItemIsSelectable)
            else:
                tree_widget_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

            for loop in Abstract_Loop.__subclasses__():
                if start_disabling:
                    break

                if loop_or_block_name == loop.__name__:
                    loop_object: Abstract_Loop = self.primary_block_layout.shaped.loop_dictionary[loop]
                    parent_loop = loop
                    
                    if "properties" in dir(loop_object):
                        for property_name in dir(loop_object.properties):
                            property_value = getattr(loop_object.properties, property_name)

                            if type(property_value) == BlockRepresentation:
                                # Has block representation. Disabled everything below this object.
                                if property_value == BlockRepresentation.FrequencyResponse:
                                    start_disabling = True
                                    break
    
    def copy_layout_and_update_modules(self, shaped_to_original=False):
        """ Doesn't appear to be used anywhere. This likely can be removed.
        """
        # Copy layouts and FRDs.
        if shaped_to_original:
            self.primary_block_layout.copy_shaped_to_original()
        else:
            self.primary_block_layout.copy_original_to_shaped()

        # Update block layout module.
        self.enable_or_disable_treeview_items()
        self.get_selected_block()

        # Update plot module.
        self.set_line_data_from_frd_data(self.primary_block_layout)

    def create_block_explorer_items(self, dictionary_item:dict, parent_item:QTreeWidgetItem) -> QTreeWidgetItem:
        """ Creates the block explorer tree items that are attached to the parent tree item based off of
        the structure of a dictionary where items in a dictionary are added and nested dictionaries are further traversed.
        This is called recursively.

        Args:
            dictionary_item (dict): The dictionary to fill this tree item with.
            parent_item (QTreeWidgetItem): The tree item to fill.

        Returns:
            QTreeWidgetItem: The filled out tree item.
        """
        if not hasattr(dictionary_item, "keys"):
            # Last item in the dictionary. Do nothing.
            return
        else:
            for key in dictionary_item.keys():
                top_level_item = QTreeWidgetItem()
                top_level_item.setText(0, key.replace('_', ' '))
                self.create_block_explorer_items(dictionary_item[key], top_level_item)
                
                # Attach the top-level item to the parent item.
                if type(parent_item) == QTreeWidget:
                    parent_item.addTopLevelItem(top_level_item)
                else:
                    parent_item.addChild(top_level_item)

    def update_modules(self, secondary_layout_file:str=None) -> None:
        """ Updates the block explorer and plot modules by computing the shaped FRDs and then passing that to the plot module. This is
        called and used to react to all gui changes and updates in the block property table.

        Args:
            secondary_layout_file (str, optional): The filename that corresponds to a valid secondary block layout to re-evaluate. Defaults to None.
        """
        if secondary_layout_file:
            primary_servo_controller = self.primary_block_layout.shaped.find_loop_or_block_by_type(Servo_Controller)

            self.secondary_block_layouts[secondary_layout_file].update_shaped_frds(primary_servo_controller)
            self.set_line_data_from_frd_data(self.secondary_block_layouts[secondary_layout_file])
        else:
            self.primary_block_layout.update_shaped_frds()
            self.set_line_data_from_frd_data(self.primary_block_layout)

            # Update secondary block layouts by swapping out their controller response (servo only) and locking their
            # servo plant response.
            primary_servo_controller = self.primary_block_layout.shaped.find_loop_or_block_by_type(Servo_Controller)
            for filename in self.secondary_block_layouts.keys():
                self.secondary_block_layouts[filename].update_shaped_frds(primary_servo_controller)
                self.set_line_data_from_frd_data(self.secondary_block_layouts[filename])

        self.enable_or_disable_treeview_items()
        #self.get_selected_block() # dont call this since this is the event that triggers this
        
    def refresh_selected_block(self) -> None:
        """ Refreshes the selected block in the block explorer by reloading the block property table.
        """
        if self.selected_block is not None:
            shaped_block = self.primary_block_layout.shaped.find_loop_or_block_by_name(self.selected_block)
            original_block = self.primary_block_layout.original.find_loop_or_block_by_name(self.selected_block)
            self.set_selected_block(shaped_block, original_block)

    def set_selected_block(self, shaped_block, original_block) -> None:
        """ Sets and fills out the block property table according to the loop or block selected. The shaped loop or block provides the current
        shaped values while the original loop or block provides the original values to display.

        Args:
            shaped_block (Abstract_Loop or Abstract_Block): The shaped loop or block that was selected.
            original_block (Abstract_Loop or Abstract_Block): The original loop or block that was selected.
        """
        if is_loop(shaped_block) or is_block(shaped_block):
            self.gui.property_table_header.setText("None")
            self.property_table_rows.clear()
            self.gui.property_table.clear()

            self.generate_property_table(shaped_block, original_block)
            
            self.gui.property_table_header.setText(self.selected_block)
            header = self.gui.property_table.header()
            self.gui.property_table.setColumnWidth(0, 150)
            #header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(0, QHeaderView.Interactive)

            header.setSectionResizeMode(2, QHeaderView.Stretch)
            header.setSectionResizeMode(2, QHeaderView.Interactive)
            self.gui.property_table.expandAll()
    
    def get_selected_block(self) -> None:
        """ Gets the currently selected block according to the block explorer. This also updates the block property table
        iff anything is selected.
        """
        items = self.gui.block_explorer.selectedItems()

        # Enforce single item selecting.
        if len(items) > 1:
            raise RuntimeError("Multi-item selecting for the block explorer is not supported!")
        else:
            if len(items) != 0:
                self.selected_block = items[0].text(0)

        # Clear the entire table.
        self.gui.property_table_header.setText("None")
        self.property_table_rows.clear()
        self.gui.property_table.clear()

        if self.selected_block is None:
            return
        
        shaped_block = self.primary_block_layout.shaped.find_loop_or_block_by_name(self.selected_block)
        original_block = self.primary_block_layout.original.find_loop_or_block_by_name(self.selected_block)
        self.set_selected_block(shaped_block, original_block)

    def generate_property_table(self, shaped_block, original_block) -> None:
        """ This function ultimately generates the rows that populate the block property table.

        Args:
            shaped_block (Abstract_Loop or Abstract_Block): The loop or block to retrieve property information from.
            original_block (Abstract_Loop or Abstract_Block): The loop or block to retrieve property information from.
        """
        # Iterate through each property and determine if it is a block or just a property.
        if "properties" not in dir(shaped_block):
            if is_block(shaped_block):
                raise AssertionError("The {} model does not contain any properties!".format(shaped_block))
        else:
            # The model has properties. Process them based off of type (e.g., float, bool, Filter, etc.)
            for property_name in shaped_block.properties.__dict__: # NOTE: dir() sorts __dict__ alphabetically.
                property_value = getattr(shaped_block.properties, property_name)
                # print("pv", property_value, type(property_value), inspect.isclass(type(property_value)) )

                # Ignore special properties.
                if property_name.startswith("__") and property_name.endswith("__"):
                    continue
                elif issubclass(type(property_value), Abstract_Block):
                    # Another nested block. Go deeper.

                    original_block_nested = getattr(shaped_block.properties, property_name)
                    self.generate_property_table(property_value, original_block_nested)
                    continue
                
                top_level_item = QTreeWidgetItem()
                self.gui.property_table.addTopLevelItem(top_level_item)

                if type(property_value) == bool:
                    table_row = Custom_QWidgets.Check_Box_Property_Table_Row(self.gui, top_level_item, shaped_block.properties, original_block.properties, \
                                                                                property_name, change_event=self.update_modules)
                    self.property_table_rows.append(table_row)
                elif (type(property_value) == int) or (type(property_value) == float):
                    # Current Value.
                    table_row = Custom_QWidgets.Line_Edit_Property_Table_Row(self.gui, top_level_item, shaped_block.properties, original_block.properties, \
                                                                                property_name, change_event=self.update_modules)
                    self.property_table_rows.append(table_row)
                elif issubclass(type(property_value), Enum):
                    table_row = Custom_QWidgets.Combo_Box_Property_Table_Row(self.gui, top_level_item, shaped_block.properties, original_block.properties, \
                                                                            property_name, change_event=self.update_modules)
                    self.property_table_rows.append(table_row)
                    pass
                elif (type(property_value) == list) and (type(property_value[0]) == Filter_Model):
                    table_row = Custom_QWidgets.Filter_Property_Table_Row(self.gui, top_level_item, shaped_block.properties, original_block.properties, \
                                                                        property_name, change_event=self.update_modules)
                    self.property_table_rows.append(table_row)
                elif  (type(property_value) == Enhanced_Tracking_Control):
                    table_row = Custom_QWidgets.ETC_Property_Table_Row(self.gui, top_level_item, shaped_block.properties, original_block.properties, \
                                                                        property_name, change_event=self.update_modules)
                    self.property_table_rows.append(table_row)
                elif (type(property_value) == FR):
                    table_row = Custom_QWidgets.Ansys_Frequency_Response_Property_Table_Row(self.gui, top_level_item, shaped_block.properties, original_block.properties, \
                                                                        property_name, change_event=self.update_modules)
                    self.property_table_rows.append(table_row)
                else:
                    raise ValueError("The {} property has an unsupported {} type! Value={}".format(property_name, type(property_value).__name__, property_value))

    def text_changed_event(self, model_prop , widget, property):
        """ This function doesn't appear to be used and likely can be removed.
        """
        setattr(model_prop, property, widget.text())
