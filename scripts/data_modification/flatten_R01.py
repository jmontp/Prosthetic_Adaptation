
import h5py
import numpy as np
import pandas as pd
from pandas import DataFrame
import threading
from functools import lru_cache
import os
from scipy.io import loadmat


#TODO - verify if I can delete this function since I think its not neccesary
def get_column_name(column_string_list, num_last_keys):
    filter_strings = ['right', 'left']
    filtered_list = filter(
        lambda x: not x in filter_strings, column_string_list)
    column_string = '_'.join(filtered_list)
    return column_string



def get_end_points_R01(d,out_dict,parent_key='', sep='/',num_last_keys=2):


    # Tree traversal
    for k,v in d.items():

        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v,h5py._hl.group.Group):
            get_end_points_R01(v,out_dict,new_key,sep=sep)

        # Where the magic happens when you reach an end point
        else:
            column_string_list = (parent_key+sep+k).split(sep)[-num_last_keys:]
            column_string = get_column_name(column_string_list,num_last_keys)
            
            str_dict = {0:'x',1:'y',2:'z',3:'e'}

            if 'event' not in column_string and 'LHS' not in column_string and 'RHS' not in column_string and 'cvel' not in column_string:


                #If you have only one stride then it is converted into a 2D array
                # Turn it into a 3d array
                if len(v.shape) == 1:
                    v = v[:].reshape(1,1,v.shape[0])

                if len(v.shape) == 2:
                    v = v[:,:].reshape(1,v.shape[0],v.shape[1])

                # Verify if we have a 3D matrix. If we do, we need to break it down
                for i in range(v.shape[1]):
                    column_string_prepended = column_string+"_"+str_dict[i]
                    v_curr = v[:,i,:].ravel()
                    if (column_string_prepended not in out_dict):
                        out_dict[column_string_prepended] = [[new_key+"_"+str_dict[i]],[v_curr]]
                    else:
                        out_dict[column_string_prepended][0].append(new_key+"_"+str_dict[i])
                        out_dict[column_string_prepended][1].append(v_curr)  
             

            # elif(len(v.shape)>1):   
            #     print(f'{v.name} shape {v.shape}')
            #     if (column_string not in out_dict):
            #         out_dict[column_string] = [[new_key],[v]]
            #     else:
            #         out_dict[column_string][0].append(new_key)
            #         out_dict[column_string][1].append(v)
            # else:
            #     pass


def skip_column(column_name):
    
    if('subjectdetails' in column_name or\
        'CutPoint' in column_name or\
        'description' in column_name or\
        '_ParticipantDetails' in column_name or\
        'events' in column_name or \
        # 'Stair' in column_name or \
        # 'Sts' in column_name or\
        'velProf' in column_name or\
        'VelProf' in column_name):

        return True

    else:
        return False
        

def downsample_forceplates(columns_to_endpoint_dict):
    """
    This function will downsample everything with a forceplate from 
    1kHz to 100Hz
    """
    #Do the same for all the endpoint lists
    for feature_list in columns_to_endpoint_dict.values():
        #Traverse through all the end-point names
        for i,key in enumerate(feature_list[0]):
            #If they have forceplate in the name, trim the data
            if "forceplate" in key:
                #The first index corresponds to the data at that end point
                feature_list[1][i] = feature_list[1][i][::10]


def add_nan_padding(columns_to_endpoint_dict):
    """
    This function will add nan to values to fill the 
    gaps when a feature does not have an experiment

    Example, joint angles do not appear in stairs (I think)
    """


    #Do a double for loop to compare all the values with one another
    for column_name_1, column_endpoint_list_1 in columns_to_endpoint_dict.items():
        #Filter based on the endpoint name
        if skip_column(column_name_1):
            continue

        for column_name_2, column_endpoint_list_2 in columns_to_endpoint_dict.items():
            
            #Filter based on the endpoint name
            if skip_column(column_name_2):
                continue

            #Create two dictionaries to analyze if there are missing elements in each
            dict_1 = {'/'.join(path_name.split('/')[:-2]) : path_dataset for path_name, path_dataset in zip(*column_endpoint_list_1)}
            dict_2 = {'/'.join(path_name.split('/')[:-2]) : path_dataset for path_name, path_dataset in zip(*column_endpoint_list_2)}

            #Get feature 2's name so that we can add it to the endpoint list
            feature_1_name = '/'.join(column_endpoint_list_1[0][0].split('/')[-2:])    

            #For every feature in dictionary 1, verify if it is in dictionary 2
            for key_2 in dict_2:

                if skip_column(key_2):
                    continue

                try:
                        dict_1[key_2]
                
                #If you don't have the key, then add it
                except KeyError as e:
                    #print(f"{column_name_1} did not have key {key_2} relative to {column_name_2}")

                    #Add the endpoint name
                    new_endpoint_name = key_2 + '/' + feature_1_name
                    column_endpoint_list_1[0].append(new_endpoint_name)

                    #Add an empty dataset that matches the rest of the datasets
                    nan_array = np.empty(dict_2[key_2].shape)
                    nan_array[:] = np.nan
                    column_endpoint_list_1[1].append(nan_array)


def add_experiment_info(random_endpoint_list, df):
        """
        This function will add information stored in the trial name
        to the pandas dataframe
        """
        
        ## Add task information 
        sorted_random_endpoint_list =  [(y,x.shape[0]) for y,x in sorted(zip(*random_endpoint_list),
                #Sort by the experiment. (Subtract the column name)
                key=lambda pair: '/'.join(pair[0].split('/')[:-2]))]

        #Initialize vector information
        type_vector = []
        speed_vector = []
        incline_vector = []
        time_vector = []
        
        for experiment_name, experiment_num_rows in sorted_random_endpoint_list:
            
            #Split the string to get the different parts
            experiment_content = experiment_name.split('/')
            
            #The first entry has the ambulation mode
            experiment_type = experiment_content[0]
            #The second entry contains info about the trial
            experiment_info = experiment_content[1]

            #Get the experiment type vector
            experiment_type_vector = [experiment_type]*experiment_num_rows

            #Get the experiment type vector
            dt = 1.0/100.0
            experiment_time_vector = [dt*i for i in range(experiment_num_rows)]

            #Handle every experiment type 
            if(experiment_type == 'Run'):
                
                #Running incline is always 0                
                experiment_incline_vector = [0]*experiment_num_rows
                
                #Get running speed
                speed = float(experiment_info[1:].replace('x','.'))
                experiment_speed_vector = [speed]*experiment_num_rows


            elif(experiment_type == 'Stair'):
                
                #Get incline from experiment info
                incline_deg_string, incline_number_string = experiment_info.split('_')
                
                #For the experiment number odd is ascent. Even, descent
                incline_sign = 1 if int(incline_number_string)%2 == 0 else -1
                #The degrees are in the second and third positions
                incline_deg = float(incline_deg_string[1:2])
                #Create the incline vector for this experiment
                experiment_incline_vector = [incline_sign*incline_deg]*experiment_num_rows

                #The walking speed is user selected and not specified
                experiment_speed_vector = [np.nan]*experiment_num_rows

            elif(experiment_type == 'Sts'):

                #There is no speed or incline in sit to stand
                experiment_incline_vector = [np.nan]*experiment_num_rows
                experiment_speed_vector = [np.nan]*experiment_num_rows

            elif(experiment_type == 'Tread'):
                
                #The walking speed is set at random based on the protocol
                experiment_speed_vector = [np.nan]*experiment_num_rows

                #The incline is specified in experiment info
                incline_sign = 1 if experiment_info[0] == 'i' else -1
                incline_deg = float(experiment_info[1:])
                experiment_incline_vector = [incline_sign*incline_deg]*experiment_num_rows

            elif(experiment_type == 'Wtr'):

                #There is no speed or incline in walk to run
                experiment_incline_vector = [np.nan]*experiment_num_rows
                experiment_speed_vector = [np.nan]*experiment_num_rows
            else:
                raise ValueError(f"Experiment Type not recognized: {experiment_type}")

            #Add all the info for the experiment
            type_vector.extend(experiment_type_vector)
            speed_vector.extend(experiment_speed_vector)
            incline_vector.extend(experiment_incline_vector)
            time_vector.extend(experiment_time_vector)


        df['ambulationMode'] = type_vector
        df['inclineDeg'] = incline_deg
        df['speed'] = speed_vector
        df['time'] = time_vector


        ### Add time information
        df['dt'] = 1.0/100.0


#This is the main function that will perform the flattening
# Only works for streaming right now
def flatten_r01_normalized():

    #Determine the dataset that you want to use
    dataset = 'Streaming'

    #Get the file
    file_name = f'../../data/r01_dataset/{dataset}.mat'
    h5py_file = h5py.File(file_name)[dataset]

    # Iterate through all the subjects, make a file per subject to keep it RAM bound
    for subject in h5py_file.keys():
        
        #Create the name to save to
        save_name = f'../../data/r01_dataset/r01_{dataset}_flattened_{subject}.parquet'
        # save_name = f'r01_flattened_{subject}.parquet'   

        print("Flattening subject: " + subject)

        #Get the data for the subject
        data = h5py_file[subject]

        # Obtain the names and references to the data for 
        # each end point
        columns_to_endpoint_dict = {}
        get_end_points_R01(data, columns_to_endpoint_dict)

        #If we are doing Streaming dataset, we need to downsample the 
        #force plates as they have have 1kHz sampling vs everything 
        # else has 100Hz
        if 'Streaming' in file_name:
            downsample_forceplates(columns_to_endpoint_dict)


        #Some features do not have data for all the trials. This will
        # through the alignment of the flattened version out. 
        # Create numpy arrays with NaN values such that all features match
        add_nan_padding(columns_to_endpoint_dict)
       

        # Create the pandas dataframe to store all the info
        df = DataFrame()

        #Save one list so that we can add task information
        random_endpoint_list = None
        #Concatenate all the information
        for column_name, endpoint_list in columns_to_endpoint_dict.items():

            #Filter based on the endpoint name
            if skip_column(column_name):
                continue
            
            #Save an endpoint list so that we can extract information 
            # from the name
            if random_endpoint_list is None:
                random_endpoint_list = endpoint_list

            # Since everyone has the same end-points, make sure that they are sorted properly
            # Sort only using the endpoint name. Only keep the dataset
            sorted_end_point_list = [x for _,x in sorted(zip(*endpoint_list),
                #Sort by the experiment. (Subtract the column name)
                key=lambda pair: '/'.join(pair[0].split('/')[:-2]))]

            # Get the data to add it to a dataframe
            data_array = np.concatenate(sorted_end_point_list, axis=0).flatten()

            #Add data array to the column
            df[column_name] = data_array

        #Add experiment information such as ambulation mode, speed, and incline
        add_experiment_info(random_endpoint_list,df)

        #Save to parquet file
        abs_save_name = os.path.abspath(save_name)
        print(f"Saving in {abs_save_name}")
        df.to_parquet(path = abs_save_name)


        
 

#%%

#%%
# def get_endpoints_AY():
#     pass
#     #%%
#     substrings = ['ik','conditions']
#     #Get all the directories that match substrings
#     end_points = [directory for directory in os.walk('local-storage/AY-dataset/') if any([sub in directory[0] for sub in substrings])]
    
#     #f = loadmat(end_points[0][0] +"/" + end_points[0][2][0]) 
#     f = pd.read_parquet('local-storage/AY-dataset/AB06/10_09_18/levelground/ik/AY_AB06_test.par') 

    
    #Remove Nones from the list 
    
# #%%
# import matlab.engine
# eng = matlab.engine.start_matlab()
# #%%
# def convert_mat_to_parquet(mat):
   
#     mat_file = eng.load(mat)
#     new_file_name = mat + ".parquet"
#     eng.parquetwrite(new_file_name,mat_file['data'],nargout=0)
    
#%%
if __name__ == '__main__':
    pass
    flatten_r01_normalized()
    # determine_different_strides()

