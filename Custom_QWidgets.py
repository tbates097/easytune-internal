""" This file contains all of the custom widgets used for this tool defined in either QtDesigner or in code. pyqt_ui.py imports the
promoted widgets defined in here.
"""
from abc import ABC, abstractmethod
from enum import Enum
from PyQt5.QtGui import QIntValidator, QDoubleValidator
from PyQt5.QtWidgets import *

from Blocks import *
import Globals
from pyqt_ui import Ui_MainWindow


class Property_Table_Header(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class Flat_Header_Button(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class C_QLabel(QLabel):
    def __init__(self, text):
        super().__init__()

        self.setText(text)
        self.setWordWrap(True)

class C_QPropertyLabel(QLabel):
    def __init__(self, property):
        super().__init__()

        # Format units.
        property_label = property
        if UNIT_DELIMITER in property_label:
            # Everything after the delimiter is considered the unit.
            index = property_label.find(UNIT_DELIMITER)
            property_label = property_label[:index] + '  (' + property_label[index+len(UNIT_DELIMITER):] + ')'

            # If there still is a delimiter, that is a slash.
            # ___ = /
            # ____ = *
            if "___" in property_label:
                property_label = property_label.replace("___", '*')
            if UNIT_DELIMITER in property_label:
                property_label = property_label.replace(UNIT_DELIMITER, '/')

        property_label = property_label.replace('_',' ')
        self.setText(property_label)
        
        self.setWordWrap(True)

    def refresh_based_on_equality(self, are_the_same:bool):
        if are_the_same:
            self.setStyleSheet("color: black; font: normal;")
        else:
            self.setStyleSheet("color: #006298; font: bold italic;")

class Property_Table_Row():
    @abstractmethod
    def does_shaped_equal_original(self):
        pass

    @abstractmethod
    def refresh(self):
        pass
    
class ETC_Property_Table_Row(Property_Table_Row):
    def __init__(self, gui:Ui_MainWindow, top_level_item:QTreeWidgetItem, shaped_block, original_block, property_name, change_event):
        super().__init__()
        self.shaped_block = shaped_block
        self.original_block = original_block
        self.property_name = property_name
        self.shaped_etc = getattr(self.shaped_block, self.property_name)
        self.original_etc = getattr(self.original_block, self.property_name)
        self.change_event = change_event

        # Only allow Filter types.
        if type(self.shaped_etc) != Enhanced_Tracking_Control:
            raise TypeError("The EnhancedTrackingControl widget does not support {} of type {}!".format(type(self.shaped_etc)))
    
        # Generate all the sub-components that go into setting etc: one combo box and two spin boxes
        # Filter Number
        self.setup_option = self.shaped_etc.properties.Setup
        setup_label = QTreeWidgetItem()
        setup_label.setText(0, "Setup")
        options = [ETC_SETUP_PARAMETER_MAPPING[setup] for setup in ETC_Setup]
        self.setup_widget = C_QComboBox(self.setup_option, enum_text=options, change_event=self.update_etc)
        temp = C_QComboBox(self.original_etc.properties.Setup, enum_text=options, change_event=None, is_read_only=True)
        top_level_item.addChild(setup_label)
        gui.property_table.setItemWidget(setup_label, 1, self.setup_widget)
        gui.property_table.setItemWidget(setup_label, 2, temp)

        bandwidth_widget = QTreeWidgetItem()
        bandwidth_widget.setText(0, "Bandwidth")
        self.bandwidth_widget = C_QLineEdit(self.shaped_etc.properties, "Bandwidth", change_event=self.update_etc)
        temp = C_QLineEdit(self.original_etc.properties, "Bandwidth", is_read_only=True)
        top_level_item.addChild(bandwidth_widget)
        gui.property_table.setItemWidget(bandwidth_widget, 1, self.bandwidth_widget)
        gui.property_table.setItemWidget(bandwidth_widget, 2, temp)

        scale_widget = QTreeWidgetItem()
        scale_widget.setText(0, "Scale")
        self.scale_widget = C_QLineEdit(self.shaped_etc.properties, "Scale", change_event=self.update_etc)
        temp = C_QLineEdit(self.original_etc.properties, "Scale", is_read_only=True)
        top_level_item.addChild(scale_widget)
        gui.property_table.setItemWidget(scale_widget, 1, self.scale_widget)
        gui.property_table.setItemWidget(scale_widget, 2, temp)

        self.top_level_item = top_level_item
        self.gui = gui

        """ Label. """
        self.label_widget = C_QPropertyLabel(property_name)

        # Add widgets to top-level item.
        gui.property_table.setItemWidget(top_level_item, 0, self.label_widget)

        # Update gui.
        self.refresh()

    def update_etc(self):
        try:
            self.shaped_etc.properties.Setup = ETC_Setup(self.setup_widget.currentIndex())
            # Has issues with calling this function before the widget is saved to self.
        except:
            pass
        pass

        if self.change_event:
            self.change_event()

    def does_shaped_equal_original(self):
        return True

    def refresh(self):
        self.label_widget.refresh_based_on_equality(self.does_shaped_equal_original())

class Filter_Property_Table_Row(Property_Table_Row):
    def __init__(self, gui:Ui_MainWindow, top_level_item:QTreeWidgetItem, shaped_block, original_block, property_name, change_event):
        super().__init__()
        self.property_name = property_name
        self.shaped_filters = getattr(shaped_block, self.property_name)
        self.original_filters = getattr(original_block, self.property_name)
        self.change_event = change_event

        # Only allow Filter types.
        if (type(self.shaped_filters) != list) and (type(self.shaped_filters[0]) != Filter_Model):
            raise TypeError("The FilterSelection widget does not support {} of type {}!".format(type(self.shaped_filters), type(self.shaped_filters[0])))
        
        self.num_filters = len(self.shaped_filters)
        
        """ Label. """
        self.label_widget = C_QPropertyLabel(property_name)
        gui.property_table.setItemWidget(top_level_item, 0, self.label_widget)

        """ Filter Number. """
        self.selected_filter = 0
        filter_number_tree_item = QTreeWidgetItem()
        filter_number_tree_item.setText(0, "Filter Number")
        self.filter_number_combo_box = C_QComboBox(self.selected_filter, max_value=self.num_filters, change_event=self.update_filter)

        top_level_item.addChild(filter_number_tree_item)
        gui.property_table.setItemWidget(filter_number_tree_item, 1, self.filter_number_combo_box)

        """ Filter Type. """
        filter_type_tree_item = QTreeWidgetItem()
        filter_type_tree_item.setText(0, "Filter Type")
        self.shaped_filter_type_combo_box = C_QComboBox(self.shaped_filters[self.selected_filter].properties.filter_type, change_event=self.update_filter)
        self.original_filter_type_combo_box = C_QComboBox(self.original_filters[self.selected_filter].properties.filter_type, is_read_only=True)

        top_level_item.addChild(filter_type_tree_item)
        gui.property_table.setItemWidget(filter_type_tree_item, 1, self.shaped_filter_type_combo_box)
        gui.property_table.setItemWidget(filter_type_tree_item, 2, self.original_filter_type_combo_box)

        self.top_level_item = top_level_item
        self.gui = gui
        self.parameters_fields: QTreeWidgetItem = []

        # Filter Parameters
        self.generate_filter_parameters_fields()
        self.update_filter_numbers()

        # Update gui.
        #self.refresh()

    def update_filter_numbers(self):
        for i in range(self.num_filters):
            self.filter_number_combo_box.setItemText(i, "{} ({})".format(i, self.shaped_filters[i].properties.filter_type.name.replace('_', ' ')))
    
    def generate_filter_parameters_fields(self):
        # Clear fields
        for widget in self.parameters_fields:
            self.top_level_item.removeChild(widget)

        self.parameters_fields.clear()
        #print("regen fields")

        # Add new fields and re-initialize.
        num_current_parameters = len(self.shaped_filters[self.selected_filter].properties.parameters)
        num_original_parameters = len(self.original_filters[self.selected_filter].properties.parameters)
        max_parameter_fields = max(num_current_parameters, num_original_parameters)
        for i in range(max_parameter_fields):
            filter_type = QTreeWidgetItem()

            # Current Value.
            l1 = None
            text1 = "-"
            if i < num_current_parameters:
                text1 = FILTER_PARAMETER_MAPPING[self.shaped_filters[self.selected_filter].properties.filter_type][i]
                l1 = QLineEdit()
                l1.setClearButtonEnabled(True)
                l1.setFrame(False)
                l1.setMaxLength(20)
                l1.setValidator(QDoubleValidator())
                
                l1.setText(str(self.shaped_filters[self.selected_filter].properties.parameters[i]))
                l1.setCursorPosition(0)
                l1.editingFinished.connect(self.update_filter)
                l1.textEdited.connect(self.update_filter)

            # Original Value.
            l2 = None
            text2 = "-"
            if i < num_original_parameters:
                text2 = FILTER_PARAMETER_MAPPING[self.original_filters[self.selected_filter].properties.filter_type][i]
                l2 = QLineEdit()
                l2.setFrame(False)
                l2.setText(str(self.original_filters[self.selected_filter].properties.parameters[i]))
                l2.setCursorPosition(0)
                l2.setEnabled(False)

            filter_type.setText(0, text1 + ' / ' + text2)
            self.top_level_item.addChild(filter_type)

            if l1:
                self.gui.property_table.setItemWidget(filter_type, 1, l1)
            if l2:
                self.gui.property_table.setItemWidget(filter_type, 2, l2)

            self.gui.property_table.addTopLevelItem(self.top_level_item)
            self.parameters_fields.append(filter_type)
            
    def update_filter(self):
        current_index = self.filter_number_combo_box.currentIndex()
        current_type = self.shaped_filter_type_combo_box.currentIndex()
        
        #print("filter change to #={} of type={}", current_index, current_type)
        if self.selected_filter != current_index:
            self.selected_filter = current_index
            
            # Did the filter number change?
            # Update filter type and parameters.
            #print("swpa filter #")
            
            # Generate fields first if needed then change combo box because that event is attached to all changes, even in code.
            self.generate_filter_parameters_fields()
            self.shaped_filter_type_combo_box.setCurrentIndex(self.shaped_filters[self.selected_filter].properties.filter_type.value)
            self.original_filter_type_combo_box.setCurrentIndex(self.original_filters[self.selected_filter].properties.filter_type.value)
        elif self.shaped_filters[self.selected_filter].properties.filter_type != FilterType(current_type):
            #print("swpa filter type")
            # Did the filter type change?
            # Update parameters fields and save.
            self.shaped_filters[self.selected_filter].properties.filter_type = FilterType(current_type)

            # Changed type, clear coefficients.
            self.generate_filter_parameters_fields()
            self.update_filter_numbers()
            pass
        else:
            #print("change param")
            # save parameters.
            parameter_values = []
            for field in self.parameters_fields:
                if self.gui.property_table.itemWidget(field, 1):
                    value = self.gui.property_table.itemWidget(field, 1).text()
                    if not value:
                        value = 0.0
                        self.gui.property_table.itemWidget(field, 1).setText("0.0")
                    else:
                        value = float(value)
                    parameter_values.append(value)
            self.shaped_filters[self.selected_filter].properties.parameters = parameter_values

        if self.change_event:
            self.change_event()

    def does_shaped_equal_original(self):
        if len(self.shaped_filters[self.selected_filter].properties.parameters) != len(self.original_filters[self.selected_filter].properties.parameters):
            return False
        else:
            for i in range(len(self.shaped_filters[self.selected_filter].properties.parameters)):
                if abs(self.shaped_filters[self.selected_filter].properties.parameters[i] - self.original_filters[self.selected_filter].properties.parameters[i]) > Globals.FUZZ:
                    return False
        
        return True

    def refresh(self):
        self.update_filter()
        self.label_widget.refresh_based_on_equality(self.does_shaped_equal_original())

class C_QAnsysFrequencyResponseButton(QPushButton):
    def __init__(self, block, property_name, change_event=None, is_read_only=False):
        super().__init__()
        self.block = block
        self.property_name = property_name
        self.type = type(getattr(self.block, self.property_name))
        self.change_event = change_event

        if self.type != FR:
            raise TypeError("The FrequencyResponse Button widget does not support {}!".format(self.type))
        
        fr: FR = getattr(self.block, self.property_name)
        if fr.filepath:
            self.setText(fr.filepath)
            self.setToolTip(fr.filepath)
        else:
            self.setText("Upload File")
            self.setToolTip("Upload File")

        # Hook up event(s).
        if is_read_only:
            self.setEnabled(False)
        else:
            self.pressed.connect(self.state_changed)

    def state_changed(self):
        file_dialog = QFileDialog()
        file_dialog.setWindowTitle("Open File")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        file_dialog.setNameFilters(["Ansys Frequency Response Files (*.txt)", "All Files (*)"])
        import os
        DOWNLOADS_DIRECTORY = os.path.join(os.environ.get('USERPROFILE'), "Downloads")
        file_dialog.setDirectory(DOWNLOADS_DIRECTORY)

        if file_dialog.exec():
            selected_file = file_dialog.selectedFiles()[0]
            #print("Selected file", selected_file)
            fr: FR = getattr(self.block, self.property_name)
            #print("fr id a ", id(fr))
            fr.parse_fr_file(selected_file)
            setattr(self.block, self.property_name, fr)
            #print("fr id b ", id(getattr(self.model, self.property_name)))
            self.setText(fr.filepath)
            self.setToolTip(fr.filepath)
            #setattr(self.model, self.property_name, value)

            if self.change_event:
                self.change_event()

class Ansys_Frequency_Response_Property_Table_Row(Property_Table_Row):
    def __init__(self, gui:Ui_MainWindow, top_level_item:QTreeWidgetItem, shaped_block, original_block, property_name, change_event):
        super().__init__()
        self.change_event = change_event

        """ Label. """
        self.label_widget = C_QPropertyLabel(property_name)

        """ Shaped. """
        self.shaped_widget = C_QAnsysFrequencyResponseButton(shaped_block, property_name, change_event=self.change_event)

        """ Original. Does not exist. """

        # Add widgets to top-level item.
        gui.property_table.setItemWidget(top_level_item, 0, self.label_widget)
        gui.property_table.setItemWidget(top_level_item, 1, self.shaped_widget)

        # Update gui.
        self.refresh()

    def does_shaped_equal_original(self):
        pass

    def refresh(self):
        pass

class C_QComboBox(QComboBox):
    def __init__(self, value, min_value:int=0, max_value:int=None, enum_text:list[str]=None, block=None, property_name=None, \
                 is_read_only=False, change_event=None, refresh_event=None):
        super().__init__()
        self.block = block
        self.property_name = property_name
        self.type = type(value) if (self.block is None) and (self.property_name is None) else type(getattr(self.block, self.property_name))
        self.change_event = change_event
        self.refresh_event = refresh_event
        self.index_to_enum_offset = 0
 
        if max_value:
            # Enforce that value must be an integer.
            if self.type != int:
                raise TypeError("The ComboBox widget does not support {}!".format(self.type))
            
            # Ignore enum_class and enum_text. Generate a list of options based off of [min_value, max_value] instead.
            enum_text = [str(i) for i in range(min_value, max_value)]
        else:
            # Only allow enums otherwise.
            if not issubclass(self.type, Enum):
                raise TypeError("The ComboBox widget does not support {}!".format(self.type))

            # Confirm that the user facing text matches the enum provided.
            if enum_text is None:
                # Generate our own user-facing text.
                enum_text = [enum.name.replace('_', ' ') for enum in self.type]
            else:
                # We provided some alternative mapping. Validate that.
                if len(self.type) != len(enum_text):
                    raise ValueError("The number of enums ({}) does not match the number of user-facing text ({})!".format(len(self.type), len(enum_text)))
                
            min_value = Globals.DEFAULT_MIN
            for enum in self.type:
                if enum.value < min_value:
                    min_value = enum.value
            self.index_to_enum_offset = min_value

            # Convert the incoming enum value to an integer value.
            value = value.value - self.index_to_enum_offset

        # Only allow list[str] types.
        if (type(enum_text) != list) and (type(enum_text[0]) != str):
            raise TypeError("The ComboBox widget does not support {}!".format(type(enum_text)))
        
        # Hook up the options.
        self.addItems(enum_text)

        # Load in the properties' current value.
        self.setCurrentIndex(value)

        # Disable wheel events to stop accidental filter changes.
        self.wheelEvent = lambda event: None

        if is_read_only:
            self.setEnabled(False)
        else:
            # (Optional) Bind the gui to the backend variable.
            if (block is not None) and (property_name is not None):
                self.currentIndexChanged.connect(self.state_changed)
            elif self.change_event:
                self.currentIndexChanged.connect(self.change_event)

    def state_changed(self):
        did_change = True
        if self.block and self.property_name:
            did_change = (self.currentIndex() + self.index_to_enum_offset) != getattr(self.block, self.property_name)

        setattr(self.block, self.property_name, self.type(self.currentIndex() + self.index_to_enum_offset))

        if did_change:
            self.change_event()

        if self.refresh_event:
            self.refresh_event()

    def refresh(self):
        pass

class Combo_Box_Property_Table_Row(Property_Table_Row):
    def __init__(self, gui:Ui_MainWindow, top_level_item:QTreeWidgetItem, shaped_block, original_block, property_name, change_event):
        super().__init__()
        self.change_event = change_event

        """ Label. """
        self.label_widget = C_QPropertyLabel(property_name)

        """ Shaped. """
        self.shaped_widget = C_QComboBox(value=getattr(shaped_block, property_name), block=shaped_block, property_name=property_name, \
                                         change_event=self.change_event, refresh_event=self.refresh)

        """ Original. """
        self.original_widget = C_QComboBox(value=getattr(shaped_block, property_name), block=original_block, property_name=property_name, \
                                           is_read_only=True)

        # Add widgets to top-level item.
        gui.property_table.setItemWidget(top_level_item, 0, self.label_widget)
        gui.property_table.setItemWidget(top_level_item, 1, self.shaped_widget)
        gui.property_table.setItemWidget(top_level_item, 2, self.original_widget)

        # Update gui.
        self.refresh()

    def does_shaped_equal_original(self):
        return True

    def refresh(self):
        self.shaped_widget.refresh()
        self.original_widget.refresh()
        self.label_widget.refresh_based_on_equality(self.does_shaped_equal_original())

class C_QCheckBox(QCheckBox):
    def __init__(self, block, property_name, is_read_only=False, change_event=None, refresh_event=None):
        super().__init__()
        self.block = block
        self.property_name = property_name
        self.type = type(getattr(self.block, self.property_name))
        self.change_event = change_event
        self.refresh_event = refresh_event

        # Only allow bool types.
        if (self.type != bool):
            raise TypeError("The CheckBox widget does not support {}!".format(self.type))

        # Hook up event(s).
        if is_read_only:
            self.setEnabled(False)
        else:
            self.stateChanged.connect(self.state_changed)

        # Refresh the widget with the current value.
        self.refresh()

    def state_changed(self):
        did_change = self.isChecked() != getattr(self.block, self.property_name)

        setattr(self.block, self.property_name, self.isChecked())

        if did_change:
            self.change_event()

        if self.refresh_event:
            self.refresh_event()

    def refresh(self):
        self.setChecked(getattr(self.block, self.property_name))

class Check_Box_Property_Table_Row(Property_Table_Row):
    def __init__(self, gui:Ui_MainWindow, top_level_item:QTreeWidgetItem, shaped_block, original_block, property_name, change_event):
        super().__init__()
        self.change_event = change_event

        """ Label. """
        self.label_widget = C_QPropertyLabel(property_name)

        """ Shaped. """
        self.shaped_widget = C_QCheckBox(shaped_block, property_name, change_event=self.change_event, refresh_event=self.refresh)

        """ Original. """
        self.original_widget = C_QCheckBox(original_block, property_name, is_read_only=True)

        # Add widgets to top-level item.
        gui.property_table.setItemWidget(top_level_item, 0, self.label_widget)
        gui.property_table.setItemWidget(top_level_item, 1, self.shaped_widget)
        gui.property_table.setItemWidget(top_level_item, 2, self.original_widget)

        # Update gui.
        self.refresh()

    def does_shaped_equal_original(self):
        if self.shaped_widget.isChecked() == self.original_widget.isChecked():
            return True
        else:
            return False

    def refresh(self):
        self.shaped_widget.refresh()
        self.original_widget.refresh()
        self.label_widget.refresh_based_on_equality(self.does_shaped_equal_original())

class C_QLineEdit(QLineEdit):
    def __init__(self, block, property_name, is_read_only=False, change_event=None, refresh_event=None):
        super().__init__()

        self.block = block
        self.property_name = property_name
        self.type = type(getattr(self.block, self.property_name))
        self.change_event = change_event
        self.refresh_event = refresh_event

        # Only allow int, float, and str types.
        if (self.type != int) and (self.type != float) and (self.type != str):
            raise TypeError("The LineEdit widget does not support {}!".format(self.type))

        # Add validation based off of property type.
        if self.type == int:
            self.setValidator(QIntValidator())
        elif self.type == float:
            self.setValidator(QDoubleValidator())

        # Remove frame.
        self.setFrame(False)

        # Set max length.
        self.setMaxLength(26)

        # Hook up event(s).
        if is_read_only:
            self.setReadOnly(True)
            self.setStyleSheet("color: grey")
        else:
            # Enable the clear button.
            self.setClearButtonEnabled(True)

            # Connect to return pressed event.
            self.returnPressed.connect(self.text_changed)
        
        self.setCursorPosition(0)

        self.refresh()

    def focusOutEvent(self, event):
        self.text_changed()
        self.setCursorPosition(0)
        super().focusOutEvent(event) # because we overrode the focusoutevent, we need to recall the parent's implementation of it.

    def text_changed(self):
        did_change = self.text() != str(getattr(self.block, self.property_name))

        if self.text():
            # Non-empty text.
            #print("set ", self.block, self.property_name, self.type(self.text()))
            setattr(self.block, self.property_name, self.type(self.text()))
        else:
            # Empty text.
            if self.type == int:
                setattr(self.block, self.property_name, 0)
            elif self.type == float:
                setattr(self.block, self.property_name, 0.0)
            else:
                setattr(self.block, self.property_name, "")
        
        # Update primary response now that we updated the attribute.
        if (self.text() != "") and did_change:
            if self.change_event:
                self.change_event()

        # Refresh gui.
        if self.refresh_event:
            self.refresh_event()

        self.refresh()

        #print(getattr(self.block, self.property_name))

    def refresh(self):
        self.setText(str(getattr(self.block, self.property_name)))
        self.setCursorPosition(0)

class Line_Edit_Property_Table_Row(Property_Table_Row):
    def __init__(self, gui:Ui_MainWindow, top_level_item:QTreeWidgetItem, shaped_block, original_block, property_name, change_event):
        super().__init__()
        self.change_event = change_event

        """ Label. """
        self.label_widget = C_QPropertyLabel(property_name)

        """ Shaped. """
        self.shaped_widget = C_QLineEdit(shaped_block, property_name, change_event=self.change_event, refresh_event=self.refresh)

        """ Original. """
        self.original_widget = C_QLineEdit(original_block, property_name, is_read_only=True)

        # Add widgets to top-level item.
        gui.property_table.setItemWidget(top_level_item, 0, self.label_widget)
        gui.property_table.setItemWidget(top_level_item, 1, self.shaped_widget)
        gui.property_table.setItemWidget(top_level_item, 2, self.original_widget)

        # Update gui.
        self.refresh()

    def does_shaped_equal_original(self):
        if self.shaped_widget.text() == self.original_widget.text():
            return True
        else:
            return False

    def refresh(self):
        #self.shaped_widget.refresh()
        #self.original_widget.refresh()
        self.label_widget.refresh_based_on_equality(self.does_shaped_equal_original())