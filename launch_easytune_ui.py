#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EasyTune UI Launcher
Simple launcher script for the EasyTune graphical interface
"""

import sys
import os

# Add the current directory to Python path to ensure imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from EasyTuneUI import main
    
    if __name__ == "__main__":
        print("🚀 Starting EasyTune UI...")
        main()
        
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Please ensure all required modules are installed:")
    print("- tkinter (usually comes with Python)")
    print("- automation1")
    print("- numpy") 
    print("- scipy")
    print("- plotly")
    input("Press Enter to exit...")
    
except Exception as e:
    print(f"❌ Error starting EasyTune UI: {e}")
    input("Press Enter to exit...") 