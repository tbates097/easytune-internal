import control
import copy
import math
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.font_manager as font_manager
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
import numpy as np
from PyQt5.QtGui import QIntValidator, QDoubleValidator, QColor
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
import time
import threading
import warnings

from Block_Layout import Block_Layout_With_Data
from FRD_Data import Loop_Type, FR_Type, LOOP_RESPONSES, get_user_facing_text
import Globals
from pyqt_ui import Ui_MainWindow
import Utils


PLOT_MODULE_TITLE = "Plot"

CURSOR_COLOR = 'red'
CURSOR_LINE_STYLE = 'solid'
GRID_LINE_COLOR = '0.9'
GRID_LINE_STYLE = 'solid'
ORIGINAL_LINE_STYLE = 'dashed'

FRD = "FRD"
FILENAME = "File"
FR_TYPE = "FR_Type"
FREQUENCY = "Frequency"
OMEGA = "Omega"
FREQUENCY_LABEL = "Frequency [hertz]"
MAGNITUDE_LABEL = "Magnitude [dB]"
PHASE_LABEL = "Phase [degrees]"
PRIMARY_RESPONSE = "Primary Response"
MAGNITUDE = "MAGNITUDE"
PHASE = "PHASE"
LEGEND = "LEGEND"
ORIGINAL = "Original"
SHAPED = "Shaped"
LINE = "Plot"
VALUES = "Values"
SMALL_SIZE = 10
MEDIUM_SIZE = 12
BIGGER_SIZE = 14
DEBOUNCE_TIME_INTERVAL = 0.3
""" In seconds. Determines how much time must elapse before calling the resize window event. """

MAX_CURSORS = 2

class FR_Lines():
    """ Stores shaped and original line data for both magnitude and phase.
    """
    class Lines():
        """ Stores magnitude and phase line data.
        """
        def __init__(self):
            self.magnitude_line = None
            self.phase_line = None

        def __del__(self):
            # Delete lines.
            if self.magnitude_line:
                self.magnitude_line.remove()
            if self.phase_line:
                self.phase_line.remove()

    def __init__(self):
        self.original = __class__.Lines()
        self.shaped = __class__.Lines()

    def __del__(self):
        del self.original
        del self.shaped

class Plot_Module():
    def __init__(self, gui:Ui_MainWindow):
        def export_as_plotly():
            """ Provides the ability to save the current figure as a plotly file. """
            import plotly
            import plotly.tools as tls
            plotly_fig = tls.mpl_to_plotly(self.fig)
            plotly.offline.plot(plotly_fig, filename=self.primary_frd_filename)

        def format_coordinate(x, y):
            """ Provides the ability to override the default cursor text in matplotlib. """
            if self.cursor_closest_information[FR_TYPE]:
                return "{} ({})\n{:.4g} hz, {} = {:.4g} | {} = {:.4g}".format(self.cursor_closest_information[FILENAME], self.cursor_closest_information[FR_TYPE].name, \
                                                                self.cursor_closest_information[FREQUENCY], \
                                                                MAGNITUDE_LABEL, self.cursor_closest_information[MAGNITUDE], \
                                                                PHASE_LABEL, self.cursor_closest_information[PHASE])
            else:
                return ""

        class Custom_Toolbar(NavigationToolbar):
            """ Generate our own custom toolbar. """
            def __init__(self, figure, actual_fig, parent=None):
                super().__init__(figure, parent)

                self.figure = actual_fig
                self.plotly_button = QPushButton("Export")
                pixmapi = getattr(QStyle, "SP_FileDialogStart")
                icon = self.style().standardIcon(pixmapi)
                self.plotly_button.setIcon(icon)
                self.plotly_button.pressed.connect(export_as_plotly)

                self.addAction(icon, "Export as Plotly File", export_as_plotly)

        self.is_initialized = False
        warnings.filterwarnings("ignore", category=UserWarning)
        self.gui = gui
        self.background = None

#region Fonts and Font Sizes
        # Initialize fonts and font sizes for matplotlib.
        font_path = Globals.FONT_DIRECTORY + "Barlow-Medium.ttf"
        font_manager.fontManager.addfont(font_path)
        property = font_manager.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.sans-serif'] = property.get_name()
        plt.rc('font', size=SMALL_SIZE)         # controls default text sizes.
        plt.rc('axes', titlesize=MEDIUM_SIZE)   # font size of the axes title.
        plt.rc('axes', labelsize=MEDIUM_SIZE)   # font size of the x and y labels.
        plt.rc('xtick', labelsize=SMALL_SIZE)   # font size of the tick labels.
        plt.rc('ytick', labelsize=SMALL_SIZE)   # font size of the tick labels.
        plt.rc('legend', fontsize=MEDIUM_SIZE)  # legend font size.
        plt.rc('figure', titlesize=BIGGER_SIZE) # font size of the figure title.
        plt.rcParams['legend.title_fontsize'] = MEDIUM_SIZE
#endregion

#region Sub-Plots
        # Generate the subplots.
        self.fig, self.sub_plots = plt.subplot_mosaic([[MAGNITUDE],[PHASE],[LEGEND]], \
                                                        gridspec_kw={"height_ratios":[0.46, 0.46, 0.08], "hspace":0.08, \
                                                                    "left":0.1, "top":0.95, "right":0.975, "bottom":0.1})
        # Bring to front.
        self.sub_plots[LEGEND].axis('off')
        self.sub_plots[LEGEND].set_zorder(999)
        self.legend_lines = []
        self.legend_labels = []
        self.legend_font = font_manager.FontProperties(size=8)
        
        # Share the magnitude's frequency axis with the phase.
        self.sub_plots[MAGNITUDE].sharex(self.sub_plots[PHASE])

        # Change subplot cursor formatting.
        self.sub_plots[MAGNITUDE].format_coord = format_coordinate
        self.sub_plots[PHASE].format_coord = format_coordinate
        self.sub_plots[LEGEND].format_coord = lambda x, y : ""
        
        # Format the subplots.
        self.sub_plots[MAGNITUDE].set_xscale('log', base=10)
        self.sub_plots[MAGNITUDE].tick_params(axis='x', which='both', labelbottom=False)
        self.sub_plots[MAGNITUDE].set_ylabel(MAGNITUDE_LABEL)
        self.sub_plots[MAGNITUDE].axhline(0, color='grey', lw=0.8)
        self.sub_plots[MAGNITUDE].grid(which="both", color=GRID_LINE_COLOR, linestyle=GRID_LINE_STYLE)
        
        self.sub_plots[PHASE].set_xscale('log', base=10)
        self.sub_plots[PHASE].set_xlabel(FREQUENCY_LABEL)
        self.sub_plots[PHASE].set_ylabel(PHASE_LABEL)
        self.sub_plots[PHASE].axhline(-180, color='grey', lw=0.8)
        self.sub_plots[PHASE].set_ylim([-370, 10])
        self.sub_plots[PHASE].set_yticks(np.arange(-360, 1, 45))
        self.sub_plots[PHASE].grid(which="both", color=GRID_LINE_COLOR, linestyle=GRID_LINE_STYLE)

        # Reset the color cycle for secondary lines.
        from cycler import cycler
        color_map = mpl.colormaps["Pastel2"]
        colors = color_map.colors
        custom = cycler(color=colors)
        self.sub_plots[MAGNITUDE].set_prop_cycle(custom)
        self.sub_plots[PHASE].set_prop_cycle(custom)
#endregion

#region Cursor
        # Cursor
        for key in self.cursors.keys():
            self.cursors[key] = self.sub_plots[key].axvline(color=CURSOR_COLOR, lw=0.8, ls=CURSOR_LINE_STYLE, visible=False)
            self.sub_plots[key].draw_artist(self.cursors[key])

        self.cursor_is_visible = True
        self.cursor_text = None
        self.cursor_information_expanded = {}
#end region

#region Initialization
        # Frequencies.
        self.omega = []
        self.frequency_hz = []

        # Initialize data on what responses are checked.
        self.checked_responses = {} 
        """ dict [loop] [fr_type] -> bool """

        # Initialize stored frd data.
        self.primary_frd_data = None 
        self.primary_frd_filename = Globals.DEFAULT_FILE
        self.secondary_frd_datas = {} 
        """ dict [filename] -> FRD_data """

        # Initialize store line data.
        self.primary_line_data = {}
        """ dict [loop] [fr_type] [shaped/original] -> Line2D """
        self.secondary_line_data = {}
        """ dict [loop] [fr_type] [shaped/original] -> Line2D """

        for loop in Loop_Type:
            self.gui.loop_response.addItem(loop.name)

            # Reset the sub-plot color cycle so that plot colors are consistent between subplots.
            self.sub_plots[MAGNITUDE].set_prop_cycle(None)
            self.sub_plots[PHASE].set_prop_cycle(None)

            self.primary_line_data[loop] = {}
            self.checked_responses[loop] = {}
            self.cursor_information_expanded[loop] = {}
            for fr_type in LOOP_RESPONSES[loop]:
                # Initialize sub plot dictionary.
                self.primary_line_data[loop][fr_type] = FR_Lines()
                self.checked_responses[loop][fr_type] = False
                self.cursor_information_expanded[loop][fr_type] = None

                # Create user facing name for the enum.
                response_name = fr_type.name.replace('_', ' ')

                # Initialize responses.
                # Shaped.
                self.primary_line_data[loop][fr_type].shaped.magnitude_line = self.sub_plots[MAGNITUDE].plot([], [], label=response_name + "(Shaped)", visible=False)[0]
                self.primary_line_data[loop][fr_type].shaped.phase_line = self.sub_plots[PHASE].plot([], [], label=response_name + "(Shaped)", visible=False)[0]

                color = self.primary_line_data[loop][fr_type].shaped.magnitude_line.get_color()
                color = color[1:] # Strip the stupid hashtag
                color = Utils.lighter(Utils.hex_to_rgb(color), 0.5)
                color = Utils.make_color_more_grey(color)
                color = Utils.rgb_to_hex(color)

                # Original.
                self.primary_line_data[loop][fr_type].original.magnitude_line = self.sub_plots[MAGNITUDE].plot([], [], label=response_name + "(Original)", visible=False, color=color, ls=ORIGINAL_LINE_STYLE)[0]
                self.primary_line_data[loop][fr_type].original.phase_line = self.sub_plots[PHASE].plot([], [], label=response_name + "(Original)", visible=False, color=color, ls=ORIGINAL_LINE_STYLE)[0]
#end region

#region Plot Space and Toolbar
        layout = gui.plot_view
        figure = FigureCanvas(self.fig)
        figure.setMinimumSize(600,400)
        self.figure_canvas = figure
        toolbar = Custom_Toolbar(figure, self.gui)
        self.toolbar = toolbar

        layout.insertWidget(0, toolbar)
        layout.insertWidget(1, figure)
        double_validator = QDoubleValidator()
        self.gui.active_frequency.setValidator(double_validator)
        self.gui.active_frequency.editingFinished.connect(self.frequency_text_edited_event)
        
        header = self.gui.stability_analysis_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        
        self.loop_to_view_changed()
#end region

#region Events
        plt.connect('motion_notify_event', self.cursor_was_moved_event)
        plt.connect('button_press_event', self.cursor_was_clicked_event)
        plt.connect('button_release_event', self.cursor_was_released_event)

        self.gui.goal_sensitivity_peak.valueChanged.connect(self.analyze_open_loop_margins)
        self.gui.hide_cursor.stateChanged.connect(self.hide_cursor_changed_event)
        self.gui.response_types.itemChanged.connect(self.show_or_hide_responses)
        self.gui.show_original_responses.stateChanged.connect(self.show_or_hide_responses)
        self.gui.show_primary_response_only.stateChanged.connect(self.show_or_hide_responses)
        self.gui.loop_response.currentIndexChanged.connect(self.loop_to_view_changed)
        self.gui.cursor_information.itemExpanded.connect(self.cursor_info_expanded_collapse_event)
        self.gui.cursor_information.itemCollapsed.connect(self.cursor_info_expanded_collapse_event)
#end region

        if len(self.sub_plots[MAGNITUDE].lines) != len(self.sub_plots[PHASE].lines):
            raise AssertionError("The number of magnitude ({}) and phase lines ({}) do not match!" \
                                 .format(len(self.sub_plots[MAGNITUDE].lines), len(self.sub_plots[PHASE].lines)))
        
        self.is_initialized = True

    def connect_resize_event(self) -> None:
        """ Tells the plot module to link to matplotlib's resize canvas event so that we can capture any background changes.
        """
        self.resize_event = self.fig.canvas.mpl_connect("resize_event", self.on_draw)

    def cursor_info_expanded_collapse_event(self, tree_view_item:QTreeWidgetItem) -> None:
        """ Event that is called whenever a tree item is expanded or collapsed in the cursor information section.

        Args:
            tree_view_item (QTreeWidgetItem): The tree item that changed.
        """
        fr_type = tree_view_item.text(0).replace(' ', '_')
        fr_type = FR_Type[fr_type]
        self.cursor_information_expanded[self.get_plotted_loop()][fr_type] = tree_view_item.isExpanded()

    def loop_to_view_changed(self) -> None:
        """ Event that is called whenever the loop view combobox changes.
        """
        self.gui.cursor_information.clear()
        self.gui.response_types.clear()

        loop = self.get_plotted_loop()
        self.fig.suptitle(loop.name.replace('_', ' ') + " Loop", fontsize=BIGGER_SIZE)
        for fr_type in LOOP_RESPONSES[loop]:
            # Create user facing name for the enum.
            response_name = fr_type.name.replace('_', ' ')
            
            # Because we depend on the user facing text to pull the correct response type, changing this casues certain fields to not appear.

            #if response_name.startswith(loop.name):
            #    response_name = response_name[len(loop.name):]

            # Generate response checklist.
            item = QListWidgetItem()
            item.setText(response_name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            
            self.gui.response_types.addItem(item)

            # Generate cursor information.
            parent_item = QTreeWidgetItem()
            parent_item.setText(0, response_name)

            magnitude_item = QTreeWidgetItem()
            magnitude_item.setText(0, MAGNITUDE_LABEL)
            magnitude_item.setText(1, '-')
            magnitude_item.setText(2, '-')

            phase_item = QTreeWidgetItem()
            phase_item.setText(0, PHASE_LABEL)
            phase_item.setText(1, '-')
            phase_item.setText(2, '-')

            parent_item.addChild(magnitude_item)
            parent_item.addChild(phase_item)

            self.gui.cursor_information.addTopLevelItem(parent_item)

            self.cursor_information_expanded[loop][fr_type] = None

        header = self.gui.cursor_information.header()
        for col in range(self.gui.cursor_information.columnCount()):
            header.resizeSection(col, header.sizeHintForColumn(col))
        header.setSectionResizeMode(QHeaderView.ResizeToContents)

        self.update_cursor_information()
        self.analyze_open_loop_margins()
        
        self.restore_checked_state()
        self.refresh_plotter()
        self.update_subplot_limits()
        self.capture_background()
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
        
    background = None
    saving_background = False
    resize_debounce_timer = None
    def on_draw(self, event) -> None:
        """ Callback to register with 'draw_event'. """
        if self.resize_debounce_timer:
            self.resize_debounce_timer.cancel()

        self.resize_debounce_timer = threading.Timer(DEBOUNCE_TIME_INTERVAL, self.capture_background)
        self.resize_debounce_timer.start()

    is_restoring = False
    def show_or_hide_responses(self) -> None:
        """ Event that is called whenever the "show original", response type, or "show primary only" options change.
        """
        if self.is_restoring:
            return
        
        self.update_checked_responses()
        self.refresh_plotter()
        self.update_subplot_limits()
        self.capture_background()

    def capture_background(self) -> None:
        """ Captures the background of the figure. This hides all lines, captures the background, then un-hides the lines.
        By capturing the background of the figure, we can draw new lines rapidly using a technique called "blit". This drastically
        improves cursor and line drawing performance when doing live updates.
        """
        if self.saving_background or not self.is_initialized:
            return
        else:
            self.saving_background = True
            
            #print("capture background")

            # Hide all plots and the cursor
            original_visibility = {}
            shaped_visibility = {}
            cursor_visibility = False
            for loop in Loop_Type:
                for fr_type in LOOP_RESPONSES[loop]:
                    original_visibility[fr_type] = self.primary_line_data[loop][fr_type].original.magnitude_line.get_visible()
                    self.primary_line_data[loop][fr_type].original.magnitude_line.set_visible(False)
                    self.primary_line_data[loop][fr_type].original.phase_line.set_visible(False)

                    shaped_visibility[fr_type] = self.primary_line_data[loop][fr_type].shaped.magnitude_line.get_visible()
                    self.primary_line_data[loop][fr_type].shaped.magnitude_line.set_visible(False)
                    self.primary_line_data[loop][fr_type].shaped.phase_line.set_visible(False)

                    #self.sub_plots[MAGNITUDE].draw_artist(self.line_data[loop][fr_type].shaped.magnitude_line)
                    #self.sub_plots[PHASE].draw_artist(self.line_data[loop][fr_type].shaped.phase_line)
                    #self.sub_plots[MAGNITUDE].draw_artist(self.line_data[loop][fr_type].original.magnitude_line)
                    #self.sub_plots[PHASE].draw_artist(self.line_data[loop][fr_type].original.phase_line)

            for key in self.cursors.keys():
                cursor_visibility = self.cursors[key].get_visible()
                self.cursors[key].set_visible(False)
                #self.sub_plots[MAGNITUDE].draw_artist(cursor)
                #self.sub_plots[PHASE].draw_artist(cursor)

            #legends = [self.sub_plots[MAGNITUDE].legend(), self.sub_plots[PHASE].legend()]
            
            #self.fig.canvas.blit(self.fig.bbox)
            #self.fig.canvas.flush_events()
            self.fig.canvas.draw()
            #self.fig.canvas.draw_idle()
            #self.fig.canvas.flush_events()
            
            #self.saving_background = False
            #return
            # Save the background.
            self.background = self.fig.canvas.copy_from_bbox(self.fig.bbox)

            for loop in Loop_Type:
                for fr_type in LOOP_RESPONSES[loop]:
                    self.primary_line_data[loop][fr_type].original.magnitude_line.set_visible(original_visibility[fr_type])
                    self.primary_line_data[loop][fr_type].original.phase_line.set_visible(original_visibility[fr_type])

                    self.primary_line_data[loop][fr_type].shaped.magnitude_line.set_visible(shaped_visibility[fr_type])
                    self.primary_line_data[loop][fr_type].shaped.phase_line.set_visible(shaped_visibility[fr_type])

                    #self.sub_plots[MAGNITUDE].draw_artist(self.line_data[loop][fr_type].shaped.magnitude_line)
                    #self.sub_plots[PHASE].draw_artist(self.line_data[loop][fr_type].shaped.phase_line)
                    #self.sub_plots[MAGNITUDE].draw_artist(self.line_data[loop][fr_type].original.magnitude_line)
                    #self.sub_plots[PHASE].draw_artist(self.line_data[loop][fr_type].original.phase_line)

            for key in self.cursors.keys():
                self.cursors[key].set_visible(cursor_visibility)
                #self.sub_plots[MAGNITUDE].draw_artist(cursor)
                #self.sub_plots[PHASE].draw_artist(cursor)

            #self.fig.canvas.blit(self.fig.bbox)
            #self.fig.canvas.flush_events()
            

            self.fig.canvas.draw_idle()
            self.fig.canvas.flush_events()
            self.saving_background = False
            

    def is_response_checked(self, loop:Loop_Type, fr_type:FR_Type) -> bool:
        """ Gets whether or not the frequency response is checked for viewing.

        Args:
            loop (Loop_Type): The loop that the frequency response belongs to.
            fr_type (FR_Type): The frequency response to check.

        Returns:
            bool: If the target frequency response is checked.
        """
        return self.checked_responses[loop][fr_type]

    def update_subplot_limits(self) -> None:
        """ Manually updates the limits of the magnitude and phase plots according to the min and max values of the lines
        that are displayed. This also updates the legend according to what's displayed.
        """
        loop = self.get_plotted_loop()
        minimums = { FREQUENCY:Globals.DEFAULT_MIN, MAGNITUDE:Globals.DEFAULT_MIN, PHASE: Globals.DEFAULT_MIN}
        maximums = { FREQUENCY:Globals.DEFAULT_MAX, MAGNITUDE:Globals.DEFAULT_MAX, PHASE: Globals.DEFAULT_MAX}
        original_visibility = self.show_original_response()
        secondary_visibility = not self.show_primary_response_only()
        lines = []
        labels = []
        for fr_type in LOOP_RESPONSES[loop]:
            if self.is_response_checked(loop, fr_type):
                for key in minimums.keys():
                    if key == FREQUENCY:
                        data = np.array(self.primary_line_data[loop][fr_type].shaped.magnitude_line.get_xdata())
                        if original_visibility:
                            data = np.concatenate((data, self.primary_line_data[loop][fr_type].original.magnitude_line.get_xdata()))

                        if secondary_visibility:
                            for filename in self.secondary_line_data.keys():
                                data = np.concatenate((data, self.secondary_line_data[filename][loop][fr_type].shaped.magnitude_line.get_xdata()))
                                if original_visibility:
                                    data = np.concatenate((data, self.secondary_line_data[filename][loop][fr_type].original.magnitude_line.get_xdata()))
                    elif key == MAGNITUDE:
                        data = np.array(self.primary_line_data[loop][fr_type].shaped.magnitude_line.get_ydata())
                        if original_visibility:
                            data = np.concatenate((data, self.primary_line_data[loop][fr_type].original.magnitude_line.get_ydata()))

                        if secondary_visibility:
                            for filename in self.secondary_line_data.keys():
                                data = np.concatenate((data, self.secondary_line_data[filename][loop][fr_type].shaped.magnitude_line.get_ydata()))
                                if original_visibility:
                                    data = np.concatenate((data, self.secondary_line_data[filename][loop][fr_type].original.magnitude_line.get_ydata()))
                    elif key == PHASE:
                        data = np.array(self.primary_line_data[loop][fr_type].shaped.phase_line.get_ydata())
                        if original_visibility:
                            data = np.concatenate((data, self.primary_line_data[loop][fr_type].original.phase_line.get_ydata()))

                        if secondary_visibility:
                            for filename in self.secondary_line_data.keys():
                                data = np.concatenate((data, self.secondary_line_data[filename][loop][fr_type].shaped.phase_line.get_ydata()))
                                if original_visibility:
                                    data = np.concatenate((data, self.secondary_line_data[filename][loop][fr_type].original.phase_line.get_ydata()))
                    else:
                        raise NotImplementedError("Unexpected key: {}".format(key))
                    
                    if len(data) == 0:
                        continue

                    new_min = min(data)
                    if new_min < minimums[key]:
                        minimums[key] = new_min

                    new_max = max(data)
                    if new_max > maximums[key]:
                        maximums[key] = new_max

                """ Decide which lines are listed in the legend. """
                # Always add everything (shaped and original) from the primary response.
                include_primary_filename = len(self.secondary_line_data) != 0
                label_name = get_user_facing_text(loop, fr_type)
                lines.append(self.primary_line_data[loop][fr_type].shaped.magnitude_line)
                labels.append("{}{} ({})".format(self.primary_frd_filename + ' ' if include_primary_filename else "", \
                                label_name, SHAPED))
                if original_visibility:
                    lines.append(self.primary_line_data[loop][fr_type].original.magnitude_line)
                    labels.append("{}{} ({})".format(self.primary_frd_filename + ' ' if include_primary_filename else "", \
                                label_name, ORIGINAL))

                # Only add the secondary shaped response.
                if not self.show_primary_response_only():
                    for key in self.secondary_line_data.keys():
                        lines.append(self.secondary_line_data[key][loop][fr_type].shaped.magnitude_line)
                        labels.append("{} {} ({})".format(key, \
                                label_name, SHAPED))

        self.legend_lines = lines
        self.legend_labels = labels
        # Legend
        
        #self.fig.legend(self.legend_lines, self.legend_labels, prop=self.legend_font, bbox_to_anchor=(1, 0), borderaxespad=0.)
        #self.fig.tight_layout(w_pad=0.5)  
        # (x0,y0,width,height)
        bb = (self.fig.subplotpars.right, self.fig.subplotpars.top,
                self.fig.subplotpars.right-self.fig.subplotpars.left, .1)
        
        from textwrap import wrap
        # https://matplotlib.org/stable/users/explain/axes/legend_guide.html
        self.legend_labels = ['\n'.join(wrap(l, 22)) for l in self.legend_labels]
        #self.sub_plots[LEGEND].legend(self.legend_lines, self.legend_labels, prop=self.legend_font, \
        #                                 loc="upper right", borderaxespad=0. )
        self.sub_plots[LEGEND].legend(self.legend_lines, self.legend_labels, prop=self.legend_font, \
                                        bbox_to_anchor=(0, 0, 1., 0), ncols=6, loc='upper left', mode="expand", borderaxespad=0)

        #self.fig.tight_layout()
        #self.fig.subplots_adjust(left=0, top=1, bottom=0, right=0.825)
        #self.sub_plots[MAGNITUDE].legend(self.legend_lines, self.legend_labels, loc="upper right", prop=self.legend_font, draggable=True)
        #self.sub_plots[PHASE].legend(self.legend_lines, self.legend_labels, loc="upper right", prop=self.legend_font, draggable=True)

        if minimums[FREQUENCY] == Globals.DEFAULT_MIN:
            # No data, do nothing.
            return
        
        def pad(value, is_min=True):
            if value == 0:
                return -10 if is_min else 10
            elif value < 0:
                sign = -1
            else:
                sign = +1

            padded = abs(value/10)
            return sign*abs(value) - padded if is_min else sign*abs(value) + padded

        # Frequency
        #min_exponent = math.floor(np.log10(minimums[FREQUENCY]))
        #max_exponent = math.ceil(np.log10(maximums[FREQUENCY]))
        #self.sub_plots[MAGNITUDE].set_xlim(pad(10**min_exponent), pad(10**max_exponent, is_min=False))
        #self.sub_plots[PHASE].set_xlim(pad(10**min_exponent), pad(10**max_exponent, is_min=False))
        self.sub_plots[MAGNITUDE].set_xlim(pad(minimums[FREQUENCY]), pad(maximums[FREQUENCY], is_min=False))
        self.sub_plots[MAGNITUDE].set_xscale('log')
        self.sub_plots[PHASE].set_xlim(pad(minimums[FREQUENCY]), pad(maximums[FREQUENCY], is_min=False))
        self.sub_plots[PHASE].set_xscale('log')
        
        self.sub_plots[MAGNITUDE].set_ylim(pad(minimums[MAGNITUDE]), pad(maximums[MAGNITUDE], is_min=False))
        #self.sub_plots[PHASE].set_ylim(pad(minimums[PHASE]), pad(maximums[PHASE], is_min=False))

        #self.sub_plots[MAGNITUDE].autoscale_view(tight=True, scalex=True, scaley=True)
        #self.sub_plots[PHASE].autoscale_view(tight=True, scalex=True, scaley=False)


        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def temporarily_show_easytune_plots(self, show=True) -> None:
        """ Temporarily shows EasyTune responses by showing only the servo's shaped and original open loop and sensitivity responses.

        Args:
            show (bool, optional): If we should show the EasyTune responses or revert back to what it was before. Defaults to True.
        """
        if show:
            # Capture the current plot settings to restore later.
            self.temporary_show_original_response = self.gui.show_original_responses.checkState()
            self.temporary_show_primary_response_only = self.gui.show_primary_response_only.checkState()
            self.temporary_get_plotted_loop = self.get_plotted_loop()
            self.temporary_checked_responses = copy.deepcopy(self.checked_responses)

            # Block signals temporarily so that we aren't updating each change.
            self.gui.show_original_responses.blockSignals(True)
            self.gui.show_primary_response_only.blockSignals(True)
            self.gui.loop_response.blockSignals(True)
            self.gui.response_types.blockSignals(True)

            self.gui.show_original_responses.setCheckState(Qt.CheckState.Checked)
            self.gui.show_primary_response_only.setCheckState(Qt.CheckState.Unchecked)
            self.gui.loop_response.setCurrentText(Loop_Type.Servo.name)

            self.loop_to_view_changed()

            # Uncheck all except  open loop and sensitivity
            loop = self.get_plotted_loop() # should always be servo
            for fr_type in LOOP_RESPONSES[loop]:
                response_type_checkboxes: list[QListWidgetItem] = self.gui.response_types.findItems(fr_type.name.replace('_', ' '), Globals.QT_EXACT_MATCH_CRITERIA)
                if len(response_type_checkboxes) != 1:
                    raise LookupError("{} checkbox item(s) exists for the {} response type! There should only be one!".format(len(response_type_checkboxes), fr_type.name))
                
                checkbox = response_type_checkboxes[0]

                if (fr_type == FR_Type.Servo_Open_Loop) or (fr_type == FR_Type.Servo_Sensitivity):
                    checkbox.setCheckState(Qt.CheckState.Checked)
                else:
                    checkbox.setCheckState(Qt.CheckState.Unchecked)

            self.gui.show_original_responses.blockSignals(False)
            self.gui.show_primary_response_only.blockSignals(False)
            self.gui.loop_response.blockSignals(False)
            self.gui.response_types.blockSignals(False)
        else:
            self.gui.show_original_responses.blockSignals(True)
            self.gui.show_primary_response_only.blockSignals(True)
            self.gui.loop_response.blockSignals(True)
            self.gui.response_types.blockSignals(True)

            self.gui.loop_response.setCurrentText(self.temporary_get_plotted_loop.name)
            self.loop_to_view_changed()

            # Restore back to previous
            self.gui.show_original_responses.setCheckState(self.temporary_show_original_response)
            self.gui.show_primary_response_only.setCheckState(self.temporary_show_primary_response_only)
            self.checked_responses = copy.deepcopy(self.temporary_checked_responses)
            self.restore_checked_state()

            self.gui.show_original_responses.blockSignals(False)
            self.gui.show_primary_response_only.blockSignals(False)
            self.gui.loop_response.blockSignals(False)
            self.gui.response_types.blockSignals(False)

    def set_line_data_from_frd_data(self, block_layout:Block_Layout_With_Data, regen_original=False, delete_secondary=False) -> None:
        """ Sets this modules' frequency to plot and all line data that corresponds with the block layout and updates the cursor and stability analysis table.

        Args:
            block_layout (Block_Layout_With_Data): The block layout to set line data from.
            regen_original (bool, optional): If this should update the original line data. Defaults to False.
            delete_secondary (bool, optional): If line data generated from the passed in secondary block layout should be deleted. Defaults to False.
        """
        # The primary response dictates the frequency the plot.
        line_data = {}
        if block_layout.is_primary:
            self.primary_frd_filename = block_layout.filename
            self.primary_frd_data = copy.deepcopy(block_layout.frd_data)

            omega = block_layout.frequency_radians
            are_the_same = Utils.are_arrays_the_same(self.omega, omega)
            recompute_original = regen_original
            if (not are_the_same) or (self.omega is None):
                #print("update omega", omega)
                self.omega = omega
                self.frequency_hz = Utils.radian_to_hertz(omega)
                self.clear_frequency() # Clear frequency information and reset the cursor
                recompute_original = True

                # Auto-check the open loop response iff nothing else is checked.
                loop = self.get_plotted_loop()
                any_checked = False
                for fr_type in LOOP_RESPONSES[loop]:
                    if self.checked_responses[loop][fr_type]:
                        any_checked = True
                        break
                
                if not any_checked:
                    open_loop_type = FR_Type.find_response_for_loop(loop, "Open_Loop")
                    response_type_checkboxes: list[QListWidgetItem] = self.gui.response_types.findItems(open_loop_type.name.replace('_', ' '), Globals.QT_EXACT_MATCH_CRITERIA)
                    if len(response_type_checkboxes) != 1:
                        raise LookupError("{} checkbox item(s) exists for the {} response type! There should only be one!".format(len(response_type_checkboxes), fr_type.name))
                    response_type_checkboxes[0].setCheckState(Qt.CheckState.Checked)

            if not are_the_same:
                self.capture_background()

            line_data = self.primary_line_data

            if recompute_original:
                self.set_line_data(line_data, block_layout, convert_original=True)
        else:
            if delete_secondary:
                del self.secondary_frd_datas[block_layout.filename]
                del self.secondary_line_data[block_layout.filename]

                self.show_or_hide_responses()

                return
            else:
                self.secondary_frd_datas[block_layout.filename] = copy.deepcopy(block_layout.frd_data)

                # Generate line data iff the data does not already exist.
                if block_layout.filename not in self.secondary_line_data.keys():
                    self.secondary_line_data[block_layout.filename] = {}
                    for loop in Loop_Type:
                        self.secondary_line_data[block_layout.filename][loop] = {}
                        for fr_type in LOOP_RESPONSES[loop]:
                            self.secondary_line_data[block_layout.filename][loop][fr_type] = FR_Lines()

                            # Generate line plots.
                            self.secondary_line_data[block_layout.filename][loop][fr_type].shaped.magnitude_line = \
                                self.sub_plots[MAGNITUDE].plot([], [], label=block_layout.filename + "(Shaped)", visible=False)[0]
                            self.secondary_line_data[block_layout.filename][loop][fr_type].shaped.phase_line = \
                                self.sub_plots[PHASE].plot([], [], label=block_layout.filename + "(Shaped)", visible=False)[0]
                            
                            self.secondary_line_data[block_layout.filename][loop][fr_type].original.magnitude_line = \
                                self.sub_plots[MAGNITUDE].plot([], [], label=block_layout.filename + "(Original)", visible=False)[0]
                            self.secondary_line_data[block_layout.filename][loop][fr_type].original.phase_line = \
                                self.sub_plots[PHASE].plot([], [], label=block_layout.filename + "(Original)", visible=False)[0]

                line_data = self.secondary_line_data[block_layout.filename]

        # Convert magnitude and phase.
        self.set_line_data(line_data, block_layout)

        self.show_or_hide_responses()
        self.update_cursor_information()

        # Update the plot statistics as we only need to do this once we load something!
        self.analyze_open_loop_margins()

        # print("set frequencies, update plotter")

    def convert_magnitude_and_phase(self, magnitude:list[float], phase_radians:list[float]) -> tuple[list[float], list[float]]:
        """ The magnitudes and phases to convert to dB and hertz.

        Args:
            magnitude (list[float]): The magnitudes to convert to dB.
            phase_radians (list[float]): The phases to convert to hertz.

        Returns:
            tuple[list[float], list[float]]: [The magnitudes in dB, The phases in hertz]
        """
        magnitude_db = Utils.to_dB(magnitude)
        phase_degrees = np.degrees(phase_radians)
        try:
            for i in range(len(phase_degrees)):
                phase_degrees[i] = Utils.wrap_phase(phase_degrees[i])
        except:
            phase_degrees = Utils.wrap_phase(phase_degrees)
        return [np.array(magnitude_db), np.array(phase_degrees)]

    def set_line_data(self, line_data:dict, block_layout:Block_Layout_With_Data, convert_original=False) -> None:
        """ Does the actual computation of the magnitude (dB) and phase (degrees) at the saved frequencies.

        Args:
            line_data (dict): The line data to set.
            block_layout (Block_Layout_With_Data): The block layout to get data from.
            convert_original (bool, optional): If the original line data should be updated. Defaults to False.
        """
        def convert_frd(frd, omega):
            # Limit the evaluating frequencies to whatever the primary range is (prevent extrapolation).
            is_valid = False
            try:
                frd_data = frd.eval(omega)
                [magnitude, phase_radians] = Utils.complex_to_magnitude_and_phase(frd_data) # phase is already wrapped between [-pi, pi]
                is_valid = True
            except ValueError as e:
                if convert_original:
                    #print("[Warning] Cannot plot the original {} due to change in frequencies.".format(fr_type))
                    pass
                else:
                    print("[Warning] Cannot plot the {} {} due to invalid inputs. Error: {}".format("shaped" if not convert_original else "original", fr_type, e))

                return [False, [], []]
            except Exception as e:
                print("Unable to evaluate the system at the given frequencies for FR Type {}! Smooth={}".format(fr_type, e, frd.ifunc != None))
                raise

            return [is_valid] + self.convert_magnitude_and_phase(magnitude, phase_radians)

        do_once = True
        omega = self.omega
        frequency_hz = Utils.radian_to_hertz(omega)
        frd_dict = block_layout.frd_data
        for loop in Loop_Type:
            for fr_type in LOOP_RESPONSES[loop]:
                if convert_original:
                    frd = frd_dict[loop][fr_type].original
                else:
                    frd = frd_dict[loop][fr_type].shaped

                # Clear then set for sanity.
                if convert_original:
                    line_data[loop][fr_type].original.magnitude_line.set_data([], [])
                    line_data[loop][fr_type].original.phase_line.set_data([], [])
                else:
                    line_data[loop][fr_type].shaped.magnitude_line.set_data([], [])
                    line_data[loop][fr_type].shaped.phase_line.set_data([], [])

                if frd is None:
                    continue
                else:
                    # HACK: If the frequency arrays are basically the same, fuzz the desired frequencies to be equal to the frequencies stored in the frd.
                    # After getting the close enough magnitudes and phases, use the original desired frequencies when plotting.
                    if do_once:
                        do_once = False

                        # Assumes that all FRDs share the same frequency values.
                        if Utils.are_arrays_the_same(self.omega, frd.frequency) and not Utils.are_arrays_exactly_the_same(self.omega, frd.frequency):
                            # These are close enough according to our fuzz but the frd.eval() function will bitch that these aren't the same resulting in
                            # no plot.
                            omega = frd.frequency
                            
                    [is_valid, magnitude_db, phase_degrees] = convert_frd(frd, omega)

                # Set if valid.
                if is_valid:
                    if convert_original:
                        line_data[loop][fr_type].original.magnitude_line.set_data(frequency_hz, magnitude_db)
                        line_data[loop][fr_type].original.phase_line.set_data(frequency_hz, phase_degrees)
                    else:
                        line_data[loop][fr_type].shaped.magnitude_line.set_data(frequency_hz, magnitude_db)
                        line_data[loop][fr_type].shaped.phase_line.set_data(frequency_hz, phase_degrees)

    def analyze_open_loop_margins(self) -> None:
        """ Analyzes open loop margins.
        """
        if self.primary_frd_data is None:
            return
        
        """ Performs a stability analysis on the open-loop response and updates the stability table.
        """
        data = []
        loop_type = self.get_plotted_loop()

        if loop_type == Loop_Type.Servo:
            fr_type = FR_Type.Servo_Open_Loop
        elif loop_type == Loop_Type.Current:
            fr_type = FR_Type.Current_Open_Loop

        self.gui.stability_analysis_group_box.setTitle(fr_type.name.replace('_', ' ') + " Stability Analysis")

        shaped_frd = self.primary_frd_data[loop_type][fr_type].shaped
        if shaped_frd is not None:
            [gain_margin, phase_margin, sensitivity_margin, \
            gain_crossover_frequency, phase_crossover_frequency, sensitivity_crossover_frequency] = control.stability_margins(shaped_frd)
            data += [["Shaped Gain Margin (dB)", Utils.to_dB(gain_margin), Utils.radian_to_hertz(gain_crossover_frequency)], \
                    ["Shaped Phase Margin (degrees)", phase_margin, Utils.radian_to_hertz(phase_crossover_frequency)], \
                    ["Shaped Sensitivity (dB)", -Utils.to_dB(sensitivity_margin), Utils.radian_to_hertz(sensitivity_crossover_frequency)]]
        
        original_frd = self.primary_frd_data[loop_type][fr_type].original
        if original_frd is not None:
            [gain_margin, phase_margin, sensitivity_margin, \
            gain_crossover_frequency, phase_crossover_frequency, sensitivity_crossover_frequency] = control.stability_margins(original_frd)
            data += [["Original Gain Margin (dB)", Utils.to_dB(gain_margin), Utils.radian_to_hertz(gain_crossover_frequency)], \
                    ["Original Phase Margin (degrees)", phase_margin, Utils.radian_to_hertz(phase_crossover_frequency)], \
                    ["Original Sensitivity (dB)", -Utils.to_dB(sensitivity_margin), Utils.radian_to_hertz(sensitivity_crossover_frequency)]]
        
        # Clear then reset the table.
        self.gui.stability_analysis_table.setRowCount(0)
        self.gui.stability_analysis_table.setRowCount(len(data))

        for row in range(len(data)):
            for column in range(len(data[row])):
                value = data[row][column]
                if type(value) != str:
                    value = "{:0.4g}".format(value)

                item = QTableWidgetItem(value)

                if ("Sensitivity" in data[row][0]) and (column == 1):
                    if float(value) > self.gui.goal_sensitivity_peak.value():
                        item.setBackground(QColor(255, 207, 207)) # Light Red.
                    else:
                        item.setBackground(QColor(255, 255, 255)) # White.

                self.gui.stability_analysis_table.setItem(row, column, item)

    def update_checked_responses(self) -> None:
        """ Event that is called to cache what responses were checked off by the user.
        """
        loop = self.get_plotted_loop()

        for fr_type in LOOP_RESPONSES[loop]:
            response_type_checkboxes: list[QListWidgetItem] = self.gui.response_types.findItems(fr_type.name.replace('_', ' '), Globals.QT_EXACT_MATCH_CRITERIA)
            if len(response_type_checkboxes) != 1:
                raise LookupError("{} checkbox item(s) exists for the {} response type! There should only be one!".format(len(response_type_checkboxes), fr_type.name))
            
            checkbox = response_type_checkboxes[0]
            is_checked = checkbox.checkState() == Qt.CheckState.Checked
            self.checked_responses[loop][fr_type] = is_checked

    def show_original_response(self) -> bool:
        """ Gets whether or not the show original response checkbox was checked or not.

        Returns:
            bool: True, if checked. False, otherwise.
        """
        return self.gui.show_original_responses.checkState() == Qt.CheckState.Checked
    
    def show_primary_response_only(self) -> bool:
        """ Gets whether or not the show primary response only checkbox was checked or not.

        Returns:
            bool: True, if checked. False, otherwise.
        """
        return self.gui.show_primary_response_only.checkState() == Qt.CheckState.Checked
    
    def restore_checked_state(self) -> None:
        """ Based off of what response were checked for this loop type (cached), restore what was checked due to a change in loop view.
        """
        self.is_restoring = True
        loop = self.get_plotted_loop()
        for fr_type in LOOP_RESPONSES[loop]:
            response_type_checkboxes: list[QListWidgetItem] = self.gui.response_types.findItems(fr_type.name.replace('_', ' '), Globals.QT_EXACT_MATCH_CRITERIA)
            if len(response_type_checkboxes) != 1:
                raise LookupError("{} checkbox item(s) exists for the {} response type! There should only be one!".format(len(response_type_checkboxes), fr_type.name))
            
            checkbox = response_type_checkboxes[0]
            #print("restore checkstate {} {}".format(fr_type, self.checked_responses[loop][fr_type]))
            checkbox.setCheckState(Qt.CheckState.Checked if self.checked_responses[loop][fr_type] else Qt.CheckState.Unchecked)
        self.is_restoring = False

    def get_plotted_loop(self) -> Loop_Type:
        """ Gets the currently plotted loop.
        """
        for loop in Loop_Type:
            if self.gui.loop_response.currentText() == loop.name:
                return loop
        return None
    

    def refresh_plotter(self) -> None:
        """ Redraws the plotter according to what responses were checked, if the original response should be displayed, and what loop is currently displayed. 
        Assumes that all lines have been updated before redrawing.
        """
        if self.background and not self.saving_background:
            cv = self.fig.canvas
            cv.restore_region(self.background)
        else:
            return

        original_visibility = self.show_original_response()
        
        for loop in Loop_Type:
            if self.get_plotted_loop() != loop:
                # Make all invisible.
                for fr_type in LOOP_RESPONSES[loop]:
                    self.primary_line_data[loop][fr_type].shaped.magnitude_line.set_visible(False)
                    self.primary_line_data[loop][fr_type].shaped.phase_line.set_visible(False)
                    self.primary_line_data[loop][fr_type].original.magnitude_line.set_visible(False)
                    self.primary_line_data[loop][fr_type].original.phase_line.set_visible(False)

                    self.sub_plots[MAGNITUDE].draw_artist(self.primary_line_data[loop][fr_type].shaped.magnitude_line)
                    self.sub_plots[PHASE].draw_artist(self.primary_line_data[loop][fr_type].shaped.phase_line)
                    self.sub_plots[MAGNITUDE].draw_artist(self.primary_line_data[loop][fr_type].original.magnitude_line)
                    self.sub_plots[PHASE].draw_artist(self.primary_line_data[loop][fr_type].original.phase_line)

                    for filename in self.secondary_line_data.keys():
                        self.secondary_line_data[filename][loop][fr_type].shaped.magnitude_line.set_visible(False)
                        self.secondary_line_data[filename][loop][fr_type].shaped.phase_line.set_visible(False)
                        self.secondary_line_data[filename][loop][fr_type].original.magnitude_line.set_visible(False)
                        self.secondary_line_data[filename][loop][fr_type].original.magnitude_line.set_visible(False)

                        self.sub_plots[MAGNITUDE].draw_artist(self.secondary_line_data[filename][loop][fr_type].shaped.magnitude_line)
                        self.sub_plots[PHASE].draw_artist(self.secondary_line_data[filename][loop][fr_type].shaped.phase_line)
                        self.sub_plots[MAGNITUDE].draw_artist(self.secondary_line_data[filename][loop][fr_type].original.magnitude_line)
                        self.sub_plots[PHASE].draw_artist(self.secondary_line_data[filename][loop][fr_type].original.phase_line)
            else:
                for fr_type in LOOP_RESPONSES[loop]:
                    # Search for the checkbox item that corresponds to this response type.
                    shaped_visibility = self.checked_responses[loop][fr_type] and len(self.primary_line_data[loop][fr_type].shaped.magnitude_line.get_xdata())

                    #print("loop {} fr_type {} show {} original {}".format(loop, fr_type,shaped_visibility, original_visibility))

                    self.primary_line_data[loop][fr_type].shaped.magnitude_line.set_visible(shaped_visibility)
                    self.primary_line_data[loop][fr_type].shaped.phase_line.set_visible(shaped_visibility)

                    if self.show_primary_response_only():
                        for filename in self.secondary_line_data.keys():
                            self.secondary_line_data[filename][loop][fr_type].shaped.magnitude_line.set_visible(False)
                            self.secondary_line_data[filename][loop][fr_type].shaped.phase_line.set_visible(False)
                            self.secondary_line_data[filename][loop][fr_type].original.magnitude_line.set_visible(False)
                            self.secondary_line_data[filename][loop][fr_type].original.magnitude_line.set_visible(False)

                            self.sub_plots[MAGNITUDE].draw_artist(self.secondary_line_data[filename][loop][fr_type].shaped.magnitude_line)
                            self.sub_plots[PHASE].draw_artist(self.secondary_line_data[filename][loop][fr_type].shaped.phase_line)
                            self.sub_plots[MAGNITUDE].draw_artist(self.secondary_line_data[filename][loop][fr_type].original.magnitude_line)
                            self.sub_plots[PHASE].draw_artist(self.secondary_line_data[filename][loop][fr_type].original.phase_line)
                    else:
                        for filename in self.secondary_line_data.keys():
                            self.secondary_line_data[filename][loop][fr_type].shaped.magnitude_line.set_visible(shaped_visibility)
                            self.secondary_line_data[filename][loop][fr_type].shaped.phase_line.set_visible(shaped_visibility)
                            #self.secondary_line_data[filename][loop][fr_type].original.magnitude_line.set_visible(False)
                            #self.secondary_line_data[filename][loop][fr_type].original.magnitude_line.set_visible(False)

                            self.sub_plots[MAGNITUDE].draw_artist(self.secondary_line_data[filename][loop][fr_type].shaped.magnitude_line)
                            self.sub_plots[PHASE].draw_artist(self.secondary_line_data[filename][loop][fr_type].shaped.phase_line)
                            #self.sub_plots[MAGNITUDE].draw_artist(self.secondary_line_data[filename][loop][fr_type].original.magnitude_line)
                            #self.sub_plots[PHASE].draw_artist(self.secondary_line_data[filename][loop][fr_type].original.phase_line)

                    response_cursor_information: list[QTreeViewWidgetItem] = self.gui.cursor_information.findItems(fr_type.name.replace('_', ' '), Globals.QT_EXACT_MATCH_CRITERIA)
                    if len(response_cursor_information) != 1:
                        raise LookupError("{} tree view item(s) exists for the {} response type! There should only be one!".format(len(response_type_checkboxes), fr_type.name))
                    
                    # Update the response based off of if it was checked or not.
                    cursor_info_expanded = self.cursor_information_expanded[loop][fr_type]

                    if shaped_visibility:
                        response_cursor_information[0].setExpanded(cursor_info_expanded if cursor_info_expanded is not None else True)
                        self.primary_line_data[loop][fr_type].original.magnitude_line.set_visible(original_visibility)
                        self.primary_line_data[loop][fr_type].original.phase_line.set_visible(original_visibility)
                    else:
                        response_cursor_information[0].setExpanded(cursor_info_expanded if cursor_info_expanded is not None else False)
                        self.primary_line_data[loop][fr_type].original.magnitude_line.set_visible(False)
                        self.primary_line_data[loop][fr_type].original.phase_line.set_visible(False)
                    
                    self.sub_plots[MAGNITUDE].draw_artist(self.primary_line_data[loop][fr_type].shaped.magnitude_line)
                    self.sub_plots[PHASE].draw_artist(self.primary_line_data[loop][fr_type].shaped.phase_line)
                    self.sub_plots[MAGNITUDE].draw_artist(self.primary_line_data[loop][fr_type].original.magnitude_line)
                    self.sub_plots[PHASE].draw_artist(self.primary_line_data[loop][fr_type].original.phase_line)

        for key in self.cursors.keys():
            # Set visibility first before redrawing.
            self.cursors[key].set_xdata([self.cursor_frequency])
            self.cursors[key].set_visible(self.cursor_is_visible)
            self.sub_plots[key].draw_artist(self.cursors[key])

        if self.background:
            cv.blit(self.fig.bbox)
            cv.flush_events()

#region Cursor
    cursors = {MAGNITUDE:None, PHASE:None}
    cursor_click_event = None
    cursor_frequency = 0.0
    cursor_frequency_index = -1
    cursor_is_visible = False
    cursor_is_in_magnitude = False
    cursor_is_in_phase = False
    cursor_closest_information = {FILENAME:None, FR_TYPE:None, FREQUENCY:None, MAGNITUDE:None, PHASE:None}

    def update_frequency(self, frequency:float) -> None:
        """ Updates the crosshair on the plot.

        Args:
            frequency (float): The raw frequency or x position of the cursor.
        """
        [frequency, frequency_index] = self.snap_to_frequency(frequency)
        self.cursor_frequency_index = frequency_index
        self.cursor_frequency = frequency

        # Update frequency text field.
        self.gui.active_frequency.setText(str(frequency))

        self.update_cursor_information()

    def clear_frequency(self) -> None:
        """ Clears the frequency of the cursor.
        """
        self.gui.active_frequency.clear()
        self.cursor_frequency_index = -1
        self.update_cursor_information()

    def cursor_set_visibility(self, visibility:bool) -> None:
        """ Set the visibility of the cursor.

        Args:
            visibility (bool): The visibility to set the cursor to.
        """
        self.cursor_is_visible = visibility
        self.refresh_plotter()

    def update_cursor_information(self):
        """ Updates the cursor information displayed.
        """
        if not self.is_initialized:
            return
        
        if self.cursor_frequency_index == -1:
            return
        
        for loop in Loop_Type:
            for fr_type in LOOP_RESPONSES[loop]:
                # Convert enum to name (replace underscore with space).
                fr_name = fr_type.name.replace('_', ' ')

                # Find item first.
                items: list[QTreeWidgetItem] = self.gui.cursor_information.findItems(fr_name, Globals.QT_EXACT_MATCH_CRITERIA)
                num_items = len(items)
                if num_items != 1:
                    if num_items == 0:
                        # Items that aren't loaded due to a different loop type.
                        continue
                    else:
                        raise RuntimeError("Zero or multiple items ({}) were found for the {} response type! ".format(num_items, fr_name))
                else:
                    keys = [SHAPED, ORIGINAL]
                    for key in keys:
                        index_to_use = None
                        magnitude = '-'
                        phase = '-'
                        
                        if key == SHAPED:
                            column = 1
                            frequency_array1 = self.primary_line_data[loop][fr_type].shaped.magnitude_line.get_xdata()
                            magnitude_array = self.primary_line_data[loop][fr_type].shaped.magnitude_line.get_ydata()
                            frequency_array2 = self.primary_line_data[loop][fr_type].shaped.phase_line.get_xdata()
                            phase_array = self.primary_line_data[loop][fr_type].shaped.phase_line.get_ydata()

                            # The shaped frequency must always be up-to-date and match exactly.
                            if len(frequency_array1):
                                index_to_use = self.cursor_frequency_index
                        else:
                            column = 2
                            frequency_array1 = self.primary_line_data[loop][fr_type].original.magnitude_line.get_xdata()
                            magnitude_array = self.primary_line_data[loop][fr_type].original.magnitude_line.get_ydata()
                            frequency_array2 = self.primary_line_data[loop][fr_type].original.phase_line.get_xdata()
                            phase_array = self.primary_line_data[loop][fr_type].original.phase_line.get_ydata()

                            # The original frequency may differ from the shaped frequency.
                            # Are they the same?
                            if len(frequency_array1):
                                if Utils.are_arrays_the_same(frequency_array1, self.frequency_hz):
                                    #print("array the same!", len(frequency_array1), len(self.frequency_hz))
                                    # Yes, just use this index.
                                    index_to_use = self.cursor_frequency_index
                                else:
                                    # No, get where this index truly is.
                                    #print("array not the same!")
                                    index_to_use = Utils.find_float_in_array(frequency_array1, self.cursor_frequency)

                                    if (index_to_use == -1) and \
                                        (frequency_array1[0] <= self.cursor_frequency) and (self.cursor_frequency <= frequency_array1[-1]):
                                        raise ValueError("The desired frequency was not found for {} {} despite being within range! {} not in {}".format(self.cursor_frequency, key.lower(), fr_type, frequency_array1))

                        if (len(frequency_array1) != len(frequency_array2)) or \
                            (len(frequency_array1) != len(magnitude_array)) or \
                            (len(magnitude_array) != len(phase_array)):
                            raise RuntimeError("The {}'s {} magnitude ({}), phase ({}), frequency1 ({}), or frequency2 ({}) lengths do not match!".format( \
                                fr_type, key.lower(), len(magnitude_array), len(phase_array), len(frequency_array1), len(frequency_array2)))
                        
                        # Because the frequency range can grow or shrink, we need to check for indexes and offset them if needed.
                        # 1.) If the index is out of range, then set empty.
                        # 2.) If the index range does not match, then offset accordingly.
                        try:
                            if index_to_use is not None:
                                magnitude = Utils.format_float(magnitude_array[index_to_use])
                                phase = Utils.format_float(phase_array[index_to_use])
                            else:
                                # Out of range. No data to report.
                                pass
                        except:
                            print("FR_Type: {} key:{}".format(fr_type, key.lower()))
                            raise

                        # Column, Role, Value.
                        items[0].child(0).setData(column, 0, magnitude) # Magnitude
                        items[0].child(1).setData(column, 0, phase) # Phase

    def hide_cursor_changed_event(self):
        """ Event called when the hide cursor checkbox has changed.
        """
        if self.gui.hide_cursor.isChecked() and self.cursor_is_visible:
            self.cursor_set_visibility(False)
        elif not self.gui.hide_cursor.isChecked() and not self.cursor_is_visible:
            self.cursor_set_visibility(True)
        else:
            return

    def frequency_text_edited_event(self):
        """ Event called when the frequency text field has changed.
        """
        self.update_frequency(float(self.gui.active_frequency.text()))

    def snap_to_frequency(self, frequency:float) -> tuple[float, int]:
        """ Snaps the raw frequency from the cursor to the closest real data point.

        Args:
            frequency (float): The frequency to try and snap.

        Returns:
            tuple[float, int]: [The snapped frequency, The index of the snapped frequency]
        """
        if len(self.frequency_hz) == 0:
            return [-1, -1]
        
        # Clamp frequency to edges or snap to closest data point.
        frequency_index = -1
        if frequency < min(self.frequency_hz):
            frequency = min(self.frequency_hz)
            frequency_index = 0
        elif frequency > max(self.frequency_hz):
            frequency = max(self.frequency_hz)
            frequency_index = len(self.frequency_hz)-1
        else:
            # Snap to closest frequency.
            for i in range(1, len(self.frequency_hz)):
                if (self.frequency_hz[i-1] <= frequency) and (frequency <= self.frequency_hz[i]):
                    # In range.
                    if (frequency - self.frequency_hz[i-1]) <= (self.frequency_hz[i] - frequency):
                        # Lower bound is closer to cursor.
                        frequency = self.frequency_hz[i-1]
                        frequency_index = i-1
                    else:
                        # Upper bound is closer to cursor.
                        frequency = self.frequency_hz[i]
                        frequency_index = i
                    break
        
        return [frequency, frequency_index]

    def cursor_was_moved_event(self, event):
        """ Processes the mouse event for when the mouse moves.
        """
        if self.primary_frd_data is None:
            # No data to process, do nothing.
            return

        # Not in axes, clear the dynamic plot text.
        if event.inaxes is None:
            if self.cursor_text:
                # Clear cursor text.
                pass
        else:
            active_tool = self.toolbar.canvas.toolbar.mode.name
            self.cursor_closest_information[FR_TYPE] = None
            cursor_frequency = event.xdata # frequency
            cursor_value = event.ydata # magnitude or phase
            ax = event.inaxes

            self.is_in_magnitude = ax.get_ylabel() == MAGNITUDE_LABEL
            self.is_in_phase = ax.get_ylabel() == PHASE_LABEL
            if self.is_in_magnitude and self.is_in_phase:
                raise RuntimeError("Internal error. Did not expect to find the cursor in both the magnitude and phase plots.")
            elif (not self.is_in_magnitude) and (not self.is_in_phase):
                # Not in either plot (but in the legend "plot"), do nothing.
                return

            # In axes and was click and dragged, update cursor.
            if self.cursor_click_event and (event.inaxes == self.cursor_click_event.inaxes):
                # Actually, only update the cursor info iff the cursor is visible and no tools are selected.
                if self.cursor_is_visible and (active_tool == "NONE"):
                    self.update_frequency(cursor_frequency)
                    self.refresh_plotter()
            
            # Find the nearest data point given this frequency.
            min_distance = Globals.DEFAULT_MIN
            cursor_omega = Utils.hertz_to_radian(cursor_frequency)
            def check_closest_then_update(filename, frd):
                if frd is None:
                    return
                
                nonlocal min_distance
                nonlocal cursor_frequency
                nonlocal cursor_omega

                # Find which point on this secondary response is the closest to where we are now.
                closest_idx = np.searchsorted(frd.frequency, cursor_omega)
                if closest_idx == len(frd.frequency):
                    closest_idx = len(frd.frequency)-1

                frequency = Utils.radian_to_hertz(frd.frequency[closest_idx])
                magnitude = frd.magnitude[0][0][closest_idx]
                phase = frd.phase[0][0][closest_idx]
                [magnitude, phase] = self.convert_magnitude_and_phase(magnitude, phase)
                value = magnitude if self.is_in_magnitude else phase

                distance = math.sqrt((frequency-cursor_frequency)**2 + (value-cursor_value)**2)
                if distance < min_distance:
                    # Found the closest file and response.
                    min_distance = distance
                    self.cursor_closest_information[FILENAME] = filename
                    self.cursor_closest_information[FR_TYPE] = fr_type
                    self.cursor_closest_information[FREQUENCY] = frequency
                    self.cursor_closest_information[MAGNITUDE] = magnitude
                    self.cursor_closest_information[PHASE] = phase

            loop = self.get_plotted_loop()

            # Check the primary response first.
            for fr_type in LOOP_RESPONSES[loop]:
                is_checked = self.checked_responses[loop][fr_type]
                if is_checked:
                    # Check this response.
                    frd = self.primary_frd_data[loop][fr_type].shaped
                    check_closest_then_update(self.primary_frd_filename, frd)

            # Check all secondary responses next.
            for filename in self.secondary_frd_datas.keys():
                frd_dict = self.secondary_frd_datas[filename]
                for fr_type in LOOP_RESPONSES[loop]:
                    is_checked = self.checked_responses[loop][fr_type]
                    if is_checked:
                        # Check this response.
                        frd = frd_dict[loop][fr_type].shaped
                        check_closest_then_update(filename, frd)

            if self.cursor_closest_information[FILENAME]:
                #print("closest response is {} {}".format(self.cursor_closest_information[FILENAME], self.cursor_closest_information[FR_TYPE]))
                pass

    def cursor_was_clicked_event(self, event):
        """ Processes the event for when any mouse button has been clicked. Occurs once even when a mouse button is being held down.
        """
        if not event.inaxes:
            return
        
        self.cursor_click_event = event

    def cursor_was_released_event(self, event):
        self.cursor_click_event = None

#endregion