#!usr/bin/env python3

# pylint: disable=line-too-long
"""Script to process data gathered with \MultisineDisturbance\Multisine.ascriptlib using the Multisine_GatherFrequencyResponse function""" # pylint: disable=anomalous-backslash-in-string

import os
import csv
import re
#import urllib.request
import matplotlib.pyplot as plt
from scipy import signal
import numpy as np

# Grab the a1_file_handler from BitBucket
#urllib.request.urlretrieve(r"https://scm2.aerotech.com/projects/MRG/repos/automation1pythontools/raw/Automation1FileHandler/a1_file_handler.py?at=refs%2Fheads%2Fmaster", os.path.join(os.getcwd(), 'a1_file_handler.py'))
from a1_file_handler import DatFile # pylint: disable=wrong-import-position

class MultisineInfo():
    '''Class to store one sequence of a sequential multisine disturbance'''
    def __init__(self, start_freq=None,end_freq=None,freq_spacing=None,num_periods=None):
        self.start_freq=start_freq
        self.end_freq=end_freq
        self.freq_spacing=freq_spacing
        self.num_periods=num_periods
    def __str__(self):
        temp_str = []
        for key in self.__dict__:
            if self.__dict__[key] is None:
                continue
            if isinstance(self.__dict__[key], list):
                temp_str.append("  {key} = List[{value}]".format(key=key, value=len(self.__dict__[key])))
            else:
                temp_str.append("  {key} = {value}".format(key=key, value=self.__dict__[key]))
        return '\n' + '\n'.join(temp_str)

    def __repr__(self):
        return self.__str__()

def _calc_multisine_freq_response(signal_in:list, signal_out:list, multisine_info:MultisineInfo, num_pts_per_period:int, sample_time:float, window='boxcar', num_avg_limit=None, plot_time=False): # pylint: disable=too-many-arguments, too-many-locals
    bin_start_freq = multisine_info.start_freq
    bin_end_freq = multisine_info.end_freq
    bin_freq_spacing = multisine_info.freq_spacing

    #good_freqs = np.arange(bin_start_freq,bin_end_freq + bin_freq_spacing, bin_freq_spacing)

    num_avgs = int(np.round(len(signal_in) / num_pts_per_period))

    if num_avg_limit is not None:
        if num_avg_limit > num_avgs:
            print('Number of averages limit exceeds the number of averages possible, using all {0} averages.'.format(num_avgs))
        else:
            # take the first section(s) of data:
            end_ind = int(np.round(num_pts_per_period * num_avg_limit))
            signal_in = signal_in[0:end_ind]
            signal_out = signal_out[0:end_ind]
            num_avgs = num_avg_limit

    #Calculate the Auto
    dummy = signal_in[:]
    frequency, s_xx = signal.csd(signal_in, dummy,  fs = 1/sample_time, window = window, nperseg = num_pts_per_period, scaling = 'spectrum', noverlap = num_pts_per_period/2)

    #Only take the bins that were excited:
    #good_ind = [frequency.index(i) for i in good_freqs] #Works on lists, not np arrays
    #good_ind = np.where(np.in1d(frequency,good_freqs))

    #This array is actually always the bins based upon the base num periods: [N:N*2-1]
    good_ind = np.arange(multisine_info.num_periods,multisine_info.num_periods*2, dtype=int)

    frequency, s_xy = signal.csd(signal_out, signal_in, fs = 1/sample_time, window = window, nperseg = num_pts_per_period, scaling = 'spectrum', noverlap = num_pts_per_period/2)

    g_hat_cross_auto = s_xy[good_ind]/s_xx[good_ind]

    mag = 20.0 * np.log10(np.abs(g_hat_cross_auto))
    phase = np.mod(-1*np.angle(g_hat_cross_auto, deg=True),-360.0)

    #Also calculate coherence if we can
    if num_avgs > 1:
        _, coherence = signal.coherence(signal_in, signal_out, fs = 1/sample_time, window=window, nperseg=num_pts_per_period, noverlap=num_pts_per_period/2)
        #plt.figure(figsize=(16,9))
        #plt.semilogx(freq,coherence)
        #plt.semilogx(freq[goodInd],coherence[goodInd],'r*')
        #plt.suptitle('Coherence {0}Hz : {1}Hz : {2}Hz'.format(binStartFreq,binFreqSpacing,binEndFreq))
        coherence = coherence[good_ind]
    else:
        coherence=None

    if plot_time:
        plt.figure(figsize=(16,9))
        plt.subplot(2,1,1)
        plt.plot(signal_in,label='raw in')
        plt.subplot(2,1,2)
        plt.plot(signal_out,label='raw out')
        plt.suptitle('{0}Hz : {1}Hz : {2}Hz'.format(bin_start_freq,bin_freq_spacing,bin_end_freq))

    return (frequency[good_ind],mag,phase,coherence)

def analyze_frd_folder(this_run_dir, window='boxcar', input_var='LT_After', output_var='LT_Before', input_scale=1.0, output_scale=-1.0, num_avg_limit=None): # pylint: disable=too-many-locals,too-many-arguments,too-many-branches,too-many-statements
    '''
    Processes a folder of multisine frequency data and returns a tuple of the frequency, magnitude, phase, and axis

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

    filenames = []
    outputfilenames = []
    chunks = []
    num_pts = []
    axes = []

    #read in the run information
    with open(os.path.join(this_run_dir, "FRD_RunInfo.txt"), mode='r') as txt_file:
        for this_line in txt_file.readlines():
            if 'Axis' in this_line:
                axes.append(re.search(r'Axis: (\S+)', this_line).groups()[0]) #extract the axis name from the line
            continue

    #read in the filenames from the csv file generated in Aeroscript
    with open(os.path.join(this_run_dir, "FRD_FileLog.csv"), mode='r') as csv_file:
        this_reader = csv.DictReader(csv_file)
        for row in this_reader:
            filenames.append(row['filename'])

            #Calculate the start, end, and spacing based upon the integer values
            this_num_pts = float(row['numPts'])
            this_num_periods = float(row['numPeriods'])
            this_spacing = float(row['sampleRate']) / this_num_pts
            this_start = this_spacing * this_num_periods
            this_end = this_start*2.0-this_spacing

            chunks.append(MultisineInfo(start_freq=this_start,end_freq=this_end,freq_spacing=this_spacing,num_periods=this_num_periods))
            num_pts.append(this_num_pts)
            outputfilenames.append(os.path.join(this_run_dir, os.path.basename(row['filename'])))

    freqs = {}
    mag = {}
    phase = {}
    coh = {}
    for axis in axes:
        freqs[axis] = []
        mag[axis] = []
        phase[axis] = []
        coh[axis] = []

    for this_filename, this_chunk, this_num_pts in zip(outputfilenames,chunks,num_pts):
        try:
            #load in the data
            this_dat_file = DatFile.create_from_file(this_filename)
            all_data = this_dat_file.all_data
            sample_rate = this_dat_file.sample_rate

            #calculate magnitude and phase
            for axis in axes:
                this_freq, this_mag, this_phase, this_coh = _calc_multisine_freq_response(np.multiply(all_data[input_var+'{0}'.format(axis)], input_scale), np.multiply(all_data[output_var+'{0}'.format(axis)], output_scale), this_chunk, this_num_pts, 1.0/sample_rate,window,num_avg_limit,True)

                freqs[axis].extend(this_freq)
                mag[axis].extend(this_mag)
                phase[axis].extend(this_phase)
                if this_coh is not None:
                    coh[axis].extend(this_coh)
                else:
                    coh[axis] = None
        except :
            print(all_data.keys())
            raise

    #Flatten the dictionary if there is only one entry to a list
    if len(axes) == 1:
        freqs = freqs[axes[0]]
        mag = mag[axes[0]]
        phase = phase[axes[0]]
        coh = coh[axes[0]]
        axes = axes[0]

    return (freqs, mag, phase, axes, coh)

if __name__ == '__main__':

    THIS_DATA_FOLDER = r'C:\ProgramData\Aerotech\Automation1-iSMC\fs\user\MIMO SystemID\Normal'

    FREQS, MAG_DB, PHASE, AXIS_NAME, COH = analyze_frd_folder(THIS_DATA_FOLDER,input_var='Lt_After', output_var='Lt_Before')
    FREQS, MAG_DB_WIND, PHASE_WIND, AXIS_NAME, COH_WIND = analyze_frd_folder(THIS_DATA_FOLDER,'hann',input_var='Lt_After', output_var='Lt_Before')

    RESPONSE_TYPE = 'Open Loop'

    #Plot everything
    plt.figure(figsize=(16,12))
    if COH is not None:
        NUM_PLOTS=3
    else:
        NUM_PLOTS=2

    AX1 = plt.subplot(NUM_PLOTS, 1, 1)
    # Add the 0 dB line in if it crosses it
    if np.any(np.greater(MAG_DB, 0.0)) and np.any(np.less(MAG_DB, 0.0)):
        plt.axhline(0.0, color='black')
    plt.semilogx(FREQS, MAG_DB, label='Boxcar')
    plt.semilogx(FREQS, MAG_DB_WIND, label='Hann')
    plt.grid(which='both')
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('Magnitude [dB]')
    plt.legend()

    plt.subplot(NUM_PLOTS, 1, 2, sharex=AX1)
    plt.axhline(-180.0, color='black')
    plt.semilogx(FREQS, PHASE)
    plt.semilogx(FREQS, PHASE_WIND)
    plt.grid(which='both')
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('Phase [deg]')

    if NUM_PLOTS == 3:
        plt.subplot(3, 1, 3, sharex=AX1)
        plt.axhline(1.0, color='black')
        plt.semilogx(FREQS, COH)
        plt.semilogx(FREQS, COH_WIND)
        plt.grid(which='both')
        plt.xlabel('Frequency [Hz]')
        plt.ylabel('Coherence')

    plt.suptitle('{0} {1} Frequency Response'.format(AXIS_NAME,RESPONSE_TYPE))

    AX1.set_xlim([FREQS[0], FREQS[-1]])

    plt.tight_layout()

    outputStr = os.path.join(THIS_DATA_FOLDER,"result.png")
    plt.savefig(outputStr, dpi = 100,transparent=True)


    plt.show()
