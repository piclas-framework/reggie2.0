# -*- coding: utf-8 -*-
# ==================================================================================================================================
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
# ==================================================================================================================================
from __future__ import print_function  # required for print() function with line break via "end=' '"
import os
import numpy as np
from externalcommand import ExternalCommand
import analyze_functions
import combinations
import tools
import csv
import logging
import glob
import shutil
import types

# import h5 I/O routines
try:
    import h5py

    h5py_module_loaded = True
except ImportError:
    # raise ImportError('Could not import h5py module. This is required for anaylze functions.')
    print(tools.red('Could not import h5py module. This is required for anaylze functions.'))
    h5py_module_loaded = False

# import vtk I/O routines
try:
    import vtk
    import vtk.util.numpy_support

    vtk_module_loaded = True
except ImportError:
    # raise ImportError('Could not import vtk module. This is required for anaylze functions.')
    print(tools.red('Could not import vtk module. This is required for anaylze functions.'))
    vtk_module_loaded = False

# import pyplot for creating plots
try:
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator  # required for setting axis format to integer only (p-convergence)

    pyplot_module_loaded = True  # will be set false if user does not supply read-in flag in getAnalyzes(path, example) function
except ImportError:
    # raise ImportError('Could not import matplotlib.pyplot module. This is required for anaylze functions.')
    print(tools.red('Could not import matplotlib.pyplot module. This is required for anaylze functions.'))
    pyplot_module_loaded = False

# Check if types.SimpleNamespace is available
try:
    SimpleNamespace = types.SimpleNamespace  # Python 3.3+
except AttributeError:
    # For older python versions than Python 3.3, the class can be implemented as follows (in Python 3.3 the implementation is in C)
    class SimpleNamespace(object):
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

        def __repr__(self):
            keys = sorted(self.__dict__)
            items = ("{}={!r}".format(k, self.__dict__[k]) for k in keys)
            return "{}({})".format(type(self).__name__, ", ".join(items))

        def __eq__(self, other):
            return self.__dict__ == other.__dict__


def displayTable(mylist, nVar, nRuns):  # noqa: D103 Missing docstring in public function
    # mylist = [ [1 2 3] [1 2 3] [1 2 3] [1 2 3] ] example with 4 nVar and 3 nRuns
    print(" nRun   " + "   ".join(7 * " " + "nVar=[" + str(i).rjust(4) + "]" for i in range(nVar)))
    for j in range(nRuns):
        print(str(j).rjust(5), end=' ')  # skip linebreak
        for i in range(nVar):
            print("%20.12e" % mylist[i][j], end=' ')  # skip linebreak
        print("")


def writeTableToFile(mylist, nVar, nRuns, firstColumn, path, name):  # noqa: D103 Missing docstring in public function
    # if a path is supplied, create a .csv file with the data
    if path is not None:
        myfile = os.path.join(path, name)
        with open(myfile, 'w') as f:
            for j in range(nRuns):
                line = "%20.12e, " % firstColumn[j]
                line += ",".join("%20.12e" % mylist[i][j] for i in range(nVar))
                f.write(line + "\n")


def displayVector(vector, nVar):  # noqa: D103 Missing docstring in public function
    print(8 * " " + "   ".join(7 * " " + "nVar=[" + str(i).rjust(4) + "]" for i in range(nVar)))
    print(6 * " " + " ".join("%20.12e" % vector[i] for i in range(nVar)))


def copyReferenceFile(run, path, path_ref_source):
    """Copy new reference file: This is completely independent of the outcome of the current compare data file"""
    # Check whether the file for copying exists
    if not os.path.exists(path):
        s = tools.red("copyReferenceFile: Could not find file=[%s] for copying" % path)
        print(s)
        exit(1)

    # Check whether the destination for copying the file exists
    if not os.path.exists(os.path.dirname(path_ref_source)):
        s = tools.red("copyReferenceFile: Could not find location=[%s] for copying" % os.path.dirname(path_ref_source))
        print(s)
        exit(1)

    # Copy file and create new reference
    shutil.copy(path, path_ref_source)
    s = tools.yellow("New reference files are copied from file=[%s] to file=[%s]" % (path, path_ref_source))
    print(s)
    run.analyze_results.append(s)
    run.analyze_successful = False
    return run


# ==================================================================================================


def getAnalyzes(path, example, args):
    """
    For every example a list of analyzes is built from the specified anaylzes in 'analyze.ini'. The anaylze list is performed after a set of runs is completed.

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
    2.9   compare data file column
    """
    global pyplot_module_loaded

    # 1.  Read the analyze options from file 'path'
    analyze = []  # list
    options_list, _, _ = combinations.readKeyValueFile(path)

    options = {}  # dict
    for option in options_list:
        # set all upper case characters to lower case
        if len(option.values) > 1:
            options[option.name.lower()] = option.values  # set name to lower case
        else:
            options[option.name.lower()] = option.values[0]  # set name to lower case

        # check for empty lists and abort
        if option.values[0] == '':
            raise Exception(tools.red("initialization of analyze.ini failed due to empty parameter [%s = %s], which is not allowed." % (option.name, option.values)))

    # 1.1   Check for general analyze options
    # only use matplot lib if the user wants to (can cause problems on some systems causing "system call itnerrupt" errors randomly aborting the program)
    use_matplot_lib = options.get('use_matplot_lib', 'False')
    if pyplot_module_loaded:
        if use_matplot_lib in ('True', 'true', 't', 'T'):
            pyplot_module_loaded = True
        else:
            pyplot_module_loaded = False

    # 1.3 Get the names of the files (incl. wildcards) which are to be deleted in the anaylsis stage
    clean_up_files = options.get('clean_up_files', None)
    if clean_up_files:
        analyze.append(Clean_up_files(clean_up_files))

    # 2.0   L2 error from file
    # fmt: off
    L2ErrorFile = SimpleNamespace( \
                  file           =       options.get('analyze_l2_file',None), \
                  tolerance      = float(options.get('analyze_l2_file_tolerance',1.0e-5)), \
                  tolerance_type =       options.get('analyze_l2_file_tolerance_type','absolute'), \
                  error_name     =       options.get('L2_file_error_name','L_2') )
    # fmt: on
    if L2ErrorFile.file:
        if L2ErrorFile.tolerance_type in ('absolute', 'delta', '--delta'):
            L2ErrorFile.tolerance_type = "absolute"
        elif L2ErrorFile.tolerance_type in ('relative', "--relative"):
            L2ErrorFile.tolerance_type = "relative"
        else:
            raise Exception(tools.red("initialization of L2 error from file failed. [L2_file_tolerance_type = %s] not accepted." % L2ErrorFile.tolerance_type))
        analyze.append(Analyze_L2_file(L2ErrorFile))

    # 2.1   L2 error upper limit
    L2Error = SimpleNamespace(tolerance=float(options.get('analyze_l2', -1.0)), error_name=options.get('l2_error_name', 'L_2'))
    if L2Error.tolerance > 0:
        analyze.append(Analyze_L2(L2Error))

    # 2.2   h-convergence test
    # fmt: off
    ConvtestH = SimpleNamespace( \
                cells      = [float(cell) for cell in options.get('analyze_convtest_h_cells',['-1.'])], \
                tolerance  = float(options.get('analyze_convtest_h_tolerance',1e-2)), \
                rate       = float(options.get('analyze_convtest_h_rate',1)), \
                error_name =       options.get('analyze_convtest_h_error_name','L_2') )
    # fmt: on
    # only do convergence test if supplied cells count > 0
    if min(ConvtestH.cells) > 0 and ConvtestH.tolerance > 0 and 0.0 <= ConvtestH.rate <= 1.0:
        analyze.append(Analyze_Convtest_h(ConvtestH))

    # 2.3   p-convergence test
    # fmt: off
    ConvtestP = SimpleNamespace( \
                rate       = float(options.get('analyze_convtest_p_rate',-1)), \
                percentage = float(options.get('analyze_convtest_p_percentage',0.75)), \
                error_name = options.get('analyze_convtest_p_error_name','L_2') )
    # fmt: on
    # only do convergence test if convergence rate and tolerance >0
    if 0.0 <= ConvtestP.rate <= 1.0:
        analyze.append(Analyze_Convtest_p(ConvtestP))

    # 2.4   t-convergence test
    # One of the four following methods can be used. The sequence is of selection is fixed
    #   initial_timestep = None
    #   timestep_factor  = [-1.]
    #   total_timesteps  = None
    #   timesteps        = [-1.]

    # 2.4.1   must have the following form: "Initial Timestep  :    1.8503722E-01"
    # fmt: off
    ConvtestTime = SimpleNamespace( \
                   initial_timestep = options.get('analyze_convtest_t_initial_timestep',None), \
                   tolerance        = float(options.get('analyze_convtest_t_tolerance',1e-2)), \
                   rate             = float(options.get('analyze_convtest_t_rate',1)), \
                   error_name       = options.get('analyze_convtest_t_error_name','L_2'), \
                   order            = float(options.get('analyze_convtest_t_order',-1000)), \
                   timestep_factor  = [-1.], \
                   total_timesteps  = None, \
                   timesteps        = [-1.], \
                   )

    if ConvtestTime.initial_timestep is None :
        # 2.4.2   supply the timestep_factor externally
        ConvtestTime.timestep_factor         = [float(timestep) for timestep in options.get('analyze_convtest_t_timestep_factor',['-1.'])]

        if min(ConvtestTime.timestep_factor) <= 0.0 :
            # 2.4.3   automatically get the total number of timesteps must have the following form: "#Timesteps :    1.6600000E+02"
            ConvtestTime.total_timesteps   = options.get('analyze_convtest_t_total_timesteps',None)

            if ConvtestTime.total_timesteps is None :
                # 2.4.4   supply the timesteps externally
                ConvtestTime.timesteps       = [float(timesteps) for timesteps in options.get('analyze_convtest_t_timesteps',['-1.'])]
                if min(ConvtestTime.timesteps) <= 0.0 :
                    ConvtestTime.method      = 0
                    ConvtestTime.method_name = None
                else :
                    ConvtestTime.method      = 4
                    ConvtestTime.method_name = 'timesteps from analyze.ini'
            else :
                ConvtestTime.method      = 3
                ConvtestTime.method_name = 'total number of timesteps ['+ConvtestTime.total_timesteps+']'
        else :
            ConvtestTime.method      = 2
            ConvtestTime.method_name = 'timestep_factor from analyze.ini'
    else :
        ConvtestTime.method      = 1
        ConvtestTime.method_name = 'initial_timestep ['+ConvtestTime.initial_timestep+']'
    # fmt: on

    # only do convergence test if supplied cells count > 0
    if ConvtestTime.tolerance > 0 and 0.0 <= ConvtestTime.rate <= 1.0 and ConvtestTime.method_name and ConvtestTime.order > -1000:
        logging.getLogger('logger').info("t-convergence test: Choosing " + ConvtestTime.method_name + " (method = " + str(ConvtestTime.method) + ")")
        analyze.append(Analyze_Convtest_t(ConvtestTime))

        # analyze.append(Analyze_Convtest_t(convtest_t_order , convtest_t_error_name , convtest_t_tolerance , convtest_t_rate , convtest_t_method , convtest_t_name , convtest_t_initial_timestep , convtest_t_timestep_factor , convtest_t_total_timesteps , convtest_t_timesteps)) # noqa: E501
        # def __init__(                                order , name                  , tolerance            , rate            , method            , method_name     , ini_timestep                , timestep_factor            , total_iter                 , iters) : # noqa: E501

    # 2.5   h5diff (relative or absolute HDF5-file comparison of an output file with a reference file)
    # options can be read in multiple times to realize multiple compares for each run
    # fmt: off
    h5diff = SimpleNamespace( \
             one_diff_per_run = options.get('h5diff_one_diff_per_run',False), \
             reference_file   = options.get('h5diff_reference_file',None), \
             file             = options.get('h5diff_file',None), \
             data_set         = options.get('h5diff_data_set',None), \
             tolerance_value  = options.get('h5diff_tolerance_value',1.0e-5), \
             tolerance_type   = options.get('h5diff_tolerance_type','absolute'), \
             sort             = options.get('h5diff_sort',False), \
             sort_dim         = options.get('h5diff_sort_dim',-1), \
             sort_var         = options.get('h5diff_sort_var',-1), \
             reshape          = options.get('h5diff_reshape',False), \
             reshape_dim      = options.get('h5diff_reshape_dim',-1), \
             reshape_value    = options.get('h5diff_reshape_value',-1), \
             flip             = options.get('h5diff_flip',False), \
             max_differences  = options.get('h5diff_max_differences',0), \
             var_attribute    = options.get('h5diff_var_attribute',None), \
             var_name         = options.get('h5diff_var_name',None), \
             referencescopy   = args.referencescopy )
    # fmt: on
    # only do h5diff test if all variables are defined
    if h5diff.reference_file and h5diff.file and h5diff.data_set:
        analyze.append(Analyze_h5diff(h5diff))

    # 2.6   vtudiff (relative and/or absolute vtu-file comparison of an output file with a reference file)
    # options can be read in multiple times to realize multiple compares for each run
    # default values for tolerance are set in the Analyze_vtudiff class, to enable only using one type but also both together
    vtudiff = SimpleNamespace(
        one_diff_per_run=options.get('vtudiff_one_diff_per_run', False),
        reference_file=options.get('vtudiff_reference_file', None),
        file=options.get('vtudiff_file', None),
        abs_tolerance_value=options.get('vtudiff_absolute_tolerance_value', None),
        rel_tolerance_value=options.get('vtudiff_relative_tolerance_value', None),
        sort=options.get('vtudiff_sort', False),
        sort_dim=options.get('vtudiff_sort_dim', -1),
        sort_var=options.get('vtudiff_sort_var', -1),
        reshape=options.get('vtudiff_reshape', False),
        reshape_dim=options.get('vtudiff_reshape_dim', -1),
        reshape_value=options.get('vtudiff_reshape_value', -1),
        flip=options.get('vtudiff_flip', False),
        max_differences=options.get('vtudiff_max_differences', 0),
        array_name=options.get('vtudiff_array_name', None),
        referencescopy=args.referencescopy,
    )
    # only do vtudiff test if all variables are defined
    if vtudiff.reference_file and vtudiff.file:
        analyze.append(Analyze_vtudiff(vtudiff))

    # 2.7   check array bounds in hdf5 file
    # check_hdf5_span: use row or column (default is column)
    # fmt: off
    CheckHDF5 = SimpleNamespace( \
                file           = options.get('check_hdf5_file',None), \
                data_set       = options.get('check_hdf5_data_set',None), \
                span           = options.get('check_hdf5_span',2), \
                dimension      = options.get('check_hdf5_dimension',None),\
                limits         = options.get('check_hdf5_limits',None) )
    if all([CheckHDF5.file, CheckHDF5.data_set, CheckHDF5.dimension, CheckHDF5.limits]) :
        analyze.append(Analyze_check_hdf5(CheckHDF5))

    # 2.8   check data file row
    CompareDataFile = SimpleNamespace( \
                      one_diff_per_run = options.get('compare_data_file_one_diff_per_run',True), \
                      name             = options.get('compare_data_file_name',None), \
                      reference        = options.get('compare_data_file_reference',None), \
                      tolerance        = options.get('compare_data_file_tolerance',None), \
                      tolerance_type   = options.get('compare_data_file_tolerance_type','absolute'), \
                      line             = options.get('compare_data_file_line','last'), \
                      delimiter        = options.get('compare_data_file_delimiter',','), \
                      max_differences  = options.get('compare_data_file_max_differences',0), \
                      referencescopy   = args.referencescopy )
    if CompareDataFile.name and CompareDataFile.reference and CompareDataFile.tolerance:
        analyze.append(Analyze_compare_data_file(CompareDataFile))

    # 2.9   integrate data file column
    #   integrate_line_file            : file name (path) which is analyzed
    #   integrate_line_delimiter       : delimiter symbol if not comma-separated
    #   integrate_line_columns         : two columns for the values x and y supplied as 'x:y'
    #   integrate_line_integral_value  : integral value used for comparison
    #   integrate_line_tolerance_value : tolerance that is used in comparison
    #   integrate_line_tolerance_type  : type of tolerance, either 'absolute' or 'relative'
    #   integrate_line_option          : special option, e.g., calculating a rate by dividing the integrated values by the time step which is used in the values 'x'
    #   integrate_line_multiplier      : factor for multiplying the result (in order to acquire a physically meaning value for comparison)
    IntegrateLine = SimpleNamespace( \
                    file            = options.get('integrate_line_file',None), \
                    delimiter       = options.get('integrate_line_delimiter',','), \
                    columns         = options.get('integrate_line_columns',None), \
                    integral_value  = options.get('integrate_line_integral_value',None), \
                    tolerance_value = options.get('integrate_line_tolerance_value',1e-5), \
                    tolerance_type  = options.get('integrate_line_tolerance_type','absolute'), \
                    option          = options.get('integrate_line_option',None), \
                    multiplier      = options.get('integrate_line_multiplier',1) )
    if all([IntegrateLine.file,  IntegrateLine.delimiter, IntegrateLine.columns, IntegrateLine.integral_value]) :
        if IntegrateLine.tolerance_type in ('absolute', 'delta', '--delta') :
            IntegrateLine.tolerance_type = "absolute"
        elif IntegrateLine.tolerance_type in ('relative', "--relative") :
            IntegrateLine.tolerance_type = "relative"
        else :
            raise Exception(tools.red("initialization of integrate line failed. integrate_line_tolerance_type '%s' not accepted." % IntegrateLine.tolerance_type))
        analyze.append(Analyze_integrate_line(IntegrateLine))

    # 2.10   compare data file column
    #   compare_column_file            : file name (path) which is analyzed
    #   compare_column_reference_file  : reference file name (path)
    #   compare_column_delimiter       : delimiter symbol if not comma-separated
    #   compare_column_index           : index of the column that is to be compared
    #   compare_column_tolerance_value : tolerance that is used in comparison
    #   compare_column_tolerance_type  : type of tolerance, either 'absolute' or 'relative'
    #   compare_column_multiplier      : factor for multiplying the result (in order to acquire a physically meaning value for comparison)
    CompareColumn = SimpleNamespace( \
                    one_diff_per_restart_file   = options.get('compare_column_one_diff_per_restart_file',False), \
                    one_diff_per_run            = options.get('compare_column_one_diff_per_run',True), \
                    file                        = options.get('compare_column_file',None), \
                    reference_file              = options.get('compare_column_reference_file',None), \
                    delimiter                   = options.get('compare_column_delimiter',','), \
                    index                       = options.get('compare_column_index',None), \
                    tolerance_value             = options.get('compare_column_tolerance_value',1e-5), \
                    tolerance_type              = options.get('compare_column_tolerance_type','absolute'), \
                    multiplier                  = options.get('compare_column_multiplier',1), \
                    referencescopy              = args.referencescopy )
    if all([CompareColumn.file, CompareColumn.reference_file,  CompareColumn.delimiter, CompareColumn.index]) :
        analyze.append(Analyze_compare_column(CompareColumn,example))

    # 2.11   compare corresponding files from different commands
    #   compare_across_commands_file             : file name (path) which is analyzed
    #   compare_across_commands_column_delimiter : delimiter symbol if not comma-separated
    #   compare_across_commands_column_index     : index of the column that is to be compared
    #   compare_across_commands_line_number      :
    #   compare_across_commands_tolerance_value  : tolerance that is used in comparison
    #   compare_across_commands_tolerance_type   : type of tolerance, either 'absolute' or 'relative'
    #   compare_across_commands_reference        :
    CompareAcrossCommands = SimpleNamespace( \
                            file             = options.get('compare_across_commands_file',None), \
                            column_delimiter = options.get('compare_across_commands_column_delimiter',','), \
                            column_index     = options.get('compare_across_commands_column_index',None), \
                            line_number      = options.get('compare_across_commands_line_number','last'), \
                            tolerance_value  = options.get('compare_across_commands_tolerance_value',1e-5), \
                            tolerance_type   = options.get('compare_across_commands_tolerance_type','absolute'), \
                            reference        = options.get('compare_across_commands_reference',0) )
    if all([CompareAcrossCommands.file, CompareAcrossCommands.column_delimiter, CompareAcrossCommands.column_index, CompareAcrossCommands.line_number, CompareAcrossCommands.reference ]) :
        if CompareAcrossCommands.tolerance_type in ('absolute', 'delta', '--delta') :
            CompareAcrossCommands.tolerance_type = "absolute"
        elif CompareAcrossCommands.tolerance_type in ('relative', "--relative") :
            CompareAcrossCommands.tolerance_type = "relative"
        else :
            raise Exception(tools.red("initialization of compare across commands failed. compare_across_commands_tolerance_type '%s' not accepted." % CompareAcrossCommands.tolerance_type))
        analyze.append(Analyze_compare_across_commands(CompareAcrossCommands))
    # fmt: on

    return analyze


# ==================================================================================================


class Analyze:  # main class from which all analyze functions are derived
    total_errors = 0  # errors gathered during run
    total_infos = 0  # information/warnings gathered during run


# ==================================================================================================


class Clean_up_files:
    """Clean up the output folder by deleting specified files"""

    def __init__(self, clean_up_files):
        self.files = clean_up_files

    def perform(self, runs):  # noqa: ARG002
        return  # do nothing

    def execute(self, run):
        """
        General workflow:

        1.  Iterate over all runs
        1.1   remove all files that are specified (if they exist)
        """
        # 1.1   remove all files that are specified (if they exist)
        for remove_file in self.files:
            path = os.path.join(run.target_directory, remove_file)

            wildcards = glob.glob(path)
            for wildcard in wildcards:
                if not os.path.exists(wildcard):
                    s = tools.red("Clean_up_files: Could not find file=[%s] for removing" % wildcard)
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    continue
                else:
                    print(tools.yellow("[remove_folder]: deleting file '%s'" % wildcard))
                    os.remove(wildcard)

    def __str__(self):
        return "Clean up the output folder by deleting specified files"


# ==================================================================================================


class Analyze_L2_file(Analyze):
    """Read the L2 error norms from std.out and compare with pre-defined upper barrier"""

    def __init__(self, L2ErrorFile):
        self.file = L2ErrorFile.file
        self.L2_tolerance = L2ErrorFile.tolerance
        self.L2_tolerance_type = L2ErrorFile.tolerance_type
        self.error_name = L2ErrorFile.error_name  # string name of the L2 error in the std.out file (default is "L_2")

    def perform(self, runs):
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
        LastLines = 2000  # search the last X lines in the std.out file for the L2 error
        # 1.  Iterate over all runs
        for run in runs:
            # 1.1   Read L2 errors from std out channel
            try:
                L2_errors = np.array(analyze_functions.get_last_L2_error(run.stdout, self.error_name, LastLines))
            except Exception:
                s = tools.red("L2 analysis failed: L2 error could not be read from %s (searching for %s in the last %s lines)" % ('std.out', self.error_name, LastLines))
                print(s)

                # 1.1.1   append info for summary of errors
                run.analyze_results.append(s)

                # 1.1.2   set analyzes to fail
                run.analyze_successful = False
                Analyze.total_errors += 1
                continue  # with next run

            # 1.2   Check existence of the reference file
            path_ref = os.path.join(run.target_directory, self.file)

            if not os.path.exists(path_ref):
                s = tools.red("Analyze_L2_file: cannot find reference L2 error file=[%s]" % self.file)
                print(s)
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
                continue  # with next run
            else:
                # 1.2.1   Read content of the reference file and store in self.file_data list
                self.file_data = []
                with open(path_ref) as f:
                    for line in f.readlines():  # iterate over all lines of the file
                        self.file_data.append(line)

            # 1.2   Read reference L2 errors from self.file_data list
            try:
                L2_errors_ref = np.array(analyze_functions.get_last_L2_error(self.file_data, self.error_name, LastLines))
            except Exception:
                s = tools.red("L2 analysis failed: L2 error could not be read from %s (searching for %s in the last %s lines)" % (self.file, self.error_name, LastLines))
                print(s)

                # 1.2.1   append info for summary of errors
                run.analyze_results.append(s)

                # 1.2.2   set analyzes to fail
                run.analyze_successful = False
                Analyze.total_errors += 1
                continue  # with next run

            # 1.3   Check length of L2 errors in std out and reference file
            if len(L2_errors) != len(L2_errors_ref):
                s = tools.red("L2 analysis failed: number of L2 errors in std out [%s] do not match number of L2 errors in ref file [%s]. They must be the same." % (len(L2_errors), len(L2_errors_ref)))
                print(s)

                # 1.2.1   append info for summary of errors
                run.analyze_results.append(s)

                # 1.2.2   set analyzes to fail
                run.analyze_successful = False
                Analyze.total_errors += 1
                continue  # with next run

            # 1.4   calculate difference and determine compare with tolerance
            success = tools.diff_lists(L2_errors, L2_errors_ref, self.L2_tolerance, self.L2_tolerance_type)
            if not all(success):
                s = tools.red("Mismatch in L2 error comparison with reference file data: " + ", ".join(["[%s with %s]" % (L2_errors[i], L2_errors_ref[i]) for i in range(len(success)) if not success[i]]))
                print(s)

                # 1.4.1   append info for summary of errors
                run.analyze_results.append(s)

                # 1.4.2   set analyzes to fail
                run.analyze_successful = False
                Analyze.total_errors += 1

    def __str__(self):
        return "perform L2 error comparison with L2 errors in file [%s], tolerance=%s (%s) for error named [%s]" % (self.file, self.L2_tolerance, self.L2_tolerance_type, self.error_name)


# ==================================================================================================


class Analyze_L2(Analyze):
    """Read the L2 error norms from std.out and compare with pre-defined upper barrier"""

    def __init__(self, L2Error):
        self.L2_tolerance = L2Error.tolerance  # tolerance value for comparison with the L_2 error from std.out
        self.error_name = L2Error.error_name  # string name of the L2 error in the std.out file (default is "L_2")

    def perform(self, runs):
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
        LastLines = 2000  # search the last X lines in the std.out file for the L2 error
        # 1.  Iterate over all runs
        for run in runs:
            # 1.1   read L2 errors from 'std.out' file
            try:
                L2_errors = np.array(analyze_functions.get_last_L2_error(run.stdout, self.error_name, LastLines))
            except Exception:
                s = tools.red("L2 analysis failed: L2 error could not be read from %s (searching for %s in the last %s lines)" % ('std.out', self.error_name, LastLines))
                print(s)

                # 1.1.1   append info for summary of errors
                run.analyze_results.append(s)

                # 1.1.2   set analyzes to fail
                run.analyze_successful = False
                Analyze.total_errors += 1
                continue

            L2_errors_str = "[" + ", ".join(str(x) for x in L2_errors) + "]"
            # 1.2   if one L2 errors is larger than the tolerance -> fail
            if (L2_errors > self.L2_tolerance).any():
                s = tools.red("analysis failed. L2 error: L2_errors > " + str(self.L2_tolerance) + " " + L2_errors_str)
                print(s)

                # 1.3   append info for summary of errors
                run.analyze_results.append(s)

                # 1.4   set analyzes to fail
                run.analyze_successful = False
                Analyze.total_errors += 1
            else:
                print(tools.indent(tools.blue('%s: %s' % (self.error_name, L2_errors_str)), 2))

    def __str__(self):
        return "perform L2 error comparison with a pre-defined tolerance=%s for %s:" % (self.L2_tolerance, self.error_name)


# ==================================================================================================


class Analyze_Convtest_h(Analyze):
    """
    Convergence test for a fixed polynomial degree and different meshes defined in 'parameter.ini'

    The analyze routine read the L2 error norm from a set of runs and determines the order of convergence
    between the runs and averages the values. The average is compared with the polynomial degree p+1.
    """

    def __init__(self, ConvtestH):
        # fmt: off
        self.cells = ConvtestH.cells           # number of cells used for h-convergence calculation (only the ratio of two
                                               # consecutive values is important for the EOC calcultion)
        self.tolerance = ConvtestH.tolerance   # determine success rate by comparing the relative convergence error with a tolerance
        self.rate = ConvtestH.rate             # success rate: for each nVar, the EOC is determined (the number of successful EOC vs.
                                               # the number of total EOC tests determines the success rate which is compared with this rate)
        self.error_name = ConvtestH.error_name # string name of the L2 error in the std.out file (default is "L_2")
        # fmt: on

    def perform(self, runs):
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

        LastLines = 2000  # search the last X lines in the std.out file for the L2 error
        # 1.  check if number of successful runs is equal the number of supplied cells
        nRuns = len(runs)
        if nRuns < 2:
            for run in runs:
                s = "analysis failed: h-convergence not possible with only 1 run"
                print(tools.red(s))
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
                return
        if len(self.cells) == nRuns:
            # 1.1   read the polynomial degree from the first run -> must not change!
            p = float(runs[0].parameters.get('N', -1))

            # 1.2   get L2 errors of all runs and create np.array
            try:
                L2_errors = np.array([analyze_functions.get_last_L2_error(run.stdout, self.error_name) for run in runs])
                L2_errors = np.transpose(L2_errors)
            except Exception:
                for run in runs:  # find out exactly which L2 error could not be read
                    try:
                        L2_errors_test = np.array(analyze_functions.get_last_L2_error(run.stdout, self.error_name, LastLines))  # noqa: F841 local variable 'test' is assigned to but never used
                    except Exception:  # noqa: PERF203 `try`-`except` within a loop incurs performance
                        s = tools.red("h-convergence failed: L2 error could not be read from %s (searching for %s in the last %s lines)" % ('std.out', self.error_name, LastLines))
                        print(s)

                        # 1.2.1   append info for summary of errors
                        run.analyze_results.append(s)

                        # 1.2.2   set analyzes to fail
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                return

            # 1.3   get number of variables from L2 error array
            nVar = len(L2_errors)
            print(tools.blue("L2 errors for nVar=" + str(nVar)))
            displayTable(L2_errors, nVar, nRuns)

            # 1.4   determine order of convergence between two runs
            L2_order = np.array([analyze_functions.calcOrder_h(self.cells, L2_errors[i]) for i in range(nVar)])
            print(tools.blue("L2 orders for nVar=" + str(nVar)))
            displayTable(L2_order, nVar, nRuns - 1)

            # 1.4.1   determine average convergence rate
            mean = [np.mean(L2_order[i]) for i in range(nVar)]
            print(tools.blue("L2 average order for nVar=%s (expected order = %s)" % (nVar, p + 1)))
            displayVector(mean, nVar)

            if pyplot_module_loaded:  # this boolean is set when importing matplotlib.pyplot
                f = plt.figure()  # create figure
                for i in range(nVar):
                    if 1 == 2:
                        self.grid_spacing = [1.0 / ((p + 1) * float(x)) for x in self.cells]
                        plt.plot(self.grid_spacing, L2_errors[i], 'ro-')  # create plot
                        plt.xlabel('Average grid spacing for unit domain length L_domain=1')  # set x-label
                    else:
                        plt.plot(self.cells, L2_errors[i], 'ro-')  # create plot
                        plt.xlabel('Number of cells')  # set x-label
                    if min(L2_errors[i]) > 0.0:  # log plot only if greater zero
                        plt.xscale('log')  # set x-axis to log scale
                        plt.yscale('log')  # set y-axis to log scale
                    plt.title('nVar = %s (of %s), MIN = %4.2e, MAX = %4.2e, O(%.2f)' % (i, nVar - 1, min(L2_errors[i]), max(L2_errors[i]), mean[i]))  # set title
                    plt.ylabel('L2 error norm')  # set y-label
                    # plt.show() # display the plot figure for the user (comment out when running in batch mode)
                    f_save_path = os.path.join(os.path.dirname(runs[0].target_directory), "L2_error_nVar" + str(i) + "_order%.2f.pdf" % mean[i])  # set file path for saving the figure to the disk
                    f.savefig(f_save_path, bbox_inches='tight')  # save figure to .pdf file
                    plt.cla()
                plt.close(f)
            else:
                print(
                    tools.yellow(
                        'Could not import matplotlib.pyplot module. ' 'This is required for creating plots under "Analyze_Convtest_h(Analyze)". \nSet "use_matplot_lib=True" in analyze.ini in order to activate plotting.'
                    )
                )

            # 1.4.2   write L2 error data to file
            writeTableToFile(L2_errors, nVar, nRuns, self.cells, os.path.dirname(runs[0].target_directory), "L2_error_order%.2f.csv" % mean[0])

            # 1.5   determine success rate by comparing the relative convergence error with a tolerance
            print(tools.blue("relative order error (tolerance = %.4e)" % self.tolerance))
            relErr = [abs(mean[i] / (p + 1) - 1) for i in range(nVar)]
            displayVector(relErr, nVar)
            success = [relErr[i] < self.tolerance for i in range(nVar)]
            print(tools.blue("success convergence"))
            print(5 * " " + "".join(str(success[i]).rjust(21) for i in range(nVar)))

            # 1.6   compare success rate with pre-defined rate, fails if not reached
            if float(sum(success)) / nVar >= self.rate:
                print(tools.blue("h-convergence successful"))
            else :  # fmt: skip
                print(tools.red("h-convergence failed" + "\n" + "success rate=" + str(float(sum(success)) / nVar) + " tolerance rate=" + str(self.rate)))

                # 1.7     interate over all runs
                for run in runs:
                    # 1.6.1   add failed info if success rate is not reached to all runs
                    run.analyze_results.append("analysis failed: h-convergence " + str(success))

                    # 1.6.2   set analyzes to fail if success rate is not reached for all runs
                    run.analyze_successful = False
                    Analyze.total_errors += 1

        else:
            s = "cannot perform h-convergence test, because number of successful runs must equal the number of cells"
            print(tools.red(s))
            for run in runs:
                run.analyze_results.append(s)  # append info for summary of errors
                run.analyze_successful = False  # set analyzes to fail
                Analyze.total_errors += 1  # increment errror counter
            print(tools.yellow("nRun  " + str(nRuns)))
            print(tools.yellow("cells " + str(len(self.cells))))

    def __str__(self):
        return "perform L2 h-convergence test and compare the order of convergence with the polynomial degree"


# ==================================================================================================


class Analyze_Convtest_t(Analyze):
    """
    Convergence test for different time steps defined in 'parameter.ini' (e.g. CFLScale)

    The analyze routine read the L2 error norm from a set of runs and determines the order of convergence
    between the runs and averages the values. The average is compared with the temporal order supplied by the user.
    """

    def __init__(self, ConvtestTime):
        # fmt: off
        # 1.   set the order of convergence, tolerance, rate and error name (name of the error in the std.out)
        self.order      = ConvtestTime.order      # user-supplied convergence order
        self.tolerance  = ConvtestTime.tolerance  # determine success rate by comparing the relative convergence error with a tolerance
        self.rate       = ConvtestTime.rate       # success rate: for each nVar, the EOC is determined (the number of successful EOC vs.
                                                  # the number of total EOC tests determines the success rate which is compared with this rate)

        self.error_name = ConvtestTime.error_name # string name of the L2 error in the std.out file (default is "L_2")

        # 3.   set the method and input variables
        self.method     = ConvtestTime.method      # choose between four methods: initial timestep, list of timestep_factor, total number of timesteps, list of timesteps.
                                                   # The lists are user-supplied and the other methods are read automatically from the std.out
        self.name            = ConvtestTime.method_name     # string for the name of the method (used for pyplot)
        self.ini_timestep    = ConvtestTime.initial_timestep# 1.) initial timestep (automatically from std.out)
        self.timestep_factor = ConvtestTime.timestep_factor # 2.) list of timestep_factor (user-supplied list)
        self.total_iter      = ConvtestTime.total_timesteps # 3.) total number of timesteps (automatically from std.out)
        self.iters           = ConvtestTime.timesteps       # 4.) list of timesteps (user-supplied list)

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
        # fmt: off

    def perform(self, runs):
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

        LastLines = 2000  # search the last 35 lines in the std.out file for the L2 error
        # 1.  check if number of successful runs is at least two
        nRuns = len(runs)
        if nRuns < 2:
            for run in runs:
                s = "analysis failed: t-convergence not possible with only 1 run"
                print(tools.red(s))
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
                return
        if self.number_of_x_values in (-1, nRuns):
            # 1.1   for method 1.) or 3.) det the values for x_values from std.out
            if self.method in (1, 3):
                print(self.get_x_values)
                if self.method == 1:  # 1.) initial timestep (automatically from std.out)
                    try:
                        self.x_values = np.array([analyze_functions.get_initial_timesteps(run.stdout, self.get_x_values) for run in runs])
                    except Exception:
                        for run in runs:  # find out exactly which L2 error could not be read
                            try:
                                self.x_values_test = np.array(analyze_functions.get_initial_timesteps(run.stdout, self.get_x_values))
                            except Exception:  # noqa: PERF203 `try`-`except` within a loop incurs performance
                                s = tools.red("t-convergence failed: could not read [%s] from output (searching in all lines)" % self.get_x_values)
                                print(s)

                                # 1.2.1   append info for summary of errors
                                run.analyze_results.append(s)

                                # 1.2.2   set analyzes to fail
                                run.analyze_successful = False
                                Analyze.total_errors += 1
                        return
                elif self.method == 3:  # 3.) total number of timesteps (automatically from std.out)
                    try:
                        self.x_values = np.array([analyze_functions.get_last_number_of_timesteps(run.stdout, self.get_x_values) for run in runs])
                    except Exception:
                        for run in runs:  # find out exactly which L2 error could not be read
                            try:
                                self.x_values_test = np.array(analyze_functions.get_last_number_of_timesteps(run.stdout, self.get_x_values, LastLines))
                            except Exception:  # noqa: PERF203 `try`-`except` within a loop incurs performance
                                s = tools.red("t-convergence failed: could not read [%s] from %s (searching in the last %s lines)" % ('std.out', self.get_x_values, LastLines))
                                print(s)

                                # 1.2.1   append info for summary of errors
                                run.analyze_results.append(s)

                                # 1.2.2   set analyzes to fail
                                run.analyze_successful = False
                                Analyze.total_errors += 1
                        return
                # transpose the vector and reduce the dimension of the array from 2 to 1
                self.x_values = np.transpose(self.x_values)
                self.x_values = self.x_values[0]

            # 1.2   get L2 errors of all runs and create np.array
            try:
                L2_errors = np.array([analyze_functions.get_last_L2_error(run.stdout, self.error_name, LastLines) for run in runs])
                L2_errors = np.transpose(L2_errors)
            except Exception:
                for run in runs:  # find out exactly which L2 error could not be read
                    try:
                        L2_errors_test = np.array(analyze_functions.get_last_L2_error(run.stdout, self.error_name, LastLines))  # noqa: F841 local variable 'test' is assigned to but never used
                    except Exception:  # noqa: PERF203 `try`-`except` within a loop incurs performance
                        s = tools.red("t-convergence failed: some L2 errors could not be read from %s (searching for '%s' in the last %s lines)" % ('std.out', self.error_name, LastLines))
                        print(s)

                        # 1.2.1   append info for summary of errors
                        run.analyze_results.append(s)

                        # 1.2.2   set analyzes to fail
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                return

            # 1.3   get number of variables from L2 error array
            nVar = len(L2_errors)
            print(tools.blue("L2 errors for nVar=" + str(nVar)))
            displayTable(L2_errors, nVar, nRuns)

            # 1.4   determine order of convergence between two runs
            if self.method == 1:  # 1.) initial timestep (automatically from std.out)
                L2_order = np.array([analyze_functions.calcOrder_h(self.x_values, L2_errors[i], True) for i in range(nVar)])  # invert (e.g. the timestep) for positive order calculation (eg. O(-4) -> O(4))
            else:
                L2_order = np.array([analyze_functions.calcOrder_h(self.x_values, L2_errors[i]) for i in range(nVar)])
            print(tools.blue("L2 orders for nVar=" + str(nVar)))
            displayTable(L2_order, nVar, nRuns - 1)

            # 1.4.1   determine average convergence rate
            mean = [np.mean(L2_order[i]) for i in range(nVar)]
            print(tools.blue("L2 average order for nVar=%s (expected order = %s)" % (nVar, self.order)))
            displayVector(mean, nVar)

            if pyplot_module_loaded:  # this boolean is set when importing matplotlib.pyplot
                f = plt.figure()  # create figure
                for i in range(nVar):
                    if 1 == 2:
                        self.grid_spacing = [1.0 / ((self.order) * float(x)) for x in self.x_values]
                        plt.plot(self.grid_spacing, L2_errors[i], 'ro-')  # create plot
                        plt.xlabel('Average grid spacing for unit domain length L_domain=1')  # set x-label
                    else:
                        plt.plot(self.x_values, L2_errors[i], 'ro-')  # create plot
                        plt.xlabel('x: %s' % self.name)  # set x-label
                    if min(L2_errors[i]) > 0.0:  # log plot only if greater zero
                        plt.xscale('log')  # set x-axis to log scale
                        plt.yscale('log')  # set y-axis to log scale
                    plt.title('nVar = %s (of %s), MIN = %4.2e, MAX = %4.2e, O(%.2f)' % (i, nVar - 1, min(L2_errors[i]), max(L2_errors[i]), mean[i]))  # set title
                    plt.ylabel('L2 error norm')  # set y-label
                    # plt.show() # display the plot figure for the user (comment out when running in batch mode)
                    f_save_path = os.path.join(os.path.dirname(runs[0].target_directory), "L2_error_nVar" + str(i) + "_order%.2f.pdf" % mean[i])  # set file path for saving the figure to the disk
                    f.savefig(f_save_path, bbox_inches='tight')  # save figure to .pdf file
                    plt.cla()
                plt.close(f)
            else:
                print(
                    tools.yellow(
                        'Could not import matplotlib.pyplot module. ' 'This is required for creating plots under "Analyze_Convtest_t(Analyze)". \nSet "use_matplot_lib=True" in analyze.ini in order to activate plotting.'
                    )
                )

            # 1.4.2   write L2 error data to file
            writeTableToFile(L2_errors, nVar, nRuns, self.x_values, os.path.dirname(runs[0].target_directory), "L2_error_order%.2f.csv" % mean[0])

            # 1.5   determine success rate by comparing the relative convergence error with a tolerance
            print(tools.blue("relative order error (tolerance = %.4e)" % self.tolerance))
            relErr = [abs(mean[i] / (self.order) - 1) for i in range(nVar)]
            displayVector(relErr, nVar)
            success = [relErr[i] < self.tolerance for i in range(nVar)]
            print(tools.blue("success convergence"))
            print(5 * " " + "".join(str(success[i]).rjust(21) for i in range(nVar)))

            # 1.6   compare success rate with pre-defined rate, fails if not reached
            if float(sum(success)) / nVar >= self.rate:
                print(tools.blue("t-convergence successful"))
            else :  # fmt: skip
                print(tools.red("t-convergence failed" + "\n" + "success rate=" + str(float(sum(success)) / nVar) + " tolerance rate=" + str(self.rate)))

                # 1.7     interate over all runs
                for run in runs:
                    # 1.6.1   add failed info if success rate is not reached to all runs
                    run.analyze_results.append("analysis failed: t-convergence " + str(success))

                    # 1.6.2   set analyzes to fail if success rate is not reached for all runs
                    run.analyze_successful = False
                    Analyze.total_errors += 1

        else :  # fmt: skip
            s = "cannot perform t-convergence test, because number of successful runs must equal the number of supplied %s in the user-supplied list" % self.name
            print(tools.red(s))
            for run in runs:
                run.analyze_results.append(s)  # append info for summary of errors
                run.analyze_successful = False  # set analyzes to fail
                Analyze.total_errors += 1  # increment errror counter
            print(tools.yellow("[nRun] = [%s]" % nRuns))
            print(tools.yellow("[%s] = [%s] values for x_values (must equal the number of nRun)" % (self.name, len(self.x_values))))

    def __str__(self):
        return "perform L2 t-convergence test and compare the order of convergence with %s against the supplied order of convergence" % self.name


# ==================================================================================================


class Analyze_Convtest_p(Analyze):
    """
    Convergence test for a fixed mesh and different (increasing!) polynomial degrees defined in 'parameter.ini'

    The analyze routine reads the L2 error norm from a set of runs and determines the order of convergence
    between the runs and compares them. With increasing polynomial degree, the order of convergence must increase for this anaylsis to be successful.
    """

    def __init__(self, ConvtestP):
        # fmt: off
        self.rate       = ConvtestP.rate       # success rate: for each nVar, the EOC is determined (the number of successful EOC vs.
                                               # the number of total EOC tests determines the success rate which is compared with this rate)
        self.percentage = ConvtestP.percentage # for the p-convergence, the EOC must increase with p, hence the sloop must increase
                                               # percentage yields the minimum ratio of increasing EOC vs. the total number of EOC for each nVar
        self.error_name = ConvtestP.error_name # string name of the L2 error in the std.out file (default is "L_2")
        # fmt: on

    def perform(self, runs):
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

        LastLines = 2000  # search the last 35 lines in the std.out file for the L2 error
        # 1.  read the polynomial degree  for all runs
        p = [float(run.parameters.get('N', -1)) for run in runs]  # get polynomial degree

        # 2. check if number of successful runs is equal the number of supplied cells
        nRuns = len(runs)
        if nRuns < 2:
            for run in runs:
                s = "analysis failed: p-convergence not possible with only 1 run"
                print(tools.red(s))
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
                return

        if len(p) == nRuns:
            # 2.2   get L2 errors of all runs and create np.array
            try:
                L2_errors = np.array([analyze_functions.get_last_L2_error(run.stdout, self.error_name, LastLines) for run in runs])
                L2_errors = np.transpose(L2_errors)
            except Exception:
                for run in runs:  # find out exactly which L2 error could not be read
                    try:
                        L2_errors_test = np.array(analyze_functions.get_last_L2_error(run.stdout, self.error_name, LastLines))  # noqa: F841 local variable 'test' is assigned to but never used
                    except Exception:  # noqa: PERF203 `try`-`except` within a loop incurs performance
                        s = tools.red("p-convergence failed: some L2 errors could not be read from %s (searching for '%s' in the last %s lines)" % ('std.out', self.error_name, LastLines))
                        print(s)

                        # 1.2.1   append info for summary of errors
                        run.analyze_results.append(s)

                        # 1.2.2   set analyzes to fail
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                return

            # 2.3   get number of variables from L2 error array
            nVar = len(L2_errors)

            print(tools.blue("L2 errors nVar=" + str(nVar)))
            displayTable(L2_errors, nVar, nRuns)
            writeTableToFile(L2_errors, nVar, nRuns, p, os.path.dirname(runs[0].target_directory), "L2_error.csv")

            if pyplot_module_loaded:  # this boolean is set when importing matplotlib.pyplot
                f = plt.figure()  # create figure
                for i in range(nVar):
                    ax = f.gca()  # set axis handle
                    plt.plot(p, L2_errors[i], 'ro-')  # create plot
                    # plt.xscale('log')                                  # set x-xis to log scale
                    if min(L2_errors[i]) > 0.0:  # log plot only if greater zero
                        plt.yscale('log')  # set y-xis to log scale
                    plt.title('nVar = %s (of %s), MIN = %4.2e, MAX = %4.2e' % (i, nVar - 1, min(L2_errors[i]), max(L2_errors[i])))  # set title
                    plt.xlabel('Polynomial degree')  # set x-label
                    plt.ylabel('L2 error norm')  # set y-label
                    ax.xaxis.set_major_locator(MaxNLocator(integer=True))  # set x-axis format to integer only
                    # plt.show() # display the plot figure for the user (comment out when running in batch mode)
                    f_save_path = os.path.join(os.path.dirname(runs[0].target_directory), "L2_error_nVar" + str(i) + ".pdf")  # set file path for saving the figure to the disk
                    f.savefig(f_save_path, bbox_inches='tight')  # save figure to .pdf file
                    plt.cla()
                plt.close(f)
            else:
                print(
                    tools.yellow(
                        'Could not import matplotlib.pyplot module. ' 'This is required for creating plots under "Analyze_Convtest_p(Analyze)". \nSet "use_matplot_lib=True" in analyze.ini in order to activate plotting.'
                    )
                )

            # 2.4   determine order of convergence between two runs
            L2_order = np.array([analyze_functions.calcOrder_p(p, L2_errors[i]) for i in range(nVar)])
            print(tools.blue("L2 orders for nVar=" + str(nVar)))
            displayTable(L2_order, nVar, nRuns - 1)

            # 2.5   check if the order of convergence is always increasing with increasing polynomial degree
            increasing = []
            for j in range(nVar):
                increasing_run = [L2_order[j][i] > L2_order[j][i - 1] for i in range(1, len(p) - 1)]  # check for increasing order of convergence
                print(increasing_run)
                if 1 == 1:
                    if abs(float(len(increasing_run))) > 0:
                        increasing.append(float(sum(increasing_run)) / float(len(increasing_run)))
                    else:
                        increasing.append(0.0)
                else:
                    increasing.append(all(increasing_run))
            print(tools.blue("Increasing order of convergence, percentage"))
            print(5 * " " + "".join(str(increasing[i]).rjust(21) for i in range(nVar)))

            # 2.6   determine success rate from increasing convergence
            success = [increasing[i] >= self.percentage for i in range(nVar)]
            print(tools.blue("success convergence (if percentage >= %.2f)" % self.percentage))
            print(5 * " " + "".join(str(success[i]).rjust(21) for i in range(nVar)))

            # 2.7   compare success rate with pre-defined rate, fails if not reached
            if float(sum(success)) / nVar >= self.rate:
                print(tools.blue("p-convergence successful"))
            else :  # fmt: skip
                print(tools.red("p-convergence failed" + "\n" + "success rate=" + str(float(sum(success)) / nVar) + " tolerance rate=" + str(self.rate)))

                # 2.8     interate over all runs
                for run in runs:
                    # 2.8.1   add failed info if success rate is not reached to all runs
                    run.analyze_results.append("analysis failed: p-convergence " + str(success))

                    # 2.8.2   set analyzes to fail if success rate is not reached for all runs
                    run.analyze_successful = False
                    Analyze.total_errors += 1

                    # global_errors+=1
        else :  # fmt: skip
            s = "cannot perform p-convergence test, because number of successful runs must equal the number of polynomial degrees p"
            print(tools.red(s))
            for run in runs:
                run.analyze_results.append(s)  # append info for summary of errors
                run.analyze_successful = False  # set analyzes to fail
                Analyze.total_errors += 1  # increment errror counter
            print(tools.yellow("nRun   " + str(nRuns)))
            print(tools.yellow("len(p) " + str(len(p))))

    def __str__(self):
        return "perform L2 p-convergence test and check if the order of convergence increases with increasing polynomial degree"


# ==================================================================================================


class Analyze_h5diff(Analyze, ExternalCommand):
    def __init__(self, h5diff):
        # Set number of diffs per run [True/False]
        self.one_diff_per_run = h5diff.one_diff_per_run in ('True', 'true', 't', 'T')

        # Create dictionary for all keys/parameters and insert a list for every value/options
        self.prms = {
            "reference_file": h5diff.reference_file,
            "file": h5diff.file,
            "data_set": h5diff.data_set,
            "tolerance_value": h5diff.tolerance_value,
            "tolerance_type": h5diff.tolerance_type,
            "sort": h5diff.sort,
            "sort_dim": h5diff.sort_dim,
            "sort_var": h5diff.sort_var,
            "reshape": h5diff.reshape,
            "reshape_dim": h5diff.reshape_dim,
            "reshape_value": h5diff.reshape_value,
            "flip": h5diff.flip,
            "max_differences": h5diff.max_differences,
            "var_attribute": h5diff.var_attribute,
            "var_name": h5diff.var_name,
        }
        for key, prm in self.prms.items():
            # Check if prm is not of type 'list'
            if not isinstance(prm, list):
                # create list with prm as entry
                self.prms[key] = [prm]

        # Get the number of values/options for each key/parameter
        numbers = {key: len(prm) for key, prm in self.prms.items()}

        ExternalCommand.__init__(self)

        # Get maximum number of values (from all possible keys)
        self.nCompares = numbers[max(numbers, key=numbers.get)]

        # Check all numbers and if a key has only 1 number, increase the number to maximum and use the same value for all
        for key, number in numbers.items():
            if number == 1:
                self.prms[key] = [self.prms[key][0] for i in range(self.nCompares)]
                numbers[key] = self.nCompares

        if any([(number != self.nCompares) for number in numbers.values()]):
            raise Exception(tools.red("Number of multiple data sets for multiple h5diffs is inconsistent. Please ensure all options have the same length or length=1."))

        # Check tolerance type (absolute or relative) and set the correct h5diff command line argument
        for compare in range(self.nCompares):
            tolerance_type_loc = self.prms["tolerance_type"][compare]
            if tolerance_type_loc in ('absolute', 'delta', '--delta'):
                self.prms["tolerance_type"][compare] = "--delta"
            elif tolerance_type_loc in ('relative', "--relative"):
                self.prms["tolerance_type"][compare] = "--relative"
            else:
                raise Exception(tools.red("initialization of h5diff failed. h5diff_tolerance_type '%s' not accepted." % tolerance_type_loc))

        # Check dataset sorting
        for compare in range(self.nCompares):
            sort_loc = self.prms["sort"][compare]
            if sort_loc in ('True', 'true', 't', 'T', True):
                self.prms["sort"][compare] = True
            elif sort_loc in ('False', 'false', 'f', 'F', False):
                self.prms["sort"][compare] = False
            else:
                raise Exception(tools.red("initialization of h5diff failed. h5diff_sort '%s' not accepted." % sort_loc))

        # Check dataset reshaping
        for compare in range(self.nCompares):
            reshape_loc = self.prms["reshape"][compare]
            if reshape_loc in ('True', 'true', 't', 'T', True):
                self.prms["reshape"][compare] = True
            elif reshape_loc in ('False', 'false', 'f', 'F', False):
                self.prms["reshape"][compare] = False
            else:
                raise Exception(tools.red("initialization of h5diff failed. h5diff_reshape '%s' not accepted." % reshape_loc))

        # Check dataset flipping (transpose)
        for compare in range(self.nCompares):
            flip_loc = self.prms["flip"][compare]
            if flip_loc in ('True', 'true', 't', 'T', True):
                self.prms["flip"][compare] = True
            elif flip_loc in ('False', 'false', 'f', 'F', False):
                self.prms["flip"][compare] = False
            else:
                raise Exception(tools.red("initialization of h5diff failed. h5diff_flip '%s' not accepted." % flip_loc))

        # set logical for creating new reference files and copying them to the example source directory
        self.referencescopy = h5diff.referencescopy

    def perform(self, runs):
        global h5py_module_loaded
        # Check if this analysis can be performed: h5py must be imported
        if not h5py_module_loaded:  # this boolean is set when importing h5py
            print(tools.red('Could not import h5py module. This is required for "Analyze_h5diff". Aborting.'))
            Analyze.total_errors += 1
            return

        '''
        General workflow:
        1.  iterate over all runs
        1.1.0   Read the hdf5 file
        1.1.1.0   Read the dataset from the hdf5 file
        1.1.1.1   Reshape the dataset if required
        1.1.2   compare shape of the dataset of both files, throw error if they do not coincide
        1.1.3   add failed info if return a code != 0 to run
        1.1.4   set analyzes to fail if return a code != 0
        1.2.0   When sorting is used, the sorted array is written to the original .h5 file with a new name
        1.2.1   Execute the command 'cmd' = 'h5diff -r --XXX [value] ref_file file DataArray'
        1.2.2   Check maximum number of differences if user has selected h5diff_max_differences > 0
        1.3   if the command 'cmd' returns a code != 0, set failed
        1.3.1   add failed info (for return a code != 0) to run
        1.3.2   set analyzes to fail (for return a code != 0)
        '''
        if self.one_diff_per_run and (self.nCompares != len(runs)):
            raise Exception(tools.red("Number of h5diffs [=%s] and runs [=%s] is inconsistent. Please ensure all options have the same length or set h5diff_one_diff_per_run=F." % (self.nCompares, len(runs))))

        # 1.  Iterate over all runs
        for iRun, run in enumerate(runs):
            # Check whether the list of diffs is to be used one-at-a-time, i.e., a list of diffs for a list of runs (each run only performs one diff, not all of them)
            if self.one_diff_per_run:
                # One comparison for each run
                compares = [iRun]
            else:
                # All comparisons for every run
                compares = range(self.nCompares)

            n = 0
            # Iterate over all comparisons for h5diff
            for compare in compares:
                # fmt: off
                n+=1
                reference_file_loc   = self.prms["reference_file"][compare]
                file_loc             = self.prms["file"][compare]
                data_set_loc         = self.prms["data_set"][compare]
                tolerance_value_loc  = float(self.prms["tolerance_value"][compare])
                tolerance_type_loc   = self.prms["tolerance_type"][compare]
                sort_loc             = self.prms["sort"][compare]
                sort_dim_loc         = int(self.prms["sort_dim"][compare])
                sort_var_loc         = int(self.prms["sort_var"][compare])
                reshape_loc          = self.prms["reshape"][compare]
                reshape_dim_loc      = int(self.prms["reshape_dim"][compare])
                reshape_value_loc    = int(self.prms["reshape_value"][compare])
                flip_loc             = self.prms["flip"][compare]
                max_differences_loc  = int(self.prms["max_differences"][compare])
                var_attribute_loc    = self.prms["var_attribute"][compare]
                var_name_loc         = self.prms["var_name"][compare]

                # 1.1.0   Read the hdf5 file
                path            = os.path.join(run.target_directory,file_loc)
                path_ref_target = os.path.join(run.target_directory,reference_file_loc)
                path_ref_source = os.path.join(run.source_directory,reference_file_loc)
                # fmt: on

                # Copy new reference file: This is completely independent of the outcome of the current h5diff
                if self.referencescopy:
                    run = copyReferenceFile(run, path, path_ref_source)
                    s = tools.yellow("Analyze_h5diff: performed reference copy instead of analysis!")
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_infos += 1
                    # do not skip the following analysis tests, because reference file will be created -> continue
                    continue

                if not os.path.exists(path):
                    s = tools.red("Analyze_h5diff: file does not exist, file=[%s]" % path)
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    continue
                if not os.path.exists(path_ref_target):
                    s = tools.red("Analyze_h5diff: reference file does not exist, file=[%s]" % path_ref_target)
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    continue

                # Open h5 file and read container info
                # --------------------------------------------
                #     r       : Readonly, file must exist
                #     r+      : Read/write, file must exist
                #     w       : Create file, truncate if exists
                #     w- or x : Create file, fail if exists
                #     a       : Read/write if exists, create otherwise (default
                # --------------------------------------------
                # When sorting is used, the sorted array is written to the original .h5 file with a new name. The same happens when using dataset reshaping.
                if sort_loc or reshape_loc or flip_loc:
                    f1 = h5py.File(path, 'r+')
                    f2 = h5py.File(path_ref_target, 'r+')
                else:
                    f1 = h5py.File(path, 'r')
                    f2 = h5py.File(path_ref_target, 'r')

                # Usage:
                # -------------------
                # available keys   : print("Keys: %s" % f1.keys())         # yields, e.g., <KeysViewHDF5 ['DG_Solution', 'PartData']>
                # first key in list: a_group_key = list(f1.keys())[0]      # yields 'DG_Solution'
                # -------------------

                # 1.1.1.0   Read the datasets from the hdf5 file
                # Check if the container in the file and the ref. have the same name
                data_set_loc = data_set_loc.split()
                if len(data_set_loc) > 1:
                    data_set_loc_file = data_set_loc[0]  # first dataset name for result
                    data_set_loc_ref = data_set_loc[1]  # second dataset name for reference
                else:
                    data_set_loc_file = data_set_loc[0]
                    data_set_loc_ref = data_set_loc[0]

                # Read the file
                try:
                    # Read dataset array with name data_set_loc_file
                    b1 = f1[data_set_loc_file][:]
                    dtype1 = f1[data_set_loc_file].dtype

                    # Flip the array dimensions
                    try:
                        if flip_loc:
                            b2 = b1.transpose()
                            b1 = b2
                    except Exception as e:
                        s = tools.red("Analyze_h5diff: Could not transpose the .h5 dataset [%s] array under in file [%s] (h5diff_flip = T). Error message [%s]" % (data_set_loc_file, path, e))
                        print(s)
                        run.analyze_results.append(s)
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                        continue

                    shape1 = b1.shape

                    # Set default values, which are required if flip_loc=T
                    if not reshape_loc:
                        # Set values that effectively do not change the original shape if applied. The array has already been transposed in this case.
                        reshape_dim_loc = 0
                        reshape_value_loc = shape1[0]

                except Exception as e:
                    s = tools.red("Analyze_h5diff: Could not open .h5 dataset [%s] under in file [%s]. Error message [%s]" % (data_set_loc_file, path, e))
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    continue

                # Read the reference
                try:
                    b2 = f2[data_set_loc_ref][:]
                    shape2 = b2.shape
                except Exception as e:
                    s = tools.red("Analyze_h5diff: Could not open .h5 dataset [%s] under in file [%s]. Error message [%s]" % (data_set_loc_ref, path_ref_target, e))
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    continue

                # 1.1.1.1   Reshape the dataset if required (or transpose it when flip_loc=T)
                if reshape_loc or flip_loc:
                    # Create new re-shaped array for storing to .h5
                    old_shape = shape1
                    newShape = list(shape1)
                    old_value = newShape[reshape_dim_loc]
                    newShape[reshape_dim_loc] = reshape_value_loc
                    newShape = tuple(newShape)
                    # Check if shape is being increased
                    if reshape_value_loc > old_value:
                        s = tools.red("Analyze_h5diff: Reshaping is currently only implemented with the purpose to reduce array sizes. You are trying to increase the array shape from %s to %s" % (old_shape, newShape))
                        print(s)
                        run.analyze_results.append(s)
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                        continue
                    # Check if row or column is changed
                    if reshape_dim_loc == 0:
                        b1_reshaped = b1[:reshape_value_loc, :]
                    elif reshape_dim_loc == 1:
                        b1_reshaped = b1[:, :reshape_value_loc]
                    elif reshape_dim_loc == 2:
                        b1_reshaped = b1[:, :, :reshape_value_loc]
                    elif reshape_dim_loc == 3:
                        b1_reshaped = b1[:, :, :, :reshape_value_loc]
                    else:
                        s = tools.red(
                            "Analyze_h5diff: Reshaping is currently only implemented for specific arrays (dim 0 and 1 reshape 2D array) "
                            "and dim 3 and 4 reshape the last dimension of 3D and 4D arrays. Use h5diff_reshape_dim=1 or 2)"
                        )
                        print(s)
                        run.analyze_results.append(s)
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                        continue

                    shape1 = b1_reshaped.shape

                    # Set name of new array
                    data_set_loc_file_new = data_set_loc_file + "_reshaped"

                    # check if dataset exists in file (if more than one array should be compared so the flipped/reshaped dataset was already created)
                    if data_set_loc_file_new not in f1:
                        # File: Create new dataset
                        dset = f1.create_dataset(data_set_loc_file_new, shape=shape1, dtype=dtype1)
                    else:
                        dset = f1[data_set_loc_file_new]

                    # Write as C-continuous array via np.ascontiguousarray()
                    dset.write_direct(np.ascontiguousarray(b1_reshaped))

                    # Close .h5 file
                    # f1.close()

                    # Replace original data and update the shape info for b1
                    b1 = b1_reshaped

                    # In the following, compare the reshaped array instead of the original one
                    str_1 = "'%s' (instead of '%s') from %s" % (data_set_loc_file_new, data_set_loc_file, file_loc)
                    print(
                        tools.yellow(
                            "    Reshaping dim=%s to value=%s (the old value was %s).\n"
                            "Now using: %s, which has a changed shape from %s to %s" % (reshape_dim_loc, reshape_value_loc, old_value, str_1, old_shape, newShape)
                        )
                    )

                    data_set_loc_file = data_set_loc_file_new

                # Check whether a single variable or the complete dataset shall be compared
                if var_attribute_loc is not None and var_name_loc is not None:
                    compare_single_variable = True
                else:
                    compare_single_variable = False

                # 1.1.2 compare shape of the dataset of both files, throw error if they do not coincide
                if shape1 != shape2 and not compare_single_variable:  # e.g.: b1.shape = (48, 1, 1, 32)
                    self.result = tools.red(
                        tools.red(
                            "h5diff failed because datasets for [%s,%s] are not comparable due to different shapes: Files [%s] and [%s] have shapes [%s] and [%s]"
                            % (data_set_loc_file, data_set_loc_ref, f1, f2, b1.shape, b2.shape)
                        )
                    )
                    print(" " + self.result)

                    # 1.1.3   add failed info if return a code != 0 to run
                    run.analyze_results.append(self.result)

                    # 1.1.4   set analyzes to fail if return a code != 0
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                else:
                    # 1.2.0 When sorting is used, the sorted array is written to the original .h5 file with a new name
                    if sort_loc:
                        # Sort by X
                        if sort_dim_loc == 1:  # Sort by row
                            # Note that sort_var_loc begins at 0 as python starts at 0
                            b1_sorted = b1[:, b1[sort_var_loc, :].argsort()]
                            b2_sorted = b2[:, b2[sort_var_loc, :].argsort()]
                        elif sort_dim_loc == 2:  # Sort by column
                            # Note that sort_var_loc begins at 0 as python starts at 0
                            b1_sorted = b1[b1[:, sort_var_loc].argsort()]
                            b2_sorted = b2[b2[:, sort_var_loc].argsort()]
                        else:
                            s = tools.red(
                                "Analyze_h5diff: Sorting failed, because currently only sorting of 2-dimensional arrays is implemented.\n"
                                "This means, that sorting by rows (dim=1) and columns (dim=2) is allowed. However, dim=[%s]" % sort_dim_loc
                            )
                            print(s)
                            run.analyze_results.append(s)
                            run.analyze_successful = False
                            Analyze.total_errors += 1
                            continue

                        data_set_loc_file_new = data_set_loc_file + "_sorted"
                        data_set_loc_ref_new = data_set_loc_ref + "_sorted"
                        # File: Create new dataset
                        dset = f1.create_dataset(data_set_loc_file_new, shape=shape1, dtype=dtype1)
                        # Write as C-continuous array via np.ascontiguousarray()
                        dset.write_direct(np.ascontiguousarray(b1_sorted))
                        f1.close()

                        # Reference file: Create new dataset
                        dset = f2.create_dataset(data_set_loc_ref_new, shape=shape2, dtype=dtype1)
                        # Write as C-continuous array via np.ascontiguousarray()
                        dset.write_direct(np.ascontiguousarray(b2_sorted))
                        f2.close()

                        # In the following, compare the two sorted arrays instead of the original ones
                        str_1 = "'%s' (instead of '%s') from %s" % (data_set_loc_file_new, data_set_loc_file, file_loc)
                        str_2 = "'%s' (instead of '%s') from %s" % (data_set_loc_ref_new, data_set_loc_ref, reference_file_loc)
                        print(tools.yellow("    Sorting dim=%s by variable=%s (variable indexing begins at 0). Now comparing: %s with %s" % (sort_dim_loc, sort_var_loc, str_1, str_2)))
                        data_set_loc_file = data_set_loc_file_new
                        data_set_loc_ref = data_set_loc_ref_new

                    else:
                        # Close .h5 files to prevent the error: h5diff: <tildbox_reference_State_001.0000000000000000.h5>: unable to open file
                        f1.close()
                        f2.close()

                    # 1.2.1 Comparison of a single variable using NumPy's isclose or the complete dataset using h5diff
                    if compare_single_variable:
                        try:
                            # Open datasets again to get dimension sizes
                            f1 = h5py.File(path, 'r')
                            f2 = h5py.File(path_ref_target, 'r')

                            def get_variable_dimension(f, dataset_path, variable_attribute, variable_name):
                                '''Check dataset for variable names in attributes and return the index of the variable name (corresponds to the column of the hdf5 array)'''
                                # Check if the dataset has attributes containing variable names for dimensions
                                try:
                                    dataset = f
                                    # check if attribute exists (case insensitive)
                                    attrs = [attr for attr in dataset.attrs]
                                    lower_attrs = [attr.lower() for attr in attrs]
                                    if variable_attribute.lower() in lower_attrs:
                                        variable_attribute_index = lower_attrs.index(variable_attribute.lower())
                                        # attr_name is correctly spelled name of the attribute
                                        attr_name = attrs[variable_attribute_index]
                                        variable_names = [name.decode('utf-8').lower() for name in dataset.attrs[attr_name]]
                                        # check if variable name exists (case insensitive)
                                        if variable_name.lower() in variable_names:
                                            f.close()
                                            return list(variable_names).index(variable_name.lower())
                                        else:
                                            print("Variable name '%s' not found in dimension names." % variable_name)
                                            return None
                                    else:
                                        print("No '%s' attribute found in dataset '%s'." % (variable_attribute, dataset_path))
                                        return None
                                except KeyError:
                                    print("Dataset '%s' not found in the file." % dataset_path)
                                    return None

                            dim1 = get_variable_dimension(f1, data_set_loc_file, var_attribute_loc, var_name_loc)
                            dim2 = get_variable_dimension(f2, data_set_loc_ref, var_attribute_loc, var_name_loc)
                            # Extract slices along the specified dimension from arrays b1 and b2 which are already reshaped/flipped so they have the same dimensions-if arrays were flipped dim1 and dim2 correspond to rows
                            if flip_loc:
                                data1_slice = np.ravel(b1[dim1, ...])
                                data2_slice = np.ravel(b2[dim2, ...])
                            else:
                                data1_slice = np.ravel(b1[..., dim1])
                                data2_slice = np.ravel(b2[..., dim2])

                            # Ensure data slices are converted to float
                            data1_slice = np.array(data1_slice, dtype=float)
                            data2_slice = np.array(data2_slice, dtype=float)

                            # np.isclose creates a boolean array with True for elements that are close to each other within a tolerance
                            if tolerance_type_loc == '--delta':
                                data_compare = np.isclose(data1_slice, data2_slice, atol=tolerance_value_loc)
                            else:
                                data_compare = np.isclose(data1_slice, data2_slice, rtol=tolerance_value_loc)
                            NbrOfDifferences = np.sum(~data_compare)

                            if NbrOfDifferences > 0:
                                s = "Comparison failed for [%s] of [%s] with [%s] due to %s differences\n" % (var_name_loc, path, reference_file_loc, NbrOfDifferences)
                                if NbrOfDifferences > max_differences_loc:
                                    s = tools.red(s)
                                    # create apply boolean mask to get differences and remove masked values with compressed()
                                    masked_array = np.ma.array(data1_slice, mask=data_compare)
                                    real_diffs = masked_array.compressed()
                                    masked_array_ref = np.ma.array(data2_slice, mask=data_compare)
                                    real_diffs_ref = masked_array_ref.compressed()
                                    # find original indices of non-masked values for printing and debugging
                                    non_masked_indices = np.where(~masked_array.mask)[0]
                                    # print out first and last 20 different entries
                                    num_entries = min(20, real_diffs.shape[0])
                                    total_entries = real_diffs.shape[0]
                                    indices = list(range(num_entries))
                                    # ensure unique indices if there are less than 20 differences
                                    if total_entries > num_entries:
                                        indices += list(range(max(num_entries, total_entries - num_entries), total_entries))
                                    # print out differences
                                    print(tools.red("{:<20} | {:<45} | {:<45}".format('Index', var_name_loc, var_name_loc + '_ref')) + tools.yellow(" | {:<20} | {:<20}".format('Absolute Diff', 'Relative Diff')))
                                    print('-' * 160)
                                    for i in indices:
                                        abs_diff = np.abs(real_diffs[i] - real_diffs_ref[i])
                                        rel_diff = abs_diff / np.abs(real_diffs_ref[i])
                                        print(
                                            tools.red("{:<20} | {:<45} | {:<45}".format(non_masked_indices[i], str(real_diffs[i]), str(real_diffs_ref[i])))
                                            + tools.yellow(" | {:<20} | {:<20}".format(str(abs_diff), str(rel_diff)))
                                        )
                                    run.analyze_results.append(s)
                                    run.analyze_successful = False
                                    Analyze.total_errors += 1
                                else:
                                    s = s.replace("Comparison failed for", "Comparison ignored for")
                                    s2 = ", but %s difference(s) are allowed (given by compare_data_file_max_differences). This analysis is therefore marked as passed." % max_differences_loc
                                    s2 = tools.pink(s + s2)
                                    print(s2)

                            else:
                                NbrOfMatches = np.sum(data_compare)
                                if NbrOfMatches == 0:
                                    s = tools.red("Analyze_compare_data_file: Found zero matching values. Wrong data file under [%s] or format that could possibly not be read correctly" % (path))
                                    print(s)
                                    run.analyze_results.append(s)
                                    run.analyze_successful = False
                                    Analyze.total_errors += 1
                                else:
                                    s = tools.blue(tools.indent("Compared %s of %s with %s and got %s matching columns" % (var_name_loc, path, reference_file_loc, NbrOfMatches), 2))
                                    print(s)

                        # The python comparison of single variables could not be executed
                        except Exception as ex:
                            self.result = tools.red("h5diff failed. (Exception=" + str(ex) + ")")
                            print(" " + self.result)

                            # 1.3.1   Add failed info if return a code != 0 to run
                            run.analyze_results.append(tools.red("h5diff failed. Comparison of single variable %s failed with Exception=%s" % (var_name_loc, ex)))

                            # 1.3.2   Set analyzes to fail if return a code != 0
                            run.analyze_successful = False
                            Analyze.total_errors += 1

                    else:
                        # Execute the command 'cmd' = 'h5diff -r [--type] [value] [.h5 file] [.h5 reference] [DataSetName_file] [DataSetName_reference]'
                        cmd = ["h5diff", "-r", tolerance_type_loc, str(tolerance_value_loc), str(file_loc), str(reference_file_loc), str(data_set_loc_file), str(data_set_loc_ref)]
                        try:
                            s = "Running [%s] ..." % ("  ".join(cmd))
                            self.execute_cmd(cmd, run.target_directory, name="h5diff" + str(n), string_info=tools.indent(s, 2), displayOnFailure=False)  # run the code

                            # 1.2.2   Check maximum number of differences if user has selected h5diff_max_differences > 0
                            try:
                                if max_differences_loc > 0 and self.return_code != 0:
                                    for line in self.stdout[-1:]:  # check only the last line in std.out
                                        lastline = line.rstrip()
                                        idx = lastline.find('differences found')  # the string should look something like "XX differences found"
                                        if idx >= 0:
                                            NbrOfDifferences = int(lastline[:idx])  # get the number of differences that where identified by h5diff
                                            if NbrOfDifferences <= max_differences_loc:
                                                s = tools.indent(
                                                    "%s, but %s differences are allowed (given by h5diff_max_differences). The h5diff is therefore marked as passed." % (str(lastline), max_differences_loc), 2
                                                )
                                                s = tools.purple(s)
                                                print(s)
                                                self.return_code = 0
                            # If this try fails, just ignore it
                            except Exception:
                                pass

                            # 1.3   If the command 'cmd' returns a code != 0, set failed
                            if self.return_code != 0:
                                print(tools.indent("tolerance_type       : " + tolerance_type_loc, 2))
                                print(tools.indent("tolerance_value      : " + str(tolerance_value_loc), 2))
                                print(tools.indent("file                 : " + str(file_loc), 2))
                                print(tools.indent("reference            : " + str(reference_file_loc), 2))
                                print(tools.indent("dataset in file      : " + str(data_set_loc_file), 2))
                                print(tools.indent("dataset in reference : " + str(data_set_loc_ref), 2))
                                # run.analyze_results.append("h5diff failed (self.return_code != 0) for [%s] vs. [%s] in [%s] vs. [%s]" % (str(data_set_loc_ref),str(data_set_loc_file),str(reference_file_loc),str(file_loc))) # noqa: E501
                                run.analyze_results.append("h5diff failed (self.return_code != 0) for [%s] vs. [%s] in [%s] vs. [%s]" % (data_set_loc_file, data_set_loc_ref, file_loc, reference_file_loc))

                                # 1.3.1   Add failed info if return a code != 0 to run
                                print(" ")
                                # print(tools.indent(10*" // h5diff // ",2))
                                print(tools.indent(132 * "–", 2))
                                print(tools.indent("| ", 2) + tools.yellow("Note: First column corresponds to %s and second column to %s" % (file_loc, reference_file_loc)))
                                if len(self.stdout) > 20:
                                    for line in self.stdout[:10]:  # print first 10 lines
                                        print(tools.indent('| ' + line.rstrip(), 2))
                                    print(tools.indent("| ... leaving out intermediate lines", 2))
                                    for line in self.stdout[-10:]:  # print last 10 lines
                                        print(tools.indent('| ' + line.rstrip(), 2))
                                else:
                                    for line in self.stdout:  # print all lines
                                        print(tools.indent('| ' + line.rstrip(), 2))
                                    if len(self.stdout) == 1:
                                        run.analyze_results.append(str(self.stdout))
                                # print(tools.indent(10*" // h5diff // ",2))
                                print(tools.indent(132 * "–", 2))
                                print(" ")

                            # 1.3.2   Set analyzes to fail if return a code != 0
                            run.analyze_successful = False
                            Analyze.total_errors += 1

                        # The tool h5diff could not be executed
                        except Exception as ex:
                            self.result = tools.red("h5diff failed. (Exception=" + str(ex) + ")")  # print result here, because it was not added in "execute_cmd"
                            print(" " + self.result)

                            # 1.3.1   Add failed info if return a code != 0 to run
                            run.analyze_results.append(tools.red("h5diff failed. (Exception=" + str(ex) + ")"))
                            run.analyze_results.append(
                                tools.red(r"Maybe h5diff is not found automatically. Find it with \"locate -b '\h5diff'\" and add the corresponding path, e.g., \"export PATH=/opt/hdf5/1.X/bin/:$PATH\"")
                            )

                            # 1.3.2   Set analyzes to fail if return a code != 0
                            run.analyze_successful = False
                            Analyze.total_errors += 1

    def __str__(self):
        return "perform h5diff between two files: [" + str(self.prms["file"][0]) + "] + reference [" + str(self.prms["reference_file"][0]) + "]"


# ==================================================================================================


class Analyze_vtudiff(Analyze, ExternalCommand):
    # Improvement: https://discourse.vtk.org/t/introducing-a-new-data-comparison-utility-in-vtk/12549/9
    # Comparison of two vtk arrays directly in python so that converting in numpy arrays is not necessary, currently only in C++ and not yet as python utility function
    def __init__(self, vtudiff):
        # Set number of diffs per run [True/False]
        self.one_diff_per_run = vtudiff.one_diff_per_run in ('True', 'true', 't', 'T')

        # Create dictionary for all keys/parameters and insert a list for every value/options
        self.prms = {
            "reference_file": vtudiff.reference_file,
            "file": vtudiff.file,
            "array_name": vtudiff.array_name,
            "absolute_tolerance_value": vtudiff.abs_tolerance_value,
            "relative_tolerance_value": vtudiff.rel_tolerance_value,
            "sort": vtudiff.sort,
            "sort_dim": vtudiff.sort_dim,
            "sort_var": vtudiff.sort_var,
            "reshape": vtudiff.reshape,
            "reshape_dim": vtudiff.reshape_dim,
            "reshape_value": vtudiff.reshape_value,
            "flip": vtudiff.flip,
            "max_differences": vtudiff.max_differences,
        }
        for key, prm in self.prms.items():
            # Check if prm is not of type 'list'
            if not isinstance(prm, list):
                # create list with prm as entry
                self.prms[key] = [prm]

        # Get the number of values/options for each key/parameter
        numbers = {key: len(prm) for key, prm in self.prms.items()}

        ExternalCommand.__init__(self)

        # Get maximum number of values (from all possible keys)
        self.nCompares = numbers[max(numbers, key=numbers.get)]

        # Check all numbers and if a key has only 1 number, increase the number to maximum and use the same value for all
        for key, number in numbers.items():
            if number == 1:
                self.prms[key] = [self.prms[key][0] for i in range(self.nCompares)]
                numbers[key] = self.nCompares

        if any([(number != self.nCompares) for number in numbers.values()]):
            raise Exception(tools.red("Number of multiple data sets for multiple vtudiffs is inconsistent. Please ensure all options have the same length or length=1."))

        # Check dataset sorting
        for compare in range(self.nCompares):
            sort_loc = self.prms["sort"][compare]
            if sort_loc in ('True', 'true', 't', 'T', True):
                self.prms["sort"][compare] = True
            elif sort_loc in ('False', 'false', 'f', 'F', False):
                self.prms["sort"][compare] = False
            else:
                raise Exception(tools.red("initialization of vtudiff failed. vtudiff_sort '%s' not accepted." % sort_loc))

        # Check dataset reshaping
        for compare in range(self.nCompares):
            reshape_loc = self.prms["reshape"][compare]
            if reshape_loc in ('True', 'true', 't', 'T', True):
                self.prms["reshape"][compare] = True
            elif reshape_loc in ('False', 'false', 'f', 'F', False):
                self.prms["reshape"][compare] = False
            else:
                raise Exception(tools.red("initialization of vtudiff failed. vtudiff_reshape '%s' not accepted." % reshape_loc))

        # Check dataset flipping (transpose)
        for compare in range(self.nCompares):
            flip_loc = self.prms["flip"][compare]
            if flip_loc in ('True', 'true', 't', 'T', True):
                self.prms["flip"][compare] = True
            elif flip_loc in ('False', 'false', 'f', 'F', False):
                self.prms["flip"][compare] = False
            else:
                raise Exception(tools.red("initialization of vtudiff failed. vtudiff_flip '%s' not accepted." % flip_loc))

        # set logical for creating new reference files and copying them to the example source directory
        self.referencescopy = vtudiff.referencescopy

    def perform(self, runs):
        global vtk_module_loaded
        # Check if this analysis can be performed: vtk must be imported
        if not vtk_module_loaded:  # this boolean is set when importing vtk
            print(tools.red('Could not import vtk module. This is required for "Analyze_vtudiff". Aborting.'))
            Analyze.total_errors += 1
            return
        # default values for tolerances
        abs_default_tolerance = 1.0e-5
        rel_default_tolerance = 1.0e-8
        '''
        General workflow:
        1.    iterate over all runs
        1.1.0 Check if files are found
        1.1.1 Setup reader to read data from the vtu file
        1.1.2 read in data and convert it to numpy array
            ( not tested
            1.1.3 Reshape the dataset if required (or transpose it when flip_loc=T)
            1.2.0 sanity checks if data and reference data match
            1.2.1 When sorting is used, the sorted array is written to a new .vtu file with a new name
            ) not tested
        1.3   Compare the data with the reference data
        '''
        if self.one_diff_per_run and (self.nCompares != len(runs)):
            raise Exception(tools.red("Number of vtudiffs [=%s] and runs [=%s] is inconsistent. Please ensure all options have the same length or set vtudiff_one_diff_per_run=F." % (self.nCompares, len(runs))))

        # 1.  Iterate over all runs
        for iRun, run in enumerate(runs):
            # Check whether the list of diffs is to be used one-at-a-time, i.e., a list of diffs for a list of runs (each run only performs one diff, not all of them)
            if self.one_diff_per_run:
                # One comparison for each run
                compares = [iRun]
            else:
                # All comparisons for every run
                compares = range(self.nCompares)

            n = 0
            # Iterate over all comparisons for vtudiff
            for compare in compares:
                n += 1
                reference_file_loc = self.prms["reference_file"][compare]
                file_loc = self.prms["file"][compare]
                abs_tolerance_value_loc = self.prms["absolute_tolerance_value"][compare]
                rel_tolerance_value_loc = self.prms["relative_tolerance_value"][compare]
                sort_loc = self.prms["sort"][compare]
                sort_dim_loc = int(self.prms["sort_dim"][compare])
                sort_var_loc = int(self.prms["sort_var"][compare])
                reshape_loc = self.prms["reshape"][compare]
                reshape_dim_loc = int(self.prms["reshape_dim"][compare])
                reshape_value_loc = int(self.prms["reshape_value"][compare])
                flip_loc = self.prms["flip"][compare]
                array_name_loc = self.prms["array_name"][compare]
                max_differences_loc = int(self.prms["max_differences"][compare])

                # 1.1.0 Check if files are found
                path = os.path.join(run.target_directory, file_loc)
                path_ref_target = os.path.join(run.target_directory, reference_file_loc)
                path_ref_source = os.path.join(run.source_directory, reference_file_loc)

                # abort for flip/reshape/sort since only core functionality is adapted from h5diff and not tested/optimized yet
                if flip_loc or reshape_loc or sort_loc:
                    s = tools.red("Analyze_vtudiff: flip, reshape, and sort are not yet tested for .vtu files. Please set vtudiff_flip, vtudiff_reshape, and/or vtudiff_sort to False.")
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    continue

                # Copy new reference file: This is completely independent of the outcome of the current vtudiff
                if self.referencescopy:
                    run = copyReferenceFile(run, path, path_ref_source)
                    s = tools.yellow("Analyze_vtudiff: performed reference copy instead of analysis!")
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_infos += 1
                    # do not skip the following analysis tests, because reference file will be created -> continue
                    continue

                if not os.path.exists(path):
                    s = tools.red("Analyze_vtudiff: file does not exist, file=[%s]" % path)
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    continue
                if not os.path.exists(path_ref_target):
                    s = tools.red("Analyze_vtudiff: reference file does not exist, file=[%s]" % path_ref_target)
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    continue

                # 1.1.1 Setup reader to read data from the vtu file
                # read in generated data as unstructured grid
                reader = vtk.vtkXMLUnstructuredGridReader()
                reader.SetFileName(path)
                reader.GetOutputPort()
                reader.Update()
                # Sanity check if file was read
                if reader.CanReadFile(path) != 1:
                    s = tools.red("Analyze_vtudiff: Could not open .vtu file [%s]. Please make sure the provided reference file is a .vtu file and the result of the simulation is converted using piclas2vtk!" % (path))
                    run.analyze_results.appends(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    continue

                # read reference data as unstructured grid
                reader_ref = vtk.vtkXMLUnstructuredGridReader()
                reader_ref.SetFileName(path_ref_target)
                reader_ref.GetOutputPort()
                reader_ref.Update()
                # Sanity check if file was read
                if reader.CanReadFile(path_ref_target) != 1:
                    s = tools.red(
                        "Analyze_vtudiff: Could not open .vtu file [%s]. Please make sure the provided reference file is a .vtu file and the result of the simulation is converted using piclas2vtk!" % (path_ref_target)
                    )
                    run.analyze_results.appends(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    continue

                # 1.1.2 read in data and convert it to numpy array
                def read_in_vtk_data(data_reader, single_array_name=None):
                    '''
                    Function to read in data from vtk file and return numpy array

                    Currently cell and/or point data is read in, but can be extended to read in other data types (mainly field data if needed).

                    Input arguments:
                    - data_reader: vtk reader object
                    - single_array_name: string containing the name of the array to be read in (if None, all arrays are read in)

                    Return values:
                    - numpy_data: numpy array containing all data from the vtk file (stacked in columns)
                    - array_names_dims: dictionary containing the names of the arrays and their number of columns (number of components, e.g. 3 for Velocity for x,y and z respectively)
                    '''
                    num_arrays_per_type = [data_reader.GetOutput().GetPointData().GetNumberOfArrays(), data_reader.GetOutput().GetCellData().GetNumberOfArrays()]
                    data_getter_per_type = [data_reader.GetOutput().GetPointData, data_reader.GetOutput().GetCellData]
                    # number of arrays in the vtk file (return one for velocity, where 3 components will be added to the numpy array result)
                    vtk_num_arrays_total = 0
                    data = []
                    array_names_dims = {}
                    # loop over cell and point data and read in all arrays, if existent
                    for data_getter, num_of_arrays in zip(data_getter_per_type, num_arrays_per_type):
                        if num_of_arrays > 0:
                            array_names = [data_getter().GetArrayName(i) for i in range(num_of_arrays)]
                            lower_names = [arr_name.lower() for arr_name in array_names]
                            # check if only given arrays are compared
                            if single_array_name is not None and single_array_name.lower() in lower_names:
                                single_array_index = lower_names.index(single_array_name.lower())
                                # try to read in specific array but skip if it is not found in the current type (point or cell data respectively)
                                temp_array = np.array(data_getter().GetArray(array_names[single_array_index]), dtype=float)
                                # check if the array is a 1D array and reshape it to a 2D array to read in the dimensions correctly
                                if temp_array.ndim == 1:
                                    temp_array = temp_array.reshape(-1, 1)
                                vtk_num_arrays_total = 1
                                array_names_dims[array_names[single_array_index]] = temp_array.shape[1]
                                # only read in specific data
                                data.append(temp_array)

                            else:
                                # add number of cell and point data arrays
                                vtk_num_arrays_total = vtk_num_arrays_total + num_of_arrays
                                array_dim = data_getter().GetArray(0).GetNumberOfTuples()
                                # read in all data from vtk file
                                data = [np.array([data_getter().GetArray(i).GetTuple(j) for j in range(array_dim)]) for i in range(num_of_arrays)]
                                array_names_dims = {data_getter().GetArrayName(i): data[i].shape[1] for i in range(num_of_arrays)}

                    # Convert the list to a single numpy array (concatenated along columns) for each data type (point or cell data respectively)
                    numpy_data = np.hstack(data) if data else np.array([])
                    return numpy_data, array_names_dims

                try:
                    # Check if the array name in the file and the ref. have the same name
                    if array_name_loc is not None and len(array_name_loc.split()) > 1:
                        array_name_loc_file = array_name_loc.split()[0]  # first array name for result
                        array_name_loc_ref = array_name_loc.split()[1]  # second array name for reference
                    else:
                        array_name_loc_file = array_name_loc
                        array_name_loc_ref = array_name_loc

                    vtu_data, array_names_dims = read_in_vtk_data(reader, array_name_loc_file)
                    vtu_data_ref, array_names_dims_ref = read_in_vtk_data(reader_ref, array_name_loc_ref)
                except Exception as e:
                    s = tools.red(
                        "Analyze_vtudiff: Could not read in the data from the vtk file [%s] or [%s]. Please make sure the provided reference file is a .vtu file and the given array names exist! Error: %s"
                        % (file_loc, reference_file_loc, e)
                    )
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    continue

                # flip, reshape, and sort are not correctly implemented yet, since the operation is applied on the full numpy array which contains all vtu arrays stacked along columns
                # so flipping/reshaping the array might cause errors, moreover another variable would be needed to specify which vtu array should be flipped/reshaped/sorted
                # only allowed if a single array is compared! print statements for differences might not work correctly in this case
                if (flip_loc or reshape_loc or sort_loc) and len(array_names_dims) > 1:
                    print(tools.red('Analyze_vtudiff: The options flip, reshape, and sort are currently only implemented for single arrays.'))
                    Analyze.total_errors += 1
                    return

                try:
                    if flip_loc:
                        vtu_data = vtu_data.transpose()
                        vtu_data_ref = vtu_data_ref.transpose()
                except Exception as e:
                    s = tools.red("Analyze_vtudiff: Could not transpose array under in file [%s] (vtudiff_flip = T). Error message [%s]" % (file_loc, e))
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    continue

                data_shape = vtu_data.shape
                data_shape_ref = vtu_data_ref.shape

                # Set default values, which are required if flip_loc=T
                if not reshape_loc:
                    # Set values that effectively do not change the original shape if applied. The array has already been transposed in this case.
                    reshape_dim_loc = 0
                    reshape_value_loc = data_shape[0]

                # set name suffix for new file
                name_suffix = ''

                # 1.1.3   Reshape the dataset if required (or transpose it when flip_loc=T)
                if reshape_loc or flip_loc:
                    # Create new re-shaped array for storing to .h5
                    old_shape = data_shape
                    newShape = list(data_shape)
                    old_value = newShape[reshape_dim_loc]
                    newShape[reshape_dim_loc] = reshape_value_loc
                    newShape = tuple(newShape)
                    # Check if shape is being increased
                    if reshape_value_loc > old_value:
                        s = tools.red("Analyze_vtudiff: Reshaping is currently only implemented with the purpose to reduce array sizes. You are trying to increase the array shape from %s to %s" % (old_shape, newShape))
                        print(s)
                        run.analyze_results.append(s)
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                        continue
                    # Check if row or column is changed
                    if reshape_dim_loc == 0:
                        vtu_data = vtu_data[:reshape_value_loc, :]
                    elif reshape_dim_loc == 1:
                        vtu_data = vtu_data[:, :reshape_value_loc]
                    elif reshape_dim_loc == 2:
                        vtu_data = vtu_data[:, :, :reshape_value_loc]
                    elif reshape_dim_loc == 3:
                        vtu_data = vtu_data[:, :, :, :reshape_value_loc]
                    else:
                        s = tools.red(
                            "Analyze_vtudiff: Reshaping is currently only implemented for specific arrays (dim 0 and 1 reshape 2D array) "
                            "and dim 3 and 4 reshape the last dimension of 3D and 4D arrays. Use vtudiff_reshape_dim=1 or 2)"
                        )
                        print(s)
                        run.analyze_results.append(s)
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                        continue

                    data_shape = vtu_data.shape
                    name_suffix = name_suffix + '_reshaped'
                    file_loc_new = file_loc.split('.vtu')[0] + name_suffix + '.vtu'
                    # In the following, compare the reshaped array instead of the original one
                    str_1 = "'%s' (instead of '%s')" % (file_loc_new, file_loc)
                    print(
                        tools.yellow(
                            "    Reshaping dim=%s to value=%s (the old value was %s).\n    Now using: %s, which has a changed shape from %s to %s"
                            % (reshape_dim_loc, reshape_value_loc, old_value, str_1, old_shape, newShape)
                        )
                    )

                # 1.2.0   sanity checks if data and reference data match
                if data_shape != data_shape_ref:
                    s = tools.red("Analyze_vtudiff: Shape of the arrays in the vtk files [%s] and [%s] do not match! Shapes: %s, %s respectively!" % (file_loc, reference_file_loc, data_shape, data_shape_ref))
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    continue
                elif array_names_dims != array_names_dims_ref:
                    s = tools.red(
                        "Analyze_vtudiff: Array names or number of vtk arrays in the vtk files [%s] (Arrays: %s) do not match with [%s] (Arrays: %s)!"
                        % (file_loc, list(array_names_dims.keys()), reference_file_loc, list(array_names_dims_ref.keys()))
                    )
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    continue
                else:
                    print("\n", tools.yellow("Comparing %s vtk arrays with total of %s columns:") % (len(array_names_dims), data_shape[1]), list(array_names_dims.keys()))

                # 1.2.1 When sorting is used, the sorted array is written to a new .vtu file with a new name
                if sort_loc:
                    # Sort by X
                    if sort_dim_loc == 1:  # Sort by row
                        # Note that sort_var_loc begins at 0 as python starts at 0
                        vtu_data = vtu_data[:, vtu_data[sort_var_loc, :].argsort()]
                        vtu_data_ref = vtu_data_ref[:, vtu_data_ref[sort_var_loc, :].argsort()]
                    elif sort_dim_loc == 2:  # Sort by column
                        # Note that sort_var_loc begins at 0 as python starts at 0
                        vtu_data = vtu_data[vtu_data[:, sort_var_loc].argsort()]
                        vtu_data_ref = vtu_data_ref[vtu_data_ref[:, sort_var_loc].argsort()]
                    else:
                        s = tools.red(
                            "Analyze_vtudiff: Sorting failed, because currently only sorting of 2-dimensional arrays is implemented."
                            "\nThis means, that sorting by rows (dim=1) and columns (dim=2) is allowed. However, dim=[%s]" % sort_dim_loc
                        )
                        print(s)
                        run.analyze_results.append(s)
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                        continue

                    # In the following, compare the two sorted arrays instead of the original ones
                    name_suffix = name_suffix + '_sorted'
                    file_loc_new = file_loc.spipt('.vtu')[0] + name_suffix + '.vtu'
                    reference_file_loc_new = reference_file_loc.split('.vtu')[0] + name_suffix + '.vtu'
                    str_1 = "'%s' (instead of '%s')" % (file_loc_new, file_loc)
                    str_2 = "'%s' (instead of '%s')" % (reference_file_loc_new, reference_file_loc)
                    print(tools.yellow("    Sorting dim=%s by variable=%s (variable indexing begins at 0). Now comparing: %s with %s" % (sort_dim_loc, sort_var_loc, str_1, str_2)))

                # save new data if it was flipped, reshaped or sorted
                if sort_loc or flip_loc or reshape_loc:
                    vtk_data = vtk.vtkUnstructuredGrid()
                    # Extract points from the reader's output
                    points = reader.GetOutput().GetPoints()
                    vtk_data.SetPoints(points)
                    num_arrays_per_type = [reader.GetOutput().GetPointData().GetNumberOfArrays(), reader.GetOutput().GetCellData().GetNumberOfArrays()]
                    data_getter_per_type = [reader.GetOutput().GetPointData, reader.GetOutput().GetCellData]
                    data_writer_per_type = [vtk_data.GetPointData, vtk_data.GetCellData]
                    # loop over cell and point data and read in all arrays, if existent
                    for data_writer, data_getter, num_of_arrays in zip(data_writer_per_type, data_getter_per_type, num_arrays_per_type):
                        if num_of_arrays > 0:
                            for i in range(num_of_arrays):
                                num_of_cols = data_getter().GetArray(i).GetNumberOfComponents()
                                array_name = data_getter().GetArrayName(i)
                                array_name = array_name + name_suffix
                                vtk_new_array = vtk.util.numpy_support.numpy_to_vtk(num_array=vtu_data[:, i : i + num_of_cols], deep=True)
                                vtk_new_array.SetName(array_name)
                                # Add the new array to the VTK data
                                data_writer().AddArray(vtk_new_array)

                    output_file_loc = file_loc.split('.vtu')[0] + name_suffix + '.vtu'
                    output_file_loc = os.path.join(run.target_directory, output_file_loc)
                    # Write the VTK unstructured grid to file
                    try:
                        writer = vtk.vtkXMLUnstructuredGridWriter()
                        writer.SetFileName(output_file_loc)
                        writer.SetInputData(vtk_data)
                        writer.Write()
                        print("File written to: %s" % output_file_loc)
                    except Exception as e:
                        print("Error writing VTK file: %s" % e)

                # 1.3   Compare the data
                # np.isclose creates a boolean array with True for elements that are close to each other within a tolerance
                if abs_tolerance_value_loc and not rel_tolerance_value_loc:  # only use absolute tolerance
                    data_compare = np.isclose(vtu_data, vtu_data_ref, atol=float(abs_tolerance_value_loc))
                elif rel_tolerance_value_loc and not abs_tolerance_value_loc:  # only use relative tolerance
                    data_compare = np.isclose(vtu_data, vtu_data_ref, rtol=float(rel_tolerance_value_loc))
                else:  # use both absolute and relative tolerance otherwise
                    if abs_tolerance_value_loc is None and rel_tolerance_value_loc is None:  # use default values since no were given
                        data_compare = np.isclose(vtu_data, vtu_data_ref, atol=abs_default_tolerance, rtol=rel_default_tolerance)
                    else:  # both references were given
                        data_compare = np.isclose(vtu_data, vtu_data_ref, atol=float(abs_tolerance_value_loc), rtol=float(rel_tolerance_value_loc))
                NbrOfDifferences = np.sum(~data_compare)

                if NbrOfDifferences > 0:
                    if NbrOfDifferences > max_differences_loc:
                        # apply logical mask created by np.isclose to the data arrays
                        masked_array = np.ma.array(vtu_data, mask=data_compare)
                        masked_array_ref = np.ma.array(vtu_data_ref, mask=data_compare)
                        # get indices of differences corresponding to the orginal rows
                        non_masked_indices = np.where(np.any(~data_compare, axis=1))[0]
                        # create list of indices to print out first and last 20 entries
                        num_entries = min(20, masked_array.shape[0])
                        total_entries = len(non_masked_indices)
                        indices = list(range(num_entries))
                        # check if there are more than 20 unique indices, if yes append the last 20 unqiue indices to the list
                        if total_entries > num_entries:
                            indices += list(range(max(num_entries, total_entries - num_entries), total_entries))
                        # variables for array slicing and saving different/correct arrays, where offset counts number of already printed columns
                        offset = 0
                        error_array_names = []
                        correct_array_names = []
                        # print out differences, where array_names_dims contains the names of the vtk arrays with the corresponding number of columns (size)
                        for i, (name, size) in enumerate(list(array_names_dims.items())):
                            # check if there are any differences in the array, which are found as False in the mask
                            if np.any(~data_compare[:, offset : size + offset]):
                                # print out header
                                print(
                                    tools.red("{:<20} | {:<45} | {:<44}".format('Index', name, list(array_names_dims_ref.keys())[i] + '_ref'))
                                    + tools.yellow(" | {:<30} | {:<30}".format('Absolute Difference', 'Relative Difference'))
                                )
                                print('-' * 170)
                                # loop over unique indices and print out the differences
                                for i in indices:
                                    abs_diff = np.abs(masked_array[non_masked_indices[i], offset : size + offset] - masked_array_ref[non_masked_indices[i], offset : size + offset])
                                    rel_diff = abs_diff / np.abs(masked_array_ref[non_masked_indices[i], offset : size + offset])
                                    print(
                                        tools.red(
                                            "{:<20} | {:<45} | {:<45}".format(
                                                non_masked_indices[i],
                                                str(np.around(masked_array[non_masked_indices[i], offset : size + offset], decimals=4)),
                                                str(np.around(masked_array_ref[non_masked_indices[i], offset : size + offset], decimals=4)),
                                            )
                                        )
                                        + tools.yellow("| {:<30} | {:<30}".format(str(np.around(abs_diff, decimals=2)), str(np.around(rel_diff, decimals=2))))
                                    )
                                offset += size
                                error_array_names.append(name)
                            else:
                                correct_array_names.append(name)
                        s = "Comparison failed for %s of [%s] with [%s] due to %s differences\n" % (error_array_names, path, reference_file_loc, NbrOfDifferences)
                        s = tools.red(s)
                        if len(correct_array_names) > 0:
                            s2 = "\nComparison sucessfull for %s of [%s] with [%s]\n" % (correct_array_names, path, reference_file_loc)
                            s2 = tools.green(s2)
                            print(s2)
                        run.analyze_results.append(s)
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                    else:
                        s = s.replace("Comparison failed for", "Comparison ignored for")
                        s2 = ", but %s difference(s) are allowed (given by compare_data_file_max_differences). This analysis is therefore marked as passed." % max_differences_loc
                        s2 = tools.pink(s + s2)
                        print(s2)

                else:
                    NbrOfMatches = np.sum(data_compare)
                    if NbrOfMatches == 0:
                        s = tools.red("Analyze_compare_data_file: Found zero matching values. Wrong data file under [%s] or format that could possibly not be read correctly" % (path))
                        print(s)
                        run.analyze_results.append(s)
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                    else:
                        s = tools.blue(tools.indent("Compared %s of %s with %s and got %s matching columns" % (array_name_loc, path, reference_file_loc, data_shape), 2))
                        print(s)

    def __str__(self):
        return "perform vtudiff between two files: [" + str(self.prms["file"][0]) + "] + reference [" + str(self.prms["reference_file"][0]) + "]"


# ==================================================================================================


class Analyze_check_hdf5(Analyze):
    def __init__(self, CheckHDF5):
        # fmt: off
        self.file                = CheckHDF5.file
        self.data_set            = CheckHDF5.data_set
        self.span                = int(CheckHDF5.span)
        (self.dim1, self.dim2)   = [int(x)   for x in CheckHDF5.dimension.split(":")]
        (self.lower, self.upper) = [float(x) for x in CheckHDF5.limits.split(":")]
        # fmt: on

    def perform(self, runs):
        global h5py_module_loaded
        # check if this analysis can be performed: h5py must be imported
        if not h5py_module_loaded:  # this boolean is set when importing h5py
            print(tools.red('Could not import h5py module. This is required for "Analyze_check_hdf5". Aborting.'))
            Analyze.total_errors += 1
            return

        '''
        Description: check array bounds in hdf5 file

        General workflow:
        1.  iterate over all runs
        1.2   Read the hdf5 file
        1.2.1   Check if dataset exists
        1.3   Read the dataset from the hdf5 file
        1.3.0   Check if data set is empty
        1.3.1   loop over each dimension supplied
        1.3.2   Check either rows or columns
        1.3.3   Check if all values are within the supplied interval
        1.3.4   set analyzes to fail if return a code != 0
        '''

        # 1.  iterate over all runs
        for run in runs:
            # 1.2   Read the hdf5 file
            path = os.path.join(run.target_directory, self.file)
            if not os.path.exists(path):
                s = tools.red("Analyze_check_hdf5: file does not exist, file=[%s]" % path)
                print(s)
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
                continue

            f = h5py.File(path, 'r')
            # available keys   : print("Keys: %s" % f.keys())
            # first key in list: a_group_key = list(f.keys())[0]

            # 1.2.1   Check if dataset exists
            if self.data_set not in f.keys():
                s = tools.red("Analyze_check_hdf5: [%s] not found in file=[%s]" % (self.data_set, path))
                print(s)
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
                continue

            # 1.3   Read the dataset from the hdf5 file
            b = f[self.data_set][:]

            # 1.3.0   Check if data set is empty
            if min(b.shape) == 0:
                s = tools.red("Analyze_check_hdf5: [%s] has at least one empty dimension, shape=%s" % (self.data_set, b.shape))
                print(s)
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
                continue

            # 1.3.1   loop over each dimension supplied
            for i in range(self.dim1, self.dim2 + 1):
                # 1.3.2   Check either rows or columns
                if self.span == 1:  # Check each row element
                    # Note that sort_var_loc begins at 0 as python starts by 0
                    lower_test = any([x < self.lower for x in b[:, i]])
                    upper_test = any([x > self.upper for x in b[:, i]])
                elif self.span == 2:  # Check each column element
                    lower_test = any([x < self.lower for x in b[i, :]])
                    upper_test = any([x > self.upper for x in b[i, :]])
                else:
                    s = tools.red(
                        "Analyze_check_hdf5: Bounding box check failed for i=%s, because currently only sorting of 2-dimensional arrays is implemented.\nThis means, "
                        "that sorting by rows (dim=1) and columns (dim=2) is allowed. However, dim=[%s] (parameter: check_hdf5_span)" % (i, self.span)
                    )
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    continue

                # 1.3.3   Check if all values are within the supplied interval
                if lower_test or upper_test:
                    if self.span == 1:  # Check each row element
                        print(tools.red("values = " + str(b[:, i]) + " MIN=[" + str(min(b[:, i])) + "]" + " MAX=[" + str(max(b[:, i])) + "]"))
                    else:  # Check each column element
                        print(tools.red("values = " + str(b[i, :]) + " MIN=[" + str(min(b[i, :])) + "]" + " MAX=[" + str(max(b[i, :])) + "]"))

                    s = tools.red("HDF5 array out of bounds for dimension = %2d (array dimension index starts at 0). " % i)
                    if lower_test:
                        s += tools.red(" [values found  < " + str(self.lower) + "]")
                    if upper_test:
                        s += tools.red("  and  [values found  > " + str(self.upper) + "]")
                    print(s)
                    run.analyze_results.append(s)

                    # 1.3.4   set analyzes to fail if return a code != 0
                    run.analyze_successful = False
                    Analyze.total_errors += 1

    def __str__(self):
        return "check if the values of an hdf5 array are within specified limits: file= [" + str(self.file) + "], dataset= [" + str(self.data_set) + "]"


# ==================================================================================================


class Analyze_compare_data_file(Analyze):
    def __init__(self, CompareDataFile):
        # Set number of diffs per run [True/False]
        if isinstance(CompareDataFile.one_diff_per_run, bool):  # check if default value is still set
            self.one_diff_per_run = True
        else:
            # Check what the user set
            self.one_diff_per_run = CompareDataFile.one_diff_per_run in ('False', 'false', 'f', 'F')
            if self.one_diff_per_run:
                # User selected False
                self.one_diff_per_run = False
            else:
                # User selected something else
                self.one_diff_per_run = CompareDataFile.one_diff_per_run in (('True', 'true', 't', 'T'))
                if self.one_diff_per_run:
                    # User selected True
                    pass
                else:
                    raise Exception(tools.red("CompareDataFile.one_diff_per_run is set neither True/False, check the parameter"))

        # Create dictionary for all keys/parameters and insert a list for every value/options
        self.prms = {
            "file": CompareDataFile.name,
            "reference_file": CompareDataFile.reference,
            "tolerance_value": CompareDataFile.tolerance,
            "tolerance_type": CompareDataFile.tolerance_type,
            "line": CompareDataFile.line,
            "delimiter": CompareDataFile.delimiter,
            "max_differences": CompareDataFile.max_differences,
        }

        for key, prm in self.prms.items():
            # Check if prm is not of type 'list'
            if not isinstance(prm, list):
                # create list with prm as entry
                self.prms[key] = [prm]

        # Get the number of values/options for each key/parameter
        numbers = {key: len(prm) for key, prm in self.prms.items()}

        # Get maximum number of values (from all possible keys)
        self.nCompares = numbers[max(numbers, key=numbers.get)]

        # Check all numbers and if a key has only 1 number, increase the number to maximum and use the same value for all
        for key, number in numbers.items():
            if number == 1:
                self.prms[key] = [self.prms[key][0] for i in range(self.nCompares)]
                numbers[key] = self.nCompares

        if any([(number != self.nCompares) for number in numbers.values()]):
            raise Exception(tools.red("Number of multiple data sets for multiple compare_data_file is inconsistent. Please ensure all options have the same length or length=1."))

        # Check tolerance type (absolute or relative) and set the correct h5diff command line argument
        for compare in range(self.nCompares):
            tolerance_type_loc = self.prms["tolerance_type"][compare]
            if tolerance_type_loc in ('absolute', 'delta', '--delta'):
                self.prms["tolerance_type"][compare] = "absolute"
            elif tolerance_type_loc in ('relative', "--relative"):
                self.prms["tolerance_type"][compare] = "relative"
            else:
                raise Exception(tools.red("initialization of compare_data_file failed. compare_data_file_tolerance_type '%s' not accepted." % tolerance_type_loc))

            line_loc = self.prms["line"][compare]
            if line_loc == 'last':
                self.prms["line"][compare] = int(1e20)
            else:
                self.prms["line"][compare] = int(line_loc)

        # set logical for creating new reference files and copying them to the example source directory
        self.referencescopy = CompareDataFile.referencescopy

    def perform(self, runs):
        """
        General workflow:

        1.  iterate over all runs
        1.1   Set the file and reference file for comparison
        1.2   Check existence the file and reference values
        1.3.1   read data file
        1.3.2   read reference file
        1.3.3   check length of vectors
        1.3.4   calculate difference and determine compare with tolerance
        """
        if self.one_diff_per_run and (self.nCompares != len(runs)) and self.nCompares > 1:
            s = tools.red(
                "Number of compare_data_file tests and runs is inconsistent."
                + "Please ensure all options have the same length or set compare_data_file_one_diff_per_run=F. Nbr. of comparisons: %s, Nbr. of runs: %s" % (self.nCompares, len(runs))
            )
            print(s)
            # 1.  iterate over all runs
            for _iRun, run in enumerate(runs):
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
            return  # skip the following analysis tests

        # 1.  iterate over all runs
        for iRun, run in enumerate(runs):
            # Check whether the list of diffs is to be used one-at-a-time, i.e., a list of diffs for a list of runs (each run only performs one diff, not all of them)
            if self.one_diff_per_run:
                if self.nCompares > 1:
                    # One comparison for each run
                    compares = [iRun]
                else:
                    compares = [0]
            else:
                # All comparisons for every run
                compares = range(self.nCompares)

            # Iterate over all comparisons for h5diff
            for compare in compares:
                # fmt: off
                reference_file_loc   = self.prms["reference_file"][compare]
                file_loc             = self.prms["file"][compare]
                tolerance_value_loc  = float(self.prms["tolerance_value"][compare])
                tolerance_type_loc   = self.prms["tolerance_type"][compare]
                delimiter_loc        = self.prms["delimiter"][compare]
                max_differences_loc  = int(self.prms["max_differences"][compare])
                line_loc             = int(self.prms["line"][compare])

                # 1.1.0   Read the hdf5 file
                path            = os.path.join(run.target_directory,file_loc)
                path_ref_target = os.path.join(run.target_directory,reference_file_loc)
                path_ref_source = os.path.join(run.source_directory,reference_file_loc)
                # fmt: on

                # Copy new reference file: This is completely independent of the outcome of the current compare data file
                if self.referencescopy:
                    run = copyReferenceFile(run, path, path_ref_source)
                    s = tools.yellow("Analyze_compare_data_file: performed reference copy")
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_infos += 1
                    # do not skip the following analysis tests, because reference file will be created -> continue
                    continue

                if not os.path.exists(path) or not os.path.exists(path_ref_target):
                    s = tools.red("Analyze_compare_data_file: cannot find both file=[%s] and reference file=[%s]" % (path, reference_file_loc))
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    # do not skip the following analysis tests to see what other files might be missing
                    continue

                # 1.3.1   read data file
                line = []
                with open(path, 'r') as csvfile:
                    line_str = csv.reader(csvfile, delimiter=delimiter_loc, quotechar='!')
                    i = 0
                    header = 0
                    for row in line_str:
                        try:
                            # This will fail for header lines, but not for '-0.102704038304E-10, 0.190378371853E-10,-0.299883576917E+10'
                            line = np.array([float(x) for x in row])
                        except Exception:
                            try:
                                # Try and convert rows like this: ' -0.102704038304E-10   0.190378371853E-10  -0.299883576917E+10' because when "," is the delimiter they are read into a single element
                                line = np.array([float(x) for x in row[0].split()])
                            except Exception:
                                header += 1
                                header_line = row
                        i += 1
                        if i == line_loc:
                            print(tools.yellow(str(i)), end=' ')  # skip line break
                            break
                    line_len = len(line)

                # 1.3.2   read reference file
                # TODO: this always extracts the last line from the reference file - you probably want to compare against same line as in data file, i.e. 'line_loc'?  # noqa: TD003 existed before ruff integration
                line_ref = []
                with open(path_ref_target, 'r') as csvfile:
                    line_str = csv.reader(csvfile, delimiter=delimiter_loc, quotechar='!')
                    header_ref = 0
                    for row in line_str:
                        try:
                            # This will fail for header lines, but not for '-0.102704038304E-10, 0.190378371853E-10,-0.299883576917E+10'
                            line_ref = np.array([float(x) for x in row])
                        except Exception:  # noqa: PERF203 `try`-`except` within a loop incurs performance
                            try:
                                # Try and convert rows like this: ' -0.102704038304E-10   0.190378371853E-10  -0.299883576917E+10' because when "," is the delimiter they are read into a single element
                                line_ref = np.array([float(x) for x in row[0].split()])
                            except Exception:
                                header_ref += 1
                    line_ref_len = len(line_ref)

                # 1.3.3   check length of vectors
                if line_len != line_ref_len:
                    s = tools.red("Analyze_compare_data_file: length of lines in file [%s] and reference file [%s] are not of the same length" % (path, reference_file_loc))
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    return  # skip the following analysis tests

                # 1.3.4   calculate difference and determine compare with tolerance
                success = tools.diff_lists(line, line_ref, tolerance_value_loc, tolerance_type_loc)
                NbrOfDifferences = success.count(False)

                # if not all(success) :
                if NbrOfDifferences > 0:
                    s = "Comparison failed for [%s] with [%s] due to %s differences\n" % (path, reference_file_loc, NbrOfDifferences)
                    try:
                        test = header_line[len(success) - 1]  # dummy variable to test if the header can be accessed for the last possibly entry or not, # noqa: F841 local variable 'test' is assigned to but never used
                        s = s + "Mismatch in columns: " + ", ".join([str(header_line[i]).strip() for i in range(len(success)) if not success[i]])
                    except Exception:
                        # When the header is not in the same structure as the data itself, simply output the number of the column
                        s = s + "Mismatch in columns: " + ", ".join(['Nbr. ' + str(i + 1).strip() for i in range(len(success)) if not success[i]])
                    if NbrOfDifferences > max_differences_loc:
                        s = tools.red(s)
                        print(s)
                        run.analyze_results.append(s)
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                    else:
                        s = s.replace("Comparison failed for", "Comparison ignored for")
                        s2 = ", but %s difference(s) are allowed (given by compare_data_file_max_differences). This analysis is therefore marked as passed." % max_differences_loc
                        s2 = tools.pink(s + s2)
                        print(s2)

                else:
                    NbrOfMatches = success.count(True)
                    if NbrOfMatches == 0:
                        s = tools.red("Analyze_compare_data_file: Found zero matching values. Wrong data file under [%s] or format that could possibly not be read correctly" % (path))
                        print(s)
                        run.analyze_results.append(s)
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                    else:
                        s = tools.blue(tools.indent("Compared %s with %s and got %s matching columns" % (path, reference_file_loc, NbrOfMatches), 2))
                        print(s)

    def __str__(self):
        return "compare line in data file (e.g. .csv file): file=[%s] and reference file=[%s]" % (self.prms["file"], self.prms["reference_file"])


# ==================================================================================================


class Analyze_integrate_line(Analyze):
    def __init__(self, IntegrateLine):
        # fmt: off
        self.file                = IntegrateLine.file
        self.delimiter           = IntegrateLine.delimiter
        (self.dim1, self.dim2)   = [int(x) for x in IntegrateLine.columns.split(":")]
        self.integral_value      = float(IntegrateLine.integral_value)
        self.tolerance_value     = float(IntegrateLine.tolerance_value)
        self.tolerance_type      = IntegrateLine.tolerance_type
        self.option              = IntegrateLine.option
        self.multiplier          = float(IntegrateLine.multiplier)
        # fmt: on

    def perform(self, runs):
        """
        General workflow:

        1.  iterate over all runs
        1.2   Check existence the file and reference values
        1.3.1   read data file
        1.3.2   check column numbers
        1.3.3   get header information for integrated columns
        1.3.4   split the data array and set the two column vector x and y for integration
        1.3.5   Check the number of data points: Integration can only be performed if at least two points exist
        1.4   integrate values numerically
        """
        # 1.  iterate over all runs
        for run in runs:
            # 1.2   Check existence the file and reference values
            path = os.path.join(run.target_directory, self.file)
            if not os.path.exists(path):
                s = tools.red("Analyze_integrate_line: cannot find file=[%s] " % (self.file))
                print(s)
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
                return

            data = np.array([])
            # 1.3.1   read data file
            with open(path, 'r') as csvfile:
                line_str = csv.reader(csvfile, delimiter=self.delimiter, quotechar='!')
                max_lines = 0
                header = 0
                for row in line_str:
                    try:  # try reading a line from the data file and converting it into a numpy array
                        line = np.array([float(x) for x in row])
                        failed = False
                    except Exception:  #
                        header += 1
                        header_line = row
                        failed = True
                    if not failed:
                        data = np.append(data, line)
                    max_lines += 1

            if failed:
                s = "Analyze_integrate_line: reading of the data file [%s] has failed.\nNo float type data could be read. Check the file content." % path
                print(tools.red(s))
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
                return

            # 1.3.2 check column numbers
            line_len = len(line) - 1
            if line_len < self.dim1 or line_len < self.dim2:
                s = "cannot perform analyze Analyze_integrate_line, because the supplied columns (%s:%s) exceed the columns (%s) in the data file (the first column starts at 0)" % (self.dim1, self.dim2, line_len)
                print(tools.red(s))
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
                return

            # 1.3.3   get header information for integrated columns
            if header > 0:
                for i in range(line_len + 1):
                    header_line[i] = header_line[i].replace(" ", "")
                    # print header_line[i]
                s1 = header_line[self.dim1]
                s2 = header_line[self.dim2]
                print(tools.indent(tools.blue("Integrating (trapezoid rule) the column [%s] over [%s] with %s points: " % (s2, s1, max_lines - header)), 2), end=' ')  # skip linebreak

            # 1.3.4   split the data array and set the two column vector x and y for integration
            data = np.reshape(data, (-1, line_len + 1))
            data = np.transpose(data)
            x = data[self.dim1]
            y = data[self.dim2]

            # 1.3.5   Check the number of data points: Integration can only be performed if at least two points exist
            if max_lines - header < 2:
                s = "cannot perform analyze Analyze_integrate_line, because there are not enough lines of data to perform the integral calculation. Number of lines = %s" % (max_lines - header)
                print(tools.red(s))
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
                return

            # 1.4 integrate the values numerically
            Q = 0.0
            for i in range(max_lines - header - 1):
                # use trapezoidal rule (also known as the trapezoid rule or trapezium rule)
                dx = x[i + 1] - x[i]
                if self.option == 'DivideByTimeStep':
                    dQ = (y[i + 1] + y[i]) / 2.0
                else:
                    dQ = dx * (y[i + 1] + y[i]) / 2.0
                Q += dQ
            Q = Q * self.multiplier
            if self.tolerance_type == 'absolute':
                diff = self.integral_value - Q
            else:  # relative comparison
                ref = self.integral_value
                if abs(ref) > 0.0:
                    diff = abs(Q / ref - 1.0)
                else:
                    diff = Q
            s = "Integrated value: [%s], Reference value: [%s], %s Difference: [%s] (%s tolerance %s)" % (Q, self.integral_value, self.tolerance_type, diff, self.tolerance_type, self.tolerance_value)
            # 1.5   calculate difference and determine compare with tolerance
            success = tools.diff_value(Q, self.integral_value, self.tolerance_value, self.tolerance_type)
            if not success:
                s = tools.red("Mismatch in integrated line: " + s)
                print(s)
                run.analyze_successful = False
                run.analyze_results.append(s)
                Analyze.total_errors += 1
            else:
                print(tools.blue(s))

    def __str__(self):
        return "Integrate column data over line (e.g. from .csv file): file=[%s] and integrate columns %s over %s (the first column starts at 0)" % (self.file, self.dim2, self.dim1)


# ==================================================================================================


class Analyze_compare_column(Analyze):
    def __init__(self, CompareColumn, example):
        # Set number of diffs per restart file [True/False]
        if isinstance(CompareColumn.one_diff_per_restart_file, bool):  # check if default value is still set
            self.one_diff_per_restart_file = False
        else:
            # Check what the user set
            self.one_diff_per_restart_file = CompareColumn.one_diff_per_restart_file in ('False', 'false', 'f', 'F')
            if self.one_diff_per_restart_file:
                # User selected False
                self.one_diff_per_restart_file = False
            else:
                # User selected something else
                self.one_diff_per_restart_file = CompareColumn.one_diff_per_restart_file in (('True', 'true', 't', 'T'))
                if self.one_diff_per_restart_file:
                    # User selected True
                    pass
                else:
                    raise Exception(tools.red("CompareColumn.one_diff_per_restart_file is set neither True/False, check the parameter"))

        if self.one_diff_per_restart_file:
            self.one_diff_per_run = False
        else:
            # Set number of diffs per run [True/False]
            if isinstance(CompareColumn.one_diff_per_run, bool):  # check if default value is still set
                self.one_diff_per_run = True
            else:
                # Check what the user set
                self.one_diff_per_run = CompareColumn.one_diff_per_run in ('False', 'false', 'f', 'F')
                if self.one_diff_per_run:
                    # User selected False
                    self.one_diff_per_run = False
                else:
                    # User selected something else
                    self.one_diff_per_run = CompareColumn.one_diff_per_run in (('True', 'true', 't', 'T'))
                    if self.one_diff_per_run:
                        # User selected True
                        pass
                    else:
                        raise Exception(tools.red("CompareColumn.one_diff_per_run is set neither True/False, check the parameter"))

        # Create dictionary for all keys/parameters and insert a list for every value/options
        self.prms = {
            "file": CompareColumn.file,
            "reference_file": CompareColumn.reference_file,
            "tolerance_value": CompareColumn.tolerance_value,
            "tolerance_type": CompareColumn.tolerance_type,
            "delimiter": CompareColumn.delimiter,
        }
        # Column indices are not part of the dictionary

        if isinstance(CompareColumn.index, list):
            # make integers from list
            self.index = [int(x) for x in CompareColumn.index]
        else:
            # Split string
            self.index = [int(x) for x in CompareColumn.index.split(",")]

        for key, prm in self.prms.items():
            # Check if prm is not of type 'list'
            if not isinstance(prm, list):
                # create list with prm as entry
                self.prms[key] = [prm]

        # Get the number of values/options for each key/parameter
        numbers = {key: len(prm) for key, prm in self.prms.items()}

        # Get maximum number of values (from all possible keys)
        self.nCompares = numbers[max(numbers, key=numbers.get)]

        # Get maximum number of runs from the command line
        self.nCommands = len(example.command_lines)

        # Check all numbers and if a key has only 1 number, increase the number to maximum and use the same value for all
        for key, number in numbers.items():
            if number == 1:
                self.prms[key] = [self.prms[key][0] for i in range(self.nCompares)]
                numbers[key] = self.nCompares

        # Check if all parameters have the same length (values with only one parameter have been filled up above)
        if any([(number != self.nCompares) for number in numbers.values()]):
            raise Exception(tools.red("Number of multiple data sets for multiple compare_column is inconsistent. Please ensure all options have the same length or length=1."))

        # Check tolerance type (absolute or relative) and set the correct h5diff command line argument
        for compare in range(self.nCompares):
            tolerance_type_loc = self.prms["tolerance_type"][compare]
            if tolerance_type_loc in ('absolute', 'delta', '--delta'):
                self.prms["tolerance_type"][compare] = "absolute"
            elif tolerance_type_loc in ('relative', "--relative"):
                self.prms["tolerance_type"][compare] = "relative"
            else:
                raise Exception(tools.red("initialization of compare_column failed. compare_column_tolerance_type '%s' not accepted." % tolerance_type_loc))

        # set logical for creating new reference files and copying them to the example source directory
        self.referencescopy = CompareColumn.referencescopy

    def perform(self, runs):
        """
        General workflow:

        * Iterate over all successful runs
          * Set compares in case of one_diff_per_*
          * Iterate over all compares
            * Check existence of the file and reference
            * Iterate over all columns to be compared
              * read data file and reference file
              * check column number
              * get header information for columns
              * Check dimensions of the arrays
              * Check the number of data points: Comparison can only be performed if at least one point exists
              * calculate difference and determine compare with tolerance
        """
        if self.one_diff_per_restart_file and (self.nCompares < self.iRestartFile + 1) and self.nCompares > 1:
            s = tools.red(
                "Number of compare_column tests and command line runs is inconsistent."
                + " Please ensure all options have the same length or set compare_column_one_diff_per_restart_file=F. Nbr. of comparisons: %s, Nbr. of command line runs: %s" % (self.nCompares, self.iRestartFile + 1)
            )
            print(s)
            # 1.  iterate over all runs
            for _iRun, run in enumerate(runs):
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
            return  # skip the following analysis tests
        elif self.one_diff_per_run and (self.nCompares != len(runs)) and self.nCompares > 1:
            s = tools.red(
                "Number of compare_column tests and runs is inconsistent."
                + " Please ensure all options have the same length or set compare_column_one_diff_per_run=F. Nbr. of comparisons: %s, Nbr. of runs: %s" % (self.nCompares, len(runs))
            )
            print(s)
            # 1.  iterate over all runs
            for _iRun, run in enumerate(runs):
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
            return  # skip the following analysis tests

        count = 0
        NbrOfDifferences = 0
        # 1.  iterate over all runs
        for iRun, run in enumerate(runs):
            # count += 1
            # Check whether the list of diffs is to be used one-at-a-time, i.e., a list of diffs for a list of runs (each run only performs one diff, not all of them)
            if self.one_diff_per_restart_file:
                if self.nCompares > 1:
                    # One comparison for each run
                    compares = [self.iRestartFile]
                else:
                    compares = [0]
            elif self.one_diff_per_run:
                if self.nCompares > 1:
                    # One comparison for each run
                    compares = [iRun]
                else:
                    compares = [0]
            else:
                # All comparisons for every run
                compares = range(self.nCompares)

            # Iterate over all comparisons
            for compare in compares:
                # fmt: off
                reference_file_loc   = self.prms["reference_file"][compare]
                file_loc             = self.prms["file"][compare]
                tolerance_value_loc  = float(self.prms["tolerance_value"][compare])
                tolerance_type_loc   = self.prms["tolerance_type"][compare]
                delimiter_loc        = self.prms["delimiter"][compare]

                # 1.2   Check existence of the file and reference (copy the ref. file when self.referencescopy = True )
                path             = os.path.join(run.target_directory,file_loc)
                path_ref_target  = os.path.join(run.target_directory,reference_file_loc)
                path_ref_source  = os.path.join(run.source_directory,reference_file_loc)
                # fmt: on

                # Copy new reference file: This is completely independent of the outcome of the current compare data file
                if self.referencescopy:
                    run = copyReferenceFile(run, path, path_ref_source)
                    s = tools.yellow("Analyze_compare_column: performed reference copy")
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_infos += 1
                    # do not skip the following analysis tests, because reference file will be created -> continue
                    continue

                if not os.path.exists(path):
                    s = tools.red("Analyze_compare_column: cannot find file=[%s] " % (file_loc))
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    # do not skip the following analysis tests to see what other files might be missing
                    continue

                if not os.path.exists(path_ref_target):
                    s = tools.red("Analyze_compare_column: cannot find reference file=[%s] " % (reference_file_loc))
                    print(s)
                    run.analyze_results.append(s)
                    run.analyze_successful = False
                    Analyze.total_errors += 1
                    # do not skip the following analysis tests to see what other files might be missing
                    continue

                # Iterate over all columns to be compared
                for index_loc in self.index:
                    # 1.3.1   read data file
                    data = np.array([])
                    with open(path, 'r') as csvfile:
                        line_str = csv.reader(csvfile, delimiter=delimiter_loc, quotechar='!')
                        max_lines = 0
                        header = 0
                        # Get the number of columns from the first row
                        column_count = len(next(line_str))
                        # Rewind csv file back to the beginning
                        csvfile.seek(0)
                        # Sanity check: number of columns should not be smaller than the selected column
                        if column_count - 1 < index_loc:
                            s = ("Cannot perform analyze Analyze_compare_column, because the supplied column (%s) in %s exceeds the number of " "columns (%s) in the data file (the first column must start at 0)") % (
                                index_loc,
                                path,
                                0,
                            )
                            print(tools.red(s))
                            run.analyze_results.append(s)
                            run.analyze_successful = False
                            Analyze.total_errors += 1
                            # do not skip the following analysis tests to check other columns
                            continue
                        for row in line_str:
                            # try reading a value from the column from the data file and converting it into a numpy array
                            try:
                                line = np.array([float(row[index_loc])])
                                failed = False
                            # Assuming that the header line cannot be converted into a float and store the header line
                            except Exception:
                                header += 1
                                header_line = row[index_loc]
                                failed = True
                            if not failed:
                                data = np.append(data, line)
                            max_lines += 1

                    # Check if any data has been read-in
                    if failed:
                        s = "Analyze_compare_column: reading of the data file [%s] has failed.\nNo float type data could be read. Check the file content." % path
                        print(tools.red(s))
                        run.analyze_results.append(s)
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                        # do not skip the following analysis tests
                        continue

                    # Read reference file
                    data_ref = np.array([])
                    with open(path_ref_target, 'r') as csvfile_ref:
                        line_str = csv.reader(csvfile_ref, delimiter=delimiter_loc, quotechar='!')
                        max_lines_ref = 0
                        header_ref = 0
                        # Get the number of columns from the first row
                        column_count_ref = len(next(line_str))
                        # Rewind csv file back to the beginning
                        csvfile_ref.seek(0)
                        # Sanity check: either reference file has 1 column or at least as many columns as the column number selected for comparison
                        if column_count_ref == 1:
                            refDim = 0  # Use the only available column for the comparison
                        elif column_count_ref - 1 >= index_loc:
                            refDim = index_loc
                        elif column_count_ref - 1 < index_loc:
                            s = ("Cannot perform analyze Analyze_compare_column, because the supplied column (%s) in %s exceeds the number of " "columns (%s) in the reference file (the first column must start at 0)") % (
                                index_loc,
                                path_ref_target,
                                0,
                            )
                            print(tools.red(s))
                            run.analyze_results.append(s)
                            run.analyze_successful = False
                            Analyze.total_errors += 1
                            # do not skip the following analysis tests to check other columns
                            continue
                        for row in line_str:
                            # Try reading a value from the column from the data file and converting it into a numpy array
                            try:
                                line_ref = np.array([float(row[refDim])])
                                failed = False
                            # Assuming that the header line cannot be converted into a float and store the header line
                            except Exception:
                                header_ref += 1
                                failed = True
                            if not failed:
                                data_ref = np.append(data_ref, line_ref)
                            max_lines_ref += 1

                    if failed:
                        s = "Analyze_compare_column: reading of the data reference file [%s] has failed.\nNo float type data could be read. Check the file content." % path_ref_target
                        print(tools.red(s))
                        run.analyze_results.append(s)
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                        # do not skip the following analysis tests
                        continue

                    # Get header information for column
                    if header > 0:
                        if count == 1 or NbrOfDifferences > 0:
                            print(tools.indent(tools.blue("Comparing the column [%s] for run: %s..." % (header_line, count)), 2), end=' ')  # skip linebreak
                        else:
                            print(tools.indent(tools.blue("%s..." % (count)), 2), end=' ')  # skip linebreak

                    # Check dimensions of the arrays
                    if data.shape != data_ref.shape:
                        s = ("cannot perform analyze Analyze_compare_column, because the shape of the data in file=[%s] is %s and that of the " "reference=[%s] is %s. They cannot be different!") % (
                            path,
                            data.shape,
                            reference_file_loc,
                            data_ref.shape,
                        )
                        print(tools.red(s))
                        run.analyze_results.append(s)
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                        # do not skip the following analysis tests
                        continue

                    # Check the number of data points: Comparison can only be performed if at least one point exists
                    if max_lines - header < 1 or max_lines_ref - header_ref < 1 or max_lines - header != max_lines_ref - header_ref:
                        s = (
                            "cannot perform analyze Analyze_compare_column, because there are not enough lines of data or different numbers of "
                            "data points to perform the comparison. Number of lines = %s (file) and %s (reference file), which must be equal and "
                            "at least one."
                        ) % (max_lines - header, max_lines_ref - header_ref)
                        print(tools.red(s))
                        run.analyze_results.append(s)
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                        # do not skip the following analysis tests
                        continue

                    # Calculate difference and determine compare with tolerance
                    success = tools.diff_lists(data, data_ref, tolerance_value_loc, tolerance_type_loc)
                    NbrOfDifferences = success.count(False)

                    if NbrOfDifferences > 0:
                        s = tools.red("Analyze_compare_column() failed: Found %s differences.\n" % NbrOfDifferences)
                        s = s + tools.red("Mismatch in column: %s" % header_line[index_loc])
                        print(s)
                        run.analyze_results.append(s)
                        run.analyze_successful = False
                        Analyze.total_errors += 1
                # print new line
                print()

    def __str__(self):
        if self.one_diff_per_restart_file:
            return "compare column data with a reference (e.g. from .csv file): file=[%s] and reference=[%s] and comparison for column %s (the first column starts at 0)" % (
                self.prms["file"][self.iRestartFile],
                self.prms["reference_file"][self.iRestartFile],
                self.index,
            )
        else:
            return "compare column data with a reference (e.g. from .csv file): file=[%s] and reference=[%s] and comparison for column %s (the first column starts at 0)" % (
                self.prms["file"],
                self.prms["reference_file"],
                self.index,
            )


# ==================================================================================================


class Analyze_compare_across_commands(Analyze):
    def __init__(self, CompareAcrossCommands):
        # fmt: off
        self.file                = CompareAcrossCommands.file
        self.delimiter           = CompareAcrossCommands.column_delimiter
        self.column_index        = int(CompareAcrossCommands.column_index)
        self.tolerance_value     = float(CompareAcrossCommands.tolerance_value)
        self.tolerance_type      = CompareAcrossCommands.tolerance_type
        self.reference           = int(CompareAcrossCommands.reference)
        # fmt: on

        if CompareAcrossCommands.line_number == 'last':
            self.line_number = -1  # set to dummy value (and not to numeric infinity) for sanity check in 1.3
        else:
            self.line_number = int(CompareAcrossCommands.line_number)  # take actual line number

    def perform(self, runs):
        """
        General workflow:

        1. iterate over all runs
        1.1   check existence of the data file
        1.2   read data file
        1.3   check number of lines in data file
        1.4  check number of columns in data file
        1.5   get header information of considered column
        1.6   extract value in considered column
        2. compare results of runs among each other
        2.1   check index of reference command (1-based indexing, in accordance with directory name pattern 'cmd_0001, cmd_0002, ...'), index 0 means average of all commands
        2.2   compute reference value based extracted results
        2.3   calculate deviation of each extracted value from average and compare with tolerance
        """
        # 1.  iterate over all runs
        x_run = []  # list collecting extracted result of each run
        for run in runs:
            # 1.1   check existence of the data file
            path = os.path.join(run.target_directory, self.file)
            if not os.path.exists(path):
                s = tools.red("Analyze_compare_across_commands: cannot find compare file=[%s] " % (self.file))
                print(s)
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
                return

            # 1.2   read data file
            with open(path, 'r') as csvfile:
                line_str = csv.reader(csvfile, delimiter=self.delimiter, quotechar='!')
                i = 0
                header = 0
                for row in line_str:
                    try:  # try reading a line from the data file and converting it into a numpy array
                        line = np.array([float(x) for x in row])
                        failed = False
                    except Exception:  # count as header line
                        header += 1
                        header_line = row
                        failed = True
                    i += 1
                    if i == self.line_number:  # if line number set to 'last', this condition is never met and last stored line is taken
                        print(tools.yellow(str(i)), end=' ')  # skip line break
                        break

            if failed:  # only header lines (or non-convertable data) found
                s = "Analyze_compare_across_commands: reading of the data file [%s] has failed.\nNo float type data could be read. Check the file content." % path
                print(tools.red(s))
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
                return

            # 1.3   check number of lines in data file
            selected_line = i
            if selected_line < self.line_number:
                s = ("cannot perform analyze Analyze_compare_across_commands, because the supplied line number [%s] in [%s] exceeds the number of " "lines [%s] in the data file (the first line has number 1)") % (
                    self.line_number,
                    path,
                    selected_line,
                )
                print(tools.red(s))
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
                return

            # 1.4  check number of columns in data file
            line_len = len(line) - 1
            if line_len < self.column_index:
                s = ("cannot perform analyze Analyze_compare_across_commands, because the supplied column [%s] in [%s] exceeds the number of columns " "[%s] in the data file (the first column must start at 0)") % (
                    self.column_index,
                    path,
                    line_len,
                )
                print(tools.red(s))
                run.analyze_results.append(s)
                run.analyze_successful = False
                Analyze.total_errors += 1
                return

            # 1.5   get header information of considered column
            if header > 0:
                for i in range(line_len + 1):
                    header_line[i] = header_line[i].replace(" ", "")
                    # print header_line[i]

            # 1.6   extract value in considered column
            x_run.append(line[self.column_index])

        # 2. compare results of runs among eachother
        # 2.1   check index of reference command (1-based indexing, in accordance with directory name pattern 'cmd_0001, cmd_0002, ...'), index 0 means average of all commands
        if (self.reference > len(runs)) or (self.reference < 0):
            s = (
                "cannot perform analyze Analyze_compare_across_commands, because index of reference command [%s] exceeds number of executed commands " "[%s] (indexing starts at 1, use 0 for average of all commands)"
            ) % (self.reference, len(runs))
            print(tools.red(s))
            run.analyze_results.append(s)
            run.analyze_successful = False
            Analyze.total_errors += 1
            return

        # 2.2   compute reference value based extracted results and replicate to form reference array
        if self.reference == 0:  # take average of extracted results as reference value
            reference_value = np.mean(x_run)
        else:  # take result of specific command as reference, e.g. to evaluate parallel efficiency take first command 'MPI=1'
            reference_value = x_run[self.reference - 1]
        x_ref = np.full(len(x_run), reference_value)

        # 2.3   calculate deviation of each extracted value from average and compare with tolerance
        success = tools.diff_lists(x_run, x_ref, self.tolerance_value, self.tolerance_type)
        NbrOfDifferences = success.count(False)

        if NbrOfDifferences > 0:
            s = tools.red("Analyze_compare_across_commands() failed: Found %s difference(s)." % NbrOfDifferences)
            s = s + tools.red("Mismatch in line %s of column %s" % (selected_line, header_line[self.column_index] if header > 0 else self.column_index))
            print(s)
            run.analyze_results.append(s)
            run.analyze_successful = False
            Analyze.total_errors += 1

    def __str__(self):
        return ("compare results of corresponding runs from different commands: file [%s] and comparison " "of value in line [%s] (first line = 1, last line = -1) and column [%s] (first column = 0)") % (
            self.file,
            self.line_number,
            self.column_index,
        )
