#==================================================================================================================================
# Copyright (c) 2017 - 2018 Stephen Copplestone and Matthias Sonntag
#
# This file is part of reggie2.0 (gitlab.com/reggie2.0/reggie2.0). reggie2.0 is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version.
#
# reggie2.0 is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License v3.0 for more details.
#
# You should have received a copy of the GNU General Public License along with reggie2.0. If not, see <http://www.gnu.org/licenses/>.
#==================================================================================================================================
from __future__ import print_function # required for print() function with line break via "end=' '"
import os
import numpy as np
from externalcommand import ExternalCommand
import analyze_functions
import combinations 
import tools
import csv
import re
import logging
import glob
import shutil

# import h5 I/O routines
try :
    import h5py
    h5py_module_loaded = True
except ImportError :
    #raise ImportError('Could not import h5py module. This is required for anaylze functions.')
    print(tools.red('Could not import h5py module. This is required for anaylze functions.'))
    h5py_module_loaded = False

# import pyplot for creating plots
try :
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator # required for setting axis format to integer only (p-convergence)
    pyplot_module_loaded = True # will be set false if user does not supply read-in flag in getAnalyzes(path, example) function
except ImportError :
    #raise ImportError('Could not import matplotlib.pyplot module. This is required for anaylze functions.')
    print(tools.red('Could not import matplotlib.pyplot module. This is required for anaylze functions.'))
    pyplot_module_loaded = False

def displayTable(mylist,nVar,nRuns) :
    # mylist = [ [1 2 3] [1 2 3] [1 2 3] [1 2 3] ] example with 4 nVar and 3 nRuns
    print(" nRun   "+"   ".join(7*" "+"nVar=["+str(i).rjust(4)+"]" for i in range(nVar)))
    for j in range(nRuns) :
        print(str(j).rjust(5), end=' ') # skip linebreak
        for i in range(nVar) :
            print("%20.12e" % mylist[i][j], end=' ') # skip linebreak
        print("")

def writeTableToFile(mylist,nVar,nRuns,firstColumn,path,name) :
    # if a path is supplied, create a .csv file with the data
    if path is not None :
        myfile = os.path.join(path,name)
        with open(myfile, 'w') as f :
            for j in range(nRuns) :
                line  = "%20.12e, " % firstColumn[j]
                line += ",".join("%20.12e" % mylist[i][j] for i in range(nVar))
                f.write(line+"\n")

def displayVector(vector,nVar) :
    print(8*" "+"   ".join(7*" "+"nVar=["+str(i).rjust(4)+"]" for i in range(nVar)))
    print(6*" "+" ".join("%20.12e" % vector[i] for i in range(nVar)))

# Copy new reference file: This is completely independent of the outcome of the current compare data file
def copyReferenceFile(run,path,path_ref_source) :
    shutil.copy(path,path_ref_source)
    s = tools.red("New reference files are copied from file=[%s] to file=[%s]" % (path, path_ref_source))
    print(s)
    run.analyze_results.append(s)
    run.analyze_successful=False
    return run

#==================================================================================================

def getAnalyzes(path, example, args) :
    global pyplot_module_loaded
    """For every example a list of analyzes is built from the specified anaylzes in 'analyze.ini'. 
    The anaylze list is performed after a set of runs is completed.

     General workflow:
     1.  Read the analyze options from file 'path' into dict 'options'
     1.1   Check for general analyze options
     2.  Initialize analyze functions
     2.0   L2 error from file
     2.1   L2 error upper limit
     2.2   h-convergence test
     2.3   p-convergence test
     2.4   t-convergence test
     2.5   h5diff (relative or absolute HDF5-file comparison of an output file with a reference file)
     2.6   check array bounds in hdf5 file
     2.7   check data file row
     2.8   integrate data file column
    """

    # 1.  Read the analyze options from file 'path'
    analyze = [] # list
    options_list, _, _ = combinations.readKeyValueFile(path)
    
    options = {} # dict
    for option in options_list :
        # set all upper case characters to lower case
        if len(option.values) > 1 :
            options[option.name.lower()] = option.values    # set name to lower case
        else :
            options[option.name.lower()] = option.values[0] # set name to lower case

        # check for empty lists and abort
        if option.values[0]=='' :
            raise Exception(tools.red("initialization of analyze.ini failed due to empty parameter [%s = %s], which is not allowed." % (option.name,option.values) ))

    # 1.1   Check for general analyze options
    # only use matplot lib if the user wants to (can cause problems on some systems causing "system call itnerrupt" errors randomly aborting the program)
    use_matplot_lib = options.get('use_matplot_lib','False')
    if pyplot_module_loaded :
        if use_matplot_lib in ('True', 'true', 't', 'T') :
            pyplot_module_loaded = True
        else :
            pyplot_module_loaded = False 

    # 1.3 Get the names of the files (incl. wildcards) which are to be deleted in the anaylsis stage
    clean_up_files = options.get('clean_up_files',None)
    if clean_up_files :
        analyze.append(Clean_up_files(clean_up_files))

    # 2.0   L2 error from file
    L2_file                =       options.get('analyze_l2_file',None)
    L2_file_tolerance      = float(options.get('analyze_l2_file_tolerance',1.0e-5))
    L2_file_tolerance_type =       options.get('analyze_l2_file_tolerance_type','absolute')
    L2_file_error_name     =       options.get('L2_file_error_name','L_2')
    if L2_file :
        if L2_file_tolerance_type in ('absolute', 'delta', '--delta') :
            L2_file_tolerance_type = "absolute"
        elif L2_file_tolerance_type in ('relative', "--relative") :
            L2_file_tolerance_type = "relative"
        else :
            raise Exception(tools.red("initialization of L2 error from file failed. [L2_file_tolerance_type = %s] not accepted." % L2_file_tolerance_type))
        analyze.append(Analyze_L2_file(L2_file_error_name, L2_file, L2_file_tolerance, L2_file_tolerance_type))

    # 2.1   L2 error upper limit
    L2_tolerance  = float(options.get('analyze_l2',-1.))
    L2_error_name =       options.get('L2_error_name','L_2')
    if L2_tolerance > 0 :
        analyze.append(Analyze_L2(L2_error_name,L2_tolerance))
    
    # 2.2   h-convergence test
    convtest_h_cells      = [float(cell) for cell in options.get('analyze_convtest_h_cells',['-1.'])]
    convtest_h_tolerance  = float(options.get('analyze_convtest_h_tolerance',1e-2))
    convtest_h_rate       = float(options.get('analyze_convtest_h_rate',1))
    convtest_h_error_name =       options.get('analyze_convtest_h_error_name','L_2')
    # only do convergence test if supplied cells count > 0
    if min(convtest_h_cells) > 0 and convtest_h_tolerance > 0 and 0.0 <= convtest_h_rate <= 1.0:
        analyze.append(Analyze_Convtest_h(convtest_h_error_name, convtest_h_cells, convtest_h_tolerance, convtest_h_rate))

    # 2.3   p-convergence test
    #convtest_p_tolerance = float(options.get('analyze_convtest_p_tolerance',1e-2))
    convtest_p_rate       = float(options.get('analyze_convtest_p_rate',-1))
    convtest_p_percentage = float(options.get('analyze_convtest_p_percentage',0.75))
    convtest_p_error_name = options.get('analyze_convtest_p_error_name','L_2')
    # only do convergence test if convergence rate and tolerance >0
    if 0.0 <= convtest_p_rate <= 1.0:
        analyze.append(Analyze_Convtest_p(convtest_p_error_name,convtest_p_rate, convtest_p_percentage))

    # 2.4   t-convergence test
    # One of the four following methods can be used. The sequence is of selection is fixed

    # set default values
    convtest_t_initial_timestep = None
    convtest_t_timestep_factor  = [-1.]
    convtest_t_total_timesteps  = None
    convtest_t_timesteps       = [-1.]

    # 2.4.1   must have the following form: "Initial Timestep  :    1.8503722E-01"
    convtest_t_initial_timestep = options.get('analyze_convtest_t_initial_timestep',None)

    if convtest_t_initial_timestep is None :
        # 2.4.2   supply the timestep_factor externally
        convtest_t_timestep_factor         = [float(timestep) for timestep in options.get('analyze_convtest_t_timestep_factor',['-1.'])]

        if min(convtest_t_timestep_factor) <= 0.0 :
            # 2.4.3   automatically get the total number of timesteps must have the following form: "#Timesteps :    1.6600000E+02"
            convtest_t_total_timesteps   = options.get('analyze_convtest_t_total_timesteps',None)
            
            if convtest_t_total_timesteps is None :
                # 2.4.4   supply the timesteps externally
                convtest_t_timesteps       = [float(timesteps) for timesteps in options.get('analyze_convtest_t_timesteps',['-1.'])]
                if min(convtest_t_timesteps) <= 0.0 :
                    convtest_t_method = 0
                    convtest_t_name = None
                else :
                    convtest_t_method = 4
                    convtest_t_name   = 'timesteps from analyze.ini'
            else :
                convtest_t_method = 3
                convtest_t_name   = 'total number of timesteps ['+convtest_t_total_timesteps+']'
        else :
            convtest_t_method = 2
            convtest_t_name   = 'timestep_factor from analyze.ini'
    else :
        convtest_t_method = 1
        convtest_t_name   = 'initial_timestep ['+convtest_t_initial_timestep+']'

    convtest_t_tolerance  = float(options.get('analyze_convtest_t_tolerance',1e-2))
    convtest_t_rate       = float(options.get('analyze_convtest_t_rate',1))
    convtest_t_error_name =       options.get('analyze_convtest_t_error_name','L_2')
    convtest_t_order      = float(options.get('analyze_convtest_t_order',-1000))
    # only do convergence test if supplied cells count > 0
    if convtest_t_tolerance > 0 and 0.0 <= convtest_t_rate <= 1.0 and convtest_t_name and convtest_t_order > -1000:
        logging.getLogger('logger').info("t-convergence test: Choosing "+convtest_t_name+" (method = "+str(convtest_t_method)+")")
        analyze.append(Analyze_Convtest_t(convtest_t_order, convtest_t_error_name, convtest_t_tolerance, convtest_t_rate, convtest_t_method, convtest_t_name, convtest_t_initial_timestep, convtest_t_timestep_factor, convtest_t_total_timesteps, convtest_t_timesteps))

    # 2.5   h5diff (relative or absolute HDF5-file comparison of an output file with a reference file) 
    # options can be read in multiple times to realize multiple compares for each run
    h5diff_one_diff_per_run = options.get('h5diff_one_diff_per_run',False)
    h5diff_reference_file   = options.get('h5diff_reference_file',None)
    h5diff_file             = options.get('h5diff_file',None)
    h5diff_data_set         = options.get('h5diff_data_set',None)
    h5diff_tolerance_value  = options.get('h5diff_tolerance_value',1.0e-5)
    h5diff_tolerance_type   = options.get('h5diff_tolerance_type','absolute')
    # only do h5diff test if all variables are defined
    if h5diff_reference_file and h5diff_file and h5diff_data_set :
        analyze.append(Analyze_h5diff(h5diff_one_diff_per_run,h5diff_reference_file, h5diff_file,h5diff_data_set, h5diff_tolerance_value, h5diff_tolerance_type, args.referencescopy))

    # 2.6   check array bounds in hdf5 file
    check_hdf5_file      = options.get('check_hdf5_file',None) 
    check_hdf5_data_set  = options.get('check_hdf5_data_set',None) 
    check_hdf5_dimension = options.get('check_hdf5_dimension',None) 
    check_hdf5_limits    = options.get('check_hdf5_limits',None) 
    if all([check_hdf5_file, check_hdf5_data_set, check_hdf5_dimension, check_hdf5_limits]) :
        analyze.append(Analyze_check_hdf5(check_hdf5_file, check_hdf5_data_set, check_hdf5_dimension, check_hdf5_limits))

    # 2.7   check data file row
    compare_data_file_name           = options.get('compare_data_file_name',None)
    compare_data_file_reference      = options.get('compare_data_file_reference',None)
    compare_data_file_tolerance      = options.get('compare_data_file_tolerance',None)
    compare_data_file_tolerance_type = options.get('compare_data_file_tolerance_type','absolute')
    compare_data_file_line           = options.get('compare_data_file_line','last')
    compare_data_file_delimiter      = options.get('compare_data_file_delimiter',',')
    if all([compare_data_file_name, compare_data_file_reference, compare_data_file_tolerance, compare_data_file_line]) :
        if compare_data_file_tolerance_type in ('absolute', 'delta', '--delta') :
            compare_data_file_tolerance_type = "absolute"
        elif compare_data_file_tolerance_type in ('relative', "--relative") :
            compare_data_file_tolerance_type = "relative"
        else :
            raise Exception(tools.red("initialization of compare data file failed. h5diff_tolerance_type '%s' not accepted." % h5diff_tolerance_type))
        analyze.append(Analyze_compare_data_file(compare_data_file_name, compare_data_file_reference, compare_data_file_tolerance, compare_data_file_line, compare_data_file_delimiter, compare_data_file_tolerance_type, args.referencescopy))

    # 2.8   integrate data file column
    integrate_line_file            = options.get('integrate_line_file',None)                 # file name (path) which is analyzed
    integrate_line_delimiter       = options.get('integrate_line_delimiter',',')             # delimter symbol if not comma-separated
    integrate_line_columns         = options.get('integrate_line_columns',None)              # two columns for the values x and y supplied as 'x:y'
    integrate_line_integral_value  = options.get('integrate_line_integral_value',None)       # integral value used for comparison
    integrate_line_tolerance_value = options.get('integrate_line_tolerance_value',1e-5)      # tolerance that is used in comparison
    integrate_line_tolerance_type  = options.get('integrate_line_tolerance_type','absolute') # type of tolerance, either 'absolute' or 'relative'
    integrate_line_option          = options.get('integrate_line_option',None)               # special option, e.g., calculating a rate by dividing the integrated values by the timestep which is used in the values 'x'
    integrate_line_multiplier      = options.get('integrate_line_multiplier',1)              # factor for multiplying the result (in order to accquire a physically meaning value for comparison)
    if all([integrate_line_file,  integrate_line_delimiter, integrate_line_columns, integrate_line_integral_value]) :
        if integrate_line_tolerance_type in ('absolute', 'delta', '--delta') :
            integrate_line_tolerance_type = "absolute"
        elif integrate_line_tolerance_type in ('relative', "--relative") :
            integrate_line_tolerance_type = "relative"
        else :
            raise Exception(tools.red("initialization of integrate line failed. integrate_line_tolerance_type '%s' not accepted." % integrate_line_tolerance_type))
        analyze.append(Analyze_integrate_line(integrate_line_file, integrate_line_delimiter, integrate_line_columns, integrate_line_integral_value, integrate_line_tolerance_value, integrate_line_tolerance_type, integrate_line_option, integrate_line_multiplier))


    return analyze

#==================================================================================================
 
class Analyze() : # main class from which all analyze functions are derived
    total_errors = 0

#==================================================================================================

class Clean_up_files() :
    """Clean up the output folder by deleting sepcified files"""
    def __init__(self, clean_up_files) :
        self.files = clean_up_files

    def perform(self,runs) :
        return # do nothing

    def execute(self,run) :

        """
        General workflow:
        1.  Iterate over all runs
        1.1   remove all files that are specified (if they exist)
        """

        # 1.1   remove all files that are specified (if they exist)
        for remove_file in self.files :
            path = os.path.join(run.target_directory,remove_file)
            
            wildcards = glob.glob(path)
            for wildcard in wildcards:
                if not os.path.exists(wildcard) :
                    s = tools.red("Clean_up_files: Could not find file=[%s] for removing" % wildcard)
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful=False
                    Analyze.total_errors+=1
                    continue
                else :
                    print(tools.yellow("[remove_folder]: deleting file '%s'" % wildcard))
                    os.remove(wildcard)

    def __str__(self) :
        return "Clean up the output folder by deleting sepcified files"



#==================================================================================================

class Analyze_L2_file(Analyze) :
    """Read the L2 error norms from std.out and compare with pre-defined upper barrier"""
    def __init__(self, name, L2_file, L2_file_tolerance, L2_file_tolerance_type) :
        self.file              = L2_file
        self.L2_tolerance      = L2_file_tolerance
        self.L2_tolerance_type = L2_file_tolerance_type
        self.error_name        = name                   # string name of the L2 error in the std.out file (default is "L_2")                             

    def perform(self,runs) :

        """
        General workflow:
        1.  Iterate over all runs
        1.1   read the reference L2 errors from the std.out
        1.1.1   append info for summary of errors
        1.1.2   set analyzes to fail
        1.2   Check existence of the reference file
        1.2.1   Read content of the reference file and store in self.file_data list
        1.3   Check length of L2 errors in std out and reference file
        1.4   calculate difference and determine compare with tolerance
        """

        LastLines = 35 # search the last 35 lines in the std.out file for the L2 error
        # 1.  Iterate over all runs
        for run in runs :
            
            # 1.1   Read L2 errors from std out channel
            try:
                L2_errors = np.array(analyze_functions.get_last_L2_error(run.stdout,self.error_name,LastLines))
            except :
                s = tools.red("L2 analysis failed: L2 error could not be read from %s (searching for %s in the last %s lines)" % ('std.out',self.error_name,LastLines) )
                print(s)
                
                # 1.1.1   append info for summary of errors
                run.analyze_results.append(s)

                # 1.1.2   set analyzes to fail
                run.analyze_successful=False
                Analyze.total_errors+=1
                continue # with next run

            # 1.2   Check existence of the reference file
            path_ref = os.path.join(run.target_directory,self.file)

            if not os.path.exists(path_ref) :
                s=tools.red("Analyze_L2_file: cannot find reference L2 error file=[%s]" % self.file)
                print(s)
                run.analyze_results.append(s)
                run.analyze_successful=False
                Analyze.total_errors+=1
                continue # with next run
            else :
                # 1.2.1   Read content of the reference file and store in self.file_data list
                self.file_data = []
                with open(path_ref) as f :
                    for line in f.readlines() :   # iterate over all lines of the file
                        self.file_data.append(line)

            # 1.2   Read reference L2 errors from self.file_data list
            try:
                L2_errors_ref = np.array(analyze_functions.get_last_L2_error(self.file_data,self.error_name,LastLines))
            except :
                s = tools.red("L2 analysis failed: L2 error could not be read from %s (searching for %s in the last %s lines)" % (self.file,self.error_name,LastLines) )
                print(s)
                
                # 1.2.1   append info for summary of errors
                run.analyze_results.append(s)

                # 1.2.2   set analyzes to fail
                run.analyze_successful=False
                Analyze.total_errors+=1
                continue # with next run

            # 1.3   Check length of L2 errors in std out and reference file
            if len(L2_errors) != len(L2_errors_ref) :
                s = tools.red("L2 analysis failed: number of L2 errors in std out [%s] do not match number of L2 errors in ref file [%s]. They must be the same." % (len(L2_errors),len(L2_errors_ref)))
                print(s)
                
                # 1.2.1   append info for summary of errors
                run.analyze_results.append(s)

                # 1.2.2   set analyzes to fail
                run.analyze_successful=False
                Analyze.total_errors+=1
                continue # with next run

            # 1.4   calculate difference and determine compare with tolerance
            success = tools.diff_lists(L2_errors, L2_errors_ref, self.L2_tolerance, self.L2_tolerance_type)
            if not all(success) :
                s = tools.red("Mismatch in L2 error comparison with reference file data: "+", ".join(["[%s with %s]" % (L2_errors[i], L2_errors_ref[i]) for i in range(len(success)) if not success[i]]))
                print(s)

                # 1.4.1   append info for summary of errors
                run.analyze_results.append(s)

                # 1.4.2   set analyzes to fail
                run.analyze_successful=False
                Analyze.total_errors+=1

    def __str__(self) :
        return "perform L2 error comparison with L2 errors in file %s" % self.file


#==================================================================================================

class Analyze_L2(Analyze) :
    """Read the L2 error norms from std.out and compare with pre-defined upper barrier"""
    def __init__(self, name, L2_tolerance) :
        self.L2_tolerance = L2_tolerance # tolerance value for comparison with the L_2 error from std.out
        self.error_name   = name         # string name of the L2 error in the std.out file (default is "L_2")                             

    def perform(self,runs) :

        """
        General workflow:
        1.  Iterate over all runs
        1.1   read L2 errors from 'std.out' file
        1.1.1   append info for summary of errors
        1.1.2   set analyzes to fail
        1.2   if one L2 errors is larger than the tolerance -> fail
        1.3   append info for summary of errors
        1.4   set analyzes to fail
        """

        LastLines = 35 # search the last 35 lines in the std.out file for the L2 error
        # 1.  Iterate over all runs
        for run in runs :
            
            # 1.1   read L2 errors from 'std.out' file
            try:
                L2_errors = np.array(analyze_functions.get_last_L2_error(run.stdout,self.error_name,LastLines))
            except :
                s = tools.red("L2 analysis failed: L2 error could not be read from %s (searching for %s in the last %s lines)" % ('std.out',self.error_name,LastLines) )
                print(s)
                
                # 1.1.1   append info for summary of errors
                run.analyze_results.append(s)

                # 1.1.2   set analyzes to fail
                run.analyze_successful=False
                Analyze.total_errors+=1
                continue
            
            # 1.2   if one L2 errors is larger than the tolerance -> fail
            if (L2_errors > self.L2_tolerance).any() :
                s = tools.red("analysis failed: L2 error >"+str(self.L2_tolerance))
                print(s)
                
                # 1.3   append info for summary of errors
                run.analyze_results.append(s)

                # 1.4   set analyzes to fail
                run.analyze_successful=False
                Analyze.total_errors+=1

    def __str__(self) :
        return "perform L2 error comparison with a pre-defined tolerance"

#==================================================================================================

class Analyze_Convtest_h(Analyze) :
    """Convergence test for a fixed polynomial degree and different meshes defined in 'parameter.ini'
    The analyze routine read the L2 error norm from a set of runs and determines the order of convergence 
    between the runs and averages the values. The average is compared with the polynomial degree p+1."""
    def __init__(self, name, cells, tolerance, rate) :
        self.cells = cells           # number of cells used for h-convergence calculation (only the ratio of two 
                                     # consecutive values is important for the EOC calcultion)
        self.tolerance = tolerance   # determine success rate by comparing the relative convergence error with a tolerance
        self.rate = rate             # success rate: for each nVar, the EOC is determined (the number of successful EOC vs. 
                                     # the number of total EOC tests determines the success rate which is compared with this rate)
        self.error_name = name       # string name of the L2 error in the std.out file (default is "L_2")                             

    def perform(self,runs) :
        global pyplot_module_loaded
        """
        General workflow:
        1.  check if number of successful runs is equal the number of supplied cells
        1.1   read the polynomial degree from the first run -> must not change!
        1.2   get L2 errors of all runs and create np.array
        1.2.1   append info for summary of errors in exception
        1.2.2   set analyzes to fail
        1.3   get number of variables from L2 error array
        1.4   determine order of convergence between two runs
        1.4.1   determine average convergence rate
        1.4.2   write L2 error data to file
        1.5   determine success rate by comparing the relative convergence error with a tolerance
        1.6   compare success rate with pre-defined rate
        1.7     interate over all runs
        1.7.1   add failed info if success rate is not reached to all runs
        1.7.2   set analyzes to fail if success rate is not reached for all runs
        """

        LastLines = 35 # search the last 35 lines in the std.out file for the L2 error
        # 1.  check if number of successful runs is equal the number of supplied cells
        nRuns = len(runs)
        if nRuns < 2 :
            for run in runs :
                s="analysis failed: h-convergence not possible with only 1 run"
                print(tools.red(s))
                run.analyze_results.append(s)
                run.analyze_successful=False
                Analyze.total_errors+=1
                return
        if len(self.cells) == nRuns :

            # 1.1   read the polynomial degree from the first run -> must not change!
            p = float(runs[0].parameters.get('N',-1))

            # 1.2   get L2 errors of all runs and create np.array
            try :
                L2_errors = np.array([analyze_functions.get_last_L2_error(run.stdout,self.error_name) for \
                        run in runs])
                L2_errors = np.transpose(L2_errors)
            except :
                for run in runs : # find out exactly which L2 error could not be read
                    try :
                        L2_errors_test = np.array(analyze_functions.get_last_L2_error(run.stdout,self.error_name,LastLines))
                    except :
                        s = tools.red("h-convergence failed: L2 error could not be read from %s (searching for %s in the last %s lines)" % ('std.out',self.error_name,LastLines) )
                        print(s)
                        
                        # 1.2.1   append info for summary of errors
                        run.analyze_results.append(s)

                        # 1.2.2   set analyzes to fail
                        run.analyze_successful=False
                        Analyze.total_errors+=1
                return

            # 1.3   get number of variables from L2 error array
            nVar = len(L2_errors)
            print(tools.blue("L2 errors for nVar="+str(nVar)))
            displayTable(L2_errors,nVar,nRuns)

            # 1.4   determine order of convergence between two runs
            L2_order = np.array([analyze_functions.calcOrder_h(self.cells,L2_errors[i]) for i in range(nVar)])
            print(tools.blue("L2 orders for nVar="+str(nVar)))
            displayTable(L2_order,nVar,nRuns-1)

            # 1.4.1   determine average convergence rate
            mean = [np.mean(L2_order[i]) for i in range(nVar)]
            print(tools.blue("L2 average order for nVar=%s (exprected order = %s)" % (nVar,p+1)))
            displayVector(mean,nVar)

            if pyplot_module_loaded : # this boolean is set when importing matplotlib.pyplot
                for i in range(nVar) :
                    f = plt.figure()                             # create figure
                    if 1 == 2 :
                        self.grid_spacing = [1.0/((p+1)*float(x)) for x in self.cells]
                        plt.plot(self.grid_spacing, L2_errors[i], 'ro-')    # create plot
                        plt.xlabel('Average grid spacing for unit domain lenght L_domain=1')                # set x-label
                    else :
                        plt.plot(self.cells, L2_errors[i], 'ro-')    # create plot
                        plt.xlabel('Number of cells')                # set x-label
                    if min(L2_errors[i]) > 0.0 :                     # log plot only if greater zero 
                        plt.xscale('log')                            # set x-axis to log scale
                        plt.yscale('log')                            # set y-axis to log scale
                    plt.title('nVar = %s (of %s), MIN = %4.2e, MAX = %4.2e, O(%.2f)' % (i, nVar-1, min(L2_errors[i]), max(L2_errors[i]),mean[i])) # set title
                    plt.ylabel('L2 error norm')                  # set y-label
                    #plt.show() # display the plot figure for the user (comment out when running in batch mode)
                    f_save_path = os.path.join(os.path.dirname(runs[0].target_directory),"L2_error_nVar"+str(i)+"_order%.2f.pdf" % mean[i]) # set file path for saving the figure to the disk
                    f.savefig(f_save_path, bbox_inches='tight')                                                         # save figure to .pdf file
            else :
                print(tools.yellow('Could not import matplotlib.pyplot module. This is required for creating plots under "Analyze_Convtest_h(Analyze)". \nSet "use_matplot_lib=True" in analyze.ini in order to activate plotting.'))

            # 1.4.2   write L2 error data to file
            writeTableToFile(L2_errors,nVar,nRuns,self.cells,os.path.dirname(runs[0].target_directory),"L2_error_order%.2f.csv" % mean[0])
            
            # 1.5   determine success rate by comparing the relative convergence error with a tolerance
            print(tools.blue( "relative order error (tolerance = %.4e)" % self.tolerance))
            relErr = [abs(mean[i]/(p+1)-1) for i in range(nVar)]
            displayVector(relErr,nVar)
            success = [relErr[i] < self.tolerance for i in range(nVar)]
            print(tools.blue("success convergence"))
            print(5*" "+"".join(str(success[i]).rjust(21) for i in range(nVar)))


            # 1.6   compare success rate with pre-defined rate, fails if not reached
            if float(sum(success))/nVar >= self.rate :
                print(tools.blue("h-convergence successful"))
            else :
                print(tools.red("h-convergence failed"+"\n"+\
                        "success rate="+str(float(sum(success))/nVar)+\
                        " tolerance rate="+str(self.rate)))

                # 1.7     interate over all runs
                for run in runs :

                    # 1.6.1   add failed info if success rate is not reached to all runs
                    run.analyze_results.append("analysis failed: h-convergence "\
                            +str(success))

                    # 1.6.2   set analyzes to fail if success rate is not reached for all runs
                    run.analyze_successful=False
                    Analyze.total_errors+=1

        else :
            s="cannot perform h-convergence test, because number of successful runs must equal the number of cells"
            print(tools.red(s))
            for run in runs :
                run.analyze_results.append(s) # append info for summary of errors
                run.analyze_successful=False  # set analyzes to fail
                Analyze.total_errors+=1       # increment errror counter
            print(tools.yellow("nRun  "+str(nRuns)))
            print(tools.yellow("cells "+str(len(self.cells))))
    def __str__(self) :
        return "perform L2 h-convergence test and compare the order of convergence with the polynomial degree"

#==================================================================================================

class Analyze_Convtest_t(Analyze) :
    """Convergence test for different time steps defined in 'parameter.ini' (e.g. CFLScale)
    The analyze routine read the L2 error norm from a set of runs and determines the order of convergence 
    between the runs and averages the values. The average is compared with the temporal order supplied by the user."""
    def __init__(self, order, name, tolerance, rate, method, method_name, ini_timestep, timestep_factor, total_iter, iters) :
        # 1.   set the order of convergence, tolerance, rate and error name (name of the error in the std.out)
        self.order      = order      # user-supplied convergence order
        self.tolerance  = tolerance  # determine success rate by comparing the relative convergence error with a tolerance
        self.rate       = rate       # success rate: for each nVar, the EOC is determined (the number of successful EOC vs. 
                                     # the number of total EOC tests determines the success rate which is compared with this rate)
        self.error_name = name       # string name of the L2 error in the std.out file (default is "L_2")                             

        # 3.   set the method and input variables
        self.method     = method      # choose between four methods: initial timestep, list of timestep_factor, total number of timesteps, list of timesteps. 
                                      # The lists are user-supplied and the other methods are read automatically from the std.out
        self.name       = method_name # string for the name of the method (used for pyplot)
        self.ini_timestep    = ini_timestep    # 1.) initial timestep (automatically from std.out)
        self.timestep_factor = timestep_factor # 2.) list of timestep_factor (user-supplied list)
        self.total_iter      = total_iter      # 3.) total number of timesteps (automatically from std.out)
        self.iters           = iters           # 4.) list of timesteps (user-supplied list)

        # 3.   set variables depending on the method
        if self.method == 2 :
            self.number_of_x_values = len(self.timestep_factor)
            self.x_values           = self.timestep_factor
        elif self.method == 4:
            self.number_of_x_values = len(self.iters)
            self.x_values           = self.iters
        else :
            self.number_of_x_values = -1
            if self.method == 1 :
                self.get_x_values   = self.ini_timestep
            else :
                self.get_x_values   = self.total_iter


    def perform(self,runs) :
        global pyplot_module_loaded
        """
        General workflow:
        1.  check if number of successful runs is equal the number of supplied timestep_factor/timesteps (only method 2 and 4)
        1.1   for method 1.) or 3.) det the values for x_values from std.out
        1.2   get L2 errors of all runs and create np.array
        1.2.1   append info for summary of errors in exception
        1.2.2   set analyzes to fail
        1.3   get number of variables from L2 error array
        1.4   determine order of convergence between two runs
        1.4.1   determine average convergence rate
        1.4.2   write L2 error data to file
        1.5   determine success rate by comparing the relative convergence error with a tolerance
        1.6   compare success rate with pre-defined rate
        1.7     interate over all runs
        1.7.1   add failed info if success rate is not reached to all runs
        1.7.2   set analyzes to fail if success rate is not reached for all runs
        """

        LastLines = 35 # search the last 35 lines in the std.out file for the L2 error
        # 1.  check if number of successful runs is at least two
        nRuns = len(runs)
        if nRuns < 2 :
            for run in runs :
                s="analysis failed: t-convergence not possible with only 1 run"
                print(tools.red(s))
                run.analyze_results.append(s)
                run.analyze_successful=False
                Analyze.total_errors+=1
                return
        if self.number_of_x_values in (-1,nRuns) :
            # 1.1   for method 1.) or 3.) det the values for x_values from std.out
            if self.method in (1,3) :
                print(self.get_x_values)
                if self.method == 1 :   # 1.) initial timestep (automatically from std.out)
                    try :
                        self.x_values = np.array([analyze_functions.get_initial_timesteps(run.stdout,self.get_x_values) for run in runs])
                    except :
                        for run in runs : # find out exactly which L2 error could not be read
                            try :
                                self.x_values_test = np.array(analyze_functions.get_initial_timesteps(run.stdout,self.get_x_values))
                            except :
                                s = tools.red("t-convergence failed: could not read [%s] from output (searching in all lines)" % self.get_x_values)
                                print(s)
                                
                                # 1.2.1   append info for summary of errors
                                run.analyze_results.append(s)

                                # 1.2.2   set analyzes to fail
                                run.analyze_successful=False
                                Analyze.total_errors+=1
                        return
                elif self.method == 3 : # 3.) total number of timesteps (automatically from std.out)
                    try :
                        self.x_values = np.array([analyze_functions.get_last_number_of_timesteps(run.stdout,self.get_x_values) for run in runs])
                    except :
                        for run in runs : # find out exactly which L2 error could not be read
                            try :
                                self.x_values_test = np.array(analyze_functions.get_last_number_of_timesteps(run.stdout,self.get_x_values,LastLines))
                            except :
                                s = tools.red("t-convergence failed: could not read [%s] from %s (searching in the last %s lines)" % ('std.out',self.get_x_values,LastLines) )
                                print(s)
                                
                                # 1.2.1   append info for summary of errors
                                run.analyze_results.append(s)

                                # 1.2.2   set analyzes to fail
                                run.analyze_successful=False
                                Analyze.total_errors+=1
                        return
                # transpose the vector and reduce the dimension of the array from 2 to 1
                self.x_values = np.transpose(self.x_values)
                self.x_values = self.x_values[0]

            # 1.2   get L2 errors of all runs and create np.array
            try :
                L2_errors = np.array([analyze_functions.get_last_L2_error(run.stdout,self.error_name,LastLines) for \
                        run in runs])
                L2_errors = np.transpose(L2_errors)
            except :
                for run in runs : # find out exactly which L2 error could not be read
                    try :
                        L2_errors_test = np.array(analyze_functions.get_last_L2_error(run.stdout,self.error_name,LastLines))
                    except :
                        s = tools.red("t-convergence failed: some L2 errors could not be read from %s (searching for '%s' in the last %s lines)" % ('std.out',self.error_name,LastLines) )
                        print(s)
                        
                        # 1.2.1   append info for summary of errors
                        run.analyze_results.append(s)

                        # 1.2.2   set analyzes to fail
                        run.analyze_successful=False
                        Analyze.total_errors+=1
                return

            # 1.3   get number of variables from L2 error array
            nVar = len(L2_errors)
            print(tools.blue("L2 errors for nVar="+str(nVar)))
            displayTable(L2_errors,nVar,nRuns)

            # 1.4   determine order of convergence between two runs
            if self.method == 1 :   # 1.) initial timestep (automatically from std.out)
                L2_order = np.array([analyze_functions.calcOrder_h(self.x_values,L2_errors[i],True) for i in range(nVar)]) # invert (e.g. the timestep) for positive order calculation (eg. O(-4) -> O(4))
            else :
                L2_order = np.array([analyze_functions.calcOrder_h(self.x_values,L2_errors[i]) for i in range(nVar)])
            print(tools.blue("L2 orders for nVar="+str(nVar)))
            displayTable(L2_order,nVar,nRuns-1)

            # 1.4.1   determine average convergence rate
            mean = [np.mean(L2_order[i]) for i in range(nVar)]
            print(tools.blue("L2 average order for nVar=%s (exprected order = %s)" % (nVar,self.order)))
            displayVector(mean,nVar)

            if pyplot_module_loaded : # this boolean is set when importing matplotlib.pyplot
                for i in range(nVar) :
                    f = plt.figure()                             # create figure
                    if 1 == 2 :
                        self.grid_spacing = [1.0/((self.order)*float(x)) for x in self.x_values]
                        plt.plot(self.grid_spacing, L2_errors[i], 'ro-')    # create plot
                        plt.xlabel('Average grid spacing for unit domain lenght L_domain=1')                # set x-label
                    else :
                        plt.plot(self.x_values, L2_errors[i], 'ro-')    # create plot
                        plt.xlabel('x: %s' % self.name)                # set x-label
                    if min(L2_errors[i]) > 0.0 :                     # log plot only if greater zero 
                        plt.xscale('log')                            # set x-axis to log scale
                        plt.yscale('log')                            # set y-axis to log scale
                    plt.title('nVar = %s (of %s), MIN = %4.2e, MAX = %4.2e, O(%.2f)' % (i, nVar-1, min(L2_errors[i]), max(L2_errors[i]),mean[i])) # set title
                    plt.ylabel('L2 error norm')                  # set y-label
                    #plt.show() # display the plot figure for the user (comment out when running in batch mode)
                    f_save_path = os.path.join(os.path.dirname(runs[0].target_directory),"L2_error_nVar"+str(i)+"_order%.2f.pdf" % mean[i]) # set file path for saving the figure to the disk
                    f.savefig(f_save_path, bbox_inches='tight')                                                         # save figure to .pdf file
            else :
                print(tools.yellow('Could not import matplotlib.pyplot module. This is required for creating plots under "Analyze_Convtest_t(Analyze)". \nSet "use_matplot_lib=True" in analyze.ini in order to activate plotting.'))

            # 1.4.2   write L2 error data to file
            writeTableToFile(L2_errors,nVar,nRuns,self.x_values,os.path.dirname(runs[0].target_directory),"L2_error_order%.2f.csv" % mean[0])
            
            # 1.5   determine success rate by comparing the relative convergence error with a tolerance
            print(tools.blue( "relative order error (tolerance = %.4e)" % self.tolerance))
            relErr = [abs(mean[i]/(self.order)-1) for i in range(nVar)]
            displayVector(relErr,nVar)
            success = [relErr[i] < self.tolerance for i in range(nVar)]
            print(tools.blue("success convergence"))
            print(5*" "+"".join(str(success[i]).rjust(21) for i in range(nVar)))


            # 1.6   compare success rate with pre-defined rate, fails if not reached
            if float(sum(success))/nVar >= self.rate :
                print(tools.blue("t-convergence successful"))
            else :
                print(tools.red("t-convergence failed"+"\n"+\
                        "success rate="+str(float(sum(success))/nVar)+\
                        " tolerance rate="+str(self.rate)))

                # 1.7     interate over all runs
                for run in runs :

                    # 1.6.1   add failed info if success rate is not reached to all runs
                    run.analyze_results.append("analysis failed: t-convergence "\
                            +str(success))

                    # 1.6.2   set analyzes to fail if success rate is not reached for all runs
                    run.analyze_successful=False
                    Analyze.total_errors+=1

        else :
            s="cannot perform t-convergence test, because number of successful runs must equal the number of supplied %s in the user-supplied list" % self.name
            print(tools.red(s))
            for run in runs :
                run.analyze_results.append(s) # append info for summary of errors
                run.analyze_successful=False  # set analyzes to fail
                Analyze.total_errors+=1       # increment errror counter
            print(tools.yellow("[nRun] = [%s]" % nRuns))
            print(tools.yellow("[%s] = [%s] values for x_values (must equal the number of nRun)" % (self.name,len(self.x_values))))
    def __str__(self) :
        return "perform L2 t-convergence test and compare the order of convergence with %s against the supplied order of convergence" % self.name

#==================================================================================================

class Analyze_Convtest_p(Analyze) :
    """Convergence test for a fixed mesh and different (increasing!) polynomial degrees defined in 'parameter.ini'
    The analyze routine reads the L2 error norm from a set of runs and determines the order of convergence 
    between the runs and compares them. With increasing polynomial degree, the order of convergence must increase for this anaylsis to be successful."""
    def __init__(self, name, rate, percentage) :
        self.rate       = rate       # success rate: for each nVar, the EOC is determined (the number of successful EOC vs. 
                                     # the number of total EOC tests determines the success rate which is compared with this rate)
        self.percentage = percentage # for the p-convergence, the EOC must increase with p, hence the sloop must increase
                                     # percentage yields the minimum ratio of increasing EOC vs. the total number of EOC for each nVar
        self.error_name = name       # string name of the L2 error in the std.out file (default is "L_2")                             

    def perform(self,runs) :
        global pyplot_module_loaded

        """
        General workflow:
        1.  read the polynomial degree for all runs
        2.  check if number of successful runs is equal the number of supplied cells
        2.2   get L2 errors of all runs and create np.array
        1.2.1   append info for summary of errors
        1.2.2   set analyzes to fail
        2.3   get number of variables from L2 error array
        2.4   determine order of convergence between two runs
        2.5   check if the order of convergence is always increasing with increasing polynomial degree
        2.6   determine success rate from increasing convergence
        2.7   compare success rate with pre-defined rate, fails if not reached 
        2.8   iterate over all runs
        2.8.1   add failed info if success rate is not reached to all runs
        2.8.1   set analyzes to fail if success rate is not reached for all runs
        """

        LastLines = 35 # search the last 35 lines in the std.out file for the L2 error
        # 1.  read the polynomial degree  for all runs
        p = [float(run.parameters.get('N',-1)) for run in runs] # get polynomial degree

        # 2. check if number of successful runs is equal the number of supplied cells
        nRuns = len(runs)
        if nRuns < 2 :
            for run in runs :
                s="analysis failed: p-convergence not possible with only 1 run"
                print(tools.red(s))
                run.analyze_results.append(s)
                run.analyze_successful=False
                Analyze.total_errors+=1
                return

        if len(p) == nRuns :

            # 2.2   get L2 errors of all runs and create np.array
            try :
                L2_errors = np.array([analyze_functions.get_last_L2_error(run.stdout,self.error_name,LastLines) for \
                        run in runs])
                L2_errors = np.transpose(L2_errors)
            except :
                for run in runs : # find out exactly which L2 error could not be read
                    try :
                        L2_errors_test = np.array(analyze_functions.get_last_L2_error(run.stdout,self.error_name,LastLines))
                    except :
                        s = tools.red("p-convergence failed: some L2 errors could not be read from %s (searching for '%s' in the last %s lines)" % ('std.out',self.error_name,LastLines) )
                        print(s)
                        
                        # 1.2.1   append info for summary of errors
                        run.analyze_results.append(s)

                        # 1.2.2   set analyzes to fail
                        run.analyze_successful=False
                        Analyze.total_errors+=1
                return

            # 2.3   get number of variables from L2 error array
            nVar = len(L2_errors)
            
            print(tools.blue("L2 errors nVar="+str(nVar)))
            displayTable(L2_errors,nVar,nRuns)
            writeTableToFile(L2_errors,nVar,nRuns,p,os.path.dirname(runs[0].target_directory),"L2_error.csv")

            if pyplot_module_loaded : # this boolean is set when importing matplotlib.pyplot
                for i in range(nVar) :
                    f = plt.figure()                                    # create figure
                    ax = f.gca()                                        # set axis handle
                    plt.plot(p , L2_errors[i], 'ro-')                   # create plot
                    #plt.xscale('log')                                  # set x-xis to log scale
                    if min(L2_errors[i]) > 0.0 :                        # log plot only if greater zero 
                        plt.yscale('log')                               # set y-xis to log scale
                    plt.title('nVar = %s (of %s), MIN = %4.2e, MAX = %4.2e' % (i, nVar-1, min(L2_errors[i]), max(L2_errors[i]))) # set title
                    plt.xlabel('Polynomial degree')                     # set x-label
                    plt.ylabel('L2 error norm')                         # set y-label
                    ax.xaxis.set_major_locator(MaxNLocator(integer=True)) # set x-axis format to integer only
                    #plt.show() # display the plot figure for the user (comment out when running in batch mode)
                    f_save_path = os.path.join(os.path.dirname(runs[0].target_directory),"L2_error_nVar"+str(i)+".pdf") # set file path for saving the figure to the disk
                    f.savefig(f_save_path, bbox_inches='tight')                                                         # save figure to .pdf file
            else :
                print(tools.yellow('Could not import matplotlib.pyplot module. This is required for creating plots under "Analyze_Convtest_p(Analyze)". \nSet "use_matplot_lib=True" in analyze.ini in order to activate plotting.'))

            # 2.4   determine order of convergence between two runs
            L2_order = \
                    np.array([analyze_functions.calcOrder_p(p,L2_errors[i]) for \
                    i in range(nVar)])
            print(tools.blue("L2 orders for nVar="+str(nVar)))
            displayTable(L2_order,nVar,nRuns-1)

            # 2.5   check if the order of convergence is always increasing with increasing polynomial degree
            increasing = []
            for j in range(nVar) :
                increasing_run = []
                for i in range(1,len(p)-1) :
                    increasing_run.append(L2_order[j][i]>L2_order[j][i-1]) # check for increasing order of convergence
                    #print increasing_run,L2_order[j][i],L2_order[j][i-1]
                print(increasing_run)
                if 1==1 :
                    if abs(float(len(increasing_run))) > 0 :
                        increasing.append(float(sum(increasing_run))/float(len(increasing_run)))
                    else :
                        increasing.append(0.)
                else :
                    increasing.append(all(increasing_run))
            print(tools.blue("Increasing order of convergence, percentage"))
            print(5*" "+"".join(str(increasing[i]).rjust(21) for i in range(nVar)))
            
            # 2.6   determine success rate from increasing convergence
            success = [increasing[i] >= self.percentage for i in range(nVar)]
            print(tools.blue("success convergence (if percentage >= %.2f)" % self.percentage))
            print(5*" "+"".join(str(success[i]).rjust(21) for i in range(nVar)))

            # 2.7   compare success rate with pre-defined rate, fails if not reached
            if float(sum(success))/nVar >= self.rate :
                print(tools.blue("p-convergence successful"))
            else :
                print(tools.red("p-convergence failed"+"\n"+\
                        "success rate="+str(float(sum(success))/nVar)+\
                        " tolerance rate="+str(self.rate)))

                # 2.8     interate over all runs
                for run in runs :

                    # 2.8.1   add failed info if success rate is not reached to all runs
                    run.analyze_results.append("analysis failed: p-convergence "+str(success))

                    # 2.8.2   set analyzes to fail if success rate is not reached for all runs
                    run.analyze_successful=False
                    Analyze.total_errors+=1

                    #global_errors+=1
        else :
            s="cannot perform p-convergence test, because number of successful runs must equal the number of polynomial degrees p"
            print(tools.red(s))
            for run in runs :
                run.analyze_results.append(s) # append info for summary of errors
                run.analyze_successful=False  # set analyzes to fail
                Analyze.total_errors+=1       # increment errror counter
            print(tools.yellow("nRun   "+str(nRuns)))
            print(tools.yellow("len(p) "+str(len(p))))
    def __str__(self) :
        return "perform L2 p-convergence test and check if the order of convergence increases with increasing polynomial degree"

#==================================================================================================

class Analyze_h5diff(Analyze,ExternalCommand) :
    def __init__(self, h5diff_one_diff_per_run, h5diff_reference_file, h5diff_file, h5diff_data_set, h5diff_tolerance_value, h5diff_tolerance_type, referencescopy) :
        self.one_diff_per_run = (h5diff_one_diff_per_run in ('True', 'true', 't', 'T'))
        self.prms = { "reference_file" : h5diff_reference_file, "file" : h5diff_file, "data_set" : h5diff_data_set, "tolerance_value" : h5diff_tolerance_value, "tolerance_type" : h5diff_tolerance_type }
        for key, prm in self.prms.iteritems() : 
           if type(prm) != type([]) :
              self.prms[key] = [prm]
        numbers = {key: len(prm) for key, prm in self.prms.iteritems()}

        ExternalCommand.__init__(self)
        
        self.nCompares = numbers[ max( numbers, key = numbers.get ) ]
        for key, number in numbers.iteritems() : 
            if number == 1 : 
                self.prms[key] = [ self.prms[key][0] for i in range(self.nCompares) ]
                numbers[key] = self.nCompares

        if any( [ (number != self.nCompares) for number in numbers.itervalues() ] ) : 
            raise Exception(tools.red("Number of multiple data sets for multiple h5diffs is inconsitent. Please ensure all options have the same length or length 1.")) 

        for compare in range(self.nCompares) :
            tolerance_type_loc = self.prms["tolerance_type"][compare]  
            if tolerance_type_loc in ('absolute', 'delta', '--delta') :
                self.prms["tolerance_type"][compare] = "--delta"
            elif tolerance_type_loc in ('relative', "--relative") :
                self.prms["tolerance_type"][compare] = "--relative"
            else :
                raise Exception(tools.red("initialization of h5diff failed. h5diff_tolerance_type '%s' not accepted." % tolerance_type_loc))

        # set logical for creating new reference files and copying them to the example source directory
        self.referencescopy = referencescopy

    def perform(self,runs) :
        global h5py_module_loaded
        # check if this analysis can be performed: h5py must be imported
        if not h5py_module_loaded : # this boolean is set when importing h5py
            print(tools.red('Could not import h5py module. This is required for "Analyze_check_hdf5". Aborting.'))
            Analyze.total_errors+=1
            return

        '''
        General workflow:
        1.  iterate over all runs
        1.2   execute the command 'cmd' = 'h5diff -r --XXX [value] ref_file file DataArray'
        1.3   if the command 'cmd' returns a code != 0, set failed
        1.3.1   add failed info (for return a code != 0) to run
        1.3.2   set analyzes to fail (for return a code != 0)
        '''
        if self.one_diff_per_run and ( self.nCompares != len(runs)) :
            raise Exception(tools.red("Number of h5diffs and runs is inconsitent. Please ensure all options have the same length or set h5diff_one_diff_per_run=F.")) 

        # 1.  iterate over all runs
        for iRun, run in enumerate(runs) :
            if self.one_diff_per_run : 
                compares = [iRun]
            else : 
                compares = range(self.nCompares)
            for compare in compares : 
                reference_file_loc   = self.prms["reference_file"][compare] 
                file_loc             = self.prms["file"][compare]           
                data_set_loc         = self.prms["data_set"][compare]        
                tolerance_value_loc  = self.prms["tolerance_value"][compare] 
                tolerance_type_loc   = self.prms["tolerance_type"][compare]  

                # 1.1.0   Read the hdf5 file
                path            = os.path.join(run.target_directory,file_loc)
                path_ref_target = os.path.join(run.target_directory,reference_file_loc)
                path_ref_source = os.path.join(run.source_directory,reference_file_loc)

                # Copy new reference file: This is completely independent of the outcome of the current h5diff
                if self.referencescopy :
                    run = copyReferenceFile(run,path,path_ref_source)
                    s=tools.red("Analyze_compare_data_file: performed reference copy")
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful=False
                    Analyze.total_errors+=1
                    # do not skip the following analysis tests, because reference file will be created -> continue
                    continue 

                if not os.path.exists(path) :
                    s = tools.red("Analyze_h5diff: file does not exist, file=[%s]" % path)
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful=False
                    Analyze.total_errors+=1
                    continue
                if not os.path.exists(path_ref_target) :
                    s = tools.red("Analyze_h5diff: reference file does not exist, file=[%s]" % path_ref_target)
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful=False
                    Analyze.total_errors+=1
                    continue

                f1 = h5py.File(path,'r')
                f2 = h5py.File(path_ref_target,'r')
                # available keys   : print("Keys: %s" % f.keys())
                # first key in list: a_group_key = list(f.keys())[0]

                # 1.1.1   Read the dataset from the hdf5 file
                b1 = f1[data_set_loc][:]
                b2 = f2[data_set_loc][:]

                # 1.1.2 compare shape of the dataset of both files, throw error if they do not conincide
                if b1.shape != b2.shape :
                    self.result=tools.red(tools.red("h5diff failed,datasets are not comparable: [%s] with [%s]" % (f1,f2))) 
                    print(" "+self.result)

                    # 1.1.3   add failed info if return a code != 0 to run
                    run.analyze_results.append(self.result)

                    # 1.1.4   set analyzes to fail if return a code != 0
                    run.analyze_successful=False
                    Analyze.total_errors+=1
                else :

                    # 1.2   execute the command 'cmd' = 'h5diff -r [--type] [value] [ref_file] [file] [DataSetName]'
                    cmd = ["h5diff","-r",tolerance_type_loc,str(tolerance_value_loc),str(reference_file_loc),str(file_loc),str(data_set_loc)]
                    print(tools.indent("Running [%s]" % (" ".join(cmd)), 2), end=' ') # skip linebreak
                    try :
                        self.execute_cmd(cmd, run.target_directory,"h5diff") # run the code

                        # 1.3   if the comman 'cmd' return a code != 0, set failed
                        if self.return_code != 0 :
                            print("   tolerance_type     : "+tolerance_type_loc)
                            print("   tolernace_value    : "+str(tolerance_value_loc))
                            print("   reference          : "+str(reference_file_loc))
                            print("   file               : "+str(file_loc))
                            print("   data_set           : "+str(data_set_loc))
                            run.analyze_results.append("h5diff failed, self.return_code != 0")

                            # 1.3.1   add failed info if return a code != 0 to run
                            print(" ")
                            if len(self.stdout) > 20 :
                                for line in self.stdout[:10] : # print first 10 lines
                                    print(" "+line, end=' ') # skip linebreak
                                print(" ... leaving out intermediate lines")
                                for line in self.stdout[-10:] : # print last 10 lines
                                    print(" "+line, end=' ') # skip linebreak
                            else :
                                for line in self.stdout : # print all lines
                                    print(" "+line, end=' ') # skip linebreak
                                if len(self.stdout) == 1 :
                                    run.analyze_results.append(str(self.stdout))
                            print(" ")

                            # 1.3.2   set analyzes to fail if return a code != 0
                            run.analyze_successful=False
                            Analyze.total_errors+=1

                            #global_errors+=1
                    except Exception as ex :
                        self.result=tools.red("h5diff failed."+str(ex)) # print result here, because it was not added in "execute_cmd"
                        print(" "+self.result)

                        # 1.3.1   add failed info if return a code != 0 to run
                        run.analyze_results.append(tools.red("h5diff failed."+str(ex)))
                        run.analyze_results.append(tools.red("try adding 'export PATH=/opt/hdf5/1.X/bin/:$PATH'"))

                        # 1.3.2   set analyzes to fail if return a code != 0
                        run.analyze_successful=False
                        Analyze.total_errors+=1

    def __str__(self) :
        return "perform h5diff between two files, e.g.: ["+str(self.prms["file"][0])+"] + reference ["+str(self.prms["reference_file"][0])+"]"

#==================================================================================================

class Analyze_check_hdf5(Analyze) :
    def __init__(self, check_hdf5_file, check_hdf5_data_set, check_hdf5_dimension, check_hdf5_limits) :
        self.file                = check_hdf5_file
        self.data_set            = check_hdf5_data_set
        (self.dim1, self.dim2)   = [int(x)   for x in check_hdf5_dimension.split(":")]
        (self.lower, self.upper) = [float(x) for x in check_hdf5_limits.split(":")]

    def perform(self,runs) :
        global h5py_module_loaded
        # check if this analysis can be performed: h5py must be imported
        if not h5py_module_loaded : # this boolean is set when importing h5py
            print(tools.red('Could not import h5py module. This is required for "Analyze_check_hdf5". Aborting.'))
            Analyze.total_errors+=1
            return

        '''
        Description: check array bounds in hdf5 file

        General workflow:
        1.  iterate over all runs
        1.2   Read the hdf5 file
        1.3   Read the dataset from the hdf5 file
        1.3.1   loop over each dimension supplied
        1.3.2   Check if all values are within the supplied interval
        1.3.3   set analyzes to fail if return a code != 0
        '''

        # 1.  iterate over all runs
        for run in runs :
            # 1.2   Read the hdf5 file
            path = os.path.join(run.target_directory,self.file)
            if not os.path.exists(path) :
                s = tools.red("Analyze_check_hdf5: file does not exist, file=[%s]" % path)
                print(s)
                run.analyze_results.append(s)
                run.analyze_successful=False
                Analyze.total_errors+=1
                continue

            f = h5py.File(path,'r')
            # available keys   : print("Keys: %s" % f.keys())
            # first key in list: a_group_key = list(f.keys())[0]

            # 1.3   Read the dataset from the hdf5 file
            b = f[self.data_set][:]

            # 1.3.1   loop over each dimension supplied
            for i in range(self.dim1, self.dim2+1) : 

                # 1.3.2   Check if all values are within the supplied interval
                lower_test = any([x < self.lower for x in b[:][i]])
                upper_test = any([x > self.upper for x in b[:][i]])
                if lower_test or upper_test :
                    print(tools.red("values = "+str(b[:][i])+" MIN=["+str(min(b[:][i]))+"]"+" MAX=["+str(max(b[:][i]))+"]"))
                    s = tools.red("HDF5 array out of bounds for dimension = %2d (array dimension index starts at 0). " % i)
                    if lower_test :
                        s += tools.red(" [values found  < "+str(self.lower)+"]")
                    if upper_test :
                        s += tools.red(" [values found  > "+str(self.upper)+"]")
                    print(s)
                    run.analyze_results.append(s)
           
                    # 1.3.3   set analyzes to fail if return a code != 0
                    run.analyze_successful=False
                    Analyze.total_errors+=1


    def __str__(self) :
        return "check if the values of an hdf5 array are within specified limits: file= ["+str(self.file)+"], dataset= ["+str(self.data_set)+"]"

#==================================================================================================

class Analyze_compare_data_file(Analyze) :
    def __init__(self, compare_data_file_name, compare_data_file_reference, compare_data_file_tolerance, compare_data_file_line, compare_data_file_delimiter, compare_data_file_tolerance_type, referencescopy) :
        # set file for comparison
        self.file           = compare_data_file_name
        if type(self.file) == type([]) :
            self.file_number = len(self.file)
        else :
            self.file_number = 1

        # set reference file for comparison
        self.reference      = compare_data_file_reference
        if type(self.reference) == type([]) :
            self.reference_number = len(self.reference)
        else :
            self.reference_number = 1

        # set tolerance value
        self.tolerance      = float(compare_data_file_tolerance)

        # set tolerance type (relative or absolute)
        self.tolerance_type = compare_data_file_tolerance_type 

        # set which line in the file is to be compared with the reference file
        if compare_data_file_line == 'last' : 
            self.line = int(1e20)
        else :
            self.line = int(compare_data_file_line)

        # set the delimter symbol (',' is default)
        self.delimiter = compare_data_file_delimiter

        # set logical for creating new reference files and copying them to the example source directory
        self.referencescopy = referencescopy

    def perform(self,runs) :

        '''
        General workflow:
        1.  iterate over all runs
        1.1   Set the file and reference file for comparison
        1.2   Check existence the file and reference values
        1.3.1   read data file
        1.3.2   read refernece file
        1.3.3   check length of vectors
        1.3.4   calculate difference and determine compare with tolerance
        '''

        # 1.  iterate over all runs
        j = 0
        nRuns = len(runs)
        for run in runs :
            ##  1.1   Set the file and reference file for comparison
            if self.file_number > 1 :
                # check consistency when multiple files are supplied
                if (nRuns != self.file_number) :
                    s=tools.red("Analyze_compare_data_file: Number of data files [compare_data_file_name] %s does not match number of runs %s" % (self.file_number,nRuns))
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful=False
                    Analyze.total_errors+=1
                    return
                # set the file name
                file_name = self.file[j]
            else :
                file_name = self.file
            if self.reference_number > 1 :
                if (nRuns != self.reference_number) :
                    s=tools.red("Analyze_compare_data_file: Number of reference files [compare_data_file_name]) %s does not match number of runs %s" % (self.reference_number,nRuns))
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful=False
                    Analyze.total_errors+=1
                    return
                # set the reference file name
                ref_name  = self.reference[j]
            else :
                ref_name  = self.reference
            j += 1
            if self.file_number > 1 or self.reference_number > 1 :
                print(tools.blue("comparing file=[%s] and reference file=[%s]" % (file_name, ref_name)))

            # 1.2   Check existence the file and reference values
            path            = os.path.join(run.target_directory,file_name)
            path_ref_target = os.path.join(run.target_directory,ref_name)
            path_ref_source = os.path.join(run.source_directory,ref_name)

            # Copy new reference file: This is completely independent of the outcome of the current compare data file
            if self.referencescopy :
                run = copyReferenceFile(run,path,path_ref_source)
                s=tools.red("Analyze_compare_data_file: performed reference copy")
                print(s)
                run.analyze_results.append(s)
                run.analyze_successful=False
                Analyze.total_errors+=1
                # do not skip the following analysis tests, because reference file will be created -> continue
                continue 

            if not os.path.exists(path) or not os.path.exists(path_ref_target) :
                s=tools.red("Analyze_compare_data_file: cannot find both file=[%s] and reference file=[%s]" % (file_name, ref_name))
                print(s)
                run.analyze_results.append(s)
                run.analyze_successful=False
                Analyze.total_errors+=1
                return # skip the following analysis tests
            
            # 1.3.1   read data file
            line = []
            with open(path, 'rb') as csvfile:
                line_str = csv.reader(csvfile, delimiter=self.delimiter, quotechar='!')
                i=0
                header=0
                for row in line_str:
                    try :
                        line = np.array([float(x) for x in row])
                    except :
                        header+=1
                        header_line = row
                    i+=1
                    if i == self.line :
                        print(tools.yellow(str(i)), end=' ') # skip linebreak
                        break
                line_len = len(line)
            
            # 1.3.2   read refernece file
            line_ref = []
            with open(path_ref_target, 'rb') as csvfile:
                line_str = csv.reader(csvfile, delimiter=self.delimiter, quotechar='!')
                header_ref=0
                for row in line_str:
                    try :
                        line_ref = np.array([float(x) for x in row])
                    except :
                        header_ref+=1
                line_ref_len = len(line_ref)

            # 1.3.3   check length of vectors
            if line_len != line_ref_len :
                s=tools.red("Analyze_compare_data_file: length of lines in file [%s] and reference file [%s] are not of the same length" % (file_name, ref_name))
                print(s)
                run.analyze_results.append(s)
                run.analyze_successful=False
                Analyze.total_errors+=1
                return # skip the following analysis tests

            # 1.3.4   calculate difference and determine compare with tolerance
            success = tools.diff_lists(line, line_ref, self.tolerance, self.tolerance_type)
            if not all(success) :
                s = tools.red("Mismatch in columns: "+", ".join([str(header_line[i]).strip() for i in range(len(success)) if not success[i]]))
                print(s)
                run.analyze_results.append(s)
                run.analyze_successful=False
                Analyze.total_errors+=1
            

    def __str__(self) :
        return "compare line in data file (e.g. .csv file): file=[%s] and reference file=[%s]" % (self.file, self.reference)



#==================================================================================================

class Analyze_integrate_line(Analyze) :
    def __init__(self, integrate_line_file, integrate_line_delimiter, integrate_line_columns, integrate_line_integral_value, integrate_line_tolerance_value, integrate_line_tolerance_type, integrate_line_option, integrate_line_multiplier) :
        self.file                = integrate_line_file
        self.delimiter           = integrate_line_delimiter
        (self.dim1, self.dim2)   = [int(x)   for x in integrate_line_columns.split(":")]
        self.integral_value      = float(integrate_line_integral_value)
        self.tolerance_value     = float(integrate_line_tolerance_value)
        self.tolerance_type      = integrate_line_tolerance_type
        self.option              = integrate_line_option
        self.multiplier          = float(integrate_line_multiplier)

    def perform(self,runs) :

        '''
        General workflow:
        1.  iterate over all runs
        1.2   Check existence the file and reference values
        1.3.1   read data file
        1.3.2   check column numbers
        1.3.3   get header information for integrated columns
        1.3.4   split the data array and set the two column vector x and y for integration
        1.4   integrate values numerically
        '''

        # 1.  iterate over all runs
        for run in runs :
            # 1.2   Check existence the file and reference values
            path     = os.path.join(run.target_directory,self.file)
            if not os.path.exists(path) :
                s=tools.red("Analyze_integrate_line: cannot find file=[%s] " % (self.file))
                print(s)
                run.analyze_results.append(s)
                run.analyze_successful=False
                Analyze.total_errors+=1
                return
            
            data = np.array([])
            # 1.3.1   read data file
            with open(path, 'rb') as csvfile:
                line_str = csv.reader(csvfile, delimiter=self.delimiter, quotechar='!')
                max_lines=0
                header=0
                for row in line_str:
                    try : # try reading a line from the data file and converting it into a numpy array
                        line = np.array([float(x) for x in row])
                        failed = False
                    except : # 
                        header+=1
                        header_line = row
                        failed = True
                    if not failed :
                        data = np.append(data, line)
                    max_lines+=1

            if failed :
                s="Analyze_integrate_line: reading of the data file [%s] has failed.\nNo float type data could be read. Check the file content." %path
                print(tools.red(s))
                run.analyze_results.append(s)
                run.analyze_successful=False
                Analyze.total_errors+=1
                return

            # 1.3.2 check column numbers
            line_len = len(line) - 1
            if line_len < self.dim1 or line_len < self.dim2 :
                s="cannot perform analyze Analyze_integrate_line, because the supplied columns (%s:%s) exceed the columns (%s) in the data file (the first column starts at 0)" % (self.dim1, self.dim2, line_len)
                print(tools.red(s))
                run.analyze_results.append(s)
                run.analyze_successful=False
                Analyze.total_errors+=1
                return

            # 1.3.3   get header information for integrated columns
            if header > 0 :
                for i in range(line_len+1) :
                    header_line[i] = header_line[i].replace(" ", "")
                    #print header_line[i]
                s1 = header_line[self.dim1]
                s2 = header_line[self.dim2]
                print(tools.indent(tools.blue("Integrating the column [%s] over [%s]: " % (s2,s1)),2), end=' ') # skip linebreak
            
            # 1.3.4   split the data array and set the two column vector x and y for integration
            data = np.reshape(data, (-1, line_len +1))
            data =  np.transpose(data)
            x = data[self.dim1]
            y = data[self.dim2]

            # 1.4 integrate the values numerically
            Q=0.0
            for i in range(max_lines-header-1) :
                # use trapezoidal rule (also known as the trapezoid rule or trapezium rule)
                dx = x[i+1]-x[i]
                if self.option == 'DivideByTimeStep' :
                    dQ = (y[i+1]+y[i])/2.0
                else :
                    dQ = dx * (y[i+1]+y[i])/2.0
                Q += dQ
            Q = Q*self.multiplier
            print("integrated value (trapezoid rule) Q = %s" % Q)
            
            # 1.5   calculate difference and determine compare with tolerance
            success = tools.diff_value(Q, self.integral_value, self.tolerance_value, self.tolerance_type)
            if not success :
                s=tools.red("Mismatch in integrated line: value %s compared with reference value %s (tolerance %s and %s comparison)" % (Q, self.integral_value, self.tolerance_value, self.tolerance_type))
                print(s)
                run.analyze_successful=False
                run.analyze_results.append(s)
                Analyze.total_errors+=1


    def __str__(self) :
        return "integrate column data over line (e.g. from .csv file): file=[%s] and integrate columns %s over %s (the first column starts at 0)" % (self.file, self.dim2, self.dim1)

