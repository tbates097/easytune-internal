#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EasyTune UI - Graphical User Interface for RunEasyTune.py
Created by: Assistant
Description: Modern wizard-style UI for EasyTune optimization
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import tkinter.font as tkFont
import threading
import queue
import sys
import os
from datetime import datetime
import contextlib
from io import StringIO

# Import the main EasyTune module
import RunEasyTune

def get_brand_font(font_type, size, weight='normal'):
    """Get brand font with fallbacks for cross-platform compatibility"""
    brand_fonts = {
        'headline': ['D-Din', 'Barlow', 'Arial', 'Helvetica', 'sans-serif'],
        'body': ['Helvetica', 'Arial', 'DejaVu Sans', 'sans-serif'],
        'accent': ['Gotham', 'Montserrat', 'Arial', 'Helvetica', 'sans-serif'],
        'number': ['Proxima Nova', 'Arial', 'Helvetica', 'sans-serif'],
        'mono': ['Consolas', 'Monaco', 'Courier New', 'monospace']
    }
    
    fonts_to_try = brand_fonts.get(font_type, ['Arial'])
    
    for font_family in fonts_to_try:
        try:
            # Test if font is available by creating a temporary font object
            test_font = tkFont.Font(family=font_family, size=size, weight=weight)
            if test_font.actual('family') == font_family or font_family in ['Arial', 'sans-serif', 'monospace']:
                return (font_family, size, weight)
        except:
            continue
    
    # Final fallback
    return ('Arial', size, weight)

class RedirectText:
    """Redirect stdout to a text widget"""
    def __init__(self, text_widget, queue_obj):
        self.text_widget = text_widget
        self.queue = queue_obj
        
    def write(self, text):
        self.queue.put(text)
        
    def flush(self):
        pass

class EasyTuneUI:
    def __init__(self, root):
        self.root = root
        self.root.title("EasyTune Plus - v1.0")
        self.root.configure(bg='white')
        
        # Configure styles
        self.setup_styles()
        
        # Initialize variables
        self.controller = None
        self.available_axes = []
        self.config_data = {}
        self.current_step = 0
        self.total_steps = 5
        
        # Add stop event for thread control
        self.stop_event = threading.Event()
        self.easytune_thread = None
        
        # Setup main frame
        self.setup_main_frame()
        
        # Setup wizard steps
        self.setup_wizard()
        
        # Start with welcome screen
        self.show_step(0)
        
    def setup_styles(self):
        """Configure ttk styles with brand guidelines"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Brand Colors (PMS Guidelines)
        BRAND_DARK_BLUE = '#006298'      # PMS 7691
        BRAND_BLUE = '#00ADEF'           # PMS PROCESS BLUE  
        BRAND_CHARCOAL = '#3D4543'       # PMS 446
        BRAND_MED_GRAY = '#A7A8A9'       # PMS COOL GRAY 6
        BRAND_DARK_GRAY = '#54565A'      # PMS COOL GRAY 11
        
        # Brand Fonts (with fallbacks for system compatibility)
        HEADLINE_FONT = ('D-Din', 'Barlow', 'Arial', 'sans-serif')           # Headlines/Subheads
        BODY_FONT = ('Helvetica', 'Arial', 'sans-serif')                     # Body copy
        ACCENT_FONT = ('Gotham', 'Arial', 'sans-serif')                      # Accent/Logotype
        NUMBER_FONT = ('Proxima Nova', 'Arial', 'sans-serif')                # Numbers/Infographics
        
        # Configure text styles with brand fonts and no backgrounds
        style.configure('Title.TLabel', 
                       font=(HEADLINE_FONT[0], 16, 'bold'), 
                       foreground=BRAND_DARK_BLUE,
                       background='white')
        style.configure('Subtitle.TLabel', 
                       font=(BODY_FONT[0], 12), 
                       foreground=BRAND_DARK_GRAY,
                       background='white')
        style.configure('Header.TLabel', 
                       font=(HEADLINE_FONT[0], 14, 'bold'), 
                       foreground=BRAND_BLUE,
                       background='white')
        style.configure('Success.TLabel', 
                       font=(BODY_FONT[0], 10), 
                       foreground='#27ae60',
                       background='white')
        style.configure('Error.TLabel', 
                       font=(BODY_FONT[0], 10), 
                       foreground='#e74c3c',
                       background='white')
        style.configure('Warning.TLabel', 
                       font=(BODY_FONT[0], 10), 
                       foreground='#f39c12',
                       background='white')
        style.configure('Number.TLabel', 
                       font=(NUMBER_FONT[0], 10, 'bold'), 
                       foreground=BRAND_DARK_BLUE,
                       background='white')
        
        # Configure buttons with brand colors and fonts
        style.configure('Action.TButton', 
                       font=(ACCENT_FONT[0], 10, 'bold'),
                       background=BRAND_BLUE,
                       foreground='white')
        style.map('Action.TButton',
                 background=[('active', BRAND_DARK_BLUE),
                            ('pressed', BRAND_CHARCOAL)])
        
        style.configure('Nav.TButton', 
                       font=(BODY_FONT[0], 9),
                       background=BRAND_MED_GRAY,
                       foreground=BRAND_CHARCOAL)
        style.map('Nav.TButton',
                 background=[('active', BRAND_DARK_GRAY),
                            ('pressed', BRAND_CHARCOAL)])
        
        # Configure progress bar
        style.configure('Brand.Horizontal.TProgressbar',
                       background=BRAND_BLUE,
                       troughcolor=BRAND_MED_GRAY,
                       borderwidth=0,
                       lightcolor=BRAND_BLUE,
                       darkcolor=BRAND_BLUE)
        
        # Configure other ttk elements to have white backgrounds
        style.configure('TLabelFrame', background='white')
        style.configure('TLabelFrame.Label', background='white')
        style.configure('TFrame', background='white')
        style.configure('TCheckbutton', background='white')
        style.configure('TRadiobutton', background='white')
        
        # Configure default label and entry styles for white backgrounds
        style.configure('TLabel', background='white')
        style.configure('TEntry', fieldbackground='white')
        
    def setup_main_frame(self):
        """Setup the main application frame with brand colors"""
        # Brand Colors
        BRAND_DARK_BLUE = '#006298'      # PMS 7691
        BRAND_BLUE = '#00ADEF'           # PMS PROCESS BLUE  
        BRAND_CHARCOAL = '#3D4543'       # PMS 446
        BRAND_MED_GRAY = '#A7A8A9'       # PMS COOL GRAY 6
        
        # Header frame with brand dark blue
        self.header_frame = tk.Frame(self.root, bg=BRAND_DARK_BLUE, height=80)
        self.header_frame.pack(fill='x', pady=(0, 10))
        self.header_frame.pack_propagate(False)
        
        # Title with white text on brand blue - using headline font
        title_label = tk.Label(self.header_frame, text="EasyTune Plus Optimization Wizard", 
                              font=('D-Din', 18, 'bold'), fg='white', bg=BRAND_DARK_BLUE)
        title_label.pack(pady=20)
        
        # Progress frame - no background color
        self.progress_frame = tk.Frame(self.root, height=40, bg='white')
        self.progress_frame.pack(fill='x', padx=20, pady=(0, 10))
        self.progress_frame.pack_propagate(False)
        
        # Progress bar with brand styling
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, 
                                          maximum=100, length=400, style='Brand.Horizontal.TProgressbar')
        self.progress_bar.pack(pady=10)
        
        # Progress label
        self.progress_label = ttk.Label(self.progress_frame, text="Step 1 of 5: Connection Setup",
                                       style='Subtitle.TLabel')
        self.progress_label.pack()
        
        # Main content frame - no background color
        self.content_frame = tk.Frame(self.root, bg='white')
        self.content_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Navigation frame - no background color
        self.nav_frame = tk.Frame(self.root, height=60, bg='white')
        self.nav_frame.pack(fill='x', padx=20, pady=(0, 20))
        self.nav_frame.pack_propagate(False)
        
        # Navigation buttons
        self.prev_btn = ttk.Button(self.nav_frame, text="← Previous", style='Nav.TButton',
                                  command=self.prev_step, state='disabled')
        self.prev_btn.pack(side='left', pady=15)
        
        self.next_btn = ttk.Button(self.nav_frame, text="Next →", style='Nav.TButton',
                                  command=self.next_step)
        self.next_btn.pack(side='right', pady=15)
        
    def setup_wizard(self):
        """Setup all wizard steps"""
        self.steps = [
            self.create_connection_step,
            self.create_system_config_step,
            self.create_test_config_step,
            self.create_axis_params_step,
            self.create_execution_step
        ]
        
        self.step_frames = []
        for step_func in self.steps:
            frame = tk.Frame(self.content_frame, bg='white')
            step_func(frame)
            self.step_frames.append(frame)
    
    def create_connection_step(self, parent):
        """Step 1: Connection Setup"""
        # Brand Colors
        BRAND_DARK_BLUE = '#006298'      # PMS 7691
        
        # Title
        title = ttk.Label(parent, text="Controller Connection", style='Title.TLabel')
        title.pack(pady=(0, 20))
        
        # Connection status frame
        self.conn_status_frame = tk.Frame(parent, bg='white')
        self.conn_status_frame.pack(fill='x', pady=10)
        
        self.conn_status_label = ttk.Label(self.conn_status_frame, text="Ready to connect to controller...",
                                          style='Subtitle.TLabel')
        self.conn_status_label.pack()
        
        # Connection options
        conn_frame = tk.LabelFrame(parent, text="Connection Options", font=('D-Din', 10, 'bold'),
                                  fg=BRAND_DARK_BLUE, bg='white')
        conn_frame.pack(fill='x', pady=20, padx=20)
        
        self.connection_var = tk.StringVar(value="auto")
        
        auto_radio = ttk.Radiobutton(conn_frame, text="Auto-detect connection", 
                                    variable=self.connection_var, value="auto")
        auto_radio.pack(anchor='w', padx=10, pady=5)
        
        usb_radio = ttk.Radiobutton(conn_frame, text="Force USB connection", 
                                   variable=self.connection_var, value="usb")
        usb_radio.pack(anchor='w', padx=10, pady=5)
        
        hyperwire_radio = ttk.Radiobutton(conn_frame, text="Force Hyperwire connection", 
                                         variable=self.connection_var, value="hyperwire")
        hyperwire_radio.pack(anchor='w', padx=10, pady=5)
        
        # Connect button
        self.connect_btn = ttk.Button(conn_frame, text="Connect to Controller", 
                                     style='Action.TButton', command=self.connect_controller)
        self.connect_btn.pack(pady=10)
        
        # Available axes display
        self.axes_frame = tk.LabelFrame(parent, text="Available Axes", font=('D-Din', 10, 'bold'),
                                       fg=BRAND_DARK_BLUE, bg='white')
        self.axes_frame.pack(fill='x', pady=20, padx=20)
        
        self.axes_label = ttk.Label(self.axes_frame, text="Connect to controller to see available axes",
                                   style='Subtitle.TLabel')
        self.axes_label.pack(pady=10)
        
    def create_system_config_step(self, parent):
        """Step 2: System Configuration"""
        # Brand Colors
        BRAND_DARK_BLUE = '#006298'      # PMS 7691
        
        title = ttk.Label(parent, text="System Configuration", style='Title.TLabel')
        title.pack(pady=(0, 20))
        
        # Axes selection
        axes_frame = tk.LabelFrame(parent, text="Axes to Enable During Tuning", 
                                  font=('D-Din', 10, 'bold'), fg=BRAND_DARK_BLUE, bg='white')
        axes_frame.pack(fill='x', pady=10, padx=20)
        
        ttk.Label(axes_frame, text="Select which axes to enable during the tuning process:",
                 style='Subtitle.TLabel').pack(anchor='w', padx=10, pady=(10, 5))
        
        self.axes_checkboxes_frame = tk.Frame(axes_frame, bg='white')
        self.axes_checkboxes_frame.pack(fill='x', padx=20, pady=10)
        
        self.axes_vars = {}
        
        # Calibration files
        cal_frame = tk.LabelFrame(parent, text="Calibration Files", 
                                 font=('D-Din', 10, 'bold'), fg=BRAND_DARK_BLUE, bg='white')
        cal_frame.pack(fill='x', pady=10, padx=20)
        
        ttk.Label(cal_frame, text="Select calibration file configuration for your system:",
                 style='Subtitle.TLabel').pack(anchor='w', padx=10, pady=(10, 5))
        
        self.cal_type_var = tk.StringVar(value="with_cal")
        
        with_cal_radio = ttk.Radiobutton(cal_frame, text="Calibration files are loaded and ready", 
                                        variable=self.cal_type_var, value="with_cal")
        with_cal_radio.pack(anchor='w', padx=10, pady=2)
        
        without_cal_radio = ttk.Radiobutton(cal_frame, text="Run without calibration files", 
                                           variable=self.cal_type_var, value="without_cal")
        without_cal_radio.pack(anchor='w', padx=10, pady=2)
        
    def create_test_config_step(self, parent):
        """Step 3: Test Configuration"""
        # Brand Colors
        BRAND_DARK_BLUE = '#006298'      # PMS 7691
        
        title = ttk.Label(parent, text="Test Configuration", style='Title.TLabel')
        title.pack(pady=(0, 20))
        
        # Test type selection
        test_type_frame = tk.LabelFrame(parent, text="Test Type", 
                                       font=('D-Din', 10, 'bold'), fg=BRAND_DARK_BLUE, bg='white')
        test_type_frame.pack(fill='x', pady=10, padx=20)
        
        self.test_type_var = tk.StringVar(value="single")
        
        single_radio = ttk.Radiobutton(test_type_frame, text="Single Axis Test", 
                                      variable=self.test_type_var, value="single",
                                      command=self.update_test_config)
        single_radio.pack(anchor='w', padx=10, pady=5)
        
        multi_radio = ttk.Radiobutton(test_type_frame, text="Multi-Axis Test", 
                                     variable=self.test_type_var, value="multi",
                                     command=self.update_test_config)
        multi_radio.pack(anchor='w', padx=10, pady=5)
        
        # Single axis configuration
        self.single_config_frame = tk.LabelFrame(parent, text="Single Axis Configuration", 
                                                font=('D-Din', 10, 'bold'), fg=BRAND_DARK_BLUE, bg='white')
        self.single_config_frame.pack(fill='x', pady=10, padx=20)
        
        ttk.Label(self.single_config_frame, text="Select axis to tune:",
                 style='Subtitle.TLabel').pack(anchor='w', padx=10, pady=(10, 5))
        
        self.single_axis_var = tk.StringVar()
        self.single_axis_combo = ttk.Combobox(self.single_config_frame, textvariable=self.single_axis_var,
                                             state='readonly', width=10)
        self.single_axis_combo.pack(anchor='w', padx=10, pady=5)
        
        # Multi-axis configuration
        self.multi_config_frame = tk.LabelFrame(parent, text="Multi-Axis Configuration", 
                                               font=('D-Din', 10, 'bold'), fg=BRAND_DARK_BLUE, bg='white')
        self.multi_config_frame.pack(fill='x', pady=10, padx=20)
        
        # XY axes
        xy_frame = tk.Frame(self.multi_config_frame, bg='white')
        xy_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(xy_frame, text="XY Configuration (ganged axes):",
                 style='Subtitle.TLabel').pack(anchor='w')
        
        self.xy_axes_frame = tk.Frame(xy_frame, bg='white')
        self.xy_axes_frame.pack(fill='x', pady=5)
        
        self.xy_axes_vars = {}
        
        # Other single axes
        other_frame = tk.Frame(self.multi_config_frame, bg='white')
        other_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(other_frame, text="Other Single Axes:",
                 style='Subtitle.TLabel').pack(anchor='w')
        
        self.other_axes_frame = tk.Frame(other_frame, bg='white')
        self.other_axes_frame.pack(fill='x', pady=5)
        
        self.other_axes_vars = {}
        
        # Initial state
        self.update_test_config()
        
    def create_axis_params_step(self, parent):
        """Step 4: Axis Parameters"""
        title = ttk.Label(parent, text="Axis Parameters", style='Title.TLabel')
        title.pack(pady=(0, 20))
        
        # Scrollable frame for axis parameters
        canvas = tk.Canvas(parent, bg='white')
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        self.axis_params_frame = tk.Frame(canvas, bg='white')
        
        self.axis_params_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.axis_params_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.axis_param_vars = {}
        
    def create_execution_step(self, parent):
        """Step 5: Execution and Progress"""
        # Brand Colors
        BRAND_DARK_BLUE = '#006298'      # PMS 7691
        BRAND_BLUE = '#00ADEF'           # PMS PROCESS BLUE  
        BRAND_CHARCOAL = '#3D4543'       # PMS 446
        
        title = ttk.Label(parent, text="Execution Progress", style='Title.TLabel')
        title.pack(pady=(0, 20))
        
        # Configuration summary
        summary_frame = tk.LabelFrame(parent, text="Configuration Summary", 
                                     font=('D-Din', 10, 'bold'), fg=BRAND_DARK_BLUE, bg='white')
        summary_frame.pack(fill='x', pady=10, padx=20)
        
        self.summary_text = tk.Text(summary_frame, height=8, width=80, font=('Helvetica', 9),
                                   bg='white', fg=BRAND_CHARCOAL, relief='flat', bd=5)
        self.summary_text.pack(padx=10, pady=10, fill='x')
        
        # Control buttons
        control_frame = tk.Frame(parent)
        control_frame.pack(fill='x', pady=10)
        
        self.start_btn = ttk.Button(control_frame, text="Start EasyTune Process", 
                                   style='Action.TButton', command=self.start_easytune)
        self.start_btn.pack(side='left', padx=10)
        
        self.stop_btn = ttk.Button(control_frame, text="Stop Process", 
                                  command=self.stop_easytune, state='disabled')
        self.stop_btn.pack(side='left', padx=10)
        
        # Progress display
        progress_frame = tk.LabelFrame(parent, text="Process Output", 
                                      font=('D-Din', 10, 'bold'), fg=BRAND_DARK_BLUE, bg='white')
        progress_frame.pack(fill='both', expand=True, pady=10, padx=20)
        
        self.output_text = scrolledtext.ScrolledText(progress_frame, height=15, font=('Courier', 9),
                                                    bg=BRAND_CHARCOAL, fg=BRAND_BLUE, insertbackground=BRAND_BLUE)
        self.output_text.pack(padx=10, pady=10, fill='both', expand=True)
        
        # Setup output redirection
        self.output_queue = queue.Queue()
        self.redirect_text = RedirectText(self.output_text, self.output_queue)
        
        # Start queue monitoring
        self.monitor_output()
        
    def show_step(self, step_num):
        """Show the specified step"""
        # Hide all frames
        for frame in self.step_frames:
            frame.pack_forget()
            
        # Show current frame
        if 0 <= step_num < len(self.step_frames):
            self.step_frames[step_num].pack(fill='both', expand=True)
            
        # Adjust window height for final screen
        if step_num == 4:  # Execution step - make window taller
            self.adjust_window_height(950)  # Increased from 700 to 850 (150px more)
        else:  # Other steps - use normal height
            self.adjust_window_height(700)  # Original height
            
        # Update progress
        self.current_step = step_num
        progress = (step_num / (self.total_steps - 1)) * 100
        self.progress_var.set(progress)
        
        step_names = [
            "Connection Setup",
            "System Configuration", 
            "Test Configuration",
            "Axis Parameters",
            "Execution & Progress"
        ]
        
        self.progress_label.config(text=f"Step {step_num + 1} of {self.total_steps}: {step_names[step_num]}")
        
        # Update navigation buttons
        self.prev_btn.config(state='normal' if step_num > 0 else 'disabled')
        
        if step_num == self.total_steps - 1:
            self.next_btn.config(text="Finish", state='disabled')
        else:
            self.next_btn.config(text="Next →", state='normal')
            
        # Update step-specific elements
        if step_num == 1:  # System config
            self.update_axes_checkboxes()
        elif step_num == 2:  # Test config
            self.update_axis_combos()
        elif step_num == 3:  # Axis params
            self.update_axis_params()
        elif step_num == 4:  # Execution
            self.update_summary()
    
    def adjust_window_height(self, new_height):
        """Adjust window height while maintaining center position"""
        try:
            # Force window to update to get accurate dimensions
            self.root.update_idletasks()
            
            # Use reliable winfo methods instead of parsing geometry string
            current_width = self.root.winfo_width()
            current_height = self.root.winfo_height()
            
            # Only adjust if height is different
            if current_height != new_height:
                # If window hasn't been displayed yet, current_width might be 1
                # In that case, use the intended width of 900
                if current_width <= 1:
                    current_width = 900
                
                # Calculate center position for both X and Y
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                center_x = int(screen_width/2 - current_width/2)
                center_y = int(screen_height/2 - new_height/2)
                
                # Set new geometry with current width, new height, and properly centered position
                self.root.geometry(f'{current_width}x{new_height}+{center_x}+{center_y}')
                
                # Force another update to ensure the window is properly positioned
                self.root.update_idletasks()
                
                print(f"Window adjusted to: {current_width}x{new_height} at center ({center_x}, {center_y})")
            
        except Exception as e:
            print(f"Warning: Could not adjust window height: {e}")
            # Fallback: use center_window function for reliable centering
            center_window(self.root, 900, new_height)
    
    def next_step(self):
        """Go to next step"""
        if self.validate_current_step():
            if self.current_step < self.total_steps - 1:
                self.show_step(self.current_step + 1)
    
    def prev_step(self):
        """Go to previous step"""
        if self.current_step > 0:
            self.show_step(self.current_step - 1)
    
    def validate_current_step(self):
        """Validate current step before proceeding"""
        if self.current_step == 0:  # Connection
            if not self.controller:
                messagebox.showerror("Error", "Please connect to controller first!")
                return False
                
        elif self.current_step == 1:  # System config
            selected_axes = [axis for axis, var in self.axes_vars.items() if var.get()]
            if not selected_axes:
                messagebox.showerror("Error", "Please select at least one axis to enable!")
                return False
            if self.cal_type_var.get() == "without_cal":
                messagebox.showwarning("Warning", "You have selected to run without calibration files. This might result in suboptimal performance.")
                if not messagebox.askyesno("Continue Without Calibration", "Are you sure you want to continue without calibration files?"):
                    return False
                
        elif self.current_step == 2:  # Test config
            test_type = self.test_type_var.get()
            if test_type == "single":
                if not self.single_axis_var.get():
                    messagebox.showerror("Error", "Please select an axis for single axis test!")
                    return False
            else:  # multi
                xy_selected = [axis for axis, var in self.xy_axes_vars.items() if var.get()]
                other_selected = [axis for axis, var in self.other_axes_vars.items() if var.get()]
                if not xy_selected and not other_selected:
                    messagebox.showerror("Error", "Please select at least one axis configuration!")
                    return False
                    
        elif self.current_step == 3:  # Axis params
            # Validate that all required parameters are filled
            for axis, params in self.axis_param_vars.items():
                try:
                    vel = float(params['velocity'].get())
                    accel = float(params['acceleration'].get())
                    if vel <= 0 or accel <= 0:
                        raise ValueError()
                except (ValueError, tk.TclError):
                    messagebox.showerror("Error", f"Please enter valid positive values for {axis} axis parameters!")
                    return False
        
        return True
    
    def connect_controller(self):
        """Connect to the automation controller"""
        self.connect_btn.config(text="Connecting...", state='disabled')
        self.conn_status_label.config(text="Connecting to controller...")
        
        def connect_thread():
            try:
                connection_type = self.connection_var.get()
                
                # Use the modified connect function with connection_type parameter
                if connection_type == "auto":
                    self.controller, self.available_axes = RunEasyTune.connect()
                else:
                    # Pass the connection type to the modified connect function
                    self.controller, self.available_axes = RunEasyTune.connect(connection_type)
                
                # Update UI on main thread
                self.root.after(0, self.connection_success)
                
            except Exception as e:
                self.root.after(0, lambda: self.connection_failed(str(e)))
        
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def connection_success(self):
        """Handle successful connection"""
        self.connect_btn.config(text="Connected ✓", state='disabled')
        self.conn_status_label.config(text=f"Connected successfully! Controller: {self.controller.name}")
        
        # Update axes display
        axes_text = ", ".join(self.available_axes) if self.available_axes else "No axes found"
        self.axes_label.config(text=f"Available axes: {axes_text}")
        
        # Enable next button
        self.next_btn.config(state='normal')
    
    def connection_failed(self, error_msg):
        """Handle failed connection"""
        self.connect_btn.config(text="Connect to Controller", state='normal')
        self.conn_status_label.config(text=f"Connection failed: {error_msg}")
        messagebox.showerror("Connection Error", f"Failed to connect to controller:\n{error_msg}")
    
    def update_axes_checkboxes(self):
        """Update the axes checkboxes in system config"""
        # Clear existing checkboxes
        for widget in self.axes_checkboxes_frame.winfo_children():
            widget.destroy()
        
        self.axes_vars = {}
        
        # Create checkboxes for each available axis
        if self.available_axes:
            for i, axis in enumerate(self.available_axes):
                var = tk.BooleanVar(value=True)  # Default to selected
                self.axes_vars[axis] = var
                
                cb = ttk.Checkbutton(self.axes_checkboxes_frame, text=axis, variable=var)
                cb.grid(row=i//4, column=i%4, sticky='w', padx=10, pady=2)
    
    def update_test_config(self):
        """Update test configuration display based on selection"""
        test_type = self.test_type_var.get()
        
        if test_type == "single":
            self.single_config_frame.pack(fill='x', pady=10, padx=20)
            self.multi_config_frame.pack_forget()
        else:
            self.single_config_frame.pack_forget()
            self.multi_config_frame.pack(fill='x', pady=10, padx=20)
    
    def update_axis_combos(self):
        """Update axis combo boxes with available axes"""
        # Update single axis combo
        self.single_axis_combo['values'] = self.available_axes
        if self.available_axes:
            self.single_axis_combo.set(self.available_axes[0])
        
        # Update multi-axis checkboxes
        self.update_multi_axis_checkboxes()
    
    def update_multi_axis_checkboxes(self):
        """Update multi-axis checkboxes"""
        # Clear existing
        for widget in self.xy_axes_frame.winfo_children():
            widget.destroy()
        for widget in self.other_axes_frame.winfo_children():
            widget.destroy()
        
        self.xy_axes_vars = {}
        self.other_axes_vars = {}
        
        if self.available_axes:
            # XY axes checkboxes
            for i, axis in enumerate(self.available_axes):
                var = tk.BooleanVar()
                self.xy_axes_vars[axis] = var
                cb = ttk.Checkbutton(self.xy_axes_frame, text=axis, variable=var)
                cb.grid(row=i//4, column=i%4, sticky='w', padx=5, pady=2)
            
            # Other axes checkboxes  
            for i, axis in enumerate(self.available_axes):
                var = tk.BooleanVar()
                self.other_axes_vars[axis] = var
                cb = ttk.Checkbutton(self.other_axes_frame, text=axis, variable=var)
                cb.grid(row=i//4, column=i%4, sticky='w', padx=5, pady=2)
    
    def update_axis_params(self):
        """Update axis parameters based on test configuration"""
        # Clear existing
        for widget in self.axis_params_frame.winfo_children():
            widget.destroy()
        
        self.axis_param_vars = {}
        
        # Determine which axes need parameters
        test_type = self.test_type_var.get()
        axes_to_configure = []
        
        if test_type == "single":
            if self.single_axis_var.get():
                axes_to_configure.append(self.single_axis_var.get())
        else:
            # Multi-axis
            xy_axes = [axis for axis, var in self.xy_axes_vars.items() if var.get()]
            other_axes = [axis for axis, var in self.other_axes_vars.items() if var.get()]
            axes_to_configure.extend(xy_axes)
            axes_to_configure.extend(other_axes)
        
        # Create parameter inputs for each axis
        for i, axis in enumerate(axes_to_configure):
            # Create frame for this axis
            axis_frame = tk.LabelFrame(self.axis_params_frame, text=f"{axis} Axis Parameters",
                                      font=('D-Din', 10, 'bold'), fg='#006298', bg='white')
            axis_frame.pack(fill='x', pady=10, padx=20)
            
            # Velocity input
            vel_frame = tk.Frame(axis_frame, bg='white')
            vel_frame.pack(fill='x', padx=10, pady=5)
            
            ttk.Label(vel_frame, text="Max Velocity:", width=15).pack(side='left')
            vel_var = tk.StringVar(value="100.0")
            vel_entry = ttk.Entry(vel_frame, textvariable=vel_var, width=15)
            vel_entry.pack(side='left', padx=(10, 5))
            ttk.Label(vel_frame, text="units/s").pack(side='left')
            
            # Acceleration input
            accel_frame = tk.Frame(axis_frame, bg='white')
            accel_frame.pack(fill='x', padx=10, pady=5)
            
            ttk.Label(accel_frame, text="Max Acceleration:", width=15).pack(side='left')
            accel_var = tk.StringVar(value="1000.0")
            accel_entry = ttk.Entry(accel_frame, textvariable=accel_var, width=15)
            accel_entry.pack(side='left', padx=(10, 5))
            ttk.Label(accel_frame, text="units/s²").pack(side='left')
            
            # Store variables
            self.axis_param_vars[axis] = {
                'velocity': vel_var,
                'acceleration': accel_var
            }
    
    def update_summary(self):
        """Update the configuration summary"""
        self.summary_text.delete(1.0, tk.END)
        
        summary = "=== EasyTune Configuration Summary ===\n\n"
        
        # Controller info
        summary += f"Controller: {self.controller.name if self.controller else 'Not connected'}\n"
        summary += f"Available Axes: {', '.join(self.available_axes)}\n\n"
        
        # Enabled axes
        enabled_axes = [axis for axis, var in self.axes_vars.items() if var.get()]
        summary += f"Enabled Axes: {', '.join(enabled_axes)}\n\n"
        
        # Test configuration
        test_type = self.test_type_var.get()
        summary += f"Test Type: {test_type.title()}\n"
        
        if test_type == "single":
            summary += f"Test Axis: {self.single_axis_var.get()}\n"
        else:
            xy_axes = [axis for axis, var in self.xy_axes_vars.items() if var.get()]
            other_axes = [axis for axis, var in self.other_axes_vars.items() if var.get()]
            if xy_axes:
                summary += f"XY Configuration: {', '.join(xy_axes)}\n"
            if other_axes:
                summary += f"Other Axes: {', '.join(other_axes)}\n"
        
        summary += "\n"
        
        # Axis parameters
        summary += "Axis Parameters:\n"
        for axis, params in self.axis_param_vars.items():
            vel = params['velocity'].get()
            accel = params['acceleration'].get()
            summary += f"  {axis}: Velocity={vel} units/s, Acceleration={accel} units/s²\n"
        
        self.summary_text.insert(1.0, summary)
        self.summary_text.config(state='disabled')
    
    def start_easytune(self):
        """Start the EasyTune process"""
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.output_text.delete(1.0, tk.END)
        
        # Clear any previous stop signal
        self.stop_event.clear()
        
        def easytune_thread():
            try:
                # Redirect stdout to our text widget
                old_stdout = sys.stdout
                sys.stdout = self.redirect_text
                
                # Check if stop was requested before starting
                if self.stop_event.is_set():
                    self.output_queue.put("\n⚠️ Process stopped before starting\n")
                    return
                
                # Prepare configuration
                test_type = self.test_type_var.get()
                enabled_axes = [axis for axis, var in self.axes_vars.items() if var.get()]
                
                # Collect axis parameters from UI
                axes_params = {}
                for axis, params in self.axis_param_vars.items():
                    axes_params[axis] = {
                        'velocity': float(params['velocity'].get()),
                        'acceleration': float(params['acceleration'].get())
                    }
                
                # Determine axis configuration based on test type
                if test_type == "single":
                    single_axis = self.single_axis_var.get()
                    xy_axes = []
                    other_axes = []
                else:
                    single_axis = None
                    xy_axes = [axis for axis, var in self.xy_axes_vars.items() if var.get()]
                    other_axes = [axis for axis, var in self.other_axes_vars.items() if var.get()]
                
                # Create comprehensive ui_params including stop_event
                ui_params = {
                    'connection_type': self.connection_var.get(),
                    'controller': self.controller,
                    'available_axes': self.available_axes,
                    'all_axes': enabled_axes,
                    'test_type': test_type,
                    'single_axis': single_axis,
                    'xy_axes': xy_axes,
                    'other_axes': other_axes,
                    'axes_params': axes_params,
                    'cal_file_ready': self.cal_type_var.get() == "with_cal",
                    'stop_event': self.stop_event  # Pass stop event to EasyTune process
                }
                
                # Single call to main() - it handles everything!
                self.output_queue.put("🚀 Starting EasyTune process...\n")
                RunEasyTune.main(ui_params=ui_params)
                
                if not self.stop_event.is_set():
                    self.output_queue.put("\n🎉 EasyTune process completed successfully!\n")
                else:
                    self.output_queue.put("\n⚠️ EasyTune process was stopped by user\n")
                
            except KeyboardInterrupt:
                self.output_queue.put("\n🛑 EasyTune process stopped by user\n")
            except Exception as e:
                if not self.stop_event.is_set():
                    self.output_queue.put(f"\n❌ Error during EasyTune process: {str(e)}\n")
                    import traceback
                    self.output_queue.put(traceback.format_exc())
                else:
                    self.output_queue.put("\n⚠️ Process stopped during execution\n")
            finally:
                sys.stdout = old_stdout
                self.root.after(0, self.easytune_finished)
        
        # Store thread reference so we can manage it
        self.easytune_thread = threading.Thread(target=easytune_thread, daemon=True)
        self.easytune_thread.start()
    
    def stop_easytune(self):
        """Stop the EasyTune process"""
        self.output_queue.put("\n🛑 Stop requested by user - shutting down gracefully...\n")
        
        # Signal the thread to stop
        self.stop_event.set()
        
        # Update UI immediately
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        
        # Optional: Wait a moment for graceful shutdown
        if self.easytune_thread and self.easytune_thread.is_alive():
            self.output_queue.put("⏳ Waiting for current operation to complete...\n")
            
            # Give it 3 seconds to stop gracefully
            self.easytune_thread.join(timeout=3)
            
            if self.easytune_thread.is_alive():
                self.output_queue.put("⚠️ Process is taking longer than expected to stop\n")
                # Note: Python threads can't be forcefully killed, but the stop_event 
                # should cause it to exit at the next check point
    
    def easytune_finished(self):
        """Called when EasyTune process finishes"""
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.finish_btn.config(state='normal')
    
    def monitor_output(self):
        """Monitor the output queue and update text widget"""
        try:
            while True:
                text = self.output_queue.get_nowait()
                self.output_text.insert(tk.END, text)
                self.output_text.see(tk.END)
                self.root.update_idletasks()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.monitor_output)

def center_window(root, width=900, height=700):
    """Center the window on the screen"""
    # Get screen dimensions
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    # Calculate center position
    center_x = int(screen_width/2 - width/2)
    center_y = int(screen_height/2 - height/2)
    
    # Set window size and position
    root.geometry(f'{width}x{height}+{center_x}+{center_y}')

def main():
    """Main function to run the UI"""
    root = tk.Tk()
    
    # Set window icon and other properties
    try:
        # Try to set an icon if available
        root.iconbitmap('icon.ico')
    except:
        pass
    
    # Prevent window from being resizable during initial setup
    root.resizable(False, False)
    
    # Center the window on screen
    center_window(root, 900, 700)
    
    # Make window resizable after positioning
    root.resizable(True, True)
    
    # Create and start the application
    app = EasyTuneUI(root)
    
    # Handle window closing
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit EasyTune?"):
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Start the GUI
    root.mainloop()

if __name__ == "__main__":
    main() 