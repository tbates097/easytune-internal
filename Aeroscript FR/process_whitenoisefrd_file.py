#!usr/bin/env python3

"""Script to process data collected in AeroScript"""
# pylint: disable=line-too-long
import os
import sys
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal

import control
import scipy.optimize as optimize

# Grab the a1_file_handler from BitBucket
#urllib.request.urlretrieve(r"https://scm2.aerotech.com/projects/MRG/repos/automation1pythontools/raw/Automation1FileHandler/a1_file_handler.py?at=refs%2Fheads%2Fmaster", os.path.join(os.getcwd(), 'a1_file_handler.py'))
from a1_file_handler import DatFile # pylint: disable=wrong-import-position

def _calc_whitenoise_freq_response(signal_in:list, signal_out:list, num_avgs:int, sample_time:float, window='boxcar', plot_time=False): # pylint: disable=too-many-arguments, too-many-locals

    num_pts_per_period = len(signal_in)/num_avgs

    #Calculate the Auto
    dummy = signal_in[:]
    frequency, s_xx = signal.csd(signal_in, dummy,  fs = 1/sample_time, window = window, nperseg = num_pts_per_period, scaling = 'spectrum', noverlap = num_pts_per_period/2)

    frequency, s_xy = signal.csd(signal_out, signal_in, fs = 1/sample_time, window = window, nperseg = num_pts_per_period, scaling = 'spectrum', noverlap = num_pts_per_period/2)

    g_hat_cross_auto = s_xy/s_xx

    mag = np.abs(g_hat_cross_auto)
    phase = np.mod(-1*np.angle(g_hat_cross_auto, deg=True),-360.0)

    #Also calculate coherence if we can
    if num_avgs > 1:
        _, coherence = signal.coherence(signal_in, signal_out, fs = 1/sample_time, window=window, nperseg=num_pts_per_period, noverlap=num_pts_per_period/2)
    else:
        coherence=None

    if plot_time:
        plt.figure(figsize=(16,9))
        plt.subplot(2,1,1)
        plt.plot(signal_in,label='raw in')
        plt.subplot(2,1,2)
        plt.plot(signal_out,label='raw out')

    return (frequency[1:],mag[1:],phase[1:],coherence[1:])


def analyze_frd_file(filename, input_var='Lt_After', output_var='Lt_Before', input_scale=1.0, output_scale=-1.0, num_avgs=16, window='boxcar', plot_time=False, convert_mag_db=True): # pylint: disable=too-many-locals, too-many-arguments 
    '''
    Processes a folder of stepped sinusoidal frequency data and returns a tuple of the frequency, magnitude, phase, and axis

    Input:
        filename -> Filepath to dat file to process

    Optional Inputs:
        input_var -> Data item name to use as the FR input
        output_var -> Data item name to use as the FR output
        input_scale -> Number to scale the input values by
        output_scale -> Number to scale the output values by

    Output:
        freqs -> Frequency in Hz [list]
        magdB -> Magnitude in dB [list if only one axis, otherwise a dictionary of lists with the key being the axis name]
        phase -> Phase in degrees [list if only one axis, otherwise a dictionary of lists with the key being the axis name]
        axis -> Name of the axis [string if only one axis, otherwise a list of strings of the axis names]
    '''
    this_dat_file = DatFile.create_from_file(filename)

    all_axes = list(np.unique([x.axis_name for x in this_dat_file.data_structure_list]))
    all_labels = list(this_dat_file.all_data.keys())
    valid_axes = [x for x in all_axes if input_var+x in all_labels and output_var+x in all_labels]

    mag = {}
    phase = {}
    mag_db = {}
    coh = {}
    for this_axis in valid_axes:
        freqs, mag[this_axis], phase[this_axis], coh[this_axis] = _calc_whitenoise_freq_response(np.multiply(this_dat_file.all_data[input_var+'{0}'.format(this_axis)], input_scale), np.multiply(this_dat_file.all_data[output_var+'{0}'.format(this_axis)], output_scale), num_avgs, 1.0/this_dat_file.sample_rate,window,plot_time)
        if convert_mag_db:
            mag_db[this_axis] = np.multiply(np.log10(mag[this_axis]), 20.0)
        # wrap the phase properly
        phase[this_axis] = np.mod(phase[this_axis], -360.0)

    #Flatten the dictionary if there is only one entry to a list
    if len(valid_axes) == 1:
        mag = mag[valid_axes[0]]
        if convert_mag_db:
            mag_db = mag_db[valid_axes[0]]
        phase = phase[valid_axes[0]]
        coh = coh[valid_axes[0]]
        valid_axes = valid_axes[0]

    if convert_mag_db:
        return (freqs, mag_db, phase, coh, valid_axes)

    return (freqs, mag, phase, coh, valid_axes)

def plant_model(frequency, inertia, damping, spring, delay):
    '''
    Basic model of a spring mass system with time delay
    '''
    s = control.tf('s') # pylint: disable=invalid-name
    plant = 1.0 / (inertia*s**2 + damping*s + spring)
    mag,phase,_=plant.frequency_response(frequency*2*np.pi,squeeze=True)
    phase -= frequency*2*np.pi * delay
    return mag* np.exp(1j*(phase))

def plant_residuals(params, frequency, response):
    '''
    Calculates the residuals of a plant fit
    '''
    inertia,damping,spring,delay = params
    diff = plant_model(frequency,inertia,damping,spring,delay)-response
    return diff.astype(np.complex128).view(np.float64)

def plant_residuals_log_mag(params, frequency, response):
    '''
    Calculates the residuals of a plant fit using magnitude in dB and phase in radians
    '''
    #THIS IS COMPLETELY WRONG!
    inertia,damping,spring,delay = params
    diff = plant_model(frequency,inertia,damping,spring,delay)/response
    mag_db = 20.0 * np.log10(np.abs(diff))
    phase = np.unwrap(np.angle(diff))
    return np.concatenate([mag_db,phase])

if __name__ == '__main__':

    #Specify the data folder:
    THIS_DATA_FILE = r'FRD_WhiteNoise\OpenLoopWhiteNoise_Yaw.dat'

    #Analyze the data
    INPUT='ContEffort'
    OUTPUT='PosFbk'
    FREQS, MAG, PHASE, COH, AXIS_NAME = analyze_frd_file(THIS_DATA_FILE,input_var=INPUT,output_var=OUTPUT,input_scale=1.0,output_scale=1.0,num_avgs=32,window='hanning',convert_mag_db=False,plot_time=False)

    #Use the coherence to remove bad points:
    #if COH is not None:
    #    for INDEX,THIS_COH in enumerate(COH):
    #        if THIS_COH <= 0.5:
    #            MAG_DB[INDEX] = np.NaN
    #            PHASE[INDEX] = np.NaN

    #Export data to csv
    OUTPUT_DIR = os.path.dirname(THIS_DATA_FILE)
    with open(os.path.join(OUTPUT_DIR, 'plant_resp.csv'),'wt') as THIS_FILE:
        THIS_FILE.write(';frequency,magnitude,phase,coherence\n')
        for INDEX,THIS_FREQ in enumerate(FREQS):
            THIS_FILE.write('{0},{1},{2},{3}\n'.format(THIS_FREQ,MAG[INDEX],PHASE[INDEX],COH[INDEX]))

    #Try least squares fit
    RESP = MAG* np.exp(1j*(PHASE*np.pi/180.0))
    actual_frd = control.FRD(RESP,FREQS*2*np.pi)

    resp_guess = plant_model(FREQS,9.71578/(180/np.pi*23.65328704),1009.26/(180/np.pi*23.65328704),2621010/(180/np.pi*23.65328704),5/20000)
    guess_frd = control.FRD(resp_guess,FREQS*2*np.pi)

    param_guess = 9.71578/(180/np.pi*23.65328704),1009.26/(180/np.pi*23.65328704),2621010/(180/np.pi*23.65328704),5/20000
    parameters, cov, infodict, mesg, ier = optimize.leastsq(
            plant_residuals, param_guess, args=(FREQS, RESP),
            full_output=True)

    print(parameters)
    resp_fit = plant_model(FREQS,parameters[0],parameters[1],parameters[2],parameters[3])
    fit_frd = control.FRD(resp_fit,FREQS*2*np.pi)

    plt.figure()
    control.bode(actual_frd,omega = FREQS*2*np.pi, Hz=True, deg=True,label='actual')
    control.bode(guess_frd,omega = FREQS*2*np.pi, Hz=True, deg=True,label='guess')
    control.bode(fit_frd,omega = FREQS*2*np.pi, Hz=True, deg=True,label='fit')
    plt.suptitle('Linear Freq Spacing')
    plt.legend()

    guess_res = plant_residuals((9.71578/(180/np.pi*23.65328704),1009.26/(180/np.pi*23.65328704),2621010/(180/np.pi*23.65328704),5/20000),FREQS, RESP).view(np.complex128)
    fit_res = plant_residuals(parameters,FREQS, RESP).view(np.complex128)

    guess_residuals = np.abs(guess_res)
    fit_residuals = np.abs(fit_res)
    plt.figure()
    plt.title('Linear Freq Spacing Residuals')
    plt.loglog(FREQS,guess_residuals,label='guess')
    plt.loglog(FREQS,fit_residuals,label='fit')
    plt.legend()


    #Now move to log spaced frequencies
    logspace_freqs = np.logspace(np.log10(FREQS[0]),np.log10(FREQS[-1]), int(len(FREQS)/8))
    actual_frd_interp = control.FRD(RESP,FREQS*2*np.pi,smooth=True)
    resp_interp = actual_frd_interp.eval(logspace_freqs*2*np.pi,squeeze=True)

    resp_guess_interp = plant_model(logspace_freqs,9.71578/(180/np.pi*23.65328704),1009.26/(180/np.pi*23.65328704),2621010/(180/np.pi*23.65328704),5/20000)
    guess_frd_interp = control.FRD(resp_guess_interp,logspace_freqs*2*np.pi)

    parameters, cov, infodict, mesg, ier = optimize.leastsq(
            plant_residuals, param_guess, args=(logspace_freqs, resp_interp),
            full_output=True)

    print(parameters)

    resp_fit_interp = plant_model(logspace_freqs,parameters[0],parameters[1],parameters[2],parameters[3])
    fit_frd_interp = control.FRD(resp_fit_interp,logspace_freqs*2*np.pi)

    plt.figure()
    control.bode(actual_frd_interp,omega = logspace_freqs*2*np.pi, Hz=True, deg=True,label='actual')
    control.bode(guess_frd_interp,omega = logspace_freqs*2*np.pi, Hz=True, deg=True,label='guess')
    control.bode(fit_frd_interp,omega = logspace_freqs*2*np.pi, Hz=True, deg=True,label='fit')
    plt.suptitle('Log Freq Spacing')
    plt.legend()

    guess_res = plant_residuals((9.71578/(180/np.pi*23.65328704),1009.26/(180/np.pi*23.65328704),2621010/(180/np.pi*23.65328704),5/20000),logspace_freqs, resp_interp).view(np.complex128)
    fit_res = plant_residuals(parameters,logspace_freqs, resp_interp).view(np.complex128)

    guess_residuals = np.abs(guess_res)
    fit_residuals = np.abs(fit_res)
    plt.figure()
    plt.title('Log Freq Spacing Residuals')
    plt.loglog(logspace_freqs,guess_residuals,label='guess')
    plt.loglog(logspace_freqs,fit_residuals,label='fit')
    plt.legend()

    #Now move to log residuals
    #THIS IS COMPLETELY WRONG!

    parameters, cov, infodict, mesg, ier = optimize.leastsq(
            plant_residuals_log_mag, param_guess, args=(logspace_freqs, resp_interp),
            full_output=True)

    print(parameters)

    resp_fit_interp = plant_model(logspace_freqs,parameters[0],parameters[1],parameters[2],parameters[3])
    fit_frd_interp = control.FRD(resp_fit_interp,logspace_freqs*2*np.pi)

    plt.figure()
    control.bode(actual_frd_interp,omega = logspace_freqs*2*np.pi, Hz=True, deg=True,label='actual')
    control.bode(guess_frd_interp,omega = logspace_freqs*2*np.pi, Hz=True, deg=True,label='guess')
    control.bode(fit_frd_interp,omega = logspace_freqs*2*np.pi, Hz=True, deg=True,label='fit')
    plt.suptitle('Log Freq Spacing Log Resid')
    plt.legend()

    guess_res = plant_residuals_log_mag((9.71578/(180/np.pi*23.65328704),1009.26/(180/np.pi*23.65328704),2621010/(180/np.pi*23.65328704),5/20000),logspace_freqs, resp_interp)#.view(np.complex128)
    fit_res = plant_residuals_log_mag(parameters,logspace_freqs, resp_interp)#.view(np.complex128)

    plt.figure()
    plt.subplot(2,1,1)
    plt.title('Log Freq Spacing Log Resid Residuals')
    plt.semilogx(logspace_freqs,guess_res[0:int(len(guess_res)/2)],label='guess')
    plt.semilogx(logspace_freqs,fit_res[0:int(len(fit_res)/2)],label='fit')
    plt.legend()
    plt.subplot(2,1,2)
    plt.semilogx(logspace_freqs,guess_res[int(len(fit_res)/2):],label='guess')
    plt.semilogx(logspace_freqs,fit_res[int(len(fit_res)/2):],label='fit')
    plt.show()

    sys.exit()

    #Plot everything
    plt.figure(figsize=(16,9))
    if COH is not None:
        NUM_SUBPLOTS = 3
    else:
        NUM_SUBPLOTS = 2

    AX1 = plt.subplot(NUM_SUBPLOTS, 1, 1)
    # Add the 1 line in if it crosses it
    if np.any(np.greater(MAG, 1.0)) and np.any(np.less(MAG, 1.0)):
        plt.axhline(1.0, color='black')
    plt.loglog(FREQS, MAG)
    plt.grid(which='both')
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('Magnitude')

    plt.subplot(NUM_SUBPLOTS, 1, 2, sharex=AX1)
    plt.axhline(-180.0, color='black')
    plt.semilogx(FREQS, PHASE)
    plt.grid(which='both')
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('Phase [deg]')

    if COH is not None:
        plt.subplot(NUM_SUBPLOTS, 1, 3, sharex=AX1)
        plt.semilogx(FREQS, COH)
        plt.axhline(1.0, color='black')
        plt.grid(which='both')
        plt.xlabel('Frequency [Hz]')
        plt.ylabel('Coherence')

    plt.suptitle('{0} {1}/{2} Frequency Response'.format(AXIS_NAME,OUTPUT,INPUT))

    AX1.set_xlim([FREQS[0], FREQS[-1]])

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'plant_resp.png'),dpi=100)
    plt.show()
