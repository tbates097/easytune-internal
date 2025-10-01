"""
GenerateMCD v2.0 - Refactored Architecture
==========================================

This module provides a robust set of classes to interact with Aerotech Automation1 DLLs
for Machine Setup calculations. The design separates concerns for better reusability:

- McdProcessor: Core .NET DLL operations
- FileManager: File operations, naming, and path management  
- Strategy classes: Different naming and output approaches
- AerotechController: Main facade orchestrating everything

Main Use Cases:
1. Convert template JSON to MCD object (optionally save)
2. Convert MCD file/object to JSON (always save) 
3. Generate MCD with calculated parameters from specifications
4. Recalculate existing MCD and extract servo/feedforward parameters

Note: Use variable names like 'mcd_processor' or 'mcd_handler' - avoid 'controller' 
which is reserved for actual Automation1 controller objects.
"""
from pythonnet import load
load("coreclr")
import os
import sys
import json
from abc import ABC, abstractmethod
from tkinter import messagebox
import xml.etree.ElementTree as ET

# Import System for Type.GetType
import System
from System.Collections.Generic import List
from System import String

import clr

sys.dont_write_bytecode = True

# ============================================================================
# STRATEGY INTERFACES
# ============================================================================

class NamingStrategy(ABC):
    """Abstract base class for different file naming strategies"""
    
    @abstractmethod
    def generate_filename(self, file_type, stage_type, context=None):
        """Generate filename based on strategy
        
        Args:
            file_type: 'calculated', 'uncalculated', or 'recalculated'
            stage_type: Stage type name
            context: Additional context dict (smart_string, axis, etc.)
        
        Returns:
            str: Generated filename with extension
        """
        pass

class OutputStrategy(ABC):
    """Abstract base class for different output location strategies"""
    
    @abstractmethod
    def get_output_directory(self, file_type):
        """Get output directory for file type
        
        Args:
            file_type: 'calculated', 'uncalculated', or 'recalculated'
            
        Returns:
            str: Directory path
        """
        pass
    
    @abstractmethod
    def should_create_directories(self):
        """Whether to auto-create directories"""
        pass

# ============================================================================
# CONCRETE NAMING STRATEGIES
# ============================================================================

class DefaultNamingStrategy(NamingStrategy):
    """Default naming: [Prefix]_[stage_type].mcd"""
    
    def __init__(self, 
                 calculated_prefix="Calculated_",
                 uncalculated_prefix="Uncalculated_", 
                 recalculated_prefix="Recalculated_",
                 extension=".mcd"):
        self.prefixes = {
            'calculated': calculated_prefix,
            'uncalculated': uncalculated_prefix,
            'recalculated': recalculated_prefix
        }
        self.extension = extension
    
    def generate_filename(self, file_type, stage_type, context=None):
        prefix = self.prefixes.get(file_type, "")
        return f"{prefix}{stage_type}{self.extension}"

class SmartStringNamingStrategy(NamingStrategy):
    """Smart string naming: [smart_string].mcd or fallback to default"""
    
    def __init__(self, smart_string=None, extension=".mcd"):
        self.smart_string = smart_string
        self.extension = extension
        self.fallback = DefaultNamingStrategy(extension=extension)
    
    def generate_filename(self, file_type, stage_type, context=None):
        if self.smart_string:
            return f"{self.smart_string}{self.extension}"
        return self.fallback.generate_filename(file_type, stage_type, context)

class CustomNamingStrategy(NamingStrategy):
    """Custom naming using a provided function"""
    
    def __init__(self, naming_function, extension=".mcd"):
        self.naming_function = naming_function
        self.extension = extension
    
    def generate_filename(self, file_type, stage_type, context=None):
        base_name = self.naming_function(file_type, stage_type, context)
        return f"{base_name}{self.extension}"

# ============================================================================
# CONCRETE OUTPUT STRATEGIES
# ============================================================================

class WorkingDirectoryOutputStrategy(OutputStrategy):
    """Output to current working directory"""
    
    def __init__(self, create_dirs=True):
        self.working_dir = os.getcwd()
        self.create_dirs = create_dirs
    
    def get_output_directory(self, file_type):
        return self.working_dir
    
    def should_create_directories(self):
        return self.create_dirs

class SeparateDirectoriesOutputStrategy(OutputStrategy):
    """Output to separate directories for each file type"""
    
    def __init__(self, calculated_dir=None, uncalculated_dir=None, create_dirs=True):
        working_dir = os.getcwd()
        self.directories = {
            'calculated': calculated_dir or working_dir,
            'uncalculated': uncalculated_dir or working_dir,
            'recalculated': calculated_dir or working_dir  # Use calculated dir
        }
        self.create_dirs = create_dirs
    
    def get_output_directory(self, file_type):
        return self.directories.get(file_type, os.getcwd())
    
    def should_create_directories(self):
        return self.create_dirs

class SpecificDirectoryOutputStrategy(OutputStrategy):
    """Output strategy where calculated files go to a specific directory, others to working dir"""
    
    def __init__(self, calculated_dir, create_dirs=True):
        """
        Initialize with specific directory for calculated files
        
        Args:
            calculated_dir: Directory for calculated MCD files
            create_dirs: Whether to auto-create directories
        """
        self.calculated_dir = calculated_dir
        self.working_dir = os.getcwd()
        self.create_dirs = create_dirs
    
    def get_output_directory(self, file_type):
        if file_type == 'calculated':
            return self.calculated_dir
        return self.working_dir  # Uncalculated and recalculated go to working dir
    
    def should_create_directories(self):
        return self.create_dirs


# ============================================================================
# DRIVE CONFIGURATION MANAGER
# ============================================================================

class DriveConfigManager:
    """Manages drive configuration data and provides validation/UI support"""
    
    def __init__(self, config_file_path=None, base_dir=None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        if config_file_path is None:
            config_file_path = os.path.join(base_dir, "drive_config.json")
        
        self.config_file_path = config_file_path
        self.base_dir = base_dir
        self.config_data = self._load_config()
    
    def _load_config(self):
        """Load drive configuration from JSON file"""
        try:
            import json
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Drive config file not found at {self.config_file_path}")
            return {"drive_types": {}}
        except json.JSONDecodeError as e:
            print(f"Error parsing drive config: {e}")
            return {"drive_types": {}}
    

    # ========================================================================
    # DRIVE CONFIGURATION METHODS
    # ========================================================================
    
    def get_drive_menu_data(self, drive_type):
        """Get menu data for UI generation"""
        return self.generate_ui_menu_data(drive_type)
    
    def get_default_electrical_config(self, drive_type):
        """Get default electrical configuration for a drive type"""
        return self.get_default_electrical_dict(drive_type)
    
    def validate_electrical_configuration(self, drive_type, electrical_dict):
        """Validate electrical configuration against drive config"""
        return self.validate_electrical_dict(drive_type, electrical_dict)
    
    def get_available_drive_types_with_info(self):
        """Get available drive types with detailed information"""
        drive_types = []
        for drive_type in self.get_available_drive_types():
            drive_info = self.get_drive_info_detailed(drive_type)
            if drive_info:
                drive_types.append(drive_info)
        return drive_types
    
    def get_drive_electrical_options(self, drive_type):
        """Get electrical options available for a drive type"""
        return self.get_electrical_options(drive_type)
    
    def get_drive_option_choices(self, drive_type, option_name):
        """Get available choices for a specific electrical option"""
        return self.get_option_choices(drive_type, option_name)

    def get_available_drive_types(self):
        """Get list of all configured drive types"""
        return list(self.config_data.get("drive_types", {}).keys())
    
    def get_drive_config(self, drive_type):
        """Get complete configuration for a drive type"""
        return self.config_data.get("drive_types", {}).get(drive_type)
    
    def get_electrical_options(self, drive_type):
        """Get electrical options for a specific drive type"""
        drive_config = self.get_drive_config(drive_type)
        if drive_config:
            return drive_config.get("electrical_options", {})
        return {}
    
    def get_option_choices(self, drive_type, option_name):
        """Get available choices for a specific electrical option"""
        electrical_options = self.get_electrical_options(drive_type)
        option_config = electrical_options.get(option_name, {})
        return option_config.get("choices", [])
    
    def get_default_electrical_dict(self, drive_type):
        """Generate default electrical_dict for a drive type"""
        electrical_options = self.get_electrical_options(drive_type)
        defaults = {}
        
        for option_name, config in electrical_options.items():
            if config.get("required", False) or config.get("default"):
                default_value = config.get("default", "")
                if default_value:
                    # Add suffix if specified
                    suffix = config.get("suffix", "")
                    if suffix and not default_value.endswith(suffix):
                        default_value += suffix
                    defaults[option_name] = default_value
        
        return defaults
    
    def validate_electrical_dict(self, drive_type, electrical_dict):
        """Validate electrical_dict against drive configuration"""
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'missing_required': [],
            'invalid_choices': [],
            'suggestions': {}
        }
        
        drive_config = self.get_drive_config(drive_type)
        if not drive_config:
            results['valid'] = False
            results['errors'].append(f"Unknown drive type: {drive_type}")
            return results
        
        electrical_options = drive_config.get("electrical_options", {})
        
        # Check for missing required options
        for option_name, config in electrical_options.items():
            if config.get("required", False):
                if option_name not in electrical_dict or not electrical_dict[option_name]:
                    results['missing_required'].append(option_name)
                    results['valid'] = False
        
        # Check for invalid choices
        for option_name, value in electrical_dict.items():
            if option_name in electrical_options:
                config = electrical_options[option_name]
                choices = config.get("choices", [])
                
                if choices:  # Only validate if choices are defined
                    # Clean value for comparison (remove suffix)
                    clean_value = str(value)
                    suffix = config.get("suffix", "")
                    if suffix and clean_value.endswith(suffix):
                        clean_value = clean_value[:-len(suffix)]
                    
                    # Check if clean value is in choices
                    valid_choices = [choice.replace(suffix, "") if suffix in str(choice) else str(choice) for choice in choices]
                    if clean_value not in valid_choices:
                        results['invalid_choices'].append({
                            'option': option_name,
                            'value': value,
                            'valid_choices': choices
                        })
                        results['valid'] = False
                        
                        # Suggest default
                        default = config.get("default", "")
                        if default:
                            results['suggestions'][option_name] = default + config.get("suffix", "")
        
        # Compile error messages
        if results['missing_required']:
            results['errors'].append(f"Missing required options: {', '.join(results['missing_required'])}")
        
        if results['invalid_choices']:
            for invalid in results['invalid_choices']:
                results['errors'].append(
                    f"Invalid value '{invalid['value']}' for {invalid['option']}. "
                    f"Valid choices: {', '.join(map(str, invalid['valid_choices']))}"
                )
        
        return results
    
    def generate_ui_menu_data(self, drive_type):
        """Generate data structure for UI menu creation"""
        drive_config = self.get_drive_config(drive_type)
        if not drive_config:
            return {}
        
        menu_data = {
            'drive_info': {
                'display_name': drive_config.get('display_name', drive_type),
                'description': drive_config.get('description', ''),
                'is_multi_axis': drive_config.get('is_multi_axis', False),
                'controller_type': drive_config.get('controller_type', 'Unknown')
            },
            'options': []
        }
        
        electrical_options = drive_config.get("electrical_options", {})
        
        for option_name, config in electrical_options.items():
            option_data = {
                'name': option_name,
                'type': config.get('type', 'selection'),
                'required': config.get('required', False),
                'choices': config.get('choices', []),
                'default': config.get('default', ''),
                'description': config.get('description', ''),
                'suffix': config.get('suffix', '')
            }
            menu_data['options'].append(option_data)
        
        return menu_data
    
    def get_drive_info_detailed(self, drive_type):
        """Get detailed drive information including template validation"""
        config = self.get_drive_config(drive_type)
        if not config:
            return None
            
        template_file = config.get('template_file', f"{drive_type}_Template.json")
        template_path = os.path.join(self.base_dir, "GenerateMCD_Assets", template_file)
        
        return {
            'type': drive_type,
            'display_name': config.get('display_name', drive_type),
            'description': config.get('description', ''),
            'is_multi_axis': config.get('is_multi_axis', False),
            'controller_type': config.get('controller_type', 'Unknown'),
            'max_axes': config.get('max_axes', 1),
            'template_file': template_file,
            'template_exists': os.path.exists(template_path),
            'template_path': template_path if os.path.exists(template_path) else None,
            'electrical_options_count': len(config.get('electrical_options', {})),
            'required_options_count': sum(1 for opt in config.get('electrical_options', {}).values() if opt.get('required', False))
        }


# ============================================================================
# CORE MCD PROCESSOR
# ============================================================================

class McdProcessor:
    """
    Core class handling .NET DLL operations for MCD processing.
    Focused solely on MCD conversion, calculation, and parameter extraction.
    """
    
    def __init__(self, dll_path=None, drive_config_path=None):
        """Initialize with optional custom DLL path and drive config path"""
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self._setup_dll_paths(dll_path)
        self._init_net_objects()
        self.initialized = False
        
        # Template directory for drive-specific templates
        self.template_dir = os.path.join(self.base_dir, "GenerateMCD_Assets")
        
        # Initialize drive configuration manager
        self.drive_config_manager = DriveConfigManager(drive_config_path, self.base_dir)
    
    def _setup_dll_paths(self, custom_dll_path):
        """Setup paths to required DLLs"""
        # Config manager path
        self.config_manager_path = os.path.join(
            self.base_dir, "GenerateMCD_Assets", 
            "System.Configuration.ConfigurationManager.8.0.0", 
            "lib", "netstandard2.0"
        )
        if not os.path.exists(self.config_manager_path):
            raise FileNotFoundError(f"ConfigurationManager path not found: {self.config_manager_path}")
        
        # Automation1 DLL path
        if custom_dll_path:
            self.aerotech_dll_path = custom_dll_path
        else:
            self.aerotech_dll_path = self._find_latest_automation1_path()
    
    def _find_latest_automation1_path(self):
        """Automatically find the latest Automation1 version"""
        automation1_root = r"C:\Program Files (x86)\Aerotech\Controller Version Selector\Bin\Automation1"
        latest_version = None
        
        if os.path.exists(automation1_root):
            version_folders = [
                name for name in os.listdir(automation1_root)
                if os.path.isdir(os.path.join(automation1_root, name)) and name[0].isdigit()
            ]
            if version_folders:
                try:
                    from packaging.version import Version
                    version_folders.sort(key=Version, reverse=True)
                except ImportError:
                    def version_tuple(v):
                        return tuple(int(x) for x in v.split('.') if x.isdigit())
                    version_folders.sort(key=version_tuple, reverse=True)
                latest_version = version_folders[0]
        
        if not latest_version:
            message = "Automation1 2.11 or newer required. Please install."
            try:
                messagebox.showwarning("Automation1 Not Found", message)
            except Exception:
                print("Warning: " + message)
            return None
        
        dll_path = os.path.join(automation1_root, latest_version, "release", "Bin")
        if not os.path.exists(dll_path):
            raise FileNotFoundError(f"Aerotech DLL path not found: {dll_path}")
        return dll_path
    
    def _init_net_objects(self):
        """Initialize .NET object references"""
        self.McdFormatConverter = None
        self.MachineControllerDefinition = None
        self.JObject = None
        
        # Template paths
        self.template_path = os.path.join(self.base_dir, "GenerateMCD_Assets", "MS_Template.json")
        self.working_json_path = os.path.join(os.getcwd(), "GenerateMCD_Assets", "WorkingTemplate.json")
    
    def initialize(self):
        """Load .NET assemblies and initialize types"""
        if self.initialized:
            print("MCD Processor already initialized.")
            return
        
        if not self.aerotech_dll_path:
            raise RuntimeError("No valid Automation1 installation found")
        
        os.environ["PATH"] = self.aerotech_dll_path + ";" + os.environ["PATH"]
        os.add_dll_directory(self.aerotech_dll_path)
        
        try:
            # Load assemblies
            clr.AddReference(os.path.join(self.aerotech_dll_path, "Newtonsoft.Json.dll"))
            clr.AddReference(os.path.join(self.config_manager_path, "System.Configuration.ConfigurationManager.dll"))
            clr.AddReference(os.path.join(self.aerotech_dll_path, "Aerotech.Automation1.Applications.Core.dll"))
            clr.AddReference(os.path.join(self.aerotech_dll_path, "Aerotech.Automation1.Applications.Interfaces.dll"))
            clr.AddReference(os.path.join(self.aerotech_dll_path, "Aerotech.Automation1.Applications.Shared.dll"))
            clr.AddReference(os.path.join(self.aerotech_dll_path, "Aerotech.Automation1.DotNetInternal.dll"))
            clr.AddReference(os.path.join(self.aerotech_dll_path, "Aerotech.Automation1.Applications.Wpf.dll"))

            # Get types
            import Newtonsoft.Json.Linq
            self.JObject = Newtonsoft.Json.Linq.JObject

            type_name1 = "Aerotech.Automation1.Applications.Wpf.McdFormatConverter, Aerotech.Automation1.Applications.Wpf"
            type_name2 = "Aerotech.Automation1.DotNetInternal.MachineControllerDefinition, Aerotech.Automation1.DotNetInternal"
            
            self.McdFormatConverter = System.Type.GetType(type_name1)
            self.MachineControllerDefinition = System.Type.GetType(type_name2)

            if self.McdFormatConverter is None or self.MachineControllerDefinition is None:
                raise TypeError("Could not load required .NET types")
            
            self.initialized = True

        except Exception as e:
            self.initialized = False
            raise RuntimeError(f"Failed to initialize MCD processor: {e}")
    
    def _check_initialized(self):
        """Ensure processor is initialized"""
        if not self.initialized:
            raise RuntimeError("MCD processor not initialized. Call initialize() first.")
    
    def convert_specs_to_mcd(self, specs_dict=None, electrical_dict=None, stage_type=None, axis=None, drive_type=None):
        """
        Convert specifications to MCD object using drive-specific templates with separated configs
        
        Args:
            specs_dict (dict, optional): Mechanical configuration options ONLY
                Format: {"Travel": "-025", "Feedback": "-E1", "Cable Management": "-CMS2"}
                → Goes to: MechanicalProducts[0].ConfiguredOptions
                
            electrical_dict (dict, optional): Electrical configuration options ONLY  
                Format: {"Bus Voltage": "80", "Current": "-20A"}
                → Goes to: ElectricalProducts[0].ConfiguredOptions
                
            stage_type (str, optional): Stage model name (e.g., "ANT95L")
                → MechanicalProducts[0].Name and DisplayName
                → InterconnectedAxes[0].MechanicalAxis.DisplayName
                
            axis (str, optional): Axis identifier (e.g., "ST01")
                → InterconnectedAxes[0].Name
                
            drive_type (str, optional): Drive model name (e.g., "iXA4", "XC4e", "XR3")
                - Uses {drive_type}_Template.json (errors if not found)
                - Drive naming rules applied to InterconnectedAxes[0].ElectricalAxis.DisplayName
        
        Clean Separation:
            - specs_dict: ONLY mechanical stage options
            - electrical_dict: ONLY electrical drive options
            - No mixing of mechanical and electrical configurations
        
        Returns:
            tuple: (mcd_obj, warnings)
            
        Raises:
            FileNotFoundError: If drive_type template doesn't exist
            ValueError: If dictionary formats are invalid
            KeyError: If template structure is invalid
        """
        self._check_initialized()
        
        # Validate inputs separately
        self._validate_mechanical_specs(specs_dict)
        self._validate_electrical_specs(electrical_dict)
        if drive_type:
            self._validate_drive_type(drive_type)
        
        # Update JSON config with separated configurations
        self._update_json_config(specs_dict, electrical_dict, stage_type, axis, drive_type)
        
        with open(self.working_json_path, "r", encoding="utf-8") as f:
            json_str = f.read()
        
        jobject = self.JObject.Parse(json_str)
        warnings = List[String]()

        convert_method = self.McdFormatConverter.GetMethod("ConvertToMcd")
        mcd_obj = convert_method.Invoke(None, [jobject, warnings])
        
        return mcd_obj, list(warnings)
    
    def calculate_mcd_parameters(self, mcd_obj):
        """Calculate parameters for an MCD object"""
        self._check_initialized()
        
        warnings = List[String]()
        calculate_method = self.McdFormatConverter.GetMethod("CalculateParameters")
        calculated_mcd = calculate_method.Invoke(None, [mcd_obj, warnings])
        
        return calculated_mcd, list(warnings)
    
    def read_mcd_file(self, mcd_path):
        """Read MCD file from disk"""
        self._check_initialized()
        
        if not os.path.exists(mcd_path):
            raise FileNotFoundError(f"MCD file not found: {mcd_path}")
        
        read_from_file = self.MachineControllerDefinition.GetMethod("ReadFromFile")
        mcd = read_from_file.Invoke(None, [mcd_path])
        
        # Version check
        version = mcd.SoftwareVersion
        if not self._is_version_supported(str(version)):
            raise RuntimeError(f"Unsupported Automation1 version: {version}. Requires 2.11 or newer.")
        
        return mcd
    
    def extract_parameters_from_mcd(self, mcd_obj):
        """Extract servo and feedforward parameters from MCD object"""
        try:
            # Get ConfigurationFiles
            dotnet_type = mcd_obj.GetType()
            config_files_prop = dotnet_type.GetProperty("ConfigurationFiles")
            config_files = config_files_prop.GetValue(mcd_obj, None)

            if config_files is None:
                return None, None

            # Find Parameters entry
            parameters_filedata = None
            for item in config_files:
                key_str = str(getattr(item, "Key", None))
                if key_str == "Parameters":
                    parameters_filedata = getattr(item, "Value", None)
                    break

            if parameters_filedata is None:
                return None, None

            # Extract content
            content_prop = parameters_filedata.GetType().GetProperty("Content")
            content_bytes = content_prop.GetValue(parameters_filedata, None)

            if content_bytes is None:
                return None, None

            # Convert and parse XML
            py_bytes = bytes(bytearray(content_bytes))
            xml_text = py_bytes.decode('utf-8')
            
            servo_params = self._extract_servo_parameters_from_xml(xml_text)
            feedforward_params = self._extract_feedforward_parameters_from_xml(xml_text)
            
            return servo_params, feedforward_params

        except Exception as e:
            print(f"Error extracting parameters: {e}")
            return None, None
    
    def convert_mcd_to_json(self, mcd_path, output_json_path):
        """Convert MCD file to JSON"""
        self._check_initialized()
        
        mcd_obj = self.read_mcd_file(mcd_path)
        
        warnings = List[String]()
        convert_method = self.McdFormatConverter.GetMethod("ConvertToJson")
        json_obj = convert_method.Invoke(None, [mcd_obj, warnings])

        with open(output_json_path, 'w', encoding='utf-8') as f:
            f.write(json_obj.ToString())

        return list(warnings)
    
    def _update_json_config(self, specs_dict, electrical_dict, stage_type=None, axis=None, drive_type=None):
        """
        Update JSON configuration template with separated mechanical and electrical configs
        
        Clean Process:
        1. Load appropriate template file (drive-specific or default)
        2. Update MechanicalProducts with specs_dict (no extraction needed)
        3. Update ElectricalProducts with electrical_dict (direct application)  
        4. Update InterconnectedAxes with axis and drive display naming
        5. Save to working template file
        
        Args:
            specs_dict (dict): Mechanical configuration options only
            electrical_dict (dict): Electrical configuration options only
            stage_type (str): Stage model name
            axis (str): Axis identifier  
            drive_type (str): Drive model name for template selection
        """
        # 1. Load appropriate template file
        template_file = self._get_template_file(drive_type)
        
        with open(template_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 2. Update MechanicalProducts (simple and clean - no extraction)
        mech_products = data.get("MechanicalProducts")
        if not mech_products:
            raise KeyError(f"MechanicalProducts not found in template: {template_file}")
        
        mech_product = mech_products[0]
        
        # Update mechanical configuration options directly
        if specs_dict:
            mech_product.setdefault("ConfiguredOptions", {}).update(specs_dict)
        
        # Update stage information
        if stage_type:
            mech_product["Name"] = stage_type
            mech_product["DisplayName"] = stage_type

        # 3. Update ElectricalProducts (simple and clean - direct application)
        electrical_products = data.get("ElectricalProducts")
        if electrical_products:
            elec_product = electrical_products[0]
            
            # Set ElectricalProducts Name and DisplayName to drive_type for multi-axis drives
            if drive_type and drive_type in ['XA4', 'iXA4', 'XR3', 'iXR3']:
                elec_product["Name"] = drive_type
                elec_product["DisplayName"] = drive_type
            
            # Apply electrical configurations directly
            if electrical_dict:
                elec_config_options = elec_product.setdefault("ConfiguredOptions", {})
                
                # Process electrical configurations with proper formatting
                for key, value in electrical_dict.items():
                    # Skip empty values
                    if not value or str(value).strip() == '':
                        continue
                        
                    if key.lower() in ("bus voltage", "bus_voltage"):
                        # Ensure bus voltage has "V" suffix
                        bus_str = str(value)
                        if not bus_str.lower().endswith('v'):
                            bus_str += 'V'
                        elec_config_options["Bus Voltage"] = bus_str
                    else:
                        # Other electrical options go through as-is
                        elec_config_options[key] = value

        # 4. Update InterconnectedAxes with drive-specific naming
        interconnected_axes = data.get("InterconnectedAxes")
        if interconnected_axes:
            inter_axis = interconnected_axes[0]
            
            # Set axis name
            if axis:
                inter_axis["Name"] = axis
                
            # Set mechanical axis display name  
            if stage_type and "MechanicalAxis" in inter_axis:
                inter_axis["MechanicalAxis"]["DisplayName"] = stage_type

            # Update electrical axis display name using config display_name for multi-axis drives
            if drive_type and "ElectricalAxis" in inter_axis:
                if drive_type in ['XA4', 'iXA4', 'XR3', 'iXR3']:
                    # Use display_name from drive config for multi-axis drives
                    drive_config = self.drive_config_manager.get_drive_config(drive_type)
                    if drive_config:
                        display_name = drive_config.get('display_name', drive_type)
                        inter_axis["ElectricalAxis"]["DisplayName"] = display_name
                    else:
                        inter_axis["ElectricalAxis"]["DisplayName"] = drive_type
                else:
                    # For other drives, use the formatted drive name
                    electrical_products = data.get("ElectricalProducts")
                    if electrical_products:
                        drive_name = electrical_products[0]["Name"]
                        inter_axis["ElectricalAxis"]["DisplayName"] = self._format_drive_display_name(drive_name)

        # 5. Save updated config
        os.makedirs(os.path.dirname(self.working_json_path), exist_ok=True)
        with open(self.working_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        
        # DEBUG: Save populated template with clear filename for troubleshooting
        debug_filename = f"DEBUG_populated_template_{drive_type or 'unknown'}_{stage_type or 'unknown'}.json"
        debug_path = os.path.join(os.path.dirname(self.working_json_path), debug_filename)
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"🔍 DEBUG: Populated template saved to: {debug_path}")

    def _get_template_file(self, drive_type):
        """
        Get template file path based on drive type with strict validation
        
        Args:
            drive_type (str or None): Drive model name
            
        Returns:
            str: Path to template file
            
        Raises:
            FileNotFoundError: If drive_type specified but template doesn't exist
        """
        if drive_type:
            drive_template = os.path.join(self.template_dir, f"{drive_type}_Template.json")
            
            if os.path.exists(drive_template):
                print(f"Using drive-specific template: {drive_type}_Template.json")
                return drive_template
            else:
                # STRICT: Error if template doesn't exist (no silent fallback)
                available_drives = self.get_available_drive_types()
                raise FileNotFoundError(
                    f"Template file not found: {drive_type}_Template.json\n"
                    f"Available drive types: {', '.join(available_drives)}\n"
                    f"Template directory: {self.template_dir}"
                )
    
        # Use default template when no drive_type specified
        return self.template_path

    def _format_drive_display_name(self, drive_name):
        """
        Format drive display name according to Aerotech naming conventions
        
        Args:
            drive_name (str): Base drive name from template
            
        Returns:
            str: Properly formatted display name
            
        Rules based on template analysis:
        - XA drives (multi-axis servo drives): Add "Axis 1" → "iXA4 Axis 1"
        - XR racks (multi-axis racks): Add "Axis 1" → "XR3 Axis 1"  
        - XC drives (single-axis drives): No suffix → "XC4e"
        """
        if not drive_name:
            return ""
        
        drive_upper = drive_name.upper()
        
        # Multi-axis drives and racks get "Axis 1" suffix
        if "XA" in drive_upper or "XR" in drive_upper:
            return f"{drive_name} Axis 1"
        
        # Single-axis drives (XC series) don't get suffix
        return drive_name
    
    def _validate_mechanical_specs(self, specs_dict):
        """
        Validate mechanical specifications dictionary
        
        Args:
            specs_dict (dict or None): Mechanical configuration options
            
        Raises:
            ValueError: If specs_dict format is invalid or contains electrical options
        """
        if specs_dict is None:
            return  # Allow None
            
        if not isinstance(specs_dict, dict):
            raise ValueError("specs_dict must be a dictionary or None")
        
        # Check for electrical options that shouldn't be in specs_dict
        electrical_keys = [
            "bus voltage", "bus_voltage", "bus", 
            "current", "multiplier", "motor supply voltage",
            "axes", "expansion board"
        ]
        
        for key in specs_dict:
            if key.lower() in electrical_keys:
                raise ValueError(
                    f"Electrical option '{key}' found in specs_dict. "
                    f"Please move to electrical_dict. "
                    f"specs_dict should contain only mechanical stage options."
                )
    
    def _validate_electrical_specs(self, electrical_dict):
        """
        Validate electrical specifications dictionary
        
        Args:
            electrical_dict (dict or None): Electrical configuration options
            
        Raises:
            ValueError: If electrical_dict format is invalid
        """
        if electrical_dict is None:
            return  # Allow None
            
        if not isinstance(electrical_dict, dict):
            raise ValueError("electrical_dict must be a dictionary or None")
        
        # Validate bus voltage format if present
        for key, value in electrical_dict.items():
            if key.lower() in ("bus voltage", "bus_voltage"):
                bus_voltage = str(value).replace("V", "").replace("v", "")
                if not bus_voltage.isdigit():
                    raise ValueError(f"Bus voltage must be numeric (with optional 'V' suffix), got: {value}")

    def _validate_drive_type(self, drive_type):
        """
        Validate drive type and check if template exists
        
        Args:
            drive_type (str): Drive model name
            
        Raises:
            ValueError: If drive_type format is invalid
            FileNotFoundError: If template doesn't exist
        """
        if not isinstance(drive_type, str) or not drive_type.strip():
            raise ValueError("drive_type must be a non-empty string")
        
        # Template existence check will be done in _get_template_file
        # This is just for format validation
        
    def get_available_drive_types(self):
        """
        Auto-scan GenerateMCD_Assets folder for available drive templates
        
        Returns:
            list: Available drive types sorted alphabetically
            
        Examples: ["iXA4", "iXC4e", "XC4", "XR3"]
        """
        drive_types = []
        
        if not os.path.exists(self.template_dir):
            return drive_types
            
        try:
            for filename in os.listdir(self.template_dir):
                if filename.endswith("_Template.json") and filename != "MS_Template.json":
                    drive_type = filename.replace("_Template.json", "")
                    drive_types.append(drive_type)
        except OSError as e:
            print(f"Warning: Could not scan template directory {self.template_dir}: {e}")
            
        return sorted(drive_types)
    
    def get_drive_info(self, drive_type):
        """
        Get information about a specific drive type
        
        Args:
            drive_type (str): Drive model name
            
        Returns:
            dict: Drive information including:
                - is_multi_axis (bool): Whether drive supports multiple axes
                - controller_type (str): "DriveBased" or "PcBased" 
                - requires_axis_suffix (bool): Whether display name needs "Axis 1"
                - template_exists (bool): Whether template file exists
                - template_path (str): Full path to template file
        """
        drive_info = {
            'is_multi_axis': False,
            'controller_type': 'DriveBased', 
            'requires_axis_suffix': False,
            'template_exists': False,
            'template_path': None
        }
        
        if not drive_type:
            return drive_info
            
        upper_drive = drive_type.upper()
        
        # Determine drive characteristics based on naming patterns
        if "XA" in upper_drive or "XR" in upper_drive:
            drive_info['is_multi_axis'] = True
            drive_info['requires_axis_suffix'] = True
        
        if "XR" in upper_drive:
            drive_info['controller_type'] = 'PcBased'
        
        # Check template existence
        template_path = os.path.join(self.template_dir, f"{drive_type}_Template.json")
        drive_info['template_exists'] = os.path.exists(template_path)
        if drive_info['template_exists']:
            drive_info['template_path'] = template_path
        
        return drive_info

    def get_available_drive_types_with_info(self):
        """Get available drive types with detailed configuration information"""
        return self.drive_config_manager.get_available_drive_types_with_info()

    def get_drive_menu_data(self, drive_type):
        """Get menu data for UI generation for a specific drive type"""
        return self.drive_config_manager.generate_ui_menu_data(drive_type)
    
    def get_default_electrical_config(self, drive_type):
        """Get default electrical configuration for a drive type"""
        return self.drive_config_manager.get_default_electrical_dict(drive_type)
    
    def get_drive_electrical_options(self, drive_type):
        """Get electrical options available for a drive type"""
        return self.drive_config_manager.get_electrical_options(drive_type)
    
    def get_drive_option_choices(self, drive_type, option_name):
        """Get available choices for a specific electrical option"""
        return self.drive_config_manager.get_option_choices(drive_type, option_name)
    
    def validate_electrical_configuration(self, drive_type, electrical_dict):
        """Validate electrical configuration against drive config"""
        return self.drive_config_manager.validate_electrical_dict(drive_type, electrical_dict)

    def validate_configuration_setup(self, specs_dict, electrical_dict, drive_type):
        """
        Validate complete configuration setup with separated dictionaries using drive config
        
        Args:
            specs_dict (dict): Mechanical configuration options
            electrical_dict (dict): Electrical configuration options  
            drive_type (str): Drive model name
            
        Returns:
            dict: Validation results with detailed feedback
        """
        results = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'drive_info': {},
            'mechanical_validation': {'valid': True, 'errors': []},
            'electrical_validation': {'valid': True, 'errors': []}
        }
        
        try:
            # Validate mechanical specs
            try:
                self._validate_mechanical_specs(specs_dict)
                results['mechanical_validation']['valid'] = True
            except ValueError as e:
                results['mechanical_validation']['valid'] = False
                results['mechanical_validation']['errors'].append(str(e))
                results['valid'] = False
            
            # Validate electrical specs using drive configuration
            if drive_type and electrical_dict:
                config_validation = self.drive_config_manager.validate_electrical_dict(drive_type, electrical_dict)
                results['electrical_validation'] = {
                    'valid': config_validation['valid'],
                    'errors': config_validation['errors'],
                    'warnings': config_validation.get('warnings', []),
                    'suggestions': config_validation.get('suggestions', {})
                }
                if not config_validation['valid']:
                    results['valid'] = False
                    results['errors'].extend(config_validation['errors'])
                if config_validation.get('warnings'):
                    results['warnings'].extend(config_validation['warnings'])
            else:
                # Fallback to basic validation
                try:
                    self._validate_electrical_specs(electrical_dict)
                    results['electrical_validation']['valid'] = True
                except ValueError as e:
                    results['electrical_validation']['valid'] = False
                    results['electrical_validation']['errors'].append(str(e))
                    results['valid'] = False
            
            # Validate drive type and get drive info
            if drive_type:
                self._validate_drive_type(drive_type)
                drive_info = self.drive_config_manager.get_drive_info_detailed(drive_type)
                if drive_info:
                    results['drive_info'] = drive_info
                    if not drive_info['template_exists']:
                        available = self.drive_config_manager.get_available_drive_types()
                        results['errors'].append(f"Template not found for {drive_type}. Available: {', '.join(available)}")
                        results['valid'] = False
                else:
                    results['errors'].append(f"Unknown drive type: {drive_type}")
                    results['valid'] = False
            
        except Exception as e:
            results['errors'].append(str(e))
            results['valid'] = False
        
        return results
    
    def _is_version_supported(self, ver_str):
        """Check if Automation1 version is supported"""
        try:
            parts = ver_str.split('.')
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            return (major > 2) or (major == 2 and minor >= 11)
        except Exception:
            return False
    
    def _extract_servo_parameters_from_xml(self, xml_text):
        """Extract ServoLoop parameters from XML"""
        axis_servo_params = {}
        root = ET.fromstring(xml_text)
        for axis_elem in root.findall('.//Axes/Axis'):
            axis_index = axis_elem.attrib.get('Index')
            params = []
            for p in axis_elem.findall('P'):
                param_name = p.attrib.get('n', '')
                if param_name.startswith('ServoLoop'):
                    params.append({'name': param_name, 'value': p.text})
            if params:
                axis_servo_params[axis_index] = params
        return axis_servo_params

    def _extract_feedforward_parameters_from_xml(self, xml_text):
        """Extract Feedforward parameters from XML"""
        axis_feedforward_params = {}
        root = ET.fromstring(xml_text)
        for axis_elem in root.findall('.//Axes/Axis'):
            axis_index = axis_elem.attrib.get('Index')
            params = []
            for p in axis_elem.findall('P'):
                param_name = p.attrib.get('n', '')
                if param_name.startswith('Feedforward'):
                    params.append({'name': param_name, 'value': p.text})
            if params:
                axis_feedforward_params[axis_index] = params
        return axis_feedforward_params

# ============================================================================
# FILE MANAGER
# ============================================================================

class FileManager:
    """
    Handles all file operations - naming, saving, path management.
    Uses strategy pattern for different naming and output approaches.
    """
    
    def __init__(self, naming_strategy, output_strategy, overwrite_existing=True):
        """
        Initialize file manager with strategies
        
        Args:
            naming_strategy: Instance of NamingStrategy
            output_strategy: Instance of OutputStrategy  
            overwrite_existing: Whether to overwrite existing files
        """
        self.naming_strategy = naming_strategy
        self.output_strategy = output_strategy
        self.overwrite_existing = overwrite_existing
    
    def save_mcd_file(self, mcd_obj, file_type, stage_type, context=None):
        """
        Save MCD object to file
        
        Args:
            mcd_obj: .NET MCD object to save
            file_type: 'calculated', 'uncalculated', or 'recalculated'
            stage_type: Stage type name
            context: Additional context dict for naming
        
        Returns:
            str: Path where file was saved
        """
        # Generate filename
        filename = self.naming_strategy.generate_filename(file_type, stage_type, context)
        
        # Get output directory
        output_dir = self.output_strategy.get_output_directory(file_type)
        
        # Create directory if needed
        if self.output_strategy.should_create_directories():
            os.makedirs(output_dir, exist_ok=True)
        
        # Full path
        file_path = os.path.join(output_dir, filename)
        
        # Handle existing files
        final_path = self._handle_existing_file(file_path)
        
        # Save file
        mcd_obj.WriteToFile(final_path)
        
        return final_path
    
    def _handle_existing_file(self, file_path):
        """Handle existing file based on overwrite setting"""
        if not os.path.exists(file_path):
            return file_path
            
        if self.overwrite_existing:
            return file_path
            
        # Create versioned filename
        base, ext = os.path.splitext(file_path)
        counter = 1
        while os.path.exists(f"{base}_v{counter}{ext}"):
            counter += 1
        return f"{base}_v{counter}{ext}"

# ============================================================================
# WORKFLOW CONFIGURATIONS
# ============================================================================

class WorkflowConfigs:
    """Pre-configured setups for common workflows"""
    
    @staticmethod
    def checkout_automation(smart_string=None, output_dir=r"O:\CMP Check-out\Parameter Files\Automation1"):
        """Configuration for checkout automation workflow
        
        Args:
            smart_string: Smart string for naming (optional)
            output_dir: Directory for calculated MCD files (default: CMP checkout folder)
        """
        if smart_string:
            naming_strategy = SmartStringNamingStrategy(smart_string)
        else:
            naming_strategy = DefaultNamingStrategy(calculated_prefix="")
        output_strategy = SpecificDirectoryOutputStrategy(output_dir)
        return FileManager(naming_strategy, output_strategy, overwrite_existing=True)
    
    @staticmethod
    def parameter_extraction_only():
        """Configuration for parameter extraction (no file saving)"""
        naming_strategy = DefaultNamingStrategy()
        output_strategy = WorkingDirectoryOutputStrategy()
        return FileManager(naming_strategy, output_strategy)
    
    @staticmethod
    def development_workflow(output_dir=None):
        """Configuration for development/testing"""
        naming_strategy = DefaultNamingStrategy()
        output_strategy = SeparateDirectoriesOutputStrategy(
            calculated_dir=output_dir or os.path.join(os.getcwd(), "calculated"),
            uncalculated_dir=output_dir or os.path.join(os.getcwd(), "uncalculated")
        )
        return FileManager(naming_strategy, output_strategy, overwrite_existing=True)

# ============================================================================
# MAIN FACADE CLASS
# ============================================================================

class AerotechController:
    """
    Main facade class that orchestrates MCD processing and file management.
    Supports four main operations:
    1. Convert template JSON to MCD object (optionally save)
    2. Convert MCD file/object to JSON (always save) 
    3. Generate MCD with calculated parameters from specifications
    4. Recalculate existing MCD and extract servo/feedforward parameters
    """
    
    def __init__(self, 
                 processor=None, 
                 file_manager=None,
                 save_calculated=True,
                 save_uncalculated=True, 
                 save_recalculated=True):
        """
        Initialize controller with processor and file manager
        
        Args:
            processor: McdProcessor instance (created if None)
            file_manager: FileManager instance (default setup if None)
            save_calculated: Whether to save calculated MCD files
            save_uncalculated: Whether to save uncalculated MCD files  
            save_recalculated: Whether to save recalculated MCD files
        """
        self.processor = processor or McdProcessor()
        self.file_manager = file_manager or FileManager(
            DefaultNamingStrategy(), 
            WorkingDirectoryOutputStrategy()
        )
        
        self.save_settings = {
            'calculated': save_calculated,
            'uncalculated': save_uncalculated,
            'recalculated': save_recalculated
        }
    
    def initialize(self):
        """Initialize the MCD processor"""
        self.processor.initialize()
    
    # ========================================================================
    # FACTORY METHODS - Based on core functionality, not workflows
    # ========================================================================
    
    @classmethod
    def with_file_saving(cls, 
                        output_dir=None, 
                        naming_strategy=None,
                        separate_dirs=False,
                        overwrite=True):
        """
        Create controller that saves files to specified location
        
        Args:
            output_dir: Directory for output files (default: current working dir)
            naming_strategy: How to name files (default: standard prefixes)
            separate_dirs: Whether calculated/uncalculated go to separate subdirectories
            overwrite: Whether to overwrite existing files
        """
        processor = McdProcessor()
        
        # Default naming strategy
        if naming_strategy is None:
            naming_strategy = DefaultNamingStrategy()
        
        # Output strategy
        if separate_dirs and output_dir:
            output_strategy = SeparateDirectoriesOutputStrategy(
                calculated_dir=os.path.join(output_dir, "calculated"),
                uncalculated_dir=os.path.join(output_dir, "uncalculated")
            )
        elif output_dir:
            output_strategy = SeparateDirectoriesOutputStrategy(
                calculated_dir=output_dir,
                uncalculated_dir=output_dir
            )
        else:
            output_strategy = WorkingDirectoryOutputStrategy()
        
        file_manager = FileManager(naming_strategy, output_strategy, overwrite)
        
        return cls(processor=processor, file_manager=file_manager)
    
    @classmethod
    def without_file_saving(cls):
        """
        Create controller that works with objects in memory only
        Useful for parameter extraction, testing, or when you handle saving yourself
        """
        processor = McdProcessor()
        file_manager = FileManager(
            DefaultNamingStrategy(), 
            WorkingDirectoryOutputStrategy()
        )
        return cls(
            processor=processor,
            file_manager=file_manager,
            save_calculated=False,
            save_uncalculated=False,
            save_recalculated=False
        )
    
    @classmethod
    def with_smart_string_naming(cls, smart_string, output_dir=None, prefix=""):
        """
        Create controller that uses smart string for file naming
        
        Args:
            smart_string: Smart string to use as base filename
            output_dir: Where to save files (default: current working dir)
            prefix: Prefix to add before smart string (default: none)
        """
        processor = McdProcessor()
        
        # Smart string naming with optional prefix
        if prefix:
            # Create custom naming that adds prefix to smart string
            def custom_naming_func(file_type, stage_type, context):
                return f"{prefix}{smart_string}"
            naming_strategy = CustomNamingStrategy(custom_naming_func)
        else:
            naming_strategy = SmartStringNamingStrategy(smart_string)
        
        # Output strategy
        if output_dir:
            output_strategy = SpecificDirectoryOutputStrategy(output_dir)
        else:
            output_strategy = WorkingDirectoryOutputStrategy()
        
        file_manager = FileManager(naming_strategy, output_strategy, overwrite_existing=True)
        
        return cls(processor=processor, file_manager=file_manager)
    
    @classmethod  
    def with_default_config(cls):
        """
        Create controller with standard default configuration
        - Saves files to working directory
        - Uses standard naming (Calculated_, Uncalculated_, etc.)
        - Overwrites existing files
        """
        return cls()  # Uses default constructor
    
    @classmethod
    def for_specific_output_dir(cls, output_dir, naming_strategy=None):
        """
        Create controller that saves calculated files to a specific directory
        Uncalculated and recalculated files go to working directory
        
        Args:
            output_dir: Directory for calculated MCD files
            naming_strategy: How to name files (default: standard prefixes)
            
        This is useful for checkout-style workflows where you want calculated 
        files in a centralized location but don't need uncalculated files saved.
        """
        processor = McdProcessor()
        
        if naming_strategy is None:
            naming_strategy = DefaultNamingStrategy()
            
        output_strategy = SpecificDirectoryOutputStrategy(output_dir)
        file_manager = FileManager(naming_strategy, output_strategy, overwrite_existing=True)
        
        return cls(processor=processor, file_manager=file_manager)
    
    @classmethod
    def for_checkout_workflow(cls, smart_string=None, output_dir=r"O:\CMP Check-out\Parameter Files\Automation1"):
        """
        Create controller configured for checkout automation workflow
        
        Args:
            smart_string: Smart string for naming files (optional)
            output_dir: Directory for calculated MCD files (default: CMP checkout folder)
            
        This creates a controller that:
        - Uses smart string naming (if provided) or no prefix
        - Saves calculated files to specified directory
        - Doesn't save uncalculated files (configure separately if needed)
        - Overwrites existing files
        """
        processor = McdProcessor()
        file_manager = WorkflowConfigs.checkout_automation(smart_string, output_dir)
        
        return cls(
            processor=processor,
            file_manager=file_manager,
            save_calculated=True,
            save_uncalculated=False,  # Typical for checkout workflow
            save_recalculated=True
        )
    
    # ========================================================================
    # CORE OPERATION METHODS (The four main uses)
    # ========================================================================
    
    def json_to_mcd(self, specs_dict=None, electrical_dict=None, stage_type=None, axis=None, drive_type=None, save_file=None, auto_configure_gui=True):
        """
        Convert JSON template + specs to MCD object with separated configurations
        
        Args:
            specs_dict (dict, optional): Mechanical configuration options  
            electrical_dict (dict, optional): Electrical configuration options
            stage_type (str): Stage model name
            axis (str): Axis identifier
            drive_type (str): Drive model name for template selection
            save_file (bool): Override save setting
            auto_configure_gui (bool): Automatically show GUI if electrical_dict is missing/invalid
            
        Returns:
            tuple: (mcd_obj, warnings, file_path)
        """
        # Auto-configure electrical settings if missing or invalid
        if auto_configure_gui and drive_type and (not electrical_dict or not self._is_electrical_config_sufficient(electrical_dict, drive_type)):
            print(f"\n🔧 Drive configuration needed for {drive_type}...")
            
            # Try to get configuration via GUI
            auto_electrical_dict = self.create_electrical_config_gui(drive_type)
            
            if auto_electrical_dict:
                electrical_dict = auto_electrical_dict
                print("✅ Configuration obtained from GUI")
            else:
                print("❌ Configuration cancelled - proceeding with provided config")
                # Keep original electrical_dict (might be empty or partial)
        
        mcd_obj, warnings = self.processor.convert_specs_to_mcd(
            specs_dict, electrical_dict, stage_type, axis, drive_type
        )
        
        file_path = None
        should_save = save_file if save_file is not None else self.save_settings['uncalculated']
        
        if should_save:
            context = {'axis': axis, 'drive_type': drive_type}
            file_path = self.file_manager.save_mcd_file(
                mcd_obj, 'uncalculated', stage_type, context
            )
        
        return mcd_obj, warnings, file_path
    
    def mcd_to_json(self, mcd_path, output_json_path):
        """Convert MCD file to JSON file (always saves)"""
        return self.processor.convert_mcd_to_json(mcd_path, output_json_path)
    
    def calculate_parameters(self, specs_dict=None, electrical_dict=None, stage_type=None, axis=None, drive_type=None, save_calculated=None, save_uncalculated=None, auto_configure_gui=True):
        """
        Generate MCD with calculated parameters using separated mechanical/electrical configs
        
        Args:
            specs_dict (dict, optional): Mechanical configuration options ONLY
                Format: {"Travel": "-025", "Feedback": "-E1", "Cable Management": "-CMS2"}
                
            electrical_dict (dict, optional): Electrical configuration options ONLY
                Format: {"Bus Voltage": "80", "Current": "-20A"}
                
            stage_type (str): Stage model name (e.g., "ANT95L")
            axis (str): Axis identifier (e.g., "ST01") 
            drive_type (str): Drive model name (e.g., "iXA4", "XC4e", "XR3")
            save_calculated (bool): Override save setting for calculated MCD
            save_uncalculated (bool): Override save setting for uncalculated MCD
            auto_configure_gui (bool): Automatically show GUI if electrical_dict is missing/invalid
            
        Returns:
            tuple: (calculated_mcd, all_warnings, calculated_path)
            
        Raises:
            FileNotFoundError: If drive_type template doesn't exist
            ValueError: If specs_dict format is invalid
        """
        # Auto-configure electrical settings if missing or invalid
        if auto_configure_gui and drive_type and (not electrical_dict or not self._is_electrical_config_sufficient(electrical_dict, drive_type)):
            print(f"\n🔧 Drive configuration needed for {drive_type}...")
            
            # Try to get configuration via GUI
            auto_electrical_dict = self.create_electrical_config_gui(drive_type)
            
            if auto_electrical_dict:
                electrical_dict = auto_electrical_dict
                print("✅ Configuration obtained from GUI")
            else:
                print("❌ Configuration cancelled - proceeding with provided config")
                # Keep original electrical_dict (might be empty or partial)
        
        # Step 1: Convert specs to MCD with separated configurations
        mcd_obj, conversion_warnings = self.processor.convert_specs_to_mcd(
            specs_dict, electrical_dict, stage_type, axis, drive_type
        )
        
        # Step 2: Save uncalculated if requested
        uncalculated_path = None
        should_save_uncalc = save_uncalculated if save_uncalculated is not None else self.save_settings['uncalculated']
        if should_save_uncalc:
            context = {'axis': axis, 'drive_type': drive_type}
            uncalculated_path = self.file_manager.save_mcd_file(
                mcd_obj, 'uncalculated', stage_type, context
            )
        
        # Step 3: Calculate parameters
        calculated_mcd, calculation_warnings = self.processor.calculate_mcd_parameters(mcd_obj)
        
        # Step 4: Save calculated if requested
        calculated_path = None
        should_save_calc = save_calculated if save_calculated is not None else self.save_settings['calculated']
        if should_save_calc:
            context = {'axis': axis, 'drive_type': drive_type}
            calculated_path = self.file_manager.save_mcd_file(
                calculated_mcd, 'calculated', stage_type, context
            )
        
        all_warnings = conversion_warnings + calculation_warnings
        return calculated_mcd, all_warnings, calculated_path
    
    def recalculate_and_extract(self, mcd_path, save_recalculated=None):
        """
        Load existing MCD, recalculate parameters (fresh Machine Setup calculation), 
        and extract servo/feedforward parameters
        
        Args:
            mcd_path: Path to existing MCD file
            save_recalculated: Whether to save recalculated MCD (default: use constructor setting)
            
        Returns:
            tuple: (servo_params, feedforward_params, recalculated_mcd, file_path, warnings)
        """
        # Load and recalculate (this gives fresh calculated parameters)
        mcd_obj = self.processor.read_mcd_file(mcd_path)
        calculated_mcd, warnings = self.processor.calculate_mcd_parameters(mcd_obj)
        
        # Extract the freshly calculated parameters
        servo_params, feedforward_params = self.processor.extract_parameters_from_mcd(calculated_mcd)
        
        # Save if requested
        file_path = None
        should_save = save_recalculated if save_recalculated is not None else self.save_settings['recalculated']
        if should_save:
            file_path = self.file_manager.save_mcd_file(
                calculated_mcd, 'recalculated', 'Unknown', {'source_path': mcd_path}
            )
        
        return servo_params, feedforward_params, calculated_mcd, file_path, warnings
    
    # ========================================================================
    # BACKWARD COMPATIBILITY METHODS
    # ========================================================================
    
    def convert_to_mcd(self, specs_dict=None, stage_type=None, axis=None, workflow=None):
        """Backward compatibility - delegates to json_to_mcd
        
        Legacy method that automatically separates mixed specifications.
        For new code, use json_to_mcd with separated specs_dict and electrical_dict.
        """
        # Legacy support: try to separate mixed specifications
        mechanical_specs = None
        electrical_specs = None
        
        if specs_dict:
            mechanical_specs = dict(specs_dict)
            electrical_specs = {}
            
            # Extract electrical options for backward compatibility
            electrical_keys = ["Bus", "Bus Voltage", "bus voltage", "bus_voltage"]
            for key in list(mechanical_specs.keys()):
                if key in electrical_keys:
                    electrical_specs[key] = mechanical_specs.pop(key)
        
        mcd_obj, warnings, file_path = self.json_to_mcd(
            specs_dict=mechanical_specs, 
            electrical_dict=electrical_specs if electrical_specs else None,
            stage_type=stage_type, 
            axis=axis
        )
        return mcd_obj, file_path, warnings
    
    def calculate_from_current_mcd(self, mcd_path):
        """Backward compatibility - delegates to recalculate_and_extract"""
        servo_params, ff_params, calculated_mcd, file_path, warnings = self.recalculate_and_extract(mcd_path)
        return calculated_mcd, file_path, warnings
    
    def inspect_mcd_object(self, mcd_obj):
        """Extract parameters from MCD object"""
        return self.processor.extract_parameters_from_mcd(mcd_obj)
    
    def convert_to_json(self, mcd_path, output_json_path):
        """Convert MCD to JSON"""
        return self.mcd_to_json(mcd_path, output_json_path)
    
    # ========================================================================
    # CONFIGURATION METHODS
    # ========================================================================
    
    def configure_saving(self, calculated=None, uncalculated=None, recalculated=None):
        """Configure which file types to save"""
        if calculated is not None:
            self.save_settings['calculated'] = calculated
        if uncalculated is not None:
            self.save_settings['uncalculated'] = uncalculated
        if recalculated is not None:
            self.save_settings['recalculated'] = recalculated
    
    def get_processor(self):
        """Get direct access to MCD processor for advanced usage"""
        return self.processor
    
    def get_file_manager(self):
        """Get direct access to file manager for advanced usage"""
        return self.file_manager
    
    # ========================================================================
    # DRIVE CONFIGURATION METHODS
    # ========================================================================
    
    def get_available_drives_with_info(self):
        """Get available drive types with detailed configuration information"""
        return self.processor.get_available_drive_types_with_info()
    
    def get_drive_menu_data(self, drive_type):
        """Get menu data for UI generation for a specific drive type"""
        return self.processor.get_drive_menu_data(drive_type)
    
    def get_default_electrical_config(self, drive_type):
        """Get default electrical configuration for a drive type"""
        return self.processor.get_default_electrical_config(drive_type)
    
    def get_drive_electrical_options(self, drive_type):
        """Get all electrical options available for a drive type"""
        return self.processor.get_drive_electrical_options(drive_type)
    
    def get_drive_option_choices(self, drive_type, option_name):
        """Get available choices for a specific electrical option"""
        return self.processor.get_drive_option_choices(drive_type, option_name)
    
    def validate_electrical_configuration(self, drive_type, electrical_dict):
        """Validate electrical configuration against drive config rules"""
        return self.processor.validate_electrical_configuration(drive_type, electrical_dict)
    
    def create_electrical_config_interactively(self, drive_type):
        """Create electrical configuration interactively using drive config"""
        menu_data = self.get_drive_menu_data(drive_type)
        if not menu_data:
            print(f"❌ No configuration data found for drive type: {drive_type}")
            return None
        
        print(f"\n🔧 Configuring {menu_data['drive_info']['display_name']}")
        print(f"Description: {menu_data['drive_info']['description']}")
        print("-" * 60)
        
        electrical_dict = {}
        
        for option in menu_data['options']:
            print(f"\n{option['name']}:")
            print(f"  Description: {option['description']}")
            
            if option['required']:
                print(f"  Status: ⚠️ REQUIRED")
            else:
                print(f"  Status: Optional")
            
            if option['choices']:
                print(f"  Choices: {', '.join(option['choices'])}")
                print(f"  Default: {option['default'] or 'None'}")
                
                # For demo purposes, use defaults or first choice
                if option['required'] and not option['default']:
                    selected = option['choices'][0] if option['choices'] else ""
                else:
                    selected = option['default']
                
                if selected:
                    # Add suffix if specified
                    suffix = option.get('suffix', '')
                    if suffix and not selected.endswith(suffix):
                        selected += suffix
                    electrical_dict[option['name']] = selected
                    print(f"  ✅ Selected: {selected}")
            else:
                # Text input option
                if option['default']:
                    electrical_dict[option['name']] = option['default']
                    print(f"  ✅ Using default: {option['default']}")
        
        # Validate the final configuration
        validation = self.validate_electrical_configuration(drive_type, electrical_dict)
        if validation['valid']:
            print(f"\n✅ Configuration validated successfully!")
            return electrical_dict
        else:
            print(f"\n❌ Configuration validation failed:")
            for error in validation['errors']:
                print(f"  • {error}")
            return None
    
    def create_electrical_config_gui(self, drive_type=None):
        """Create electrical configuration using GUI window with dropdowns
        
        Args:
            drive_type (str, optional): Specific drive type to configure.
                                       If None, shows drive selection dialog first.
        
        Returns:
            dict: Electrical configuration dict if user completes configuration,
                 None if cancelled
        """
        try:
            # Import GUI module
            import tkinter as tk
            from tkinter import messagebox
            
            print("\n🖥️ Creating GUI configuration window...")
            print("⚠️ IMPORTANT: Look for a new window that will open!")
            print("   • Check your taskbar for a new window")
            print("   • Try Alt+Tab to find the window")
            print("   • Check other monitors if you have multiple displays")
            
            # Import the GUI class from the same directory
            import os
            import sys
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            
            # Add assets directory to path
            assets_dir = os.path.join(current_dir, "GenerateMCD_Assets")
            sys.path.insert(0, assets_dir)
            
            # Import the original GUI class
            from drive_config_gui import DriveConfigurationGUI
            
            # Create and show GUI
            config_gui = DriveConfigurationGUI(self, drive_type)
            result = config_gui.show()
            
            if result:
                print("✅ GUI configuration completed successfully!")
            else:
                print("❌ GUI Configuration cancelled by user")
                
            return result
            
        except ImportError as e:
            print(f"❌ GUI not available: {e}")
            print("💡 Falling back to CLI configuration...")
            return self.create_electrical_config_interactively(drive_type)
        except Exception as e:
            print(f"❌ GUI error: {e}")
            print("💡 Falling back to CLI configuration...")
            return self.create_electrical_config_interactively(drive_type)
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _is_electrical_config_sufficient(self, electrical_dict, drive_type):
        """
        Check if electrical configuration has enough information for drive type
        
        Args:
            electrical_dict (dict): Electrical configuration to check
            drive_type (str): Drive type to check against
            
        Returns:
            bool: True if config is sufficient, False if GUI needed
        """
        if not electrical_dict:
            return False
        
        try:
            # Use existing validation system
            validation = self.validate_electrical_configuration(drive_type, electrical_dict)
            
            # If validation passes, config is sufficient
            if validation.get('valid', False):
                return True
            
            # Check if it has at least some required options
            menu_data = self.get_drive_menu_data(drive_type)
            if not menu_data:
                return bool(electrical_dict)  # If no menu data, any config is sufficient
            
            # Count how many required options are present
            required_options = [opt for opt in menu_data['options'] if opt.get('required', False)]
            present_required = sum(1 for opt in required_options 
                                 if opt['name'] in electrical_dict and electrical_dict[opt['name']])
            
            # If at least half the required options are present, consider it sufficient
            return present_required >= len(required_options) * 0.5
            
        except Exception:
            # If validation fails, assume insufficient
            return False
    
    # ========================================================================
    # DEBUG & TROUBLESHOOTING METHODS
    # ========================================================================
    
    def debug_template_population(self, specs_dict=None, electrical_dict=None, stage_type=None, axis=None, drive_type=None):
        """
        Debug helper to show how the template gets populated without generating MCD
        
        Args:
            specs_dict, electrical_dict, stage_type, axis, drive_type: Same as calculate_parameters
            
        Returns:
            str: Path to debug JSON file
        """
        print(f"\n🔍 --- DEBUG: Template Population Analysis ---")
        print(f"Drive Type: {drive_type}")
        print(f"Stage Type: {stage_type}")
        print(f"Axis: {axis}")
        print(f"Mechanical Specs: {specs_dict}")
        print(f"Electrical Specs: {electrical_dict}")
        
        # Just populate the template (don't convert to MCD)
        self.processor._update_json_config(specs_dict, electrical_dict, stage_type, axis, drive_type)
        
        # Get the debug file path
        debug_filename = f"DEBUG_populated_template_{drive_type or 'unknown'}_{stage_type or 'unknown'}.json"
        debug_path = os.path.join(self.processor.template_dir, debug_filename)
        
        print(f"\n📋 Template Population Summary:")
        
        # Load and analyze the populated template
        import json
        try:
            with open(debug_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Show key sections
            if "MechanicalProducts" in data and data["MechanicalProducts"]:
                mech = data["MechanicalProducts"][0]
                print(f"   • MechanicalProducts[0].Name: {mech.get('Name', 'Not Set')}")
                print(f"   • MechanicalProducts[0].ConfiguredOptions: {mech.get('ConfiguredOptions', {})}")
            
            if "ElectricalProducts" in data and data["ElectricalProducts"]:
                elec = data["ElectricalProducts"][0]
                print(f"   • ElectricalProducts[0].Name: {elec.get('Name', 'Not Set')}")
                print(f"   • ElectricalProducts[0].DisplayName: {elec.get('DisplayName', 'Not Set')}")
                print(f"   • ElectricalProducts[0].ConfiguredOptions: {elec.get('ConfiguredOptions', {})}")
            
            if "InterconnectedAxes" in data and data["InterconnectedAxes"]:
                inter = data["InterconnectedAxes"][0]
                print(f"   • InterconnectedAxes[0].Name: {inter.get('Name', 'Not Set')}")
                if "MechanicalAxis" in inter:
                    print(f"   • InterconnectedAxes[0].MechanicalAxis.DisplayName: {inter['MechanicalAxis'].get('DisplayName', 'Not Set')}")
                if "ElectricalAxis" in inter:
                    print(f"   • InterconnectedAxes[0].ElectricalAxis.DisplayName: {inter['ElectricalAxis'].get('DisplayName', 'Not Set')}")
            
            print(f"\n💾 Full populated template saved to: {debug_path}")
            print(f"📖 Open this file to see exactly what gets passed to Aerotech's MCD converter")
            
        except Exception as e:
            print(f"❌ Error analyzing populated template: {e}")
        
        return debug_path
    
    # ========================================================================
    # UTILITY METHODS FOR DRIVE-SPECIFIC FUNCTIONALITY  
    # ========================================================================
    
    def get_available_drives(self):
        """Get list of available drive types from templates"""
        return self.processor.get_available_drive_types()
    
    def get_drive_info(self, drive_type):
        """Get information about a specific drive type"""
        return self.processor.get_drive_info(drive_type)
    
    def validate_configuration_setup(self, specs_dict, electrical_dict, drive_type):
        """
        Validate complete configuration setup with separated dictionaries
        
        Args:
            specs_dict (dict): Mechanical configuration options
            electrical_dict (dict): Electrical configuration options  
            drive_type (str): Drive model name
            
        Returns:
            dict: Validation results with detailed feedback
        """
        return self.processor.validate_configuration_setup(specs_dict, electrical_dict, drive_type)


if __name__ == "__main__":
    print("GenerateMCD v2.0 loaded with improved architecture and drive-specific templates.")
    print("Key Features: Separated mechanical/electrical configs, drive templates, validation")
    print()
    print("Usage Examples:")
    print("=" * 50)
    print()
    print("# Checkout automation with separated configurations:")
    print('specs_dict = {"Travel": "-025", "Feedback": "-E1", "Cable Management": "-CMS2"}')
    print('electrical_dict = {"Bus Voltage": "80", "Current": "-20A"}')
    print('mcd_processor = AerotechController.for_checkout_workflow("ANT95L-025-E1-UF", r"O:\\Output")')
    print("mcd_processor.initialize()")
    print("calculated_mcd, warnings, path = mcd_processor.calculate_parameters(")
    print("    specs_dict=specs_dict, electrical_dict=electrical_dict,")
    print("    stage_type='ANT95L', axis='ST01', drive_type='iXA4')")
    print()
    print("# Parameter extraction:")  
    print("mcd_processor = AerotechController.without_file_saving()")
    print("mcd_processor.initialize()")
    print("servo_params, ff_params, mcd_obj, _, warnings = mcd_processor.recalculate_and_extract('existing.mcd')")
    print()
    print("# Drive discovery:")
    print("available_drives = mcd_processor.get_available_drives()")
    print("print(f'Available drives: {available_drives}')")
    print("drive_info = mcd_processor.get_drive_info('iXA4')")
    print("print(f'Drive info: {drive_info}')")
