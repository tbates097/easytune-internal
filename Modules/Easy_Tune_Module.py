import threading
import control
import numpy as np
from scipy import stats
import time
import Utils
import os
import traceback

import a1_interface
from Block_Layout import Block_Layout_With_Data
from Blocks import Filter_Model, FilterType, Enhanced_Tracking_Control, FILTER_PARAMETER_MAPPING
from FRD_Data import Loop_Type, FR_Type, LOOP_RESPONSES, get_user_facing_text

# Only import GUI modules if needed
GUI_AVAILABLE = False
try:
    from pyqt_ui import Ui_MainWindow
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import *
    from Modules.Block_Explorer_Module import Block_Explorer_Module
    GUI_AVAILABLE = True
except ImportError:
    pass

MODULE_NAME = "EasyTune"

OPTIMIZATION_TARGET_RANGE_MIN = -3
OPTIMIZATION_TARGET_RANGE_MAX = +3

class Easy_Tune_Module():
    def __init__(self, gui:Ui_MainWindow=None, block_layout_module:Block_Explorer_Module=None):
        self.is_headless = gui is None
        self.gui = gui
        self.block_layout_module = block_layout_module
        self.active_thread = None
        self.did_easy_tune_succeed = False
        self.servo_controller = None
        self.zip_directory = None
        self.exception = None
        self.fr_filepath = None
        self.results = None  # Store analysis results
        self.original_frd = None
        self.results_filepath = None  # Store path to results file

        # Only setup GUI components if gui is provided
        if gui is not None:
            self.setup_gui()

    def setup_gui(self):
        # Add custom layout to toolbar.
        widget = QWidget()
        layout = QHBoxLayout()
        
        """ Left Column. """
        left_column_layout = QVBoxLayout()
        first_row_layout = QHBoxLayout()
        second_row_layout = QHBoxLayout()
        left_column_layout.addLayout(first_row_layout)
        left_column_layout.addLayout(second_row_layout)

        # Module Name.
        label = QLabel(MODULE_NAME)
        font = QFont()
        font.setBold(True)
        label.setFont(font)
        first_row_layout.addWidget(label)

       # spacer = QSpacerItem(100, 1)
       # first_row_layout.addSpacerItem(spacer)

        # Run Button.
        self.action_button = QPushButton("&Run")
        self.action_button.setFixedWidth(54)
        self.action_button.pressed.connect(self.run_easy_tune)
        second_row_layout.addWidget(self.action_button)

        # Running progress bar.
        self.progress_bar = QProgressBar()
        size_policy = self.progress_bar.sizePolicy()
        size_policy.setRetainSizeWhenHidden(True)
        self.progress_bar.setSizePolicy(size_policy)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0) # Setting the minimum and maximum to 0 makes the progress bar indeterminate.
        self.progress_bar.setFixedWidth(100)
        self.progress_bar.setVisible(False)
        self.progress_bar.valueChanged.connect(self.thread_changed_state)
        second_row_layout.addWidget(self.progress_bar)

        """ Right Column. """
        right_column_layout = QVBoxLayout()
        first_row_layout = QHBoxLayout()
        second_row_layout = QHBoxLayout()
        right_column_layout.addLayout(first_row_layout)
        right_column_layout.addLayout(second_row_layout)

        # Performance Slider.
        self.slider = QSlider()
        self.slider.setOrientation(Qt.Orientation.Horizontal)
        self.slider.setFixedWidth(400)
        self.slider.setFixedHeight(20)
        self.slider.setTickInterval(1)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setMinimum(OPTIMIZATION_TARGET_RANGE_MIN)
        self.slider.setMaximum(OPTIMIZATION_TARGET_RANGE_MAX)
        self.slider.setSingleStep(1)
        self.slider.setSliderPosition(0)
        first_row_layout.addWidget(self.slider)

        label = QLabel("Conservative")
        label.setToolTip("Handle variations in load better.")
        second_row_layout.addWidget(label)
        
        spacer = QSpacerItem(105, 1)
        second_row_layout.addSpacerItem(spacer)

        label = QLabel("Normal")
        second_row_layout.addWidget(label)

        spacer = QSpacerItem(95, 1)
        second_row_layout.addSpacerItem(spacer)

        label = QLabel("Aggressive")
        label.setToolTip("Better tracking performance.")
        second_row_layout.addWidget(label)

        """ Spacer Column """
        spacer_column_layout = QVBoxLayout()
        spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
        spacer_column_layout.addSpacerItem(spacer)

        """ Add the finalized layout. """
        layout.addLayout(left_column_layout)
        layout.addLayout(right_column_layout)
        layout.addLayout(spacer_column_layout)
        widget.setLayout(layout)
        self.gui.easy_tune_module.addWidget(widget)

    def run_easy_tune(self, fr_filepath=None, verification=False) -> None:
        """Launches EasyTune in a separate thread."""
        self.verification = verification
        # For headless mode (A1TestBed.py)
        if self.block_layout_module is None:
            if fr_filepath is None:
                raise ValueError("fr_filepath is required when running without block_layout_module")
            if self.active_thread is None:
                self.fr_filepath = fr_filepath
                self.active_thread = threading.Thread(target=self.easy_tune_thread)
                self.active_thread.start()
                
        # For GUI mode
        else:
            if self.active_thread is None:
                if self.block_layout_module.primary_block_layout is not None:
                    # Get FR filepath from block layout if not provided
                    self.fr_filepath = fr_filepath or self.block_layout_module.primary_block_layout.filename
                    self.active_thread = threading.Thread(target=self.easy_tune_thread)
                    self.active_thread.start()
                else:
                    raise ValueError("No block layout loaded - please load an FR file first")

    def set_thread_state(self, thread_started:bool) -> None:
        """Update thread state and GUI if available"""
        if not self.is_headless:
            if thread_started:
                self.progress_bar.setValue(1)
                self.progress_bar.setVisible(True)
            else:
                self.progress_bar.setValue(0)
                self.progress_bar.setVisible(False)

    def thread_changed_state(self) -> None:
        """ The event thats called whenever the progress bar changes values. This ultimately is called in the
        application thread and is used to handle gui changes where we normally couldn't from any secondary threads.
        """
        if self.is_headless:
            return
        
        def popup_button_clicked(button):
            if button.text() == "&Yes":
                # Accept EasyTune changes.
                self.block_layout_module.accept_optimized_controller()
            else:
                # Reject EasyTune changes.
                self.block_layout_module.restore_pre_optimized_controller()

        if self.progress_bar.value():
            # Started.
            self.progress_bar.setVisible(True)
        else:
            # Ended.
            self.progress_bar.setVisible(False)

            if self.did_easy_tune_succeed:
                self.block_layout_module.display_optimized_controller(self.servo_controller)

                # Display popup.
                # https://www.techwithtim.net/tutorials/python-module-walk-throughs/pyqt5-tutorial/messageboxes
                popup = QMessageBox()
                popup.setWindowTitle("EasyTune Completed")
                popup.setIcon(QMessageBox.Question)
                popup.setText("Would you like to keep these changes?")
                popup.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                popup.setDefaultButton(QMessageBox.Yes)
                popup.setInformativeText("Logs written to:\n" + self.zip_directory)
                popup.buttonClicked.connect(popup_button_clicked)
                popup.exec_()
            else:
                popup = QMessageBox()
                popup.setWindowTitle("EasyTune Completed")
                popup.setIcon(QMessageBox.Critical)
                popup.setText("EasyTune failed to optimize the response.")
                popup.setInformativeText("Logs written to:\n" + self.zip_directory if self.zip_directory else "")
                if self.exception:
                    popup.setDetailedText("Exception: " + repr(self.exception))
                popup.setStandardButtons(QMessageBox.Ok)
                popup.exec_()

    @staticmethod
    def analyze_plant_ff_match(block_layout_with_data, loop_type=Loop_Type.Servo):
        """Analyze how well the Inverse Feedforward matches the Plant response"""
        
        # Get frequency response data
        servo_plant = block_layout_with_data.frd_data[loop_type][FR_Type.Servo_Plant]
        servo_ff = block_layout_with_data.frd_data[loop_type][FR_Type.Servo_Inverse_Feedforward]
        
        # Get frequencies in Hz and convert to 1D array
        freq_hz = np.asarray(Utils.radian_to_hertz(servo_plant.shaped.frequency)).flatten()
        
        # Filter data to only include frequencies between 40-200 Hz
        mask = (freq_hz >= 40) & (freq_hz <= 200)
        freq_hz_filtered = freq_hz[mask]
        
        # Get magnitude responses in dB and convert to 1D arrays
        plant_response = np.asarray(servo_plant.shaped.response).flatten()[mask]
        ff_response = np.asarray(servo_ff.shaped.response).flatten()[mask]
        
        plant_mag = 20 * np.log10(np.abs(plant_response))
        ff_mag = 20 * np.log10(np.abs(ff_response))
        
        # Calculate best fit lines using filtered data
        plant_fit = np.polyfit(np.log10(freq_hz_filtered), plant_mag, 1)
        ff_fit = np.polyfit(np.log10(freq_hz_filtered), ff_mag, 1)
        
        # Get center frequency point (geometric mean of min and max freq)
        log_center_freq = np.mean(np.log10([min(freq_hz_filtered), max(freq_hz_filtered)]))
        
        # Calculate magnitudes at center frequency using fit lines
        # plant_fit[0] is slope, plant_fit[1] is y-intercept
        plant_center_mag = plant_fit[0] * log_center_freq + plant_fit[1]
        ff_center_mag = ff_fit[0] * log_center_freq + ff_fit[1]
        
        # Calculate directional differences
        center_mag_diff = ff_center_mag - plant_center_mag  # Positive means FF above plant
        slope_diff = ff_fit[0] - plant_fit[0]  # Positive means FF steeper
        
        return {
            'center_frequency_hz': 10**log_center_freq,
            'center_magnitude_difference_db': center_mag_diff,
            'slope_difference_db_per_decade': slope_diff,
            'plant_fit': plant_fit,
            'ff_fit': ff_fit,
            'plant_center_magnitude': plant_center_mag,
            'ff_center_magnitude': ff_center_mag
        }

    @staticmethod
    def print_filter_details(filters: list[Filter_Model], prefix="") -> None:
        """Helper to print filter configuration details"""
        for i, filter in enumerate(filters):
            if filter.properties.filter_type != FilterType.Empty:
                params = filter.properties.parameters
                
                # Get parameter names from mapping
                param_names = FILTER_PARAMETER_MAPPING[filter.properties.filter_type]
                
                print(f"{prefix}Filter {i}:")
                print(f"{prefix}  Type: {filter.properties.filter_type.name}")
                for name, value in zip(param_names, params):
                    print(f"{prefix}  {name}: {value:.3f}")

    def execute_easy_tune(self) -> tuple:
        """Execute the EasyTune optimization and return the results.
        
        Returns:
            tuple: (success, block_layout_with_data, number_of_generations, optimization_time_ms)
        """
        if not (hasattr(self, 'fr_filepath') and self.fr_filepath):
            raise ValueError("No FR file provided")
        
        print(f"Reading FR file: {self.fr_filepath}")
        [version, a1_data] = a1_interface.read_frequency_response_result_from_a1_file(self.fr_filepath)
        
        # Print a1_data details for debugging
        print("\nLoaded FR Data:")
        print(f"Version: {version}")
        
        block_layout_with_data = Block_Layout_With_Data(
            a1_data=a1_data, 
            filename=self.fr_filepath
        )

        print("\nAttempting EasyTune optimization...")
        [self.did_easy_tune_succeed, self.servo_controller, 
         number_of_generations, optimization_time_ms, 
         self.zip_directory, self.exception] = \
            a1_interface.run_easy_tune(block_layout_with_data.shaped, block_layout_with_data.a1_data, verification=self.verification)
        
        
        print("\nEasyTune Results:")
        print(f"Success: {self.did_easy_tune_succeed}")
        print(f"Generations: {number_of_generations}")
        print(f"Time: {optimization_time_ms/1000:.2f}s")
        print(f"Logs: {self.zip_directory}")
        
        return self.did_easy_tune_succeed, block_layout_with_data, number_of_generations, optimization_time_ms

    def generate_results_filename(self) -> str:
        """Generate a timestamped filename for the results file."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fr_basename = os.path.splitext(os.path.basename(self.fr_filepath))[0] if self.fr_filepath else "easytune"
        return f"EasyTune_Results_{fr_basename}_{timestamp}.txt"

    def write_filter_details_to_file(self, file, filters: list, prefix="", label="") -> None:
        """Helper to write filter configuration details to file"""
        if label:
            file.write(f"{prefix}{label}:\n")
        
        active_filters = [f for f in filters if f.properties.filter_type != FilterType.Empty]
        if not active_filters:
            file.write(f"{prefix}  No active filters\n")
            return
        
        for i, filter in enumerate(active_filters):
            params = filter.properties.parameters
            param_names = FILTER_PARAMETER_MAPPING[filter.properties.filter_type]
            
            file.write(f"{prefix}  Filter {i}:\n")
            file.write(f"{prefix}    Type: {filter.properties.filter_type.name}\n")
            for name, value in zip(param_names, params):
                file.write(f"{prefix}    {name}: {value:.3f}\n")

    def write_results_to_file(self, results: dict, block_layout_with_data) -> str:
        """Write the analysis results to a nicely formatted text file.
        
        Args:
            results: The results dictionary from analyze_easy_tune_results
            block_layout_with_data: The block layout data
            
        Returns:
            str: Path to the created results file
        """
        from datetime import datetime
        
        # Generate filename and create file
        filename = self.generate_results_filename()
        results_dir = os.path.dirname(self.fr_filepath) if self.fr_filepath else os.getcwd()
        filepath = os.path.join(results_dir, filename)
        
        shaped_controller = self.servo_controller
        original_controller = block_layout_with_data.shaped.user_facing_layout["Servo_Loop"]["Servo_Controller"]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            # Header
            f.write("="*80 + "\n")
            f.write("                           EASYTUNE ANALYSIS RESULTS\n")
            f.write("="*80 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"FR File: {os.path.basename(self.fr_filepath) if self.fr_filepath else 'N/A'}\n")
            f.write(f"Success: {'YES' if self.did_easy_tune_succeed else 'NO'}\n")
            if self.zip_directory:
                f.write(f"Logs: {self.zip_directory}\n")
            f.write("="*80 + "\n\n")
            
            # Controller Properties Section
            f.write("CONTROLLER PROPERTIES COMPARISON\n")
            f.write("-"*50 + "\n")
            f.write(f"{'Property':<25} {'Shaped':<15} {'Original':<15} {'Change':<10}\n")
            f.write("-"*50 + "\n")
            
            for property_name in shaped_controller.properties.__dict__:
                # Skip special properties
                if property_name.startswith("__") and property_name.endswith("__"):
                    continue
                    
                shaped_value = getattr(shaped_controller.properties, property_name)
                original_value = getattr(original_controller.properties, property_name)
                
                # Handle different property types
                if isinstance(shaped_value, (int, float)):
                    change = shaped_value - original_value
                    change_str = f"{change:+.3f}" if abs(change) > 1e-6 else "0.000"
                    f.write(f"{property_name:<25} {shaped_value:<15.3f} {original_value:<15.3f} {change_str:<10}\n")
                    
                elif isinstance(shaped_value, bool):
                    change_str = "CHANGED" if shaped_value != original_value else "SAME"
                    f.write(f"{property_name:<25} {str(shaped_value):<15} {str(original_value):<15} {change_str:<10}\n")
                    
                elif property_name in ["Servo_Filters", "Feedforward_Filters"]:
                    active_shaped = sum(1 for f in shaped_value if f.properties.filter_type != FilterType.Empty)
                    active_orig = sum(1 for f in original_value if f.properties.filter_type != FilterType.Empty)
                    change_str = f"{active_shaped-active_orig:+d}" if active_shaped != active_orig else "0"
                    f.write(f"{property_name:<25} {active_shaped:<15} {active_orig:<15} {change_str:<10}\n")
                    
                elif isinstance(shaped_value, Enhanced_Tracking_Control):
                    shaped_bw = shaped_value.properties.Bandwidth
                    original_bw = original_value.properties.Bandwidth
                    change_str = f"{shaped_bw-original_bw:+.1f}Hz" if abs(shaped_bw-original_bw) > 0.1 else "0.0Hz"
                    f.write(f"{property_name:<25} {shaped_bw:<15.1f} {original_bw:<15.1f} {change_str:<10}\n")
                    
                else:
                    change_str = "CHANGED" if str(shaped_value) != str(original_value) else "SAME"
                    f.write(f"{property_name:<25} {str(shaped_value):<15} {str(original_value):<15} {change_str:<10}\n")
            
            f.write("\n\n")
            
            # Detailed Filter Analysis
            f.write("DETAILED FILTER ANALYSIS\n")
            f.write("-"*50 + "\n")
            
            for property_name in ["Servo_Filters", "Feedforward_Filters"]:
                if property_name in results.get('Filters', {}):
                    f.write(f"\n{property_name}:\n")
                    shaped_filters = getattr(shaped_controller.properties, property_name)
                    original_filters = getattr(original_controller.properties, property_name)
                    
                    f.write("\n  Shaped Configuration:\n")
                    self.write_filter_details_to_file(f, shaped_filters, "    ")
                    
                    f.write("\n  Original Configuration:\n")
                    self.write_filter_details_to_file(f, original_filters, "    ")
            
            f.write("\n\n")
            
            # Enhanced Tracking Analysis
            if results.get('Enhanced_Tracking'):
                f.write("ENHANCED TRACKING ANALYSIS\n")
                f.write("-"*50 + "\n")
                f.write(f"{'Property':<20} {'Setup':<12} {'Bandwidth':<12} {'Scale':<10}\n")
                f.write("-"*50 + "\n")
                
                for prop_name, tracking_data in results['Enhanced_Tracking'].items():
                    shaped = tracking_data['shaped']
                    original = tracking_data['original']
                    
                    f.write(f"Shaped {prop_name}:\n")
                    f.write(f"{'  Current':<20} {str(shaped['setup']):<12} {shaped['bandwidth']:<12.1f} {shaped['scale']:<10.3f}\n")
                    f.write(f"{'  Original':<20} {str(original['setup']):<12} {original['bandwidth']:<12.1f} {original['scale']:<10.3f}\n")
                    f.write("\n")
            
            # Stability Metrics
            if results.get('Stability_Metrics'):
                f.write("STABILITY ANALYSIS\n")
                f.write("-"*50 + "\n")
                stability = results['Stability_Metrics']['original']
                
                f.write(f"Gain Margin:       {stability['gain_margin']['db']:.1f} dB @ {stability['gain_margin']['frequency_hz']:.1f} Hz\n")
                f.write(f"Phase Margin:      {stability['phase_margin']['degrees']:.1f} degrees @ {stability['phase_margin']['frequency_hz']:.1f} Hz\n")
                f.write(f"Sensitivity:       {stability['sensitivity']['db']:.1f} dB @ {stability['sensitivity']['frequency_hz']:.1f} Hz\n")
                f.write("\n")
            
            # Feedforward Analysis
            if results.get('FF_Analysis'):
                f.write("PLANT vs INVERSE FEEDFORWARD ANALYSIS\n")
                f.write("-"*50 + "\n")
                ff_analysis = results['FF_Analysis']
                
                f.write(f"Center Frequency:           {ff_analysis['center_frequency_hz']:.1f} Hz\n")
                f.write(f"Center Magnitude Diff:     {ff_analysis['center_magnitude_difference_db']:.1f} dB ")
                f.write(f"({'above' if ff_analysis['center_magnitude_difference_db'] > 0 else 'below'} plant)\n")
                f.write(f"Slope Difference:          {ff_analysis['slope_difference_db_per_decade']:.1f} dB/decade ")
                f.write(f"({'steeper' if ff_analysis['slope_difference_db_per_decade'] > 0 else 'shallower'} than plant)\n")
                f.write(f"Plant Slope:               {ff_analysis['plant_fit'][0]:.1f} dB/decade\n")
                f.write(f"Inverse FF Slope:          {ff_analysis['ff_fit'][0]:.1f} dB/decade\n")
                f.write("\n")
            
            # Footer
            f.write("="*80 + "\n")
            f.write("                              END OF REPORT\n")
            f.write("="*80 + "\n")
        
        return filepath

    def analyze_easy_tune_results(self, block_layout_with_data) -> dict:
        """Analyze the EasyTune results and return comprehensive analysis.
        
        Args:
            block_layout_with_data: The block layout data containing original and shaped controllers
            
        Returns:
            dict: Comprehensive analysis results including gains, filters, stability metrics, etc.
        """
        results = {
            'success': self.did_easy_tune_succeed,
            'Gains': {},
            'Filters': {},
            'Enhanced_Tracking': {},
            'Stability_Metrics': {},
            'FF_Analysis': {}
        }
        
        shaped_controller = self.servo_controller
        original_controller = block_layout_with_data.shaped.user_facing_layout["Servo_Loop"]["Servo_Controller"]
        
        for property_name in shaped_controller.properties.__dict__:
            # Skip special properties
            if property_name.startswith("__") and property_name.endswith("__"):
                continue
            
            shaped_value = getattr(shaped_controller.properties, property_name)
            original_value = getattr(original_controller.properties, property_name)
            
            # Handle different property types
            if isinstance(shaped_value, (int, float)):
                results['Gains'][property_name] = {
                    'shaped': shaped_value,
                    'original': original_value
                }
            elif isinstance(shaped_value, bool):
                results['Gains'][property_name] = {
                    'shaped': shaped_value,
                    'original': original_value
                }
            elif property_name in ["Servo_Filters", "Feedforward_Filters"]:
                active_shaped = sum(1 for f in shaped_value if f.properties.filter_type != FilterType.Empty)
                active_orig = sum(1 for f in original_value if f.properties.filter_type != FilterType.Empty)

                # Always include all filters (removed the success check)
                shaped_filters_to_store = {}  # Use dict instead of list
                for i, f in enumerate(shaped_value):
                    if f.properties.filter_type != FilterType.Empty:
                        shaped_filters_to_store[i] = {  # Preserve original index 'i'
                            'type': f.properties.filter_type.name,
                            'parameters': dict(zip(
                                FILTER_PARAMETER_MAPPING[f.properties.filter_type],
                                f.properties.parameters
                            ))
                        }
                
                original_filters_to_store = {}  # Use dict instead of list
                for i, f in enumerate(original_value):
                    if f.properties.filter_type != FilterType.Empty:
                        original_filters_to_store[i] = {  # Preserve original index 'i'
                            'type': f.properties.filter_type.name,
                            'parameters': dict(zip(
                                FILTER_PARAMETER_MAPPING[f.properties.filter_type],
                                f.properties.parameters
                            ))
                        }
                
                shaped_count = len(shaped_filters_to_store)
                original_count = len(original_filters_to_store)

                results['Filters'][property_name] = {
                    'shaped': {
                        'count': shaped_count,
                        'filters': shaped_filters_to_store  # Now a dict with original indices as keys
                    },
                    'original': {
                        'count': original_count,
                        'filters': original_filters_to_store  # Now a dict with original indices as keys
                    }
                }

            elif isinstance(shaped_value, Enhanced_Tracking_Control):
                if 'Enhanced_Tracking' not in results:
                    results['Enhanced_Tracking'] = {}
                    
                results['Enhanced_Tracking'][property_name] = {
                    'shaped': {
                        'setup': shaped_value.properties.Setup,
                        'bandwidth': shaped_value.properties.Bandwidth,
                        'scale': shaped_value.properties.Scale
                    },
                    'original': {
                        'setup': original_value.properties.Setup,
                        'bandwidth': original_value.properties.Bandwidth,
                        'scale': original_value.properties.Scale
                    }
                }
            else:
                # Store other properties in Gains section
                if 'Gains' not in results:
                    results['Gains'] = {}
                results['Gains'][property_name] = {
                    'shaped': str(shaped_value),
                    'original': str(original_value)
                }

        # Stability analysis results
        loop_type = Loop_Type.Servo
        fr_type = FR_Type.Servo_Open_Loop

        # Get original stability metrics
        original_frd = block_layout_with_data.frd_data[loop_type][fr_type].original
        shaped_frd = block_layout_with_data.frd_data[loop_type][fr_type].shaped

        if shaped_frd is not None:
            [s_gain_margin, s_phase_margin, s_sensitivity_margin, 
            s_gain_crossover_frequency, s_phase_crossover_frequency, s_sensitivity_crossover_frequency] = control.stability_margins(shaped_frd)

            # Store metrics in results dictionary
            if 'Stability_Metrics' not in results:
                results['Stability_Metrics'] = {}
                
            results['Stability_Metrics']['original'] = {
                'gain_margin': {
                    'db': Utils.to_dB(s_gain_margin),
                    'frequency_hz': Utils.radian_to_hertz(s_gain_crossover_frequency)
                },
                'phase_margin': {
                    'degrees': s_phase_margin,
                    'frequency_hz': Utils.radian_to_hertz(s_phase_crossover_frequency)
                },
                'sensitivity': {
                    'db': -Utils.to_dB(s_sensitivity_margin),
                    'frequency_hz': Utils.radian_to_hertz(s_sensitivity_crossover_frequency)
                }
            }
        if original_frd is not None:
            [o_gain_margin, o_phase_margin, o_sensitivity_margin, 
            o_gain_crossover_frequency, o_phase_crossover_frequency, o_sensitivity_crossover_frequency] = control.stability_margins(original_frd)

            # Store metrics in results dictionary
            if 'Stability_Metrics' not in results:
                results['Stability_Metrics'] = {}
                
            results['Stability_Metrics']['original'] = {
                'gain_margin': {
                    'db': Utils.to_dB(o_gain_margin),
                    'frequency_hz': Utils.radian_to_hertz(o_gain_crossover_frequency)
                },
                'phase_margin': {
                    'degrees': o_phase_margin,
                    'frequency_hz': Utils.radian_to_hertz(o_phase_crossover_frequency)
                },
                'sensitivity': {
                    'db': -Utils.to_dB(o_sensitivity_margin),
                    'frequency_hz': Utils.radian_to_hertz(o_sensitivity_crossover_frequency)
                }
            }
        # Analyze plant vs feedforward match
        match_analysis = self.analyze_plant_ff_match(block_layout_with_data)
        results['FF_Analysis'] = match_analysis
        
        def convert_numpy_types(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.float64):
                return float(obj)
            elif isinstance(obj, dict):
                return {k: convert_numpy_types(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_numpy_types(i) for i in obj]
            return obj

        # After collecting all results, convert numpy types
        results = convert_numpy_types(results)
        
        # Write results to file instead of printing
        self.results_filepath = self.write_results_to_file(results, block_layout_with_data)
        print(f"\nAnalysis complete. Results written to: {self.results_filepath}")
        
        return results, original_frd

    def easy_tune_thread(self) -> None:
        """The actual EasyTune thread to run when started."""
        try:
            print("\nStarting EasyTune thread...")
            self.set_thread_state(True)

            try:
                # Execute the EasyTune optimization
                success, block_layout_with_data, number_of_generations, optimization_time_ms = self.execute_easy_tune()
                
                # Analyze the results if successful
                self.results, self.original_frd = self.analyze_easy_tune_results(block_layout_with_data)
                    
            except Exception as e:
                print(f"Error during optimization: {str(e)}")
                import traceback
                traceback.print_exc()
                self.exception = e
                self.did_easy_tune_succeed = False
                return

        except Exception as e:
            print(f"Error in EasyTune thread: {str(e)}")
            print("\nFull traceback:")
            import traceback
            traceback.print_exc()
            self.exception = e
            self.did_easy_tune_succeed = False
            
        finally:
            print("EasyTune thread completed")
            self.set_thread_state(False)
            self.active_thread = None

    def get_results(self) -> dict:
        """Get the analysis results after EasyTune completion.
        
        Returns:
            tuple: (results_dict, original_frd) or (None, None) if not available
        """
        if not hasattr(self, 'results') or self.results is None:
            print("⚠️ Warning: No results available - EasyTune may not have completed successfully")
            return None, None
            
        if not hasattr(self, 'original_frd') or self.original_frd is None:
            print("⚠️ Warning: No original FRD available - analysis may have failed")
            return self.results, None
            
        return self.results, self.original_frd
