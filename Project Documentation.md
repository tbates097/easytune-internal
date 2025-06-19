# Project Documentation
The purpose of this is to provide documentation regarding how the project is structured to help guide any further developments to the tool.

### Dependencies
* clr_loader 0.2.7.post0
* pythonnet 3.0.1

### PyQt Designer
* The initial gui for this project was developed using [PyQt Designer](https://www.pythonguis.com/installation/install-qt-designer-standalone/).
    * `pip install pyqt5-tools`
    * `pyqt5-tools designer`
* This generates two files: `pyqt.ui` and `pyqt_ui.py`. `pyqt.ui` is loaded into the designer while `pyqt_ui.py` is automatically generated when saving the layout sourced from `pyqt.ui`.
* `pyqt_ui.py` is used by the application to provide the application's backbone (which generally consists most of the gui seen), but there are some parts that are generated dynamically. For example, the block layout is generated based off of the model structure and the plot had to be generated with code since you can't add matplotlib plots in the designer.

### File Structure
* The main file `System Modeling Tool.py` handles the instantiation of the application where sub-modules are also instantiated.
* Files that end with `_Module` handle the front-end and back-end of their respective modules. For example, `Plot_Module.py` handles all plot functionality.
* Files that live under the `Resources` directory are used for styling, fonts, and making the application look nice.
* Files that live under the `Automation1 DLLs` directory contain a copy of the DLLs used by the modeling tool and the custom wrapper.
* Files that live under the `Automation1 Wrapper` directory implement the custom wrapper used by .NET to call into EasyTune or facilitate some .NET object interactions.

### Block vs. Loop vs. Block Layout vs. Block Layout with Data
* __Block__ - defines the properties that comprise each block and is derived from the `Abstract_Block` class:
  * They cannot contain nested blocks.
  * Only the properties listed under the block specific `_Properties` class are publicly exposed under its property table.
  * Each block defines how its transfer function is defined, so if you wish to update it, change the block.
* __Loop__ - defines the properties and blocks that comprise each loop and is derived from the `Abstract_Loop` class:
  * They can contain nested blocks. This are to be defined under the loop specific `_Blocks` class.
  * Only the properties listed under the block specific `_Properties` class are publicly exposed under its property table.
* __Block Layout__ - defines the top-most level loop that the tool supports as well as a user-facing translation of the entire loop structure.
  * Currently, the top-level loop is the `Servo_Loop`.
  * The user-facing layout represents exactly how the entire loop is structured and displayed in the block explorer. This is automatically generated based off of what loops and blocks are nested starting from the top-most loop. For example:
    * Servo Loop
      * Servo Controller
      * Servo Plant
        * Current Loop
            * Current Controller
            * Current Plant
                * Amplifier Plant
                * Amplifier Roll off Filter
                * Motor Plant
                * Current Low Pass Filter
        * Mechanical Plant
  * The loop and block dictionaries contain pointers to the loops and blocks that are in the block layout. This facilitates access to each block without having to repeatedly search through the block layout just to modify something.
* __Block Layout with Data__ - defines the main object that is consumed by the `Block_Layout_Module`. This contains the shaped and original versions of the block layout, both layouts' frequency response data (`control.FRD`), and the Automation1 `FrequencyResponseResult` class which can either be created from scratch or retrieved when loading from a file:
  * This is responsible for retrieving all loop and block FRDs and computing the correct responses using their individual frequency responses.
  * The `FrequencyResponseResult` class is included to provide additional metadata regarding what version of Automation1 this information was generated with and provide a structure for us to use when exporting the layout to an Automation1 .fr file.

# .NET DLLs
This tool taps into .NET Automation1 DLLs that we have already developed for Studio. The reason for this is so that we can reuse the tuning algorithms such as EasyTune as well as importing and exporting Automation1 .fr files. While most things in the DLLs can be directly accessed in Python (using `pythonnet`), some things like EasyTune interact with ADT's service scheme which require a little more effort to get operational. For things that are just slightly too complicated or janky to get working in Python alone (e.g., EasyTune or .NET enumerables), these were pushed off and integrated into a custom wrapper aptly named `CustomWrapper`.

These DLLs are located under the `Automation1 DLLs` directory and are referenced by both the Python tool (in `a1_interface.py`) and .NET custom wrapper. The current DLL version of Automation1 is defined by the [version_a1.txt](/Automation1%20DLLs/version_a1.txt).

# Maintenance
### Updating the System Modeling Tool
The version for the application is stored in `Version.txt` and is read into the application as-is to display the version string. The format for this string is as follows: `major.minor.patch.build`. While `build` is not really necessary, whenever this tool is updated, do not forget to increment at least one of the other numbers.

### Updating the DLLs
Because these DLLs can change, even between minor versions of Automation1, we must keep a copy of all of the DLLs in this repository for compatibility. Updating the DLLs is pretty simple:
1. In CVS, add the desired version of Automation1.
   * __IMPORTANT__: This must be an official release. Developer versions of Automation1 do not undergo extensive testing and validation unlike official versions.
2. Navigate to directory where these artifacts are stored. For example, in CVS for Automation1 2.10.0, this directory would be `C:\CVS\Automation1\2.10.0\release\Bin`.
3. Navigate to the sub-directory: `release/bin/`.
4. Copy __all__ and __only__ the Dlls from this folder into `Automation1 DLLs`.
   * The DLLs we are interested in also depend on the DLLs in this folder which is why we must copy over all of the other DLLs.
   * You must also copy out 
5. Update [version_a1.txt](/Automation1%20DLLs/version_a1.txt) with the official version of Automation1 for tracking in Git.
   * Tip: You can view the individual versions for each DLL in file explorer by right-clicking the columns' header bar where it says "Name", "Date Modified", etc. then clicking on > "More..." > "File Version".
6. Validate that the updated artifacts don't break:
   * The tool via developer testing.
   * The .NET `CustomWrapper` project by recompiling it to make sure that no errors were thrown.
7. Confirm in Git or SourceTree that:
   * No new DLLs were added, only replaced.
   * [version_a1.txt](/Automation1%20DLLs/version_a1.txt) was updated to reflect the new version of Automation1.
8. Update [version_project.txt](/version_project.txt) by either:
   1. Incrementing the minor version (default).
   2. Incrementing the major version if you deem that the update to Automation1 was significant enough to warrant a large change.
9. Commit these DLLs.
