# EasyTune UI - Graphical User Interface

## Overview

The EasyTune UI provides a modern, wizard-style graphical interface for the RunEasyTune.py motor optimization program. Instead of dealing with multiple command-line prompts, users can now configure and run the entire EasyTune process through an intuitive GUI.

## Features

- **Wizard-Style Interface**: Step-by-step guidance through the entire process
- **Connection Management**: Auto-detect or manually specify controller connection
- **Visual Configuration**: Point-and-click configuration for all parameters
- **Real-time Progress**: Live output display during tuning process
- **Configuration Summary**: Review all settings before starting
- **Error Handling**: Clear error messages and validation

## Installation & Requirements

### Prerequisites
- Python 3.7 or higher
- tkinter (usually included with Python)
- All dependencies from RunEasyTune.py:
  - automation1
  - numpy
  - scipy
  - plotly
  - matplotlib (if used)

### Files Required
- `EasyTuneUI.py` - Main UI application
- `RunEasyTune.py` - Core EasyTune functionality
- `launch_easytune_ui.py` - Launcher script
- All modules from the `Modules/` directory

## Usage

### Starting the UI

**Option 1: Using the launcher**
```bash
python launch_easytune_ui.py
```

**Option 2: Direct execution**
```bash
python EasyTuneUI.py
```

### Step-by-Step Process

#### Step 1: Controller Connection
- Select connection type (Auto-detect, USB, or Hyperwire)
- Click "Connect to Controller" 
- Verify available axes are displayed

#### Step 2: System Configuration
- Select which axes to enable during tuning
- Confirm MCD configuration handling
- Confirm calibration files are loaded

#### Step 3: Test Configuration
- Choose test type:
  - **Single Axis**: Test one axis individually
  - **Multi-Axis**: Test multiple axes (XY ganged + individual axes)
- Configure axis groups based on your selection

#### Step 4: Axis Parameters
- Enter max velocity and acceleration for each axis
- Values should be appropriate for your system capabilities
- Use engineering units (mm/s, deg/s, etc.)

#### Step 5: Execution & Progress
- Review configuration summary
- Click "Start EasyTune Process" to begin
- Monitor real-time progress in the output window
- Process will run automatically through all phases

## UI Components Explained

### Connection Types
- **Auto-detect**: Tries standard connection first, falls back to USB
- **USB**: Forces USB connection (for direct controller connection)
- **Hyperwire**: Forces Hyperwire connection (for networked systems)

### Test Types
- **Single Axis**: Optimizes one axis at a time
- **Multi-Axis**: 
  - XY Configuration: For ganged axes that move together
  - Other Axes: Individual axes tested separately

### Parameter Guidelines
- **Max Velocity**: Maximum safe velocity for the axis
- **Max Acceleration**: Maximum safe acceleration for the axis
- Values should be conservative but realistic for your application

## Process Flow

The UI automates the same process as the command-line version:

1. **Connection & Setup**
   - Connect to controller
   - Modify MCD configuration if needed
   - Setup file directories

2. **Encoder Tuning**
   - Automatically runs encoder tuning on all enabled axes

3. **Frequency Response Testing**
   - Initial FR at center position
   - Optimization using EasyTune algorithm
   - Multi-position verification (center + corners)
   - Parameter application

4. **Results Generation**
   - Interactive plots (HTML files)
   - Performance validation
   - Log files with detailed results

## Output Files

The UI creates the same output files as the command-line version:
- `.fr` files: Frequency response data
- `.log` files: Detailed optimization logs  
- `.html` files: Interactive plots
- Performance validation reports

All files are saved to a directory based on the SO number from the controller name.

## Troubleshooting

### Common Issues

**Connection Failed**
- Check controller power and communication cables
- Verify Automation1 software is installed
- Try different connection types

**Import Errors**
- Ensure all Python dependencies are installed
- Check that RunEasyTune.py is in the same directory
- Verify Modules/ directory is present

**Process Errors**
- Check that calibration files are properly loaded
- Verify axis names and parameters are correct
- Ensure sufficient travel range for testing

### Error Messages

The UI provides clear error messages for common issues:
- Connection problems
- Missing parameters
- Invalid values
- Process failures

## Differences from Command-Line Version

### Advantages of UI
- No need to remember command sequences
- Visual configuration with validation
- Real-time progress monitoring
- Configuration review before execution
- Better error handling and user feedback

### Limitations
- Slightly higher resource usage
- Requires GUI environment
- Some advanced features may need command-line access

## Technical Details

### Architecture
- **EasyTuneUI.py**: Main GUI application using tkinter
- **Wizard Pattern**: Step-by-step interface with validation
- **Threading**: Background processing to keep UI responsive
- **Queue-based Output**: Real-time display of process output
- **Modular Design**: Separates UI from core functionality

### Thread Safety
- Main UI runs on primary thread
- EasyTune process runs on background thread
- Output redirection uses thread-safe queue
- UI updates scheduled on main thread

## Support

For issues or questions:
1. Check this README for common solutions
2. Review error messages in the UI output window
3. Check log files for detailed error information
4. Refer to the original RunEasyTune.py documentation

## Version History

- v1.0: Initial release with full wizard interface
- Supports all features from RunEasyTune.py
- Modern tkinter-based UI with real-time progress 