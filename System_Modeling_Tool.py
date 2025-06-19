import os
from PyQt5.QtWidgets import *
from PyQt5 import QtGui, QtCore
import sys

import a1_interface
import Globals
from Modules.Plot_Module import Plot_Module
from Modules.Block_Explorer_Module import Block_Explorer_Module
from Modules.Easy_Tune_Module import Easy_Tune_Module
from Modules.File_Explorer_Module import File_Explorer_Module, Export_Type
from pyqt_ui import Ui_MainWindow


PROGRAM_NAME = "System Modeling Tool"
PRIMARY_TAB_INDEX = 0
GUI: Ui_MainWindow = None
BLOCK_LAYOUT_MODULE: Block_Explorer_Module = None
EASY_TUNE_MODULE: Easy_Tune_Module = None
FILE_EXPLORER_MODULE: File_Explorer_Module = None
PLOT_MODULE: Plot_Module = None


def open_primary_file() -> None:
    """ Opens the file as primary. Used by the "Open Primary" menu option.
    """
    FILE_EXPLORER_MODULE.open_file_dialog(is_primary=True, external_call=True)

def export_file_shaped_response() -> None:
    """ Export the primary file response as if it were a brand new A1 response. Used by the "Export Primary > Shaped Response" menu option.
    """
    FILE_EXPLORER_MODULE.export_file_dialog(Export_Type.Shaped_Response)

def export_file_shaped_configuration_only() -> None:
    """ Export the primary file response as if it were the shaped component of A1 response. Used by the "Export Primary > Shaped Configuration Only" menu option.
    """
    FILE_EXPLORER_MODULE.export_file_dialog(Export_Type.Shaped_Configuration_Only)

def read_a1_file(filepath:str, is_primary:bool) -> tuple[bool, str]:
    """ Reads in an A1 data object based off of the provided filepath.

    Args:
        filepath (str): The filepath to open.
        is_primary (bool): Whether this should be loaded as a primary file or secondary file.

    Returns:
        tuple[bool, str]: [If the file was valid, The file version if valid]
    """
    [version, data] = a1_interface.read_frequency_response_result_from_a1_file(filepath)
    directory = os.path.dirname(filepath)
    filename = os.path.basename(filepath)

    # Fill block layout.
    if is_primary:
        BLOCK_LAYOUT_MODULE.initialize_primary_block_layout_from_a1_data(data, filename)
        is_valid = True
    else:
        is_valid = BLOCK_LAYOUT_MODULE.initialize_secondary_block_layout_from_a1_data(data, filename)

    if is_valid and is_primary:
        # Primary tabs only replace the start position.
        GUI.response_tabs.setTabText(PRIMARY_TAB_INDEX, filename)
        GUI.response_tabs.setTabToolTip(PRIMARY_TAB_INDEX, "({}) {}".format(version, directory + '/' + filename))

    return [is_valid, version]

def write_a1_file(filepath:str, export_type:Export_Type) -> None:
    """ Writes out an A1 data structure to an A1 compatible file.

    Args:
        filepath (str): The filepath to write or overwrite.
        export_type (Export_Type): The export type.
    """
    data = BLOCK_LAYOUT_MODULE.save_block_layout_to_fr_result(export_type)
    a1_interface.write_frequency_response_result_to_a1_file(filepath, data)

def initialize_gui() -> None:
    """ Initializes all modules and any additional gui elements.
    """
    global BLOCK_LAYOUT_MODULE
    global EASY_TUNE_MODULE
    global FILE_EXPLORER_MODULE
    global PLOT_MODULE

    PLOT_MODULE = Plot_Module(GUI)
    BLOCK_LAYOUT_MODULE = Block_Explorer_Module(GUI, PLOT_MODULE.set_line_data_from_frd_data, PLOT_MODULE.temporarily_show_easytune_plots)
    EASY_TUNE_MODULE = Easy_Tune_Module(GUI, BLOCK_LAYOUT_MODULE)
    FILE_EXPLORER_MODULE = File_Explorer_Module(GUI, read_a1_file, write_a1_file, \
                                                BLOCK_LAYOUT_MODULE.does_secondary_layout_exist, \
                                                BLOCK_LAYOUT_MODULE.delete_secondary_block_layout_from_a1_data)

    # Disable the ability to close the primary tab.
    GUI.response_tabs.tabBar().setTabButton(0, QTabBar.RightSide, None)
    GUI.response_tabs.tabBar().setTabText(0, Globals.DEFAULT_FILE)

def initialize_events() -> None:
    """ Initializes all events used by the main window (but not modules).
    """
    GUI.action_Open_File.triggered.connect(open_primary_file)
    GUI.action_Shaped_Response.triggered.connect(export_file_shaped_response)
    GUI.action_Shaped_Configuration_Only.triggered.connect(export_file_shaped_configuration_only)

    # Prevent switching away from the primary tab.
    def tab_changed_event(index):
        if index != PRIMARY_TAB_INDEX:
            GUI.response_tabs.setCurrentIndex(PRIMARY_TAB_INDEX)
    GUI.response_tabs.currentChanged.connect(tab_changed_event)

def main() -> None:
    """ The main entry point for the application.
    """
    global GUI
    GUI = Ui_MainWindow()

#region Styling
    # NOTE: https://doc.qt.io/qt-6/stylesheet-examples.html#customizing-the-foreground-and-background-colors
    application = QApplication(sys.argv)

    # Must initialize fonts after the application object has been created. Otherwise, the 1st call to addApplicationFont() will crash without traceback.
    font_files = os.listdir(Globals.FONT_DIRECTORY)
    for file in font_files:
        if file.endswith(".ttf"):
            QtGui.QFontDatabase.addApplicationFont(Globals.FONT_DIRECTORY + file)

    # Import our custom CSS file which will replace the colors defined in the QSS file with the correct hex codes.
    color_dictionary = {}
    i = 0
    with open(Globals.COLOR_FILE, "r") as file:
        for line in file:
            if len(line.strip()):
                if (not line.startswith('@')) or ('=' not in line):
                    raise ResourceWarning("Line #{} in Colors does not start with a @ or contain =".format(i))
                else:
                    items = line.split('=')
                    color_key = items[0].strip()
                    color_hex = items[1].strip()
                    color_dictionary[color_key] = color_hex
            i += 1

    # Finally, import the stylesheet.
    with open(Globals.STYLESHEET_FILE, "r") as file:
        stylesheet = file.read()

        # Replace all colors with hex.
        for color in color_dictionary.keys():
            stylesheet = stylesheet.replace(color, color_dictionary[color])

        application.setStyleSheet(stylesheet)
#end region

    window = QMainWindow()
    GUI.setupUi(window)

    # Set the A1 version.
    a1_dll_versions = a1_interface.get_a1_dll_version()
    for dll in a1_dll_versions.keys():
        automation1_version = QAction(window)
        automation1_version.setObjectName(dll.replace('.', '_'))

        automation1_version.setEnabled(False)
        automation1_version.setText("({})  {}".format(a1_dll_versions[dll], dll))

        GUI.menuHelp.addAction(automation1_version)

    # Set the tool version.
    with open(Globals.VERSION_FILE, "r") as file:
        version = file.read()

    # Update the window title with this application's version.
    window_title = "{} ({})".format(PROGRAM_NAME, version)
    window.setWindowTitle(window_title)

    # Initialize stuff.
    initialize_gui()
    initialize_events()

    # For some reason, demanding a maximized window does not work.
    # NOTE: https://stackoverflow.com/questions/27157312/qt-showmaximized-not-working-in-windows
    QtCore.QTimer.singleShot(500, window.showMaximized)

    # For some reason, we can't connect to the resize event on application start, otherwise, the application will crash without a traceback.
    # This could be due to too many resize events within a short time span which may overwhelm the main thread.
    PLOT_MODULE.connect_resize_event() 
    
    # Launch the application.
    sys.exit(application.exec_())

if __name__ == "__main__":
    main()