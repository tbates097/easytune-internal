"""
Drive Configuration GUI for GenerateMCD v2.0
===========================================
Presents a user-friendly window with dropdowns and text fields for configuring
Aerotech drive electrical options based on the drive_config.json specifications.
"""

import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from tkinter import font as tkfont

# Aerotech UI Guidelines Colors
AEROTECH_COLORS = {
    'blue1': '#0082BE',  # Primary Blue
    'grey1': '#4B545E',  # Primary Grey
    'grey2': '#DAE1E9',  # Light Grey
    'black': '#231F20',  # Primary Black
    'grey3': '#B5BBC3',  # Medium Grey
    'grey5': '#ECEFF3',  # Very Light Grey
    'grey6': '#F7F8F8',  # Background Grey
    'red1': '#DB2115',   # Error Red
    'orange1': '#EF8B22', # Warning Orange
    'green1': '#459A34'  # Success Green
}

sys.path.insert(0, r'C:\Users\tbates\Python\automated-checkout-bench')

class DriveConfigurationGUI:
    def __init__(self, mcd_processor, drive_type=None):
        self.mcd_processor = mcd_processor
        self.drive_type = drive_type
        self.root = None
        self.config_vars = {}
        self.config_widgets = {}
        self.result = None
        
        # Load Aerotech fonts if available
        self.fonts = {
            'h1': ('Source Sans Pro Semibold', 20),
            'h2': ('Source Sans Pro Semibold', 18),
            't1': ('Source Sans Pro Semibold', 16),
            't2': ('Source Sans Pro', 16),
            't3': ('Source Sans Pro', 16)
        }
        
        # Try to load Source Sans Pro, fall back to system fonts if not available
        try:
            available_fonts = list(tkfont.families())
            if 'Source Sans Pro' not in available_fonts and 'Source Sans Pro Semibold' not in available_fonts:
                # Fall back to system fonts
                self.fonts = {
                    'h1': ('Arial Bold', 20),
                    'h2': ('Arial Bold', 18),
                    't1': ('Arial Bold', 16),
                    't2': ('Arial', 16),
                    't3': ('Arial', 16)
                }
        except Exception as e:
            print(f"Font loading warning: {e}")
        
    def show_drive_selection_dialog(self):
        """Show dialog to select drive type first"""
        # Create root window if it doesn't exist
        if not self.root:
            self.root = tk.Tk()
            self.root.withdraw()  # Hide the root window
        
        selection_window = tk.Toplevel(self.root)
        selection_window.title("Select Drive Type - GenerateMCD v2.0")
        selection_window.geometry("700x500")  # Increased size from 500x400
        selection_window.resizable(True, True)  # Allow resizing
        
        # Set Aerotech colors
        selection_window.configure(bg=AEROTECH_COLORS['grey6'])  # Background Grey
        
        # Make window visible and bring to front
        selection_window.lift()  # Bring window to front
        selection_window.attributes('-topmost', True)  # Keep on top temporarily
        selection_window.after(1000, lambda: selection_window.attributes('-topmost', False))
        selection_window.focus_force()  # Force focus
        
        # Center the window
        selection_window.transient(self.root)
        selection_window.grab_set()
        
        # Get available drives
        drives_info = self.mcd_processor.get_available_drives_with_info()
        drives_with_templates = [d for d in drives_info if d['template_exists']]
        
        # Title
        title_label = tk.Label(selection_window, text="Select Aerotech Drive Type", 
                              font=self.fonts['h1'], fg=AEROTECH_COLORS['grey1'],
                              bg=AEROTECH_COLORS['grey6'])
        title_label.pack(pady=10)
        
        # Description
        desc_label = tk.Label(selection_window, 
                             text="Choose the drive type you want to configure:",
                             font=self.fonts['t1'], fg=AEROTECH_COLORS['grey1'],
                             bg=AEROTECH_COLORS['grey6'])
        desc_label.pack(pady=5)
        
        # Drive list frame
        list_frame = tk.Frame(selection_window, bg=AEROTECH_COLORS['grey6'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=15)  # Increased padding
        
        # Listbox with scrollbar
        listbox_frame = tk.Frame(list_frame, bg=AEROTECH_COLORS['grey6'])
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        drives_listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set,
                                   font=self.fonts['t2'], height=15,
                                   bg='white', fg=AEROTECH_COLORS['grey1'],
                                   selectbackground=AEROTECH_COLORS['blue1'],
                                   selectforeground='white')
        drives_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=drives_listbox.yview)
        
        # Populate listbox
        drive_list = []
        for drive in sorted(drives_with_templates, key=lambda x: x['type']):
            multi_axis_indicator = "🔧" if drive['is_multi_axis'] else "🔹"
            display_text = f"{multi_axis_indicator} {drive['type']} - {drive['display_name']}"
            drives_listbox.insert(tk.END, display_text)
            drive_list.append(drive['type'])
        
        # Info display
        info_text = scrolledtext.ScrolledText(list_frame, height=6, width=50, 
                                            font=self.fonts['t3'], state=tk.DISABLED,
                                            bg=AEROTECH_COLORS['grey5'], fg=AEROTECH_COLORS['grey1'])
        info_text.pack(fill=tk.X, pady=(10, 0))
        
        def on_drive_select(event):
            selection = drives_listbox.curselection()
            if selection:
                drive_info = drives_with_templates[selection[0]]
                info_text.config(state=tk.NORMAL)
                info_text.delete(1.0, tk.END)
                info_text.insert(tk.END, f"Drive: {drive_info['display_name']}\n")
                info_text.insert(tk.END, f"Description: {drive_info['description']}\n")
                info_text.insert(tk.END, f"Type: {drive_info['controller_type']}\n")
                info_text.insert(tk.END, f"Multi-axis: {'Yes' if drive_info['is_multi_axis'] else 'No'}\n")
                info_text.insert(tk.END, f"Configuration options: {drive_info['electrical_options_count']}\n")
                info_text.insert(tk.END, f"Required options: {drive_info['required_options_count']}")
                info_text.config(state=tk.DISABLED)
        
        drives_listbox.bind('<<ListboxSelect>>', on_drive_select)
        
        # Buttons
        button_frame = tk.Frame(selection_window, bg=AEROTECH_COLORS['grey6'])
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        def on_configure():
            selection = drives_listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a drive type to configure.")
                return
            
            selected_drive_info = drives_with_templates[selection[0]]
            selected_drive = selected_drive_info['type']
            selection_window.destroy()
            self.drive_type = selected_drive
            self.show_configuration_window()
        
        def on_cancel():
            selection_window.destroy()
            self.result = None
            if self.root:
                self.root.quit()
        
        # Primary button (Aerotech blue)
        tk.Button(button_frame, text="Configure Selected Drive", command=on_configure,
                 bg=AEROTECH_COLORS['blue1'], fg='white', 
                 font=self.fonts['t2'],
                 activebackground='#1C94D2',  # Hover state (15% lighter)
                 padx=10, pady=5).pack(side=tk.RIGHT, padx=(5, 0))
                 
        # Secondary button
        tk.Button(button_frame, text="Cancel", command=on_cancel,
                 bg=AEROTECH_COLORS['grey2'], fg=AEROTECH_COLORS['grey1'],
                 font=self.fonts['t2'],
                 activebackground='#E0E5EC',  # Hover state
                 padx=10, pady=5).pack(side=tk.RIGHT)
        
        # Select first item by default
        if drives_listbox.size() > 0:
            drives_listbox.selection_set(0)
            on_drive_select(None)
    
    def show_configuration_window(self):
        """Show the main configuration window with all options"""
        if not self.drive_type:
            self.show_drive_selection_dialog()
            return
        
        # Get menu data for the drive
        menu_data = self.mcd_processor.get_drive_menu_data(self.drive_type)
        if not menu_data:
            messagebox.showerror("Configuration Error", 
                               f"No configuration data found for drive type: {self.drive_type}")
            return
        
        # Create root window if it doesn't exist
        if not self.root:
            self.root = tk.Tk()
            
        # Configure window
        self.root.title(f"Drive Configuration - {menu_data['drive_info']['display_name']} - GenerateMCD v2.0")
        self.root.geometry("900x700")  # Increased size from 700x600
        self.root.configure(bg=AEROTECH_COLORS['grey6'])  # Background Grey
        
        # Make window visible and bring to front
        self.root.lift()  # Bring window to front
        self.root.attributes('-topmost', True)  # Keep on top temporarily
        self.root.after(1000, lambda: self.root.attributes('-topmost', False))  # Then allow it to go back
        self.root.focus_force()  # Force focus
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure Aerotech style elements
        style.configure('TFrame', background=AEROTECH_COLORS['grey6'])
        style.configure('TLabel', background=AEROTECH_COLORS['grey6'], foreground=AEROTECH_COLORS['grey1'])
        style.configure('TButton', font=self.fonts['t2'])
        style.configure('Aerotech.TButton', 
                      background=AEROTECH_COLORS['blue1'], 
                      foreground='white',
                      padding=(10, 5))
        
        # Main frame with scrollbar
        main_frame = tk.Frame(self.root, bg=AEROTECH_COLORS['grey6'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)  # Increased padding
        
        # Canvas for scrolling
        canvas = tk.Canvas(main_frame, bg=AEROTECH_COLORS['grey6'], 
                          highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Header
        header_frame = ttk.Frame(scrollable_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = tk.Label(header_frame, text=menu_data['drive_info']['display_name'], 
                              font=self.fonts['h1'], fg=AEROTECH_COLORS['grey1'],
                              bg=AEROTECH_COLORS['grey6'])
        title_label.pack()
        
        desc_label = tk.Label(header_frame, text=menu_data['drive_info']['description'],
                             font=self.fonts['t1'], fg=AEROTECH_COLORS['grey1'],
                             bg=AEROTECH_COLORS['grey6'])
        desc_label.pack()
        
        type_label = tk.Label(header_frame, 
                             text=f"{menu_data['drive_info']['controller_type']} • "
                                  f"{'Multi-axis' if menu_data['drive_info']['is_multi_axis'] else 'Single-axis'}",
                             font=self.fonts['t3'], fg=AEROTECH_COLORS['grey3'],
                             bg=AEROTECH_COLORS['grey6'])
        type_label.pack()
        
        # Configuration options - H2 Headline style
        options_frame = ttk.LabelFrame(scrollable_frame, text="Configuration Options", 
                                     padding=15, style='TLabelframe')
        style.configure('TLabelframe', background=AEROTECH_COLORS['grey6'])
        style.configure('TLabelframe.Label', font=self.fonts['h2'], 
                      foreground=AEROTECH_COLORS['grey1'],
                      background=AEROTECH_COLORS['grey6'])
        options_frame.pack(fill=tk.X, pady=10)
        
        # Create widgets for each option
        row = 0
        for option in menu_data['options']:
            self.create_option_widget(options_frame, option, row)
            row += 2  # Skip a row for spacing
        
        # Buttons frame
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, pady=30)  # More vertical space for buttons
        
        # Create Aerotech button styles
        style.configure('Primary.TButton', 
                      background=AEROTECH_COLORS['blue1'],
                      foreground='white',
                      font=self.fonts['t2'])
                      
        style.configure('Secondary.TButton',
                      background=AEROTECH_COLORS['grey2'],
                      foreground=AEROTECH_COLORS['grey1'],
                      font=self.fonts['t2'])
        
        # Action buttons with increased padding and size
        apply_defaults_btn = ttk.Button(button_frame, text="Apply Defaults", 
                                      command=self.apply_defaults,
                                      style='Secondary.TButton')
        apply_defaults_btn.pack(side=tk.LEFT, padx=(0, 15), pady=10, ipadx=5, ipady=5)
                  
        validate_btn = ttk.Button(button_frame, text="Validate Configuration", 
                                command=self.validate_config,
                                style='Secondary.TButton')
        validate_btn.pack(side=tk.LEFT, padx=(0, 15), pady=10, ipadx=5, ipady=5)
                  
        apply_btn = ttk.Button(button_frame, text="Apply Configuration", 
                             command=self.generate_mcd,
                             style='Primary.TButton')
        apply_btn.pack(side=tk.RIGHT, padx=(15, 0), pady=10, ipadx=10, ipady=5)
                  
        cancel_btn = ttk.Button(button_frame, text="Cancel", 
                              command=self.cancel,
                              style='Secondary.TButton')
        cancel_btn.pack(side=tk.RIGHT, padx=(0, 0), pady=10, ipadx=5, ipady=5)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Apply defaults on startup
        self.apply_defaults()
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (self.root.winfo_width() // 2)
        y = (self.root.winfo_screenheight() // 2) - (self.root.winfo_height() // 2)
        self.root.geometry(f"+{x}+{y}")
    
    def create_option_widget(self, parent, option, row):
        """Create appropriate widget for each configuration option"""
        # Label frame for each option
        option_frame = ttk.Frame(parent)
        option_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=5)
        parent.grid_columnconfigure(0, weight=1)
        
        # Option name with required indicator
        name_text = option['name']
        if option['required']:
            name_text += " *"
        
        name_label = tk.Label(option_frame, text=name_text, 
                            font=self.fonts['t2'],
                            fg=AEROTECH_COLORS['red1'] if option['required'] else AEROTECH_COLORS['grey1'],
                            bg=AEROTECH_COLORS['grey6'])
        name_label.grid(row=0, column=0, sticky="w", padx=(0, 20), pady=(10, 5))  # Increased padding
        
        # Description
        desc_label = tk.Label(option_frame, text=option['description'], 
                            font=self.fonts['t3'], fg=AEROTECH_COLORS['grey3'],
                            bg=AEROTECH_COLORS['grey6'])
        desc_label.grid(row=1, column=0, sticky="w", pady=(2, 10))  # Increased bottom padding
        
        if option['type'] == 'selection':
            # Dropdown for selection options
            var = tk.StringVar()
            combobox = ttk.Combobox(option_frame, textvariable=var, state="readonly", width=30)  # Wider dropdown
            combobox['values'] = option['choices']
            combobox.grid(row=0, column=1, sticky="w", padx=(20, 0))  # Increased left padding
            
            # Show default and suffix info
            default_text = f"Default: {option['default'] or 'None'}"
            if option.get('suffix'):
                default_text += f" (auto-suffix: {option['suffix']})"
            
            default_label = tk.Label(option_frame, text=default_text,
                                   font=('Arial', 8), fg='#888888')
            default_label.grid(row=1, column=1, sticky="w", padx=(10, 0))
            
            self.config_vars[option['name']] = var
            self.config_widgets[option['name']] = combobox
            
        elif option['type'] == 'text':
            # Text entry for text options
            var = tk.StringVar()
            entry = ttk.Entry(option_frame, textvariable=var, width=30)  # Wider text field
            entry.grid(row=0, column=1, sticky="w", padx=(20, 0))  # Increased left padding
            
            # Show default/placeholder
            if option['default']:
                placeholder_label = tk.Label(option_frame, text=f"Default: {option['default']}",
                                           font=('Arial', 8), fg='#888888')
                placeholder_label.grid(row=1, column=1, sticky="w", padx=(10, 0))
            
            self.config_vars[option['name']] = var
            self.config_widgets[option['name']] = entry
    
    def apply_defaults(self):
        """Apply default values to all configuration options"""
        menu_data = self.mcd_processor.get_drive_menu_data(self.drive_type)
        if not menu_data:
            return
        
        for option in menu_data['options']:
            if option['name'] in self.config_vars:
                var = self.config_vars[option['name']]
                default_value = option.get('default', '')
                
                if option['type'] == 'selection' and default_value:
                    # For dropdowns, set the default value
                    var.set(default_value)
                elif option['type'] == 'text' and default_value:
                    # For text fields, set the default value
                    var.set(default_value)
    
    def validate_config(self):
        """Validate the current configuration"""
        electrical_dict = self.get_current_config()
        
        validation = self.mcd_processor.validate_electrical_configuration(
            self.drive_type, electrical_dict)
        
        if validation['valid']:
            messagebox.showinfo("Validation Success", 
                              "✅ Configuration is valid!\n\nReady to generate MCD file.")
        else:
            error_msg = "❌ Configuration validation failed:\n\n"
            for error in validation['errors']:
                error_msg += f"• {error}\n"
            
            # Show suggestions if available
            suggestions = validation.get('suggestions', {})
            if suggestions:
                error_msg += "\n💡 Suggestions:\n"
                for option, suggestion in suggestions.items():
                    error_msg += f"• {option}: {suggestion}\n"
            
            messagebox.showerror("Validation Error", error_msg)
    
    def get_current_config(self):
        """Get the current configuration from the GUI"""
        electrical_dict = {}
        menu_data = self.mcd_processor.get_drive_menu_data(self.drive_type)
        
        for option in menu_data['options']:
            if option['name'] in self.config_vars:
                var = self.config_vars[option['name']]
                value = var.get().strip()
                
                if value:  # Only include non-empty values
                    # Apply suffix if specified for selection options
                    if option['type'] == 'selection' and option.get('suffix'):
                        if not value.endswith(option['suffix']):
                            value += option['suffix']
                    
                    electrical_dict[option['name']] = value
        
        return electrical_dict
    
    def generate_mcd(self):
        """Generate MCD with current configuration"""
        # Validate first
        electrical_dict = self.get_current_config()
        
        validation = self.mcd_processor.validate_electrical_configuration(
            self.drive_type, electrical_dict)
        
        if not validation['valid']:
            self.validate_config()  # Show validation errors
            return
        
        # Show configuration summary dialog
        config_summary = "Configuration Summary:\n" + "="*40 + "\n"
        config_summary += f"Drive Type: {self.drive_type}\n"
        config_summary += f"Electrical Configuration:\n"
        for key, value in electrical_dict.items():
            config_summary += f"  • {key}: {value}\n"
        
        result = messagebox.askyesno("Generate MCD", 
                                   f"{config_summary}\n\nProceed with MCD generation?")
        
        if result:
            self.result = electrical_dict
            self.root.quit()
            self.root.destroy()
    
    def cancel(self):
        """Cancel configuration"""
        self.result = None
        if self.root:
            self.root.quit()
            self.root.destroy()
    
    def show(self):
        """Show the configuration GUI and return the result"""
        print("Opening GUI window...")
        
        if not self.drive_type:
            print("No drive type specified - showing selection dialog")
            self.show_drive_selection_dialog()
        else:
            print(f"Configuring drive type: {self.drive_type}")
            self.show_configuration_window()
        
        if self.root:
            print("Starting GUI mainloop - window should be visible now")
            print("⚠️ LOOK FOR THE WINDOW - it may be behind other windows or on another monitor")
            self.root.mainloop()
        else:
            print("❌ Error: No root window was created")
        
        return self.result


def demo_gui():
    """Demo function to show the GUI in action"""
    try:
        from GenerateMCD_v2 import AerotechController
        
        print("🚀 Initializing GenerateMCD v2.0 with GUI Configuration...")
        mcd_processor = AerotechController.with_file_saving(
            output_dir=os.path.join(os.getcwd(), 'GUI_Demo_Output'),
            separate_dirs=True,
            overwrite=True
        )
        mcd_processor.initialize()
        print("✅ System initialized!")
        
        # Show GUI configuration
        config_gui = DriveConfigurationGUI(mcd_processor)
        electrical_config = config_gui.show()
        
        if electrical_config:
            print(f"\n✅ User configured drive with options:")
            for key, value in electrical_config.items():
                print(f"   • {key}: {value}")
            
            # Example: Generate MCD with the configuration
            print(f"\n🔧 Generating MCD for {config_gui.drive_type}...")
            
            # Use sample mechanical specs
            specs_dict = {
                'Travel': '-025',
                'Feedback': '-E1',
                'Cable Management': '-CMS2'
            }
            
            try:
                calculated_mcd, warnings, output_path = mcd_processor.calculate_parameters(
                    specs_dict=specs_dict,
                    electrical_dict=electrical_config,
                    stage_type='DemoStage',
                    axis='ST01',
                    drive_type=config_gui.drive_type
                )
                
                print(f"✅ Success! MCD generated: {output_path}")
                if warnings:
                    print(f"⚠️ Warnings: {warnings}")
                    
            except Exception as e:
                print(f"❌ MCD generation failed: {e}")
        else:
            print("\n❌ Configuration cancelled by user.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    demo_gui()
