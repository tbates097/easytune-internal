# Summary
With this tool, you can model a real Automation1 controller, both at the servo loop and current loop level, to generate frequency responses that update to your changes in real-time. You can use this to quickly prototype the controller with a real plant to analyze the shaped and original response characteristics without having to run a response with a real setup (which can be hard to acquire, setup, or be time consuming).

Each block that make up the controller are created as parameter-based models with the same parameters that you can change in Automation1. Changing these parameters automatically update their corresponding frequency responses. And, for each plant (i.e., the servo plant, amplifier plant, and mechanical plant), you can optionally import Ansys generated frequency response files in place of their parameter-based models for a more accurate plant representation.

If you do not wish to create the entire model from scratch, you can import the entire servo or current loop from a real Automation1 frequency response file (.fr). This will import all of the controller parameters that generated the response as well as the open-loop response and then back-calculate the plant from that information. Once done, you can export the controller as either an entirely new frequency response or just the shaped configuration. Thanks to recent developments, parameters that you change in the tool can then be applied directly from a .fr file in Studio, so you don't have to manually copy and paste changes for the many parameters we have.

# Features
* Model the servo and current loop quickly.
* Support for importing and exporting Automation1 compatible .fr files.
* View the shaped and original frequency responses for all responses.
* Run EasyTune on the shaped controller.
* Display, overlap, and shape multiple Automation1 .fr files with a single controller.

# Setup and Installation
### Prerequisites
* The `production-2.0` conda environment.
* [.NET 8.0](https://dotnet.microsoft.com/en-us/download/dotnet/8.0)
* [.NET Desktop Runtime 8.0.15](https://dotnet.microsoft.com/en-us/download/dotnet/8.0)

### Installation
1. Ensure that the prerequisites above have been met.
2. With the `production-2.0` conda environment, run python.
   * For example, `python "System Modeling Tool.py"`

### Is My Frequency Response File Compatible with this Tool?
* Automation1 frequency response (.fr) files are compatible as of 2.10.
* ANSYS frequency response files are compatible as long as:
  * The file ends in ".txt" so that the file appears in the open file dialog.
  * The header row contains: Frequency (Hz)	Amplitude (mm)	Phase Angle (deg)	Real (mm)	Imaginary (mm)
  * Each row ends in a newline (\n) character.
  * Each column is separated by a tab (\t) character.
  * For an example, please see [Example ANSYS File.txt](/Example%20ANSYS%20File.txt).