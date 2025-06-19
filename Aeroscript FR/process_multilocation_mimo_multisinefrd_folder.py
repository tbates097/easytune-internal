#!usr/bin/env python3

# pylint: disable=line-too-long
"""Script to process data gathered with \MultisineDisturbance\Multisine.ascriptlib using the Multisine_GatherFrequencyResponse function""" # pylint: disable=anomalous-backslash-in-string

import os
#import urllib.request
import configparser
import itertools
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal

# Grab the a1_file_handler from BitBucket
#urllib.request.urlretrieve(r"https://scm2.aerotech.com/projects/MRG/repos/automation1pythontools/raw/Automation1FileHandler/a1_file_handler.py?at=refs%2Fheads%2Fmaster", os.path.join(os.getcwd(), 'a1_file_handler.py'))
from a1_file_handler import DatFile, FrequencyResponse # pylint: disable=wrong-import-position

class MultisineInfo(FrequencyResponse.MultisineSignalParameters):
    '''Class to store one sequence of a sequential multisine disturbance'''
    def __init__(self, start_freq=None,end_freq=None,freq_spacing=None,num_periods=None,num_pts_per_iteration=None): # pylint: disable=too-many-arguments
        super().__init__(start_freq,end_freq,freq_spacing)
        self.num_periods=num_periods
        self.num_pts_per_iteration = num_pts_per_iteration
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

class FrequencyResponseWithCoherence(FrequencyResponse):
    '''Class to store frequency response data along with the coherence'''
    def __init__(self):
        super().__init__()
        self.multisine_signal_parameters = []
        self.frequency = []
        self.magnitude = []
        self.phase = []
        self.coherence = []

class FrequencyResponseData():
    '''Class to store frequency response data and easily convert complex values to mag/phase'''
    def __init__(self,complex_vals=None, phase_wrap_value_deg=-360.0):
        if complex_vals is None:
            self.complex=np.array([])
        else:
            self.complex=np.array(complex_vals)
        self.phase_wrap_value_deg = phase_wrap_value_deg
    @property
    def mag(self):
        '''Get the magnitude'''
        return np.abs(self.complex)
    @property
    def mag_dB(self): # pylint: disable=invalid-name
        '''Get the magnitude in dB'''
        return 20.0*np.log10(self.mag)
    @property
    def phase_deg(self):
        '''Get the phase in degrees'''
        return np.mod(np.angle(self.complex, deg=True)-self.phase_wrap_value_deg,360.0)+self.phase_wrap_value_deg
    @property
    def phase_rad(self):
        '''Get the phase in radians'''
        return np.mod(np.angle(self.complex)-np.deg2rad(self.phase_wrap_value_deg),360.0)+np.deg2rad(self.phase_wrap_value_deg)

def _calc_multisine_chunk_freq_response(signal_in:list, signal_out:list, multisine_info:MultisineInfo, sample_time:float, window='boxcar', num_avg_limit=None, plot_time=False): # pylint: disable=too-many-arguments, too-many-locals
    bin_start_freq = multisine_info.start_frequency
    bin_end_freq = multisine_info.end_frequency
    bin_freq_spacing = multisine_info.frequency_spacing

    #good_freqs = np.arange(bin_start_freq,bin_end_freq + bin_freq_spacing, bin_freq_spacing)
    num_pts_per_iteration = multisine_info.num_pts_per_iteration
    num_avgs = int(np.round(len(signal_in) / num_pts_per_iteration))

    if num_avg_limit is not None:
        if num_avg_limit > num_avgs:
            print('Number of averages limit exceeds the number of averages possible, using all {0} averages.'.format(num_avgs))
        else:
            # take the first section(s) of data:
            end_ind = int(np.round(num_pts_per_iteration * num_avg_limit))
            signal_in = signal_in[0:end_ind]
            signal_out = signal_out[0:end_ind]
            num_avgs = num_avg_limit

    #Calculate the Auto
    dummy = signal_in[:]
    frequency, s_xx = signal.csd(signal_in, dummy,  fs = 1/sample_time, window = window, nperseg = num_pts_per_iteration, scaling = 'spectrum', noverlap = num_pts_per_iteration/2)

    #Only take the bins that were excited:
    #good_ind = [frequency.index(i) for i in good_freqs] #Works on lists, not np arrays
    #good_ind = np.where(np.in1d(frequency,good_freqs))

    #This array is actually always the bins based upon the base num periods: [N:N*2-1]
    good_ind = np.arange(multisine_info.num_periods,multisine_info.num_periods*2, dtype=int)

    frequency, s_xy = signal.csd(signal_out, signal_in, fs = 1/sample_time, window = window, nperseg = num_pts_per_iteration, scaling = 'spectrum', noverlap = num_pts_per_iteration/2)

    g_hat_cross_auto = s_xy[good_ind]/s_xx[good_ind]

    mag = 20.0 * np.log10(np.abs(g_hat_cross_auto))
    phase = np.mod(-1*np.angle(g_hat_cross_auto, deg=True),-360.0)

    #Also calculate coherence if we can
    if num_avgs > 1:
        _, coherence = signal.coherence(signal_in, signal_out, fs = 1/sample_time, window=window, nperseg=num_pts_per_iteration, noverlap=num_pts_per_iteration/2)
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

def _calc_multisine_chunk_MIMO_freq_response(dat_file_data:dict, dist_axis:str, collection_axes:list, multisine_info:MultisineInfo, sample_rate:float, window='boxcar', num_avg_limit=None): # pylint: disable=invalid-name, too-many-arguments, too-many-locals
    '''
    Returns a tuple of column vectors of responses corresponding to this disturbance axis in the matrix [dist_axes, collection_axes]
    This tuple of vectors are (frequencies, plant_responses, sensitivity_responses)
    TODO --> Could also calculate and return the complementary_sensitivity_responses and process_sensitivity_responses
    '''
    #Back calculate the disturbance (FrequencyResponseAfter-FrequencyResponseBefore
    this_dist = np.array(dat_file_data['ContEffort'+dist_axis]) - np.array(dat_file_data['Lt_Before'+dist_axis])

    #Determine how many averages there are and if it needs to be limited
    num_avgs = int(np.round(len(this_dist) / multisine_info.num_pts_per_iteration))

    #By default use all of the data
    end_ind = None #if you slice a list [:None], the entire list is returned
    if num_avg_limit is not None:
        if num_avg_limit > num_avgs:
            print('Number of averages limit exceeds the number of averages possible, using all {0} averages.'.format(num_avgs))
        else:
            # take the first section(s) of data:
            end_ind = int(np.round(multisine_info.num_pts_per_iteration * num_avg_limit))
            num_avgs = num_avg_limit

    #Only take the bins that were excited:
    #good_ind = [frequency.index(i) for i in good_freqs] #Works on lists, not np arrays
    #good_ind = np.where(np.in1d(frequency,good_freqs))
    #This array is actually always the bins based upon the base num periods: [N:N*2-1]
    good_ind = np.arange(multisine_info.num_periods, multisine_info.num_periods*2, dtype=int)

    #calculate the Auto of the disturbance? Or should this be the ContEffort of the axis that was disturbed?
    frequency,s_rr = signal.csd(this_dist[:end_ind], this_dist[:end_ind], fs=sample_rate, window=window, nperseg=multisine_info.num_pts_per_iteration, noverlap=multisine_info.num_pts_per_iteration/2, scaling='spectrum')

    #Calculate the cross spectrum of the input to the disturbance
    _,s_ur_dist=signal.csd(this_dist[:end_ind], dat_file_data['ContEffort'+dist_axis][:end_ind], fs=sample_rate, window=window, nperseg=multisine_info.num_pts_per_iteration, noverlap=multisine_info.num_pts_per_iteration/2, scaling='spectrum')

    frequency = frequency[good_ind]
    s_rr = s_rr[good_ind]
    s_ur_dist = s_ur_dist[good_ind]

    #initialize the output to disturbance cross spectrum list
    #s_yr = []
    #s_ur = []
    g_hat = []
    g_hat_coh=[]
    s_hat = []
    s_hat_coh=[]

    #calculate the cross spectrums for all of the collection axes
    for this_ax in collection_axes:
        _,this_s_yr=signal.csd(this_dist[:end_ind], dat_file_data['PosFbk'+this_ax][:end_ind], fs=sample_rate, window=window, nperseg=multisine_info.num_pts_per_iteration, noverlap=multisine_info.num_pts_per_iteration/2, scaling='spectrum')
        _,this_s_ur=signal.csd(this_dist[:end_ind], dat_file_data['ContEffort'+this_ax][:end_ind], fs=sample_rate, window=window, nperseg=multisine_info.num_pts_per_iteration, noverlap=multisine_info.num_pts_per_iteration/2, scaling='spectrum')

        this_s_yr = this_s_yr[good_ind]
        this_s_ur = this_s_ur[good_ind]

        #s_yr.append(this_s_yr)
        #s_ur.append(this_s_ur)

        #Also calculate coherence if we can
        if num_avgs > 1:
            _,this_g_hat_coh = signal.coherence(dat_file_data['ContEffort'+dist_axis][:end_ind], dat_file_data['PosFbk'+this_ax][:end_ind], fs=sample_rate, window=window, nperseg=multisine_info.num_pts_per_iteration, noverlap=multisine_info.num_pts_per_iteration/2)
            _,this_s_hat_coh = signal.coherence(this_dist[:end_ind], dat_file_data['ContEffort'+this_ax][:end_ind], fs=sample_rate, window=window, nperseg=multisine_info.num_pts_per_iteration, noverlap=multisine_info.num_pts_per_iteration/2)
            g_hat_coh.append(this_g_hat_coh[good_ind])
            s_hat_coh.append(this_s_hat_coh[good_ind])

        g_hat.append(this_s_yr/s_ur_dist)
        s_hat.append(this_s_ur/s_rr)

    return (frequency, g_hat, s_hat, g_hat_coh, s_hat_coh)

def analyze_frd_folder_plant(this_run_dir, window='boxcar', num_avg_limit=None, input_var='ContEffort', output_var='PosFbk', input_scale=1.0, output_scale=1.0): # pylint: disable=too-many-locals,too-many-arguments,too-many-branches,too-many-statements
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

    #read in the run information
    config = configparser.ConfigParser()
    config.read(os.path.join(this_run_dir,'ProgramSettings.ini'))
    motion_axes = config['Settings']['motionAxes'].split(',')
    dist_axes = config['Settings']['disturbanceAxes'].split(',')
    collection_axes = config['Settings']['collectionAxes'].split(',')
    num_locations = [int(x) for x in config['Settings']['numLocations'].split(',')]
    amplitudes =  [float(x) for x in config['Settings']['amplitudes'].split(',')]
    start_freq = float(config['Settings']['startFreq'])
    end_freq = float(config['Settings']['endFreq'])
    point_density = int(config['Settings']['pointDensity'])
    #num_avgs = int(config['Settings']['numAvgs'])
    filename_prefix = config['Settings']['filenamePrefix']

    #read in the filenames from the csv file generated in Aeroscript
    log_df = pd.read_csv(os.path.join(this_run_dir, filename_prefix+"_FileLog.csv"))

    #create the location keys to for each axis to filter each location
    location_index_keys = [x+'LocInd' for x in motion_axes]
    #position_keys = [x+'Position' for x in motion_axes]

    #iterate over all locations. This can be done with itertools.product. This allows dynamic nested loops
    for loc_indices in itertools.product(*[range(x) for x in num_locations]):

        this_loc_df = log_df

        #filter down the data frame based on the location
        for index, loc_index in enumerate(loc_indices):
            this_loc_df = this_loc_df[this_loc_df[location_index_keys[index]]==loc_index]

        loc_str = ''.join([ax+str(loc_indices[ind]) for ind, ax in enumerate(motion_axes)])

        #initialize storage terms

        #Loop over each disturbance axis
        for dist_ax_ind, dist_axis in enumerate(dist_axes):
            #using the dataframe, get all of the filenames of this location and disturbance axis
            #filter down the data frame based on the distubance axis
            this_df = this_loc_df[this_loc_df['disturbanceAxisName']==dist_axis]

            #this_df should now only contain this location and this disturbance axes

            #Setup storage dictionary
            responses = {}
            for ax_ind, this_ax in enumerate(collection_axes):
                responses[this_ax] = FrequencyResponseWithCoherence()
                responses[this_ax].start_frequency = start_freq
                responses[this_ax].end_frequency = end_freq
                responses[this_ax].amplitude = amplitudes[dist_ax_ind]
                responses[this_ax].number_of_divisions = point_density
                responses[this_ax].index=ax_ind
                responses[this_ax].axis_name=this_ax

            #Iterate over all of the files to generate the responses chunk by chunk
            for index, row in this_df.iterrows():

                this_filename = os.path.join(this_run_dir, os.path.basename(row['filename']))
                #Calculate the start, end, and spacing based upon the integer values
                this_num_pts = float(row['numPts'])
                this_num_periods = float(row['numPeriods'])
                this_spacing = float(row['sampleRate']) / this_num_pts
                this_start = this_spacing * this_num_periods
                this_end = this_start*2.0-this_spacing
                this_info = MultisineInfo(start_freq=this_start,end_freq=this_end,freq_spacing=this_spacing,num_periods=this_num_periods,num_pts_per_iteration=this_num_pts)

                #load in the data
                this_dat_file = DatFile.create_from_file(this_filename)
                all_data = this_dat_file.all_data
                sample_rate = this_dat_file.sample_rate

                #Process these dat files for each axis that was collected and in the file
                #Loop over each collection axis
                for collection_axis in collection_axes:
                    this_freq, this_mag, this_phase, this_coh = _calc_multisine_chunk_freq_response(np.multiply(all_data[input_var+'{0}'.format(dist_axis)], input_scale), np.multiply(all_data[output_var+'{0}'.format(collection_axis)], output_scale), this_info, 1.0/sample_rate,window,num_avg_limit)

                    this_response = responses[collection_axis]

                    this_response.multisine_signal_parameters.append(this_info)
                    this_response.frequency.extend(this_freq)
                    this_response.magnitude.extend(this_mag)
                    this_response.phase.extend(this_phase)
                    this_response.coherence.extend(this_coh)

            #Now do something with each response...
            #For now just save a plot to file
            for this_ax, this_resp in responses.items():
                fig = plt.figure(figsize=(16,12))
                ax1 = plt.subplot(3, 1, 1)
                # Add the 0 dB line in if it crosses it
                if np.any(np.greater(this_resp.magnitude, 0.0)) and np.any(np.less(this_resp.magnitude, 0.0)):
                    plt.axhline(0.0, color='black')
                plt.semilogx(this_resp.frequency, this_resp.magnitude, label=window)
                plt.grid(which='both')
                plt.xlabel('Frequency [Hz]')
                plt.ylabel('Magnitude [dB]')
                plt.legend()

                plt.subplot(3, 1, 2, sharex=ax1)
                plt.axhline(-180.0, color='black')
                plt.semilogx(this_resp.frequency, this_resp.phase)
                plt.grid(which='both')
                plt.xlabel('Frequency [Hz]')
                plt.ylabel('Phase [deg]')

                plt.subplot(3, 1, 3, sharex=ax1)
                plt.axhline(1.0, color='black')
                plt.semilogx(this_resp.frequency, this_resp.coherence)
                plt.grid(which='both')
                plt.xlabel('Frequency [Hz]')
                plt.ylabel('Coherence')

                plt.suptitle('{0} Fbk / {1} Cur Frequency Response'.format(this_ax,dist_axis))

                ax1.set_xlim([this_resp.frequency[0], this_resp.frequency[-1]])
                plt.tight_layout()

                this_output_name = os.path.join(this_run_dir, '{0}Fbk_{1}Dist_PlantResp_{2}.png'.format(this_ax,dist_axis,loc_str))
                plt.savefig(this_output_name, dpi = 100,transparent=True)

                plt.close(fig)

def analyze_frd_folder(this_run_dir, window='boxcar', num_avg_limit=None): # pylint: disable=too-many-locals,too-many-arguments,too-many-branches,too-many-statements
    '''
    Processes a folder of multisine frequency data and returns a tuple of the frequency, magnitude, phase, and axis

    Input:
        this_run_dir -> Filepath to the directory to process

    Optional Inputs:
        num_avg_limit -> Number of averages to limit the data to

    Output:
        freqs -> Frequency in Hz [list]
        magdB -> Magnitude in dB [list if only one axis, otherwise a dictionary of lists with the key being the axis name]
        phase -> Phase in degrees [list if only one axis, otherwise a dictionary of lists with the key being the axis name]
        axis -> Name of the axis [string if only one axis, otherwise a list of strings of the axis names]
    '''

    #read in the run information
    config = configparser.ConfigParser()
    config.read(os.path.join(this_run_dir,'ProgramSettings.ini'))
    motion_axes = config['Settings']['motionAxes'].split(',')
    dist_axes = config['Settings']['disturbanceAxes'].split(',')
    collection_axes = config['Settings']['collectionAxes'].split(',')
    num_locations = [int(x) for x in config['Settings']['numLocations'].split(',')]
    #amplitudes =  [float(x) for x in config['Settings']['amplitudes'].split(',')]
    #start_freq = float(config['Settings']['startFreq'])
    #end_freq = float(config['Settings']['endFreq'])
    #point_density = int(config['Settings']['pointDensity'])
    #num_avgs = int(config['Settings']['numAvgs'])
    filename_prefix = config['Settings']['filenamePrefix']

    #read in the filenames from the csv file generated in Aeroscript
    log_df = pd.read_csv(os.path.join(this_run_dir, filename_prefix+"_FileLog.csv"))

    #create the location keys to for each axis to filter each location
    location_index_keys = [x+'LocInd' for x in motion_axes]
    #position_keys = [x+'Position' for x in motion_axes]

    #Initialize the data storage array for plant and sensitivity
    #These will be multidimensional [collected_ind,dist_ind,<location_indices>] where <location_indices> is the length of the number of motion_axes

    all_plant_resp = np.empty((len(collection_axes),len(dist_axes))+tuple(num_locations), dtype=FrequencyResponseData)
    all_sens_resp = np.empty((len(collection_axes),len(dist_axes))+tuple(num_locations), dtype=FrequencyResponseData)
    all_plant_resp_coh = np.empty((len(collection_axes),len(dist_axes))+tuple(num_locations), dtype=FrequencyResponseData)
    all_sens_resp_coh = np.empty((len(collection_axes),len(dist_axes))+tuple(num_locations), dtype=FrequencyResponseData)
    all_sens_resp_svd = np.empty(tuple(num_locations), dtype=FrequencyResponseData)

    first_loop = True

    #iterate over all locations. This can be done with itertools.product. This allows dynamic nested loops
    for loc_indices in itertools.product(*[range(x) for x in num_locations]):

        this_loc_df = log_df

        this_loc_matrix = np.empty((len(collection_axes),len(dist_axes)), dtype=object)

        #filter down the data frame based on the location
        for index, loc_index in enumerate(loc_indices):
            this_loc_df = this_loc_df[this_loc_df[location_index_keys[index]]==loc_index]

        #loc_str = ''.join([ax+str(loc_indices[ind]) for ind, ax in enumerate(motion_axes)])

        #Loop over each disturbance axis
        for dist_ax_ind, dist_axis in enumerate(dist_axes):
            #using the dataframe, get all of the filenames of this location and disturbance axis
            #filter down the data frame based on the distubance axis
            this_df = this_loc_df[this_loc_df['disturbanceAxisName']==dist_axis]

            #this_df should now only contain this location and this disturbance axes

            #initialize this entry into the data storage arrays
            for col_ind in range(len(collection_axes)):
                all_plant_resp[(col_ind,dist_ax_ind)+loc_indices] = FrequencyResponseData()
                all_sens_resp[(col_ind,dist_ax_ind)+loc_indices] = FrequencyResponseData(phase_wrap_value_deg=-180.0)
                all_plant_resp_coh[(col_ind,dist_ax_ind)+loc_indices] = FrequencyResponseData()
                all_sens_resp_coh[(col_ind,dist_ax_ind)+loc_indices] = FrequencyResponseData()

            if first_loop:
                frequencies = []

            #Iterate over all of the files to generate the responses chunk by chunk
            for index, row in this_df.iterrows():

                this_filename = os.path.join(this_run_dir, os.path.basename(row['filename']))
                #Calculate the start, end, and spacing based upon the integer values
                this_num_pts = float(row['numPts'])
                this_num_periods = float(row['numPeriods'])
                this_spacing = float(row['sampleRate']) / this_num_pts
                this_start = this_spacing * this_num_periods
                this_end = this_start*2.0-this_spacing
                this_info = MultisineInfo(start_freq=this_start,end_freq=this_end,freq_spacing=this_spacing,num_periods=this_num_periods,num_pts_per_iteration=this_num_pts)

                #load in the data
                this_dat_file = DatFile.create_from_file(this_filename, ignore_cnts_per_unit_sign=True)
                all_data = this_dat_file.all_data
                sample_rate = this_dat_file.sample_rate

                #process the responses
                this_freq, this_plant_col_vect, this_sens_col_vect, this_plant_coh_col_vect, this_sens_coh_col_vect = _calc_multisine_chunk_MIMO_freq_response(all_data, dist_axis, collection_axes, this_info, sample_rate, window, num_avg_limit)

                if first_loop:
                    frequencies.extend(this_freq)

                #Loop over each collection axis
                for col_ind in range(len(collection_axes)):
                    all_plant_resp[(col_ind,dist_ax_ind)+loc_indices].complex=np.append(all_plant_resp[(col_ind,dist_ax_ind)+loc_indices].complex,this_plant_col_vect[col_ind])
                    all_sens_resp[(col_ind,dist_ax_ind)+loc_indices].complex=np.append(all_sens_resp[(col_ind,dist_ax_ind)+loc_indices].complex,this_sens_col_vect[col_ind])
                    all_plant_resp_coh[(col_ind,dist_ax_ind)+loc_indices].complex=np.append(all_plant_resp_coh[(col_ind,dist_ax_ind)+loc_indices].complex,this_plant_coh_col_vect[col_ind])
                    all_sens_resp_coh[(col_ind,dist_ax_ind)+loc_indices].complex=np.append(all_sens_resp_coh[(col_ind,dist_ax_ind)+loc_indices].complex,this_sens_coh_col_vect[col_ind])

            #now loop over this column and add it to this location matrix for singular value calcs
            for col_ind in range(len(collection_axes)):
                this_loc_matrix[col_ind,dist_ax_ind] = all_sens_resp[(col_ind,dist_ax_ind)+loc_indices].complex

            if first_loop:
                # grab the position units of the axes
                unit_names = [this_dat_file.all_unit_name['PosFbk'+x] for x in collection_axes]
                first_loop = False

        #calculate the singular values
        this_loc_matrix_point = np.empty((len(collection_axes),len(dist_axes)), dtype=complex)
        all_sens_resp_svd[loc_indices] = FrequencyResponseData()
        for ind in range(len(this_loc_matrix[0,0])):
            for dist_ax_ind, dist_axis in enumerate(dist_axes):
                for col_ind in range(len(collection_axes)):
                    this_loc_matrix_point[col_ind,dist_ax_ind] = this_loc_matrix[col_ind,dist_ax_ind][ind]
            this_svd = np.linalg.svd(this_loc_matrix_point,compute_uv=False)
            all_sens_resp_svd[loc_indices].complex = np.append(all_sens_resp_svd[loc_indices].complex,complex(np.max(this_svd)))

    #initialize arrays to store the average values for now to make bold
    plant_resp_avg = np.empty((len(collection_axes),len(dist_axes)), dtype=FrequencyResponseData)
    sens_resp_avg = np.empty((len(collection_axes),len(dist_axes)), dtype=FrequencyResponseData)
    plant_resp_coh_avg = np.empty((len(collection_axes),len(dist_axes)), dtype=FrequencyResponseData)
    sens_resp_coh_avg = np.empty((len(collection_axes),len(dist_axes)), dtype=FrequencyResponseData)

    #Loop over the response matrix and calculate the averages
    for row_ind in range(len(collection_axes)):
        for col_ind in range(len(dist_axes)):
            plant_resp_avg[row_ind,col_ind] = FrequencyResponseData(np.mean([all_plant_resp[row_ind,col_ind][loc_indices].complex for loc_indices in itertools.product(*[range(x) for x in np.shape(all_plant_resp[row_ind,col_ind])])],0))
            sens_resp_avg[row_ind,col_ind] = FrequencyResponseData(np.mean([all_sens_resp[row_ind,col_ind][loc_indices].complex for loc_indices in itertools.product(*[range(x) for x in np.shape(all_sens_resp[row_ind,col_ind])])],0), phase_wrap_value_deg=-180.0)
            plant_resp_coh_avg[row_ind,col_ind] = FrequencyResponseData(np.mean([all_plant_resp_coh[row_ind,col_ind][loc_indices].complex for loc_indices in itertools.product(*[range(x) for x in np.shape(all_plant_resp_coh[row_ind,col_ind])])],0))
            sens_resp_coh_avg[row_ind,col_ind] = FrequencyResponseData(np.mean([all_sens_resp_coh[row_ind,col_ind][loc_indices].complex for loc_indices in itertools.product(*[range(x) for x in np.shape(all_sens_resp_coh[row_ind,col_ind])])],0))

    #Loop over the locations and calculate the worst singular value
    max_sens_resp_svd = FrequencyResponseData()
    for ind in range(len(this_loc_matrix[0,0])):
        max_sens_resp_svd.complex=np.append(max_sens_resp_svd.complex,np.max([all_sens_resp_svd[loc_indices].complex[ind] for loc_indices in itertools.product(*[range(x) for x in num_locations])]))

    frequencies = np.array(frequencies)

    print('Finished Processing Data!')

    #Now plot everything
    #create a subplot of responses of num_collection_ax by num_dist_ax
    plant_fig = plt.figure(figsize=(16,9))
    sens_fig = plt.figure(figsize=(16,9))
    plant_outer = plant_fig.add_gridspec(len(dist_axes),len(collection_axes),hspace=0.25)
    sens_outer = sens_fig.add_gridspec(len(dist_axes),len(collection_axes),hspace=0.25)

    plant_coh_fig = plt.figure(figsize=(16,9))
    sens_coh_fig = plt.figure(figsize=(16,9))
    plant_coh_outer = plant_coh_fig.add_gridspec(len(dist_axes),len(collection_axes),hspace=0.25)
    sens_coh_outer = sens_coh_fig.add_gridspec(len(dist_axes),len(collection_axes),hspace=0.25)

    #loop over each input
    for col_ind, this_dist_ax in enumerate(dist_axes):
        #loop over each output
        for row_ind, this_col_ax in enumerate(collection_axes):
            #Setup the plant response
            plant_inner = plant_outer[row_ind, col_ind].subgridspec(2,1,hspace=0.25)
            plant_ax1 = plt.Subplot(plant_fig, plant_inner[0])
            plant_ax2 = plt.Subplot(plant_fig, plant_inner[1],sharex=plant_ax1)

            plant_ax2.axhline(-180, color='k')

            #Now do the sensitivity response
            sens_inner = sens_outer[row_ind, col_ind].subgridspec(2,1,hspace=0.25)
            sens_ax1 = plt.Subplot(sens_fig, sens_inner[0])
            sens_ax2 = plt.Subplot(sens_fig, sens_inner[1],sharex=sens_ax1)

            this_plant_coh_outer = plant_coh_fig.add_subplot(plant_coh_outer[row_ind, col_ind])
            this_sens_coh_outer = sens_coh_fig.add_subplot(sens_coh_outer[row_ind, col_ind])

            #loop over each location
            for loc_indices in itertools.product(*[range(x) for x in np.shape(all_plant_resp[row_ind,col_ind])]):
                plant_ax1.loglog(frequencies,all_plant_resp[row_ind,col_ind][loc_indices].mag,color='b',alpha=0.1)
                plant_ax2.semilogx(frequencies,all_plant_resp[row_ind,col_ind][loc_indices].phase_deg,color='b',alpha=0.1)

                sens_ax1.semilogx(frequencies,all_sens_resp[row_ind,col_ind][loc_indices].mag_dB,color='b',alpha=0.1)
                sens_ax2.semilogx(frequencies,all_sens_resp[row_ind,col_ind][loc_indices].phase_deg,color='b',alpha=0.1)


                this_plant_coh_outer.semilogx(frequencies,all_plant_resp_coh[row_ind,col_ind][loc_indices].mag,color='b',alpha=0.1)
                this_sens_coh_outer.semilogx(frequencies,all_sens_resp_coh[row_ind,col_ind][loc_indices].mag,color='b',alpha=0.1)


            plant_ax1.loglog(frequencies,plant_resp_avg[row_ind,col_ind].mag,color='k')
            plant_ax2.semilogx(frequencies,plant_resp_avg[row_ind,col_ind].phase_deg,color='k')

            plant_ax1.grid()
            plant_ax2.grid()

            sens_ax1.semilogx(frequencies,sens_resp_avg[row_ind,col_ind].mag_dB,color='k')
            sens_ax2.semilogx(frequencies,sens_resp_avg[row_ind,col_ind].phase_deg,color='k')
            sens_ax1.grid()
            sens_ax2.grid()

            this_plant_coh_outer.semilogx(frequencies,plant_resp_coh_avg[row_ind,col_ind].mag,color='k')
            this_sens_coh_outer.semilogx(frequencies,sens_resp_coh_avg[row_ind,col_ind].mag,color='k')

            if col_ind == 0:
                #add add a row title and units to the Y axes on the left most plots (first column)
                x_offset=-0.3

                coords = plant_ax1.transAxes.inverted().transform((plant_ax1.transAxes.transform((x_offset,0.5))+plant_ax2.transAxes.transform((x_offset,0.5)))/2.0)
                plant_ax1.text(coords[0],coords[1],'To '+this_col_ax+' Feedback',transform=plant_ax1.transAxes,fontsize=14,rotation='vertical',ha='center',va='center')
                plant_ax1.set_ylabel('Mag ['+unit_names[row_ind]+'/A]')
                plant_ax2.set_ylabel('Phase [deg]')

                coords = sens_ax1.transAxes.inverted().transform((sens_ax1.transAxes.transform((x_offset,0.5))+sens_ax2.transAxes.transform((x_offset,0.5)))/2.0)
                sens_ax1.text(coords[0],coords[1],'To '+this_col_ax+' Feedback',transform=sens_ax1.transAxes,fontsize=14,rotation='vertical',ha='center',va='center')
                sens_ax1.set_ylabel('Mag [dB]')
                sens_ax2.set_ylabel('Phase [deg]')

                this_plant_coh_outer.set_ylabel('To '+this_col_ax+' Feedback\nMag')
                this_sens_coh_outer.set_ylabel('To '+this_col_ax+' Feedback\nMag')

            if row_ind == 0:
                #add title to show which axis was excited at the top (first row)
                plant_ax1.set_title('From '+this_dist_ax+' Excitation',fontsize=14)
                sens_ax1.set_title('From '+this_dist_ax+' Excitation',fontsize=14)
                this_plant_coh_outer.set_title('From '+this_dist_ax+' Excitation',fontsize=14)
                this_sens_coh_outer.set_title('From '+this_dist_ax+' Excitation',fontsize=14)

            if row_ind == len(collection_axes)-1:
                #add units to the X axes on the bottom most plots (last row)
                plant_ax2.set_xlabel('Frequency [Hz]')
                sens_ax2.set_xlabel('Frequency [Hz]')
                this_plant_coh_outer.set_xlabel('Frequency [Hz]')
                this_sens_coh_outer.set_xlabel('Frequency [Hz]')

            #surpress the frequency tick labels on the magnitude plot
            plt.setp(plant_ax1.get_xticklabels(),visible=False)
            plt.setp(sens_ax1.get_xticklabels(),visible=False)

            plant_fig.add_subplot(plant_ax1)
            plant_fig.add_subplot(plant_ax2)

            sens_fig.add_subplot(sens_ax1)
            sens_fig.add_subplot(sens_ax2)

    plant_fig.suptitle('Plant Response Matrix')
    sens_fig.suptitle('Sensitivity Response Matrix')
    plant_coh_fig.suptitle('Plant Coherence Matrix')
    sens_coh_fig.suptitle('Sensitivity Coherence Matrix')
    plant_fig.savefig(os.path.join(this_run_dir, 'PlantResponse.png'),dpi = 100,transparent=True)
    sens_fig.savefig(os.path.join(this_run_dir, 'SensitivityResponse.png'),dpi = 100,transparent=True)
    plant_coh_fig.savefig(os.path.join(this_run_dir, 'PlantCoherence.png'),dpi = 100,transparent=True)
    sens_coh_fig.savefig(os.path.join(this_run_dir, 'SensitivityCoherence.png'),dpi = 100,transparent=True)

    #Now plots the singular values of the sensitivity response
    sens_svd_fig=plt.figure(figsize=(16,9))
    plt.axhline(0.0,color='k')

    for loc_indices in itertools.product(*[range(x) for x in num_locations]):
        plt.semilogx(frequencies,all_sens_resp_svd[loc_indices].mag_dB,color='b',alpha=0.1)

    plt.semilogx(frequencies,max_sens_resp_svd.mag_dB,color='k')
    plt.grid()
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('Magnitude [dB]')
    plt.title('Sensitivity Max Singular Values')

    sens_svd_fig.savefig(os.path.join(this_run_dir, 'SensitivitySVResponse.png'),dpi = 100,transparent=True)


    plt.show()

    return frequencies,all_plant_resp,all_sens_resp,plant_resp_avg,sens_resp_avg, all_sens_resp_svd

if __name__ == '__main__':

    #THIS_DATA_FOLDER = r'O:\MRG\A1 MIMO System ID\AGS15000_AppsLab\20211207\FRD_AGS15000_4Avg_3x3'
    THIS_DATA_FOLDER = r'O:\MRG\A1 MIMO System ID\PlanarHD\20211208\4Avg'
    #THIS_DATA_FOLDER = r'O:\MRG\A1 MIMO System ID\PlanarHD\20211208\4Avg_5x5'

    FREQ,PLANT,SENS,PLANT_AVG,SENS_AVG,SENS_SVD=analyze_frd_folder(THIS_DATA_FOLDER,window='hann')
