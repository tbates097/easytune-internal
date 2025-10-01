# GenerateMCD v2.0 Usage Instructions

## Overview

GenerateMCD v2.0 provides a flexible, reusable architecture for working with Aerotech MCD files. It uses a strategy pattern design that separates concerns for better maintainability and reusability.

## Architecture Components

- **McdProcessor**: Handles core .NET DLL operations
- **FileManager**: Manages file operations, naming, and paths
- **AerotechController**: Main facade that orchestrates everything
- **Strategy Classes**: Different approaches for naming and output handling

## Four Main Use Cases

GenerateMCD supports four primary operations:

1. **Convert template JSON to MCD object** (optionally save)
2. **Convert MCD file to JSON** (always saves)
3. **Generate MCD with calculated parameters** from specifications
4. **Recalculate existing MCD and extract parameters**

## Quick Start Guide

### Important: Variable Naming Convention

⚠️ **NEVER use `controller` as a variable name** - this is reserved for actual Automation1 controller objects.

✅ **Use these instead:** `mcd_processor`, `mcd_handler`, `mcd_generator`

### Basic Usage Pattern

```python
from GenerateMCD_v2 import AerotechController

# 1. Create the processor
mcd_processor = AerotechController.with_default_config()

# 2. Initialize
mcd_processor.initialize()

# 3. Use the appropriate method for your needs
calculated_mcd, warnings, path = mcd_processor.calculate_parameters(specs_dict, stage_type, axis)
```

## Factory Methods - Choose Your Configuration

### 1. `with_default_config()`
**Use when:** You want standard behavior with minimal configuration

```python
mcd_processor = AerotechController.with_default_config()
```

**Behavior:**
- Saves files to current working directory
- Uses standard naming (`Calculated_`, `Uncalculated_`, etc.)
- Overwrites existing files
- Saves all file types

### 2. `with_file_saving(output_dir, ...)`
**Use when:** You want to control where files are saved

```python
mcd_processor = AerotechController.with_file_saving(
    output_dir=r"C:\MyMCDs",
    separate_dirs=True,  # Creates "calculated" and "uncalculated" subdirs
    overwrite=False      # Creates versioned files instead
)
```

**Parameters:**
- `output_dir`: Directory for output files
- `naming_strategy`: Custom naming strategy (optional)
- `separate_dirs`: Whether to use separate subdirectories
- `overwrite`: Whether to overwrite existing files

### 3. `with_smart_string_naming(smart_string, ...)`
**Use when:** You want files named using a smart string (like from barcode scans)

```python
mcd_processor = AerotechController.with_smart_string_naming(
    smart_string="ANT95L-025-E1-UF",
    output_dir=r"O:\CMP Check-out\Parameter Files\Automation1"
)
```

**Results in filename:** `ANT95L-025-E1-UF.mcd`

### 4. `without_file_saving()`
**Use when:** You only want to work with objects in memory

```python
mcd_processor = AerotechController.without_file_saving()
```

**Perfect for:** Parameter extraction, testing, or when you handle saving yourself

## Core Methods - The Four Main Operations

### Operation 1: Convert JSON Template to MCD

```python
mcd_processor = AerotechController.with_file_saving(output_dir=r"C:\Output")
mcd_processor.initialize()

mcd_obj, warnings, file_path = mcd_processor.json_to_mcd(
    specs_dict=my_specs,
    stage_type="ANT95L", 
    axis="ST01",
    save_file=True  # Optional override
)
```

### Operation 2: Convert MCD to JSON

```python
mcd_processor = AerotechController.with_default_config()
mcd_processor.initialize()

warnings = mcd_processor.mcd_to_json(
    mcd_path="input.mcd",
    output_json_path="output.json"
)
```

### Operation 3: Generate Calculated MCD from Specifications

```python
mcd_processor = AerotechController.with_smart_string_naming(
    smart_string="ANT95L-025-E1-UF",
    output_dir=r"O:\MyMCDs"
)
mcd_processor.initialize()

calculated_mcd, warnings, file_path = mcd_processor.calculate_parameters(
    specs_dict=my_specs,
    stage_type="ANT95L",
    axis="ST01",
    save_calculated=True,    # Optional override
    save_uncalculated=False  # Optional override
)
```

### Operation 4: Recalculate Existing MCD and Extract Parameters

```python
mcd_processor = AerotechController.without_file_saving()
mcd_processor.initialize()

servo_params, ff_params, mcd_obj, _, warnings = mcd_processor.recalculate_and_extract(
    mcd_path="existing.mcd"
)

# servo_params and ff_params are dictionaries with extracted parameters
print(f"Servo parameters: {servo_params}")
print(f"Feedforward parameters: {ff_params}")
```

## Real-World Examples

### Example 1: Checkout Automation Workflow

```python
def setup_checkout_mcd_processor(smart_string):
    """Set up MCD processor for checkout automation"""
    mcd_processor = AerotechController.with_smart_string_naming(
        smart_string=smart_string,
        output_dir=r"O:\CMP Check-out\Parameter Files\Automation1"
    )
    
    # Don't save uncalculated files for checkout
    mcd_processor.configure_saving(uncalculated=False)
    
    return mcd_processor

# Usage in checkout_test.py
smart_string = "ANT95L-025-E1-UF"  # From barcode scan
mcd_processor = setup_checkout_mcd_processor(smart_string)
mcd_processor.initialize()

for axis in test_axes:
    calculated_mcd, warnings, mcd_path = mcd_processor.calculate_parameters(
        specs_dict, stage_type, axis
    )
    print(f"Created MCD: {mcd_path}")
    # mcd_path will be: "O:\CMP Check-out\Parameter Files\Automation1\ANT95L-025-E1-UF.mcd"
```

### Example 2: Parameter Extraction for Tuning

```python
def extract_parameters_for_tuning(mcd_path):
    """Extract servo parameters from existing MCD for tuning analysis"""
    mcd_processor = AerotechController.without_file_saving()
    mcd_processor.initialize()
    
    try:
        servo_params, ff_params, _, _, warnings = mcd_processor.recalculate_and_extract(mcd_path)
        
        if warnings:
            print(f"Warnings: {warnings}")
            
        return servo_params, ff_params
        
    except Exception as e:
        print(f"Error extracting parameters: {e}")
        return None, None

# Usage in mcd_worker.py or similar
servo_params, ff_params = extract_parameters_for_tuning("test.mcd")
if servo_params:
    for axis, params in servo_params.items():
        print(f"Axis {axis} servo parameters:")
        for param in params:
            print(f"  {param['name']}: {param['value']}")
```

### Example 3: Development/Testing Workflow

```python
def setup_development_workflow():
    """Set up for development with organized file structure"""
    mcd_processor = AerotechController.with_file_saving(
        output_dir=r"C:\Development\MCDs",
        separate_dirs=True,  # Creates calculated/ and uncalculated/ subdirs
        overwrite=False      # Creates versioned files
    )
    
    return mcd_processor

# Usage
mcd_processor = setup_development_workflow()
mcd_processor.initialize()

# This creates files like:
# C:\Development\MCDs\calculated\Calculated_ANT95L.mcd
# C:\Development\MCDs\uncalculated\Uncalculated_ANT95L.mcd
calculated_mcd, warnings, path = mcd_processor.calculate_parameters(
    specs_dict, "ANT95L", "TestAxis"
)
```

## Configuration Options

### Saving Configuration

```python
# Configure which file types to save
mcd_processor.configure_saving(
    calculated=True,      # Save calculated MCDs
    uncalculated=False,   # Don't save uncalculated MCDs
    recalculated=True     # Save recalculated MCDs
)
```

### Advanced: Direct Component Access

```python
# Get direct access to components for advanced usage
processor = mcd_processor.get_processor()      # Access McdProcessor directly
file_manager = mcd_processor.get_file_manager()  # Access FileManager directly

# Use processor directly for fine-grained control
mcd_obj, warnings = processor.convert_specs_to_mcd(specs_dict, stage_type, axis)
calculated_mcd, calc_warnings = processor.calculate_mcd_parameters(mcd_obj)

# Use file_manager directly for custom saving
file_path = file_manager.save_mcd_file(calculated_mcd, 'calculated', stage_type)
```

## Custom Strategies (Advanced)

### Custom Naming Strategy

```python
from GenerateMCD_v2 import CustomNamingStrategy, FileManager, WorkingDirectoryOutputStrategy

def my_naming_function(file_type, stage_type, context):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stage_type}_{file_type}_{timestamp}"

naming_strategy = CustomNamingStrategy(my_naming_function)
output_strategy = WorkingDirectoryOutputStrategy()
file_manager = FileManager(naming_strategy, output_strategy)

mcd_processor = AerotechController(file_manager=file_manager)
```

## Error Handling

```python
try:
    mcd_processor = AerotechController.with_default_config()
    mcd_processor.initialize()
    
    calculated_mcd, warnings, path = mcd_processor.calculate_parameters(
        specs_dict, stage_type, axis
    )
    
    if warnings:
        print(f"Warnings encountered: {warnings}")
        
    print(f"Successfully created MCD: {path}")
    
except FileNotFoundError as e:
    print(f"Required files not found: {e}")
except RuntimeError as e:
    print(f"Runtime error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Backward Compatibility

GenerateMCD v2.0 maintains full backward compatibility. Old code will continue to work:

```python
# Old style (still works)
mcd_processor = AerotechController()
mcd_processor.initialize()
calculated_mcd, warnings, path = mcd_processor.calculate_parameters(specs_dict, stage_type, axis)

# Legacy methods still available
mcd_obj, path, warnings = mcd_processor.convert_to_mcd(specs_dict, stage_type, axis)
calculated_mcd, path, warnings = mcd_processor.calculate_from_current_mcd("existing.mcd")
servo_params, ff_params = mcd_processor.inspect_mcd_object(mcd_obj)
```

## Best Practices

1. **Always call `initialize()` before using the processor**
2. **Use descriptive variable names** (`mcd_processor`, not `controller`)
3. **Handle warnings appropriately** - they often contain important information
4. **Choose the right factory method** for your use case
5. **Use `without_file_saving()` for parameter extraction** to avoid unnecessary files
6. **Configure saving settings** to avoid creating unwanted files
7. **Use try/catch blocks** for robust error handling

## Migration from v1.0

If you're upgrading from the original GenerateMCD:

```python
# v1.0 style
from GenerateMCD import AerotechController
controller = AerotechController()  # BAD: conflicts with A1 controllers

# v2.0 style  
from GenerateMCD_v2 import AerotechController
mcd_processor = AerotechController.with_default_config()  # GOOD: clear naming
```

## Troubleshooting

### Common Issues

1. **"Controller has not been initialized"**
   - Solution: Call `mcd_processor.initialize()` before using

2. **"No valid Automation1 installation found"**
   - Solution: Install Automation1 2.11 or newer

3. **"MCD file not found"**
   - Solution: Verify file path exists and is accessible

4. **Files not being saved**
   - Solution: Check save settings with `configure_saving()`

### Debug Information

```python
# Check if processor is initialized
print(f"Initialized: {mcd_processor.processor.initialized}")

# Check save settings
print(f"Save settings: {mcd_processor.save_settings}")

# Access processor for debugging
processor = mcd_processor.get_processor()
print(f"DLL path: {processor.aerotech_dll_path}")
```

This architecture provides maximum flexibility while maintaining ease of use for common scenarios!
