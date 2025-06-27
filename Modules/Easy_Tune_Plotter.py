import os
import re
import time
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as font_manager
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.widgets import Cursor
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.offline as pyo
from datetime import datetime
import pandas as pd
from pathlib import Path
import json
import math

class EasyTunePlotter:
    """
    A plotting module for EasyTune that creates Bode plots and stability analysis plots
    similar to the existing UI but standalone for the RunEasyTune.py program
    """
    
    def __init__(self, output_dir=None):
        """
        Initialize the EasyTune plotter
        
        Args:
            output_dir: Directory to save plots (default: current directory)
        """
        self.output_dir = output_dir or os.getcwd()
        self.fr_files = []
        self.log_files = []
        self.stability_data = []
        
        # Plot styling constants
        self.CURSOR_COLOR = 'red'
        self.GRID_COLOR = '0.9'
        self.ORIGINAL_LINE_STYLE = 'dashed'
        self.SHAPED_LINE_STYLE = 'solid'
        
        # Set up matplotlib style
        self._setup_matplotlib_style()
        
    def _setup_matplotlib_style(self):
        """Set up consistent matplotlib styling"""
        plt.style.use('seaborn-v0_8')
        plt.rcParams.update({
            'font.size': 10,
            'axes.titlesize': 12,
            'axes.labelsize': 11,
            'xtick.labelsize': 9,
            'ytick.labelsize': 9,
            'legend.fontsize': 10,
            'figure.titlesize': 14,
            'grid.alpha': 0.3,
            'axes.grid': True
        })

    def load_fr_file(self, fr_filepath):
        """
        Load frequency response data from .fr file
        
        Args:
            fr_filepath: Path to .fr file
            
        Returns:
            dict: Frequency response data
        """
        try:
            # This would need to be implemented based on your .fr file format
            # For now, returning a placeholder structure
            fr_data = {
                'frequency': np.logspace(1, 4, 100),  # 10 Hz to 10 kHz
                'magnitude': np.zeros(100),  # Placeholder
                'phase': np.zeros(100),      # Placeholder
                'filename': os.path.basename(fr_filepath)
            }
            return fr_data
        except Exception as e:
            print(f"Error loading FR file {fr_filepath}: {e}")
            return None

    def parse_log_file(self, log_filepath):
        """
        Parse stability analysis data from log files

        Args:
            log_filepath: Path to log file

        Returns:
            dict: Parsed stability data
        """
        stability_data = {
            'filename': os.path.basename(log_filepath),
            'timestamp': None,
            'axis': None,
            'position': None,
            'phase_margin': None,
            'gain_margin': None,
            'sensitivity': None,
            'stability_passed': False
        }

        try:
            with open(log_filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract timestamp
            timestamp_match = re.search(r'📅 Timestamp: (.+)', content)
            if timestamp_match:
                stability_data['timestamp'] = timestamp_match.group(1)

            # Extract axis and position from filename
            filename = os.path.basename(log_filepath)
            axis_match = re.search(r'test-([A-Z])-', filename)
            position_match = re.search(r'-([A-Za-z\s]+)-(?:Verification)?\.log', filename)

            if axis_match:
                stability_data['axis'] = axis_match.group(1)
            if position_match:
                stability_data['position'] = position_match.group(1)

            # Extract phase margin from PHASE MARGIN ANALYSIS section
            phase_section = re.search(r'PHASE MARGIN ANALYSIS:(.*?)(?:\n[A-Z ]+ANALYSIS:|\Z)', content, re.DOTALL)
            if phase_section:
                phase_match = re.search(r'Current Value: ([\d.]+)° @ ([\d.]+) Hz', phase_section.group(1))
                if phase_match:
                    stability_data['phase_margin'] = {
                        'value': float(phase_match.group(1)),
                        'frequency': float(phase_match.group(2))
                    }

            # Extract gain margin from GAIN MARGIN ANALYSIS section
            gain_section = re.search(r'GAIN MARGIN ANALYSIS:(.*?)(?:\n[A-Z ]+ANALYSIS:|\Z)', content, re.DOTALL)
            if gain_section:
                gain_match = re.search(r'Current Value: ([\d.]+) dB @ ([\d.]+) Hz', gain_section.group(1))
                if gain_match:
                    stability_data['gain_margin'] = {
                        'value': float(gain_match.group(1)),
                        'frequency': float(gain_match.group(2))
                    }

            # Extract sensitivity from SENSITIVITY ANALYSIS section
            sensitivity_section = re.search(r'SENSITIVITY ANALYSIS:(.*?)(?:\n[A-Z ]+ANALYSIS:|\Z)', content, re.DOTALL)
            if sensitivity_section:
                sensitivity_match = re.search(r'Current Value: ([\d.]+) dB @ ([\d.]+) Hz', sensitivity_section.group(1))
                if sensitivity_match:
                    stability_data['sensitivity'] = {
                        'value': float(sensitivity_match.group(1)),
                        'frequency': float(sensitivity_match.group(2))
                    }

            # Check if analysis passed
            stability_data['stability_passed'] = '🎉 OVERALL ASSESSMENT: PASS' in content

        except Exception as e:
            print(f"Error parsing log file {log_filepath}: {e}")

        return stability_data

    def create_bode_plot(self, original_frd, shaped_frd=None, position=None):
        """Create a Bode plot from frequency response data"""
        title = f"Bode Plot for {position}"

        # Create figure with subplots
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            subplot_titles=('Magnitude', 'Phase'),
            vertical_spacing=0.1
        )
        
        # Get the string representation and parse the data
        frd_str = str(original_frd)
        lines = frd_str.split('\n')
        
        # Find where the data table starts (after "Freq [rad/s]  Response")
        data_start = 0
        for i, line in enumerate(lines):
            if "Freq [rad/s]  Response" in line:
                data_start = i + 2  # Skip the header and dashed line
                break
        
        # Get only the data lines
        data_lines = [line.strip() for line in lines[data_start:] if line.strip() and 'j' in line]
        
        # Extract frequency and response data
        freq_rad = []
        response = []
        for line in data_lines:
            parts = line.split()
            if len(parts) >= 3:  # Should have frequency and complex number
                freq_rad.append(float(parts[0]))
                real = float(parts[1])
                imag = float(parts[2].replace('j', ''))
                response.append(complex(real, imag))
        
        freq_rad = np.array(freq_rad)
        freq_hz = freq_rad / (2 * np.pi)  # Convert to Hz
        response = np.array(response)
        
        # Convert to magnitude and phase
        magnitude_db = 20 * np.log10(np.abs(response))
        phase_deg = np.angle(response, deg=True)
        
        fig.add_trace(
            go.Scatter(
                x=freq_hz,  # Changed from freq_rad
                y=magnitude_db,
                mode='lines',
                name='Original',
                line=dict(color='blue')
            ),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=freq_hz,  # Changed from freq_rad
                y=phase_deg,
                mode='lines',
                name='Original',
                line=dict(color='blue')
            ),
            row=2, col=1
        )
        
        # If shaped data is provided, add it to the plot
        if shaped_frd is not None:
            # Parse shaped data similarly
            shaped_str = str(shaped_frd)
            shaped_lines = shaped_str.split('\n')
            
            # Find where the data table starts
            data_start = 0
            for i, line in enumerate(shaped_lines):
                if "Freq [rad/s]  Response" in line:
                    data_start = i + 2
                    break
                    
            shaped_data_lines = [line.strip() for line in shaped_lines[data_start:] if line.strip() and 'j' in line]
            
            freq_rad_shaped = []
            response_shaped = []
            for line in shaped_lines:
                parts = line.split()
                if len(parts) >= 3:
                    freq_rad_shaped.append(float(parts[0]))
                    real = float(parts[1])
                    imag = float(parts[2].replace('j', ''))
                    response_shaped.append(complex(real, imag))
            
            freq_rad_shaped = np.array(freq_rad_shaped)
            freq_hz_shaped = freq_rad_shaped / (2 * np.pi)  # Convert to Hz
            response_shaped = np.array(response_shaped)
            
            magnitude_db_shaped = 20 * np.log10(np.abs(response_shaped))
            phase_deg_shaped = np.angle(response_shaped, deg=True)
            
            fig.add_trace(
                go.Scatter(
                    x=freq_hz_shaped,  # Changed from freq_rad_shaped
                    y=magnitude_db_shaped,
                    mode='lines',
                    name='Shaped',
                    line=dict(color='red')
                ),
                row=1, col=1
            )

            fig.add_trace(
                go.Scatter(
                    x=freq_hz_shaped,  # Changed from freq_rad_shaped
                    y=phase_deg_shaped,
                    mode='lines',
                    name='Shaped',
                    line=dict(color='red')
                ),
                row=2, col=1
            )
        
        # Update layout
        fig.update_layout(
            height=800,
            showlegend=True,
            title_text=title,
            title_x=0.5
        )
        
        # Update axes labels
        fig.update_xaxes(title_text="Frequency (Hz)", type="log", row=2, col=1)
        fig.update_yaxes(title_text="Magnitude (dB)", row=1, col=1)
        fig.update_yaxes(title_text="Phase (degrees)", row=2, col=1)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"Bode Plot_{position}_{timestamp}.html"
        output_path = os.path.join(self.output_dir, output_filename)
        pyo.plot(fig, filename=output_path, auto_open=False)
        print(f"📊 Bode plot saved to: {output_path}")
        
        return fig

    def create_stability_analysis_plot(self, log_files=None, output_filename=None):
        """
        Create stability analysis plots from log files
        
        Args:
            log_files: List of log file paths (if None, searches output_dir)
            output_filename: Name for output HTML file
        """
        if log_files is None:
            # Search for log files in output directory
            log_files = list(Path(self.output_dir).glob("*.log"))
        
        if not log_files:
            print("No log files found for stability analysis")
            return None
        
        # Parse all log files
        stability_data = []
        for log_file in log_files:
            data = self.parse_log_file(log_file)
            if data and any([data['phase_margin'], data['gain_margin'], data['sensitivity']]):
                stability_data.append(data)
        
        if not stability_data:
            print("No valid stability data found in log files")
            return None
        
        if not output_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"stability_analysis_{timestamp}.html"
        
        # Create stability analysis plots
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=('Crossover vs Position', 'Phase Margin vs Position', 'Gain Margin vs Position',
                          'Sensitivity vs Position', 'Stability Summary', ''),
            specs=[[{"type": "scatter"}, {"type": "scatter"}],
                   [{"type": "scatter"}, {"type": "scatter"}],
                   [{"type": "table"}, None]]
        )
        
        # Extract data for plotting
        positions = []
        axes = []
        phase_margins = []
        crossover = []
        gain_margins = []
        sensitivities = []
        statuses = []
        
        for data in stability_data:
            if data['axis'] and data['position']:
                axes.append(data['axis'])
                positions.append(f"{data['axis']}-{data['position']}")
                
                if data['phase_margin']:
                    phase_margins.append(data['phase_margin']['value'])
                    crossover.append(data['phase_margin']['frequency'])
                else:
                    phase_margins.append(None)
                    crossover.append(None)
                    
                if data['gain_margin']:
                    gain_margins.append(data['gain_margin']['value'])
                else:
                    gain_margins.append(None)
                    
                if data['sensitivity']:
                    sensitivities.append(data['sensitivity']['value'])
                else:
                    sensitivities.append(None)
                
                # New status determination logic:
                # 1. Check sensitivity first - if it's failing, the whole test fails
                sensitivity_fail = data['sensitivity'] and data['sensitivity']['value'] > 6
                
                # 2. Check phase and gain margins for warnings
                phase_warning = data['phase_margin'] and not (38 <= data['phase_margin']['value'] <= 52)
                gain_warning = data['gain_margin'] and not (6 <= data['gain_margin']['value'] <= 15)
                
                # Determine final status:
                if sensitivity_fail:
                    statuses.append('FAIL')  # Only fail if sensitivity exceeds limit
                elif phase_warning or gain_warning:
                    statuses.append('WARNING')  # Warning if margins are outside range but sensitivity is ok
                else:
                    statuses.append('PASS')  # Pass if everything is in range
        
        # Define target ranges
        phase_target = dict(min=38, max=52, target=45)
        gain_target = dict(min=6, max=15, target=10)
        sensitivity_target = dict(max=6, target=6)
        
        # Crossover plot
        #colors_cf = ['green' if 38 <= cf <= 52 else 'orange' for cf in crossover if cf is not None]
        colors_cf = ['green' for cf in crossover if cf is not None]
        fig.add_trace(
            go.Scatter(
                x=positions,
                y=crossover,
                mode='markers+lines',
                name='Crossover Frequency',
                marker=dict(size=10, color=colors_cf),
                hovertemplate="Position: %{x}<br>Crossover Frequency: %{y:.1f} Hz<extra></extra>"
            ),
            row=1, col=1
        )

        # Phase Margin plot
        colors_pm = ['green' if 38 <= pm <= 52 else 'orange' for pm in phase_margins if pm is not None]
        fig.add_trace(
            go.Scatter(
                x=positions,
                y=phase_margins,
                mode='markers+lines',
                name='Phase Margin',
                marker=dict(size=10, color=colors_pm),
                hovertemplate="Position: %{x}<br>Phase Margin: %{y:.1f}°<extra></extra>"
            ),
            row=1, col=2
        )
        
        # Add target range lines for phase margin
        fig.add_hline(y=phase_target['target'], line_dash="solid", line_color="green", 
                     annotation_text="Target (45°)", row=1, col=2)
        
        # Gain Margin plot
        colors_gm = ['green' if 6 <= gm <= 15 else 'orange' for gm in gain_margins if gm is not None]
        fig.add_trace(
            go.Scatter(
                x=positions,
                y=gain_margins,
                mode='markers+lines',
                name='Gain Margin',
                marker=dict(size=10, color=colors_gm),
                hovertemplate="Position: %{x}<br>Gain Margin: %{y:.1f} dB<extra></extra>"
            ),
            row=2, col=1
        )
        
        # Add target range lines for gain margin
        fig.add_hline(y=gain_target['target'], line_dash="solid", line_color="green", 
                     annotation_text="Target (10 dB)", row=2, col=1)
        
        # Sensitivity plot
        colors_s = []
        for s in sensitivities:
            if s is None:
                colors_s.append('gray')
            elif s <= 6:
                colors_s.append('green')  # Pass
            elif s <= 8:
                colors_s.append('orange')  # Warning
            else:
                colors_s.append('red')  # Fail

        # Add shaded regions for different zones
        fig.add_shape(
            type="rect",
            x0=positions[0] if positions else 0,
            x1=positions[-1] if positions else 1,
            y0=0,
            y1=6,
            fillcolor="green",
            opacity=0.1,
            layer="below",
            line_width=0,
            row=2, col=2
        )

        fig.add_shape(
            type="rect",
            x0=positions[0] if positions else 0,
            x1=positions[-1] if positions else 1,
            y0=6,
            y1=8,
            fillcolor="orange",
            opacity=0.1,
            layer="below",
            line_width=0,
            row=2, col=2
        )

        fig.add_shape(
            type="rect",
            x0=positions[0] if positions else 0,
            x1=positions[-1] if positions else 1,
            y0=8,
            y1=12,  # Assuming 12dB as max for visualization
            fillcolor="red",
            opacity=0.1,
            layer="below",
            line_width=0,
            row=2, col=2
        )

        # Add horizontal lines for boundaries
        fig.add_shape(
            type="line",
            x0=positions[0] if positions else 0,
            x1=positions[-1] if positions else 1,
            y0=6,
            y1=6,
            line=dict(color="green", width=2, dash="dash"),
            row=2, col=2
        )

        fig.add_shape(
            type="line",
            x0=positions[0] if positions else 0,
            x1=positions[-1] if positions else 1,
            y0=8,
            y1=8,
            line=dict(color="orange", width=2, dash="dash"),
            row=2, col=2
        )

        # Add the sensitivity trace
        fig.add_trace(
            go.Scatter(
                x=positions,
                y=sensitivities,
                mode='markers+lines',
                name='Sensitivity',
                marker=dict(size=10, color=colors_s),
                hovertemplate="Position: %{x}<br>Sensitivity: %{y:.1f} dB<br>Status: %{customdata}<extra></extra>",
                customdata=['Pass' if s <= 6 else 'Warning' if s <= 8 else 'Fail' for s in sensitivities]
            ),
            row=2, col=2
        )

        # Update y-axis range to show the zones clearly
        fig.update_yaxes(range=[0, 12], row=2, col=2)  # Adjust max value as needed
        
        # Create results table
        table_data = []
        for i, (axis, position) in enumerate(zip(axes, positions)):
            # Create the row data
            position_str = position
            phase_str = f"{phase_margins[i]:.1f}°" if phase_margins[i] is not None else "N/A"
            gain_str = f"{gain_margins[i]:.1f} dB" if gain_margins[i] is not None else "N/A"
            sensitivity_str = f"{sensitivities[i]:.1f} dB" if sensitivities[i] is not None else "N/A"
            
            # Determine status and colors for each cell
            
            # Position cell is always white
            position_color = 'white'
            
            # Phase margin color
            phase_margin = phase_margins[i]
            if phase_margin is None:
                phase_color = 'lightgray'
            elif 38 <= phase_margin <= 52:
                phase_color = 'lightgreen'
            else:
                phase_color = '#ffd700'  # Gold/orange for warning (changed from '#ffcccb')
            
            # Gain margin color
            gain_margin = gain_margins[i]
            if gain_margin is None:
                gain_color = 'lightgray'
            elif 6 <= gain_margin <= 15:
                gain_color = 'lightgreen'
            else:
                gain_color = '#ffd700'  # Gold/orange for warning (changed from '#ffcccb')
            
            # Sensitivity color and status
            sensitivity = sensitivities[i]
            if sensitivity is None:
                sensitivity_color = 'lightgray'
                status = 'N/A'
                status_color = 'lightgray'
            elif sensitivity <= 6:
                sensitivity_color = 'lightgreen'
                status = 'Pass'
                status_color = 'lightgreen'
            elif sensitivity <= 8:
                sensitivity_color = '#ffd700'  # Gold color for warning
                status = 'Warning'
                status_color = '#ffd700'
            else:
                sensitivity_color = '#ffcccb'  # Light red
                status = 'Fail'
                status_color = '#ffcccb'
            
            row = [position_str, phase_str, gain_str, sensitivity_str, status]
            colors = [position_color, phase_color, gain_color, sensitivity_color, status_color]
            
            table_data.append((row, colors))

        # Create the table
        fig.add_trace(
            go.Table(
                header=dict(
                    values=['Position', 'Phase Margin', 'Gain Margin', 'Sensitivity', 'Status'],
                    fill_color='lightgray',
                    align='center',
                    font=dict(size=12, color='black')
                ),
                cells=dict(
                    values=list(zip(*[row for row, _ in table_data])),
                    fill_color=list(zip(*[colors for _, colors in table_data])),
                    align='center',
                    font=dict(size=11, color='black')
                )
            ),
            row=3, col=1
        )
        
        # Update layout
        fig.update_layout(
            title=dict(
                text="Stability Analysis",
                font=dict(size=16)
            ),
            height=800,
            showlegend=False
        )
        
        # Update axes labels
        fig.update_xaxes(title_text="Test Position", row=1, col=1)
        fig.update_xaxes(title_text="Test Position", row=1, col=2)
        fig.update_xaxes(title_text="Test Position", row=2, col=1)
        fig.update_xaxes(title_text="Test Position", row=2, col=2)
        
        # Update y-axis labels
        fig.update_yaxes(title_text="Frequency (Hz)", row=1, col=1)
        fig.update_yaxes(title_text="Phase (deg)", row=1, col=2)
        fig.update_yaxes(title_text="Gain (dB)", row=2, col=1)
        fig.update_yaxes(title_text="Sensitivity (dB)", row=2, col=2)

        # Save plot
        output_path = os.path.join(self.output_dir, output_filename)
        pyo.plot(fig, filename=output_path, auto_open=True)
        print(f"📊 Stability analysis plot saved to: {output_path}")
        
        return fig

    def create_combined_analysis(self, fr_files=None, log_files=None):
        """
        Create a combined analysis with both Bode plots and stability analysis
        
        Args:
            fr_files: List of .fr file paths
            log_files: List of log file paths
        """
        print("🎯 Creating Combined EasyTune Analysis...")
        
        # Create stability analysis if log files provided/found
        stability_fig = self.create_stability_analysis_plot(log_files)
        if stability_fig:
            print("✅ Stability analysis created")
        
        print(f"📁 All plots saved to: {self.output_dir}")

def main():
    """Example usage of the EasyTunePlotter"""
    import glob
    
    # Initialize plotter
    plotter = EasyTunePlotter()
    
    # Find FR and log files in current directory
    fr_files = glob.glob("*.fr")
    log_files = glob.glob("*.log")
    
    print(f"Found {len(fr_files)} FR files and {len(log_files)} log files")
    
    if fr_files or log_files:
        plotter.create_combined_analysis(fr_files, log_files)
    else:
        print("No FR or log files found. Place some test files in the current directory.")

if __name__ == "__main__":
    main()