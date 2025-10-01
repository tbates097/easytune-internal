# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

- Project scope: Python-based internal tools for Automation1 controller tuning and system modeling. The repo includes a Tkinter-based EasyTune UI and a separate modeling tool originally built with PyQt Designer.
- Platform: Windows (PowerShell). Many scripts interact with connected hardware/controllers and write output to user Documents.

Rules
- Always activate the conda environment "tbates" before running scripts.
- Some scripts will connect to an Automation1 controller, move axes, modify controller configuration, or upload/download MCD files. Only run them when a controller is available and it’s safe to do so.
- Several scripts import modules from a shared network path: K:\10. Released Software\Shared Python Programs\production-2.1. Ensure that path is available on this machine or adjust sys.path accordingly.

Environment prerequisites
- Python 3.7+
- .NET 8.0 Runtime and .NET Desktop Runtime 8.0.x (as referenced in Readme.md)
- Automation1 software with the Python package automation1 available in the active environment
- For legacy/modeling UI work: pythonnet and clr_loader, and PyQt tools if editing the .ui layout (see Project Documentation.md)

Common commands (PowerShell)
- Activate environment
  ```powershell path=null start=null
  conda activate tbates
  ```

- Launch EasyTune UI (preferred)
  ```powershell path=null start=null
  python launch_easytune_ui.py
  ```
  Alternative direct start:
  ```powershell path=null start=null
  python EasyTuneUI.py
  ```

- Run the command-line EasyTune workflow (when needed)
  ```powershell path=null start=null
  python RunEasyTune.py
  ```

- Run the System Modeling Tool
  ```powershell path=null start=null
  python System_Modeling_Tool.py
  ```

- Frequency response generation test script (connects to controller and issues a Multisine FR)
  ```powershell path=null start=null
  python test_fr.py
  ```

- Data conversion utilities (uses shared a1_file_handler from K:\...)
  - Default (as written):
    ```powershell path=null start=null
    python test_a1_file_handler.py
    ```
  - Call a specific utility function without editing the file:
    ```powershell path=null start=null
    python -c "import test_a1_file_handler as t; t.main('dat_to_plt')"
    ```

Build, lint, and tests
- Build: There is no packaging/pyproject in this repo; scripts run directly. No build step is required.
- Lint: No repo-configured linter found. If ruff or flake8 are available in the environment, you can optionally run:
  ```powershell path=null start=null
  ruff check .
  ```
  or
  ```powershell path=null start=null
  flake8 .
  ```
- Tests: No formal pytest/unittest suite found. Use the provided scripts as ad-hoc tests:
  - Single “test” (script):
    ```powershell path=null start=null
    python test_fr.py
    ```
  - Run a specific function in a script:
    ```powershell path=null start=null
    python -c "import test_a1_file_handler as t; t.main('dat_to_plt')"
    ```

High-level architecture and flow
- Two primary applications
  - EasyTune UI (Tkinter):
    - Files: EasyTuneUI.py, launch_easytune_ui.py, RunEasyTune.py
    - Purpose: Provides a wizard-style GUI to configure and run the EasyTune process, manage controller connection, generate and analyze frequency responses, and apply shaped parameters.
    - Runtime behavior: Uses the automation1 Python API to connect to a controller (USB/Hyperwire), gather parameters, run FRs, and apply tuning results. Produces outputs (.fr, .log, .html) under C:\Users\<user>\Documents\Automation1\SO_<number>.
  - System Modeling Tool (PyQt origin):
    - Files: System_Modeling_Tool.py, pyqt_ui.py, and related modules documented in Project Documentation.md
    - Purpose: Parameter-based modeling of controller loops and plants, optionally overriding plants with imported FR files. Originally designed with PyQt Designer; pyqt_ui.py is the generated backbone.

- Core modules and integration
  - Modules/ directory
    - Easy_Tune_Module.py: Orchestrates the EasyTune algorithm on FR data, produces results including Gains, Filters, and Stability_Metrics, and exposes get_results().
    - EncoderTuning.py, Easy_Tune_Plotter.py, Plot_Module.py, Block_Explorer_Module.py: Support tuning workflow, visualization, and block/loop exploration.
  - FR and parameter application pipeline (representative flow from RunEasyTune.py)
    1) Connect to controller using automation1 (USB/Hyperwire)
    2) Generate frequency response files via runtime command execution
    3) Run Easy_Tune_Module on the FR file, analyze Stability_Metrics, and derive shaped parameters
    4) Optionally convert shaped filter definitions to biquad coefficients and apply to controller
    5) Persist artifacts (.fr, .html, logs) into the user’s Automation1 directory structure
  - a1_interface.py and .NET interop
    - The project uses pythonnet/clr_loader to access Automation1 DLLs and a custom .NET wrapper (“CustomWrapper”) for more complex interop (per Project Documentation.md). This enables importing/exporting Automation1 .fr files and reusing tuning algorithms.

- Modeling concepts (from Project Documentation.md)
  - Blocks vs. Loops
    - Block: Basic unit derived from Abstract_Block; defines transfer function and publicly exposed properties
    - Loop: Composition of Blocks, derived from Abstract_Loop; supports nested blocks and property exposure
  - Block Layout
    - Top-level loop is the Servo_Loop. The layout mirrors the user-facing structure (Servo Controller, Servo Plant → Current Loop → Amplifier/Motor plants, etc.) and is used to build views and compute FRDs from constituent elements.
  - Data structures
    - Block Layout with Data holds shaped/original layouts, control.FRD data, and Automation1 FrequencyResponseResult for metadata and export.

Important paths and side effects
- Many operations write to C:\Users\<user>\Documents\Automation1, creating subfolders (e.g., SO_<number>\Performance Analysis) and moving FR files there.
- RunEasyTune.py contains helpers that modify and repackage MCD files (ZIP containers) and can upload/download to a controller. Only execute when appropriate.
- Some imports reference K:\10. Released Software\Shared Python Programs\production-2.1; this must be reachable for scripts that use a1_file_handler and related utilities.

Notes from repository docs
- Readme.md: Describes the modeling tool’s purpose and features; prerequisites include .NET 8 runtime variants; Automation1 .fr files are compatible as of 2.10.
- README_UI.md: Details the EasyTune UI features, steps, and required Python dependencies (automation1, numpy, scipy, plotly, matplotlib if used). It also documents the wizard flow, output artifacts, and troubleshooting guidance.
- Project Documentation.md: Explains how PyQt Designer was used for the modeling UI, the block/loop/layout concepts, and .NET DLL usage and versioning approach.

If a WARP.md is updated in the future
- Consolidate any new run/lint/test commands added to the repo (e.g., if a pyproject.toml/tox/nox/pytest config is introduced).
- If the shared K:\ path changes, update the Rules and Environment sections accordingly.
