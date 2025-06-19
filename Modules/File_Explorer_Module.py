from pyqt_ui import Ui_MainWindow
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from enum import Enum, auto
import os
#from a1_interface import A1_VERSION
import Globals
import a1_interface

DOWNLOADS_DIRECTORY = os.path.join(os.environ.get('USERPROFILE'), "Downloads")

class Export_Type(Enum):
    Shaped_Response = auto()
    Shaped_Configuration_Only = auto()

DEFAULT_FILEPATH = os.path.join(Globals.DEFAULT_DIRECTORY, Globals.DEFAULT_FILE)
DEFAULT_VERSION = a1_interface.A1_VERSION

class File_Explorer_Module():
    def __init__(self, gui:Ui_MainWindow, read_a1_file, write_a1_file, does_secondary_file_exists, delete_block_layout):
        self.gui = gui
        self.file_count = 0
        self.read_a1_file = read_a1_file
        self.write_a1_file = write_a1_file
        self.does_secondary_file_exist = does_secondary_file_exists
        self.delete_block_layout = delete_block_layout
        self.widget_registry = {} # Tree item: widgets

        # Primary file.
        self.add_primary_file(DEFAULT_FILEPATH, DEFAULT_VERSION)

        # Create the tree widget columns.
        self.gui.tree_view_file_explorer.setColumnCount(3)
        header = self.gui.tree_view_file_explorer.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)

        # The current tree widget item selected.
        self.selected_item = None

    def open_file_dialog(self, is_primary=False, is_being_added=False, external_call=False) -> tuple[str, str]:
        """ The open file dialog that lets you pick out the primary or secondary block layout to use.

        Args:
            is_primary (bool, optional): If this dialog is for primary or secondary block layouts. Defaults to False.
            is_being_added (bool, optional): If this dialog is adding a secondary block layout or replacing one. Defaults to False.
            external_call (bool, optional): Is called from this module or a different module. Defaults to False.

        Returns:
            tuple[str, str]: [The selected file, The version of the selected file]
        """
        file_dialog = QFileDialog()
        file_dialog.setWindowTitle("Open File")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        file_dialog.setNameFilters(["A1 Frequency Response Files (*.fr)", "All Files (*)"])
        file_dialog.setDirectory(DOWNLOADS_DIRECTORY)

        selected_file = None
        version = DEFAULT_VERSION
        if file_dialog.exec():
            selected_file = file_dialog.selectedFiles()[0]

            # Check if it exists. Only allow for replacing the current file, not others.
            if is_being_added and not is_primary and self.does_secondary_file_exist(os.path.basename(selected_file)):
                # Don't allow adding files that already exist.
                popup = QMessageBox()
                popup.setWindowTitle("File Open Error")
                popup.setIcon(QMessageBox.Critical)
                popup.setText("Cannot open {} because the file already exists.".format(selected_file))
                popup.setDefaultButton(QMessageBox.Ok)
                popup.exec_()

                return [None, DEFAULT_VERSION]
            print(f"File Explorer Module: {selected_file}")
            [is_valid, version] = self.read_a1_file(selected_file, is_primary)

            if is_valid:
                if external_call and is_primary:
                    self.replace_primary_file(selected_file, version, external_call=True)
                    selected_file = None
            else:
                # Popup to inform the user that the file is not compatible.
                if is_primary:
                    raise AssertionError("Internal Error: Primary files should always be valid in terms of frequency!")
                
                popup = QMessageBox()
                popup.setWindowTitle("File Import Error")
                popup.setIcon(QMessageBox.Critical)

                if is_primary:
                    popup.setText("The file {} does not contain valid frequencies.".format(os.path.basename(selected_file)))
                else:
                    popup.setText("The file {} contains does not match or overlap with frequencies contained in the primary response.".format(os.path.basename(selected_file)))

                popup.setStandardButtons(QMessageBox.Ok)
                popup.exec_()

                selected_file = None

        return [selected_file, version]
    
    def export_file_dialog(self, export_type:Export_Type) -> None:
        """ The export file dialog that lets you export the current block layout to file.

        Args:
            export_type (Export_Type): The export type.
        """
        file_dialog = QFileDialog()
        file_dialog.setWindowTitle("Export File")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        file_dialog.setNameFilters(["A1 Frequency Response Files (*.fr)", "All Files (*)"])
        file_dialog.setDirectory(DOWNLOADS_DIRECTORY)

        selected_file = None
        if file_dialog.exec():
            selected_file = file_dialog.selectedFiles()[0]
            self.write_a1_file(selected_file, export_type)

    def add_primary_file(self, filepath:str, version:str) -> None:
        """ Generates a new tree item in the file explorer that represents a primary block layout.
        Do note, this should only ever be called once (on module initialization). However, this could
        be called multiple times to add multiple primary layouts but additional work is needed to properly support
        multiple primary layouts on the backend.

        Args:
            filepath (str): The filepath to the layout.
            version (str): The A1 version that corresponds to the layout.
        """
        directory = os.path.dirname(filepath)
        filename = os.path.basename(filepath)

        tree_widget_item = QTreeWidgetItem()
        tree_widget_item.setText(0, filename)
        tree_widget_item.setToolTip(0, "({}) {}".format(version, filepath))
        
        self.gui.tree_view_file_explorer.addTopLevelItem(tree_widget_item)

        # Option to change filepath.
        replace_primary_file_button = QToolButton()
        replace_primary_file_button.setText("...")
        replace_primary_file_button.pressed.connect(lambda: self.event_processor(replace_primary_file_button, self.event_replace_primary_file))
        self.gui.tree_view_file_explorer.setItemWidget(tree_widget_item, 1, replace_primary_file_button)

        # Option to add a secondary file.
        add_secondary_file_button = Add_Button()
        add_secondary_file_button.pressed.connect(lambda: self.event_processor(add_secondary_file_button, self.event_add_secondary_file))
        self.gui.tree_view_file_explorer.setItemWidget(tree_widget_item, 2, add_secondary_file_button)

    def replace_primary_file(self, filepath:str, version:str, external_call=False) -> None:
        """ Replaces the selected primary tree item.

        Args:
            filepath (str): The filepath to the layout.
            version (str): The A1 version that corresponds to the layout.
            external_call (bool): If this function was called from this module or not.
        """
        directory = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        print(f"File Explorer: {filename}")
        if external_call:
            # The external file open option only replaces the first primary file (even if we support multiple primary files).
            self.gui.tree_view_file_explorer.topLevelItem(0).setText(0, filename)
            self.gui.tree_view_file_explorer.topLevelItem(0).setToolTip(0, "({}) {}".format(version, filepath))
        else:
            # Replace the currently highlighted primary file.
            self.selected_item.setText(0, filename)
            self.selected_item.setToolTip(0, "({}) {}".format(version, filepath))

    def add_secondary_file(self, filepath:str, version:str) -> None:
        """ Adds a secondary tree item.

        Args:
            filepath (str): The filepath to the layout.
            version (str): The A1 version that corresponds to the layout.
        """
        directory = os.path.dirname(filepath)
        filename = os.path.basename(filepath)

        tree_widget_item = QTreeWidgetItem()
        tree_widget_item.setText(0, filename)
        tree_widget_item.setToolTip(0, "({}) {}".format(version, filepath))
        
        self.selected_item.addChild(tree_widget_item)

        # Option to change filepath.
        replace_secondary_file_button = QToolButton()
        replace_secondary_file_button.setText("...")
        replace_secondary_file_button.pressed.connect(lambda: self.event_processor(replace_secondary_file_button, self.event_replace_secondary_file))
        self.gui.tree_view_file_explorer.setItemWidget(tree_widget_item, 1, replace_secondary_file_button)

        # Option to remove the file.
        delete_secondary_file_button = Remove_Button()
        delete_secondary_file_button.pressed.connect(lambda: self.event_processor(delete_secondary_file_button, self.event_delete_secondary_file))
        self.gui.tree_view_file_explorer.setItemWidget(tree_widget_item, 2, delete_secondary_file_button)

        self.gui.tree_view_file_explorer.expandAll()

    def replace_secondary_file(self, filepath:str, version:str) -> None:
        """ Replaces the selected secondary tree item.

        Args:
            filepath (str): The filepath to the layout.
            version (str): The A1 version that corresponds to the layout.
        """
        directory = os.path.dirname(filepath)
        filename = os.path.basename(filepath)

        # Delete the secondary block layout first.
        self.delete_block_layout(self.selected_item.text(0))

        self.selected_item.setText(0, filename)
        self.selected_item.setToolTip(0, "({}) {}".format(version, filepath))

    def delete_secondary_file(self) -> None:
        """ Deletes the selected secondary tree item.
        """
        # Delete the secondary block layout first.
        self.delete_block_layout(self.selected_item.text(0))

        # Now, remove the item from the parent.
        self.selected_item: QTreeWidgetItem
        parent_item = self.selected_item.parent()
        parent_item.removeChild(self.selected_item)

#region Events
    def event_processor(self, widget:QWidget, event_to_trigger):
        """ Called so that we can get the id of the widget that triggered an event before actually calling the event.

        Args:
            widget (QWidget): The widget that changed.
            event_to_trigger (_type_): The event to call due to an event.
        """
        # Find the parent that belongs to this widget.
        iterator = QTreeWidgetItemIterator(self.gui.tree_view_file_explorer)
        while iterator.value():
            tree_widget_item = iterator.value()
            for i in range(self.gui.tree_view_file_explorer.columnCount()):
                w = self.gui.tree_view_file_explorer.itemWidget(tree_widget_item, i)
                if w == widget:
                    # Found.
                    self.selected_item = tree_widget_item
                    break

            iterator += 1
        
        event_to_trigger()

    def event_replace_primary_file(self) -> None:
        """ Event thats called to replace a primary file.
        """
        [filepath, version] = self.open_file_dialog(is_primary=True)
        if filepath:
            self.replace_primary_file(filepath, version)

    def event_add_secondary_file(self) -> None:
        """ Event thats called to add a secondary file.
        """
        [filepath, version] = self.open_file_dialog(is_being_added=True)
        if filepath:
            self.add_secondary_file(filepath, version)

    def event_replace_secondary_file(self) -> None:
        """ Event thats called to replace a secondary file.
        """
        [filepath, version] = self.open_file_dialog()
        if filepath:
            self.replace_secondary_file(filepath, version)

    def event_delete_secondary_file(self) -> None:
        """ Event thats called to delete a secondary file.
        """
        self.delete_secondary_file()
#end region

class Add_Button(QPushButton):
    def __init__(self):
        super().__init__()
        self.setText('+')

class Remove_Button(QPushButton):
    def __init__(self):
        super().__init__()
        self.setText('x')