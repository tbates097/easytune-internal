#!usr/bin/env python3

"""Script to process data collected in AeroScript"""
# pylint: disable=line-too-long

import os
import csv
import re
#import urllib.request
import matplotlib.pyplot as plt
import numpy as np


# Grab the a1_file_handler from BitBucket
#urllib.request.urlretrieve(r"https://scm2.aerotech.com/projects/MRG/repos/automation1pythontools/raw/Automation1FileHandler/a1_file_handler.py?at=refs%2Fheads%2Fmaster", os.path.join(os.getcwd(), 'a1_file_handler.py'))
from a1_file_handler import DatFile # pylint: disable=wrong-import-position

def _calc_sine_freq_response(signalin, signalout, freq, sample_time):
    '''
        Calculate the magnitude and phase difference between input and output signal
    '''

    #Calculate the Input Mag and Phase
    fr_input_mag, fr_input_phase = _calculate_sine_mag_and_phase(signalin, freq, sample_time)

    #Calculate the Output Mag and Phase
    fr_output_mag, fr_output_phase = _calculate_sine_mag_and_phase(signalout, freq, sample_time)

    #Calculate the Magnitude and Phase
    return fr_output_mag/fr_input_mag, fr_output_phase - fr_input_phase

def _calculate_sine_mag_and_phase(vals, freq, sample_time):

    '''
        Calculate the magnitude and phase of the signals
    '''

    #Calculate least-square coefficients
    data_cos, data_sin = _calc_least_squares_sine_mag(vals, freq, sample_time)

    #calculate magnitude
    magnitude = np.sqrt(data_cos*data_cos + data_sin*data_sin)

    #calculate phase
    phase = 180.0/np.pi * np.arctan2(data_cos, data_sin)

    return magnitude, phase

def _calc_least_squares_sine_mag(vals, freq, sample_time):

    omega = 2.0 * np.pi * freq

    temp = np.multiply(range(0, len(vals)), sample_time*omega)

    cos_vals = np.cos(temp)
    sin_vals = np.sin(temp)
    offset_vals = np.ones(sin_vals.shape)
    #slope_vals = np.linspace(-1,1,len(offset_vals))

    a_matrix = np.array([cos_vals, sin_vals, offset_vals]).T
    #a_matrix = np.array([cos_vals, sin_vals, offset_vals, slope_vals]).T

    fit_vals = np.linalg.lstsq(a_matrix, vals, rcond=None)

    mag_cos = fit_vals[0][0]
    mag_sin = fit_vals[0][1]

    return mag_cos, mag_sin

def analyze_frd_folder(this_run_dir, input_var='Lt_After', output_var='Lt_Before', input_scale=1.0, output_scale=-1.0): # pylint: disable=too-many-locals
    '''
    Processes a folder of stepped sinusoidal frequency data and returns a tuple of the frequency, magnitude, phase, and axis

    Input:
        this_run_dir -> Filepath to the directory to process

    Optional Inputs:
        input -> Data item name to use as the FR input
        output -> Data item name to use as the FR output
        input_scale -> Number to scale the input values by
        output_scale -> Number to scale the output values by

    Output:
        freqs -> Frequency in Hz [list]
        magdB -> Magnitude in dB [list if only one axis, otherwise a dictionary of lists with the key being the axis name]
        phase -> Phase in degrees [list if only one axis, otherwise a dictionary of lists with the key being the axis name]
        axis -> Name of the axis [string if only one axis, otherwise a list of strings of the axis names]
    '''

    #read in the filenames from the csv file generated in Aeroscript
    with open(os.path.join(this_run_dir, "FRD_Info.csv"), mode='r') as csv_file:
        this_reader = csv.reader(csv_file)
        filenames = []
        outputfilenames = []
        freqs = []
        axes = []

        for row in this_reader:
            if len(row) < 2 or row[0][0] == ';':
                if 'Axis' in row[0]:
                    axes.append(re.search(r';Axis: (\S+)', row[0]).groups()[0]) #extract the axis name from the line
                continue
            filenames.append(row[0])
            freqs.append(float(row[1]))
            outputfilenames.append(os.path.join(this_run_dir, os.path.basename(row[0])))

    mag = {}
    phase = {}
    for axis in axes:
        mag[axis] = []
        phase[axis] = []

    for this_filename, this_freq in zip(outputfilenames, freqs):
        try:
            #load in the data
            this_dat_file = DatFile.create_from_file(this_filename)

            #calculate magnitude and phase
            for axis in axes:
                this_mag, this_phase = _calc_sine_freq_response(np.multiply(this_dat_file.all_data[input_var+'{0}'.format(axis)], input_scale), np.multiply(this_dat_file.all_data[output_var+'{0}'.format(axis)], output_scale), this_freq, 1.0/this_dat_file.sample_rate)

                mag[axis].append(this_mag)
                phase[axis].append(this_phase)
        except:
            print(this_dat_file.all_data.keys())
            raise

    mag_db = {}
    for axis in axes:
        mag_db[axis] = np.multiply(np.log10(mag[axis]), 20.0)
        # wrap the phase properly
        phase[axis] = np.mod(phase[axis], -360.0)

    #Flatten the dictionary if there is only one entry to a list
    if len(axes) == 1:
        mag_db = mag_db[axes[0]]
        phase = phase[axes[0]]
        axes = axes[0]

    return (freqs, mag_db, phase, axes)

if __name__ == '__main__':

    #Specify the data folder:
    THIS_DATA_FOLDER = os.path.join(os.getcwd(), 'FRD_Z')

    #Analyze the data
    FREQS, MAG_DB, PHASE, AXIS_NAME = analyze_frd_folder(THIS_DATA_FOLDER)
    #FREQS_PLANT, MAG_DB_PLANT, PHASE_PLANT, AXIS_NAME_PLANT = analyze_frd_folder(THIS_DATA_FOLDER)

    #Plot everything
    plt.figure()

    AX1 = plt.subplot(2, 1, 1)
    # Add the 0 dB line in if it crosses it
    if np.any(np.greater(MAG_DB, 0.0)) and np.any(np.less(MAG_DB, 0.0)):
        plt.axhline(0.0, color='black')
    plt.semilogx(FREQS, MAG_DB)
    plt.grid(which='both')
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('Magnitude [dB]')

    plt.subplot(2, 1, 2, sharex=AX1)
    plt.axhline(-180.0, color='black')
    plt.semilogx(FREQS, PHASE)
    plt.grid(which='both')
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('Phase [deg]')

    plt.suptitle('{0} Open Loop Frequency Response'.format(AXIS_NAME))

    AX1.set_xlim([FREQS[0], FREQS[-1]])

    #plt.figure()
    #AX1 = plt.subplot(2, 1, 1)
    ## Add the 0 dB line in if it crosses it
    #if np.any(np.greater(MAG_DB_PLANT, 0.0)) and np.any(np.less(MAG_DB_PLANT, 0.0)):
    #    plt.axhline(0.0, color='black')
    #plt.semilogx(FREQS_PLANT, MAG_DB_PLANT)
    #plt.grid(which='both')
    #plt.xlabel('Frequency [Hz]')
    #plt.ylabel('Magnitude [dB]')

    #plt.subplot(2, 1, 2, sharex=AX1)
    #plt.axhline(-180.0, color='black')
    #plt.semilogx(FREQS_PLANT, PHASE_PLANT)
    #plt.grid(which='both')
    #plt.xlabel('Frequency [Hz]')
    #plt.ylabel('Phase [deg]')

    #plt.suptitle('{0} Plant Frequency Response'.format(AXIS_NAME_PLANT))

    #AX1.set_xlim([FREQS[0], FREQS[-1]])

    ##Show how to process a folder with multiple axes:

    ##Specify the data folder:
    #THIS_DATA_FOLDER = os.path.join(os.getcwd(), 'FRD_XY')

    ##Analyze the data
    #FREQS, MAG_DB, PHASE, AXES = analyze_frd_folder(THIS_DATA_FOLDER)

    #for THIS_AX in MAG_DB.keys():
    #    THIS_MAG_DB = MAG_DB[THIS_AX]
    #    THIS_PHASE = PHASE[THIS_AX]

    #    plt.figure()

    #    AX1 = plt.subplot(2, 1, 1)
    #    # Add the 0 dB line in if it crosses it
    #    if np.any(np.greater(THIS_MAG_DB, 0.0)) and np.any(np.less(THIS_MAG_DB, 0.0)):
    #        plt.axhline(0.0, color='black')
    #    plt.semilogx(FREQS, THIS_MAG_DB)
    #    plt.grid(which='both')
    #    plt.xlabel('Frequency [Hz]')
    #    plt.ylabel('Magnitude [dB]')

    #    plt.subplot(2, 1, 2, sharex=AX1)
    #    plt.axhline(-180.0, color='black')
    #    plt.semilogx(FREQS, THIS_PHASE)
    #    plt.grid(which='both')
    #    plt.xlabel('Frequency [Hz]')
    #    plt.ylabel('Phase [deg]')

    #    plt.suptitle('{0} Open Loop Frequency Response'.format(THIS_AX))

    #    AX1.set_xlim([FREQS[0], FREQS[-1]])


    plt.show()
