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
import re
import shutil
import collections
import combinations
from outputdirectory import OutputDirectory
from externalcommand import ExternalCommand
import tools
from analysis import Analyze, getAnalyzes, Clean_up_files, Analyze_compare_across_commands
import collections
import subprocess
import summary
# import h5 I/O routines
try :
    import h5py
    h5py_module_loaded = True
except ImportError :
    h5py_module_loaded = False

class Build(OutputDirectory,ExternalCommand) :

    def __init__(self, basedir, source_directory,configuration, number, name='build', binary_path=None) :
        self.basedir          = basedir
        self.source_directory = source_directory
        self.configuration    = configuration
        OutputDirectory.__init__(self, None, name, number)
        ExternalCommand.__init__(self)

        # initialize result as empty list
        self.result = tools.yellow("skipped building")

        # initialize examples as empty list
        self.examples = []

        # set path to binary/executable
        if binary_path :
            self.binary_path = binary_path
            head, tail       = os.path.split(binary_path)
            self.binary_dir  = head
            binary_name      = tail
        else :
            # get 'binary' from 'configuration' dict and remove it
            try :
                binary_name = self.configuration["binary"]
            except :
                print(tools.red("No 'binary'-option with the name of the binary specified in 'builds.ini'"))
                exit(1)
            self.configuration.pop('binary', None) # remove binary from config dict
            self.binary_dir  = os.path.abspath(os.path.join(self.target_directory))
            self.binary_path = os.path.abspath(os.path.join(self.target_directory, binary_name))

        # set cmake command
        self.cmake_cmd = ["cmake"]                        # start composing cmake command
        self.cmake_cmd_color = ["cmake"]                  # start composing cmake command with colors
        for (key, value) in self.configuration.items() :  # add configuration to the cmake command
            self.cmake_cmd.append("-D%s=%s" % (key, value))
            self.cmake_cmd_color.append(tools.blue("-D")+"%s=%s" % (key, value))
        self.cmake_cmd.append(self.basedir)               # add basedir to the cmake command
        self.cmake_cmd_color.append(self.basedir)               # add basedir to the cmake command

    def compile(self, buildprocs) :
        # don't compile if build directory already exists
        if self.binary_exists() :  # if the binary exists, return
            print("skipping")
            return
        else : # for build carryon: when a binary is missing remove all examples (re-run all examples)
            print("removing folder, ", end=' ') # skip linebreak
            shutil.rmtree(self.target_directory,ignore_errors=True)
            os.makedirs(self.target_directory)
            tools.create_folder(self.target_directory)
        print("building")

        # CMAKE: execute cmd in build directory
        s_Color   = "C-making with [%s] ..." % (" ".join(self.cmake_cmd_color))
        s_NoColor = "C-making with [%s] ..." % (" ".join(self.cmake_cmd))

        if self.execute_cmd(self.cmake_cmd, self.target_directory, string_info = s_Color) != 0 : # use uncolored string for cmake
            raise BuildFailedException(self) # "CMAKE failed"

        # MAKE: default with '-j'
        if not os.path.exists(os.path.join(self.target_directory,"build.ninja")) :
            self.make_cmd = ["make", "-j"]
            if buildprocs > 0 : self.make_cmd.append(str(buildprocs))
        else :
            self.make_cmd = ["ninja"]
            if buildprocs == 0 :
                self.make_cmd.append("-j0")
            elif buildprocs > 0 :
                self.make_cmd.append("-j"+str(buildprocs))
        # execute cmd in build directory
        s_NoColor="Building with [%s] ..." % (" ".join(self.make_cmd))

        if self.execute_cmd(self.make_cmd, self.target_directory, string_info = s_NoColor) != 0 :
            raise BuildFailedException(self) # "MAKE failed"
        print('-'*132)

    def __str__(self) :
        s = "BUILD in: " + self.target_directory
        return s

    def binary_exists(self) :
        return os.path.exists(self.binary_path)

class Standalone(Build) :
    def __init__(self,binary_path,source_directory) :
        Build.__init__(self, None, source_directory, {}, -1, "standalone", os.path.abspath(binary_path))

    def compile(self, buildprocs) :
        pass

    def __str__(self) :
        s = "standalone :       binary_path= " + self.binary_path + "\n"
        s+= "              target_directory= " + self.target_directory
        return s

def StandaloneAutomaticMPIDetection(binary_path) :
    '''Try and find CMake option specifying if the executable was built with MPI=ON or without any MPI libs'''
    # Default (per definition)
    MPIifOFF = False
    userblockChecked = False

    # 1st Test
    # Use try/except here, but don't terminate the program when try fails
    try:
        # Check if userblock exists and read it, otherwise don't do anything and continue
        userblock = os.path.join(os.path.dirname(os.path.abspath(binary_path)),'userblock.txt')
        #print("Checking userblock under %s " % userblock)
        if os.path.exists(userblock):
            checkCMAKELine = False
            checklibstaticLine = False
            with open(userblock) as f :
                for line in f.readlines() :   # iterate over all lines of the file
                    line = line.rstrip('\n')

                    # Only check lines within the "{[( CMAKE )]}" block
                    if checkCMAKELine:
                        Parentheses = re.search(r'\((.+)\)', line)
                        if Parentheses:
                            text = Parentheses.group(0) # get text
                            text = text[1:-1]           # remove opening and closing parentheses
                            text = re.sub(r'".*"', '', text) # remove double quotes and their content
                            parameters = text.split()
                            MPI_built_flags = [os.path.basename(binary_path).upper()+"_MPI", 'LIBS_USE_MPI']
                            if any(parameters[0] == flag for flag in MPI_built_flags):
                                value=parameters[len(parameters)-1]
                                if value.lower() == 'off':
                                    MPIifOFF = True
                                    userblockChecked = True
                                    print(tools.yellow("Automatically determined that the executable was compiled with MPI=OFF\n  File: %s\n  Line: %s" % (userblock,line)))
                                    break
                                elif value.lower() == 'on':
                                    MPIifOFF = False
                                    userblockChecked = True
                                    print(tools.yellow("Automatically determined that the executable was compiled with MPI=ON\n  File: %s\n  Line: %s" % (userblock,line)))
                                    break

                    # Only check lines within the "{[( libpiclasstatic.dir/flags.make )]}" block
                    if checklibstaticLine:
                        if "-DUSE_MPI=0" in line:
                            MPIifOFF = True
                            userblockChecked = True
                            print(tools.yellow("Automatically determined that the executable was compiled with MPI=OFF (-DUSE_MPI=0)\n  File: %s\n  Line: %s" % (userblock,line)))
                            break
                        elif "-DUSE_MPI=1" in line:
                            MPIifOFF = False
                            userblockChecked = True
                            print(tools.yellow("Automatically determined that the executable was compiled with MPI=ON (-DUSE_MPI=1)\n  File: %s\n  Line: %s" % (userblock,line)))
                            break

                    # Check which block is being passed and extract the "CMAKE" block, other blocks will be ignores
                    # Find { } strings
                    Braces = re.search(r'\{(.+)\}', line)
                    if Braces:
                        # mytext = line
                        mytext = Braces.group(0)
                        # Find [ ] strings
                        SquareBrackets = re.search(r'\[(.+)\]', mytext)
                        # Check string within [ ]
                        if SquareBrackets:
                            # Get string
                            mytext = SquareBrackets.group(0)
                            # Find ( ) strings
                            Parentheses = re.search(r'\((.+)\)', mytext)
                            # Check string within ( )
                            if Parentheses:
                                # Get string
                                parameter = Parentheses.group(0) # get text
                                # Remove opening and closing parentheses
                                parameter = parameter[1:-1]
                                # Remove leading and trailing white spaces
                                parameter = parameter.strip()
                                # Get lower case string and set logical if, finally, the line {[( CMAKE )]} is found
                                if parameter.lower() == 'cmake':
                                    checkCMAKELine = True
                                else:
                                    checkCMAKELine = False
                                # Get lower case string and set logical if, finally, the line {[( libpiclasstatic.dir/flags.make )]} is found
                                parameter = parameter.lower()
                                if parameter.startswith('lib') and parameter.endswith('static.dir/flags.make'):
                                    checklibstaticLine = True
                                else:
                                    checklibstaticLine = False

    except Exception as e:
        print(tools.red("Error checking userblock in StandaloneAutomaticMPIDetection() in check.py:\nError message [%s]\nThis program, however, will not be terminated!" % e))

    # 2nd Test
    # If the userblock test did not result in MPIifOFF=True, check the shared object dependencies of the executable and search for MPI related libs
    if not MPIifOFF and not userblockChecked:
        # Use try/except here, but don't terminate the program when try fails
        try :
            cmd=['ldd',binary_path,'|','grep','-i','"libmpi\.\|\<libmpi_"']
            a=' '.join(cmd)
            pipe = subprocess.Popen(a, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            (std, err) = pipe.communicate()

            if not isinstance(std, str):
                # convert byte std to string
                std = std.decode("utf-8", 'ignore')

            if not isinstance(err, str):
                # convert byte err to string
                err = err.decode("utf-8", 'ignore')

            # Check if the grep result is not empty
            if std or 'not a dynamic executable' in err:
                MPIifOFF = False
                if 'not a dynamic executable' in err:
                    err = err.rstrip('\n')
                    err = err.lstrip()
                    print(tools.yellow("Automatically determined that the executable was compiled with MPI libs (because file is not a dynamic executable)\n  File: %s\n  Test: %s -> returned '%s'" % (binary_path,a,err)))
                else:
                    print(tools.yellow("Automatically determined that the executable was compiled with MPI libs\n  File: %s\n  Test: %s -> returned '%s'" % (binary_path,a,std)))
            else:
                MPIifOFF = True
                print(tools.yellow("Automatically determined that the executable was compiled without MPI libs\n  File: %s\n  Test: %s -> returned '%s'" % (binary_path,a,err)))

        except Exception as e: # this fails, if the supplied command line is corrupted
            print(tools.red("Error using ldd in StandaloneAutomaticMPIDetection() in check.py:\nError message [%s]\nThis program, however, will not be terminated!" % e))

    return MPIifOFF

def getBuilds(basedir, source_directory, CMAKE_BUILD_TYPE, singledir) :
    builds = []
    i = 1
    combis, digits = combinations.getCombinations(os.path.join(source_directory, 'builds.ini'),OverrideOptionKey='CMAKE_BUILD_TYPE',OverrideOptionValue=CMAKE_BUILD_TYPE)

    # create Builds
    if singledir :
        for b in combis :
            builds.append(Build(basedir, source_directory,b,0))
    else :
        for b in combis :
            builds.append(Build(basedir, source_directory,b, i))
            i += 1
    return builds

class BuildFailedException(Exception) :
    def __init__(self, build):
        self.build = build
    def __str__(self):
        return "build.compile failed in directory '%s'." % (self.build.target_directory)

#==================================================================================================

class Example(OutputDirectory) :
    def __init__(self, source_directory, build) :
        self.source_directory = source_directory
        OutputDirectory.__init__(self, build, os.path.join("examples",os.path.basename(self.source_directory)))

    def __str__(self) :
        s = tools.yellow("EXAMPLE in: " + self.source_directory)
        return tools.indent(s,1)

def getExamples(path, build, log) :
    # checks directory with 'builds.ini'
    if os.path.exists(os.path.join(build.source_directory, 'builds.ini')) :
        example_paths = [os.path.join(path,p) for p in sorted(os.listdir(path)) \
                                              if os.path.isdir(os.path.join(path,p))]
    else :
        example_paths = [path]

    examples = [] # list of examples for each build
    # iterate over all example paths (directories of the examples)
    for p in example_paths :
        log.info('-'*132)
        log.info(tools.blue("example "+str(p)))
        # check if example should be excluded for the build.configuration
        exclude_path = os.path.join(p, 'excludeBuild.ini')
        if os.path.exists(exclude_path) :
            log.info(tools.blue("excludes under "+str(exclude_path)))
            # get all keys+values in 'excludeBuild.ini'
            options, _, _ = combinations.readKeyValueFile(exclude_path)
            # list of all excludes for comparison with 'build.configuration'
            excludes = [ { option.name : value } for option in options for value in option.values ]
            if combinations.anyIsSubset(excludes, build.configuration) :
                log.info(tools.red("  skipping example"))
                continue # any of the excludes matches the build.configuration.
                         # Skip this example for the build.configuration
            else :
                log.info(tools.yellow("  not skipping"))
        examples.append(Example(p, build))
    return  examples


#==================================================================================================
class Command_Lines(OutputDirectory) :
    def __init__(self, parameters, example, number) :
        self.parameters = parameters
        OutputDirectory.__init__(self, example, 'cmd', number)

    def __str__(self) :
        s = "command_line parameters:\n"
        s += ",".join(["%s: %s" % (k,v) for k,v in self.parameters.items()])
        return tools.indent(s,2)

def getCommand_Lines(args, path, example) :
    command_lines = []
    i = 1

    # If single execution is to be performed, remove "MPI =! 1" from command line list
    if args.noMPI or args.noMPIautomatic :
        combis, digits = combinations.getCombinations(path,OverrideOptionKey='MPI', OverrideOptionValue='1')
    else :
        combis, digits = combinations.getCombinations(path)

    for r in combis :
        command_lines.append(Command_Lines(r, example, i))
        i += 1

    return command_lines

#==================================================================================================
def SetMPIrun(build, args, MPIthreads) :
    ''' check MPI built binary (only possible for reggie-compiled binaries) '''

    # Check for variable MPI_built_flag=PICLAS_MPI (or FLEXI_MPI, depending on the executable name)
    MPI_built_flag=os.path.basename(build.binary_path).upper()+"_MPI"
    MPIbuilt = build.configuration.get(MPI_built_flag,'ON')

    # If not explicitly set to OFF, check again for 2nd variable 'LIBS_USE_MPI'
    if MPIbuilt == "ON" :
        try:
            MPIbuilt       = build.configuration.get('LIBS_USE_MPI','NOT FOUND')
            if MPIbuilt == "NOT FOUND":
                MPIbuilt = "ON" # fall back and assume MPI=ON (this fill break if the executable is actually built MPI=OFF)
            else:
                MPI_built_flag = 'LIBS_USE_MPI'
        except Exception as e:
            pass

    build.MPIbuilt = MPIbuilt

    if MPIthreads :
        # Check if single execution is wanted (independent of the compiled executable)
        if args.noMPI :
            print(tools.indent(tools.yellow("noMPI=%s, running case in single (without 'mpirun -np')" % (args.noMPI)),2))
            cmd = []
        elif args.noMPIautomatic :
            print(tools.indent(tools.yellow("noMPIautomatic=%s, running case in single (without 'mpirun -np')" % (args.noMPIautomatic)),2))
            cmd = []
        else :
            # Check whether the compiled executable was created with MPI=ON
            if MPIbuilt == "ON" :
                if args.hlrs :
                    if int(MPIthreads) < 24 :
                        cmd = ["aprun","-n",MPIthreads,"-N",MPIthreads]
                    else :
                        cmd = ["aprun","-n",MPIthreads,"-N","24"]
                else :
                    cmd = [args.MPIexe,"-np",MPIthreads,"--oversubscribe"]
            else :
                print(tools.indent(tools.yellow("Found %s=%s (binary has been built with MPI=OFF) with external setting MPIthreads=%s, running case in single (without 'mpirun -np')" % (MPI_built_flag,MPIbuilt,MPIthreads)),3))
                build.MPIrunDeactivated = True
                cmd = []
    else :
        cmd = []

    return cmd

#==================================================================================================
def copyRestartFile(path,path_target) :
    '''  Copy new restart file into example folder'''
    # Check whether the file for copying exists
    if not os.path.exists(path) :
        s = tools.red("copyRestartFile: Could not find file=[%s] for copying" % path)
        print(s)
        exit(1)

    # Check whether the destination for copying the file exists
    if not os.path.exists(os.path.dirname(path_target)) :
        s = tools.red("copyRestartFile: Could not find location=[%s] for copying" % os.path.dirname(path_target))
        print(s)
        exit(1)

    # Copy file and create new reference
    shutil.copy(path,path_target)
    s = tools.yellow("New restart file is copied from file=[%s] to file=[%s]" % (path, path_target))
    print(s)

#==================================================================================================
class Externals(OutputDirectory) :

    def __init__(self, parameters, example, number) :
        self.parameters = parameters
        OutputDirectory.__init__(self, example, '', -1)

    def __str__(self) :
        s = "external parameters:\n"
        s += ",".join(["%s: %s" % (k,v) for k,v in self.parameters.items()])
        return tools.indent(s,2)

def getExternals(path, example, build) :
    externals_pre    = []
    externals_post   = []
    externals_errors = []

    if not os.path.exists(path) :
        return externals_pre, externals_post, externals_errors
    combis, digits = combinations.getCombinations(path)

    for iCombi, combi in enumerate(combis) :

        # Check directory
        externaldirectory = combi.get('externaldirectory',None)
        if not externaldirectory or not os.path.exists(os.path.join(example.source_directory, externaldirectory)) : # string is or empty and path does not exist
            if not externaldirectory.endswith('.ini'):
                s = tools.red('getExternals: "externaldirectory" is empty or the path [%s] does not exist' % os.path.join(example.source_directory,externaldirectory))
                externals_errors.append(s)
                print(s)
                ExternalRun.total_errors+=1 # add error if externalrun fails
                continue

        # Check binary
        binary_found = False # default
        s = '' # default
        externalbinary = combi.get('externalbinary',None)
        if not externalbinary:
            s = tools.red('getExternals: External tools binary path "externalbinary" has not been supplied for external run number %s with "externaldirectory"=[%s].' % (iCombi,externaldirectory))
            externals_errors.append(s)
            print(s)
            ExternalRun.total_errors+=1 # add error if externalrun fails
            continue
        else:
            # Get binary name
            binary = os.path.basename(externalbinary).lower()

            # First: Check for the binary under ./bin directory (ignore the original full path)
            if isinstance(build, Standalone):
                # Pre-compiled mode: Use only the binary name
                binary_path = os.path.abspath(os.path.join(build.binary_dir, binary))
            else:
                # Build mode: Use the complete binary path
                binary_path = os.path.abspath(os.path.join(build.binary_dir, externalbinary))

            # Second: If the binary path does not exist
            # 1.) Check the original binary path, e.g., ./hopr/build/bin/hopr
            # 2.) for specific binaries, e.g., hopr: check the environment variable: HOPR_PATH
            if os.path.exists(binary_path):
                binary_found = True
            else:
                # If the binary is not within the ./bin/ directory, check if the path points to a binary directly
                binary_path = os.path.abspath(externalbinary)
                if os.path.exists(binary_path):
                    binary_found = True
                elif binary == 'hopr':
                    # Try and load hopr binary path form environment variables
                    hopr_path = os.getenv('HOPR_PATH')
                    if hopr_path and os.path.exists(hopr_path):
                        binary_path  = hopr_path
                        binary_found = True
                        combi['externalbinary'] = binary # over-write user-defined path
                    else:
                        s = 'Tried loading hopr binary path from environment variable $HOPR_PATH=[%s] as the supplied path does not exist.\nAdd the binary path via \"export HOPR_PATH=/opt/hopr/1.X/bin/hopr\"\n' % hopr_path

                # Display error if no binary is found
                if not binary_found:
                    s = tools.red('getExternals: %sThe supplied path [%s] via "externalbinary" does not exist.' % (s,binary_path))
                    externals_errors.append(s)
                    print(s)
                    ExternalRun.total_errors+=1 # add error if externalrun fails
                    continue

        # If the binary has been found, assign pre/post flag
        if binary_found:
            combi['binary_path'] = binary_path
            if combi.get('externalruntime','') == 'pre':
                externals_pre.append(Externals(combi, example, -1))
            elif combi.get('externalruntime','') == 'post':
                externals_post.append(Externals(combi, example, -1))
            else:
                s = tools.red('External tools is neither "pre" nor "post".')
                externals_errors.append(s)
                print(s)
                ExternalRun.total_errors+=1 # add error if externalrun fails
                continue

    return externals_pre, externals_post, externals_errors


#==================================================================================================
class ExternalRun(OutputDirectory,ExternalCommand) :
    total_errors = 0
    total_number_of_runs = 0

    def __init__(self, parameters, parameterfilepath, external, number, digits, externalruns = True) :
        self.successful         = True
        self.globalnumber       = -1
        self.analyze_results    = []
        self.analyze_successful = True
        self.parameters         = parameters
        self.digits             = digits
        self.source_directory   = os.path.dirname(parameterfilepath)

        OutputDirectory.__init__(self, external, '', -1, mkdir=False)
        ExternalCommand.__init__(self)

        # external folders already there
        self.skip = False

    def execute(self, build, external, args) :

        # set path to parameter file (single combination of values for execution "parameter.ini" for example)
        self.parameter_path = os.path.join(external.directory, external.parameterfile)

        # create parameter file with one set of combinations
        combinations.writeCombinationsToFile(self.parameters, self.parameter_path)

        # check MPI threads for mpirun
        MPIthreads = external.parameters.get('MPI')

        # check MPI built binary (only possible for reggie-compiled binaries)
        cmd = SetMPIrun(build, args, MPIthreads)

        # Get binary path
        binary_path = external.parameters.get('binary_path')

        cmd.append(binary_path)
        cmd.append(external.parameterfile)
        # append suffix commands, e.g., a second parameter file 'DSMC.ini' or '-N 12'
        cmd_suffix = external.parameters.get('cmd_suffix')
        if cmd_suffix :
            cmd.append(cmd_suffix)

        # Command for executing beforehand
        cmd_pre_execute = external.parameters.get('cmd_pre_execute')
        if cmd_pre_execute:
            cmd_pre = cmd_pre_execute.split()
            s="Running [%s] ..." % (" ".join(cmd_pre))
            self.execute_cmd(cmd_pre, external.directory, string_info = tools.indent(s, 2)) # run something

        if self.return_code != 0 :
            self.successful = False
            return

        # check if the command 'cmd' can be executed
        if self.return_code != 0 :
            print(tools.indent("Cannot run the code: "+s,2))
        else :
            s="Running [%s] ..." % (" ".join(cmd))
            self.execute_cmd(cmd, external.directory, string_info = tools.indent(s, 2)) # run the code

        if self.return_code != 0 :
            self.successful = False

    def __str__(self) :
        s = "RUN parameters:\n"
        s += ",".join(["%s: %s" % (k,v) for k,v in self.parameters.items()])
        return tools.indent(s,3)

def getExternalRuns(parameterfilepath, external) :
    """Get all combinations in 'parameter.ini'"""
    externalruns = []
    i = 1
    # get combis : for each externalrun a combination of parameters is stored in a dict containing a [key]-[value] pairs
    #              combis contains multiple dicts 'OrderedDict'
    #              example for a key = 'N' and its value = '5' for polynomial degree of 5
    #     digits : contains the number of variations for each [key]
    #              example in parameter.ini: N = 1,2,3 then digits would contain OrderedDict([('N', 2),...) for 0,1,2 = 3 different
    #              values for N)
    combis, digits = combinations.getCombinations(parameterfilepath,CheckForMultipleKeys=True)  #  parameterfilepath = path to parameter.ini (source)
    for parameters in combis :

        # check each [key] for empty [value] (e.g. wrong definition in parameter.ini file)
        for key, value in parameters.items():
            if not value :
                raise Exception(tools.red('parameter.ini contains an empty parameter definition for [%s]. Remove unnecessary commas!' % key))

        # construct run information with one set of parameters (parameter.ini will be created in target directory when the setup
        # is executed), one set of command line options (e.g. mpirun information) and the info of how many times a parameter is
        # varied under the variable 'digits'
        run = ExternalRun(parameters, parameterfilepath, external, i, digits)

        # check if the run cannot be performed due to problems encountered when setting up the folder (e.g. not all files could
        # be create or copied to the target directory)
        if not run.skip :
            externalruns.append(run) # add/append the run to the list of externalruns
        i += 1
    return externalruns


#==================================================================================================
class Run(OutputDirectory, ExternalCommand) :
    total_errors = 0
    total_number_of_runs = 0

    def __init__(self, parameters, path, command_line, number, digits) :
        self.successful         = True
        self.globalnumber       = -1
        self.analyze_results    = []
        self.analyze_successful = True
        self.parameters         = parameters
        self.digits             = digits
        self.source_directory   = os.path.dirname(path)

        OutputDirectory.__init__(self, command_line, 'run', number, mkdir=False)
        ExternalCommand.__init__(self)

        self.skip = os.path.exists(self.target_directory)
        if self.skip :
            return

        tools.create_folder(self.target_directory)

        # copy all files in the source directory (example) to the target directory: always overwrite
        for f in os.listdir(self.source_directory) :
          src = os.path.abspath(os.path.join(self.source_directory,f))
          dst = os.path.abspath(os.path.join(self.target_directory,f))
          if os.path.isdir(src) : # check if file or directory needs to be copied
              if not os.path.basename(src) == 'output_dir' : # do not copy the output_dir recursively into itself! (infinite loop)
                  shutil.copytree(src, dst) # copy tree
          else :
              # Check for symbolic links
              if os.path.islink(src):
                  # Do not copy broken symbolic links
                  if os.path.exists(src):
                      shutil.copyfile(src, dst) # copy symbolic link
              else:
                  shutil.copyfile(src, dst) # copy file
    def rename_failed(self) :
        """Rename failed run directories in order to repeat the run when the regression check is repeated.
        This routine is called if either the execution fails or an analysis."""
        shutil.rmtree(self.target_directory+"_failed",ignore_errors=True)  # remove if exists
        shutil.move(self.target_directory,self.target_directory+"_failed") # rename folder (non-existent folder fails)
        self.target_directory = self.target_directory+"_failed" # set new name for summary of errors

    def execute(self, build, command_line, args, external_failed) :
        Run.total_number_of_runs += 1
        self.globalnumber = Run.total_number_of_runs

        # Check if a possible pre-processing step has failed.
        # If so, do not run the code as the assumption is that it depends on a positive output of the (pre) external
        if external_failed:
            self.successful = False
            self.rename_failed()
            s=tools.red(tools.indent("Cannot run the code because the (pre) external run failed.",2))
            print(s)
            return

        # set path to parameter file (single combination of values for execution "parameter.ini" for example)
        self.parameter_path = os.path.join(self.target_directory, "parameter.ini")

        # create parameter file with one set of combinations
        combinations.writeCombinationsToFile(self.parameters, self.parameter_path)

        # Get MPI threads for mpirun
        MPIthreads = command_line.parameters.get('MPI')

        # Safety check: Get the mesh file, then extract the number of elements using h5py, limit the number of mpithreads
        if h5py_module_loaded:
            try:
                # Get the mesh file
                MeshFileName = combinations.readValueFromFile(self.parameter_path,'MeshFile')

                # Extract the number of elements using h5py
                with h5py.File(os.path.join(self.target_directory,MeshFileName), 'r') as MeshFile:
                    nElems = MeshFile.attrs[u'nElems']

                    # Limit the number of mpithreads
                    if MPIthreads:
                        if int(MPIthreads) > int(nElems[0]) :
                            s = tools.yellow("Automatically reducing number of MPI threads from %s to %s (number of elements in mesh)!" % (int(MPIthreads),int(nElems[0])))
                            print(s)
                        MPIthreads = str(min(int(nElems[0]),int(MPIthreads)))
            except Exception as ex :
                pass


        # check MPI built binary (only possible for reggie-compiled binaries)
        cmd = SetMPIrun(build, args, MPIthreads)

        cmd.append(build.binary_path)
        cmd.append("parameter.ini")

        # append suffix commands, e.g., a second parameter file 'DSMC.ini' or '-N 12'
        cmd_suffix = command_line.parameters.get('cmd_suffix')
        if cmd_suffix :
            cmd.append(cmd_suffix)

        # append restart file name
        cmd_restart_file = command_line.parameters.get('restart_file')
        if cmd_restart_file :
            # check if file exists
            cmd_restart_file_abspath = os.path.abspath(os.path.join(self.target_directory,cmd_restart_file))
            found = os.path.exists(cmd_restart_file_abspath)

            # Check if restartcopy is activated (if true start the simulation at t=0 and copy (create/replace if already exists) to example directory
            if args.restartcopy :
                s=tools.yellow("Restart file copy activated. Starting fresh simulation at t=0.")
                print(tools.indent(s,2))
            else : # default
                if not found :
                    self.return_code = -1
                    self.result=tools.red("Restart file not found")
                    s=tools.red("Restart file [%s] not found under [%s]" % (cmd_restart_file,cmd_restart_file_abspath))
                else :
                    cmd.append(cmd_restart_file)

        # check if the command 'cmd' can be executed
        if self.return_code != 0 :
            s=tools.red(tools.indent("Cannot run the code: "+s,2))
            print(s)
        else :
            s="Running [%s] ..." % (" ".join(cmd))
            self.execute_cmd(cmd, self.target_directory, string_info = tools.indent(s, 2)) # run the code

        # Copy restart file if required
        if cmd_restart_file and args.restartcopy:
            # 1. Get directory path and filename of the originally required restart file
            head, tail = os.path.split(cmd_restart_file_abspath)

            # 2. File path to be copied
            restart_file_path=os.path.abspath(os.path.join(self.target_directory,tail))

            # Check whether the newly created restart file actually has a different name than the one supplied in cmd_restart_file,
            # e.g., [Test_State_000.000000.h5] instead of [Test_State_000.000000_restart.h5] the first will be the source and the
            # latter will be the target file name
            try:
                file_name = os.path.join(self.target_directory,'std.out')
                with open(file_name) as f:
                    for line in f.readlines() : # iterate over all lines of the file
                        if 'WRITE STATE TO HDF5 FILE' in line:
                           s=line.rstrip()
                           FileName=re.search(r'\[(.*?)\]',s).group(1) # search for string within parenthesis [...] and check if that is a file that exists
                           replace_restart_file_path = os.path.join(self.target_directory,FileName)
                           print("replace_restart_file_path = %s" % (replace_restart_file_path))
                           print("os.path.isfile(replace_restart_file_path) = %s" % (os.path.isfile(replace_restart_file_path)))
                           if replace_restart_file_path and os.path.isfile(replace_restart_file_path):
                               print(tools.yellow("Found replacement for restart file copy: [%s] instead of [%s]" % (FileName,cmd_restart_file)))
                               restart_file_path = replace_restart_file_path
                               cmd_restart_file  = FileName
                           break
            except Exception as e:
                print(tools.red("Tried getting the first State file name from std.out. Failed. Using original restart file for copying: [%s]" % cmd_restart_file))
                print(tools.red("e = %s" % (e)))
                pass

            # 3. Target file path
            restart_file_path_target=os.path.join(self.source_directory,tail)

            # 4. Check if the file for copying exists
            found = os.path.exists(restart_file_path)
            if not found :
                # Restart file not found (or not created)
                self.return_code = -1
                self.result=tools.red("Restart file [%s] was not created" % cmd_restart_file)
                s=tools.red("Restart file (which should have been created) [%s] not found under [%s]" % (cmd_restart_file,restart_file_path))
                print(s)
            else :
                # Copy new restart file
                copyRestartFile(restart_file_path,restart_file_path_target)
                s=tools.yellow("Run(OutputDirectory, ExternalCommand): performed restart file copy!")
                print(s)

        if self.return_code != 0 :
            self.successful = False
            self.rename_failed()


    def __str__(self) :
        s = "RUN parameters:\n"
        s += ",".join(["%s: %s" % (k,v) for k,v in self.parameters.items()])
        return tools.indent(s,3)

def getRuns(path, command_line) :
    """Get all combinations in 'parameter.ini'"""
    runs = []
    i = 1
    # get combis : for each run a combination of parameters is stored in a dict containing a [key]-[value] pairs
    #              combis contains multiple dicts 'OrderedDict'
    #              example for a key = 'N' and its value = '5' for polynomial degree of 5
    #     digits : contains the number of variations for each [key]
    #              example in parameter.ini: N = 1,2,3 then digits would contain OrderedDict([('N', 2),...) for 0,1,2 = 3 different
    #              values for N)
    combis, digits = combinations.getCombinations(path,CheckForMultipleKeys=True)  # path to parameter.ini (source)
    for parameters in combis :
        # check each [key] for empty [value] (e.g. wrong definition in parameter.ini file)
        for key, value in list(parameters.items()):
            if not value :
                raise Exception(tools.red('parameter.ini contains an empty parameter definition for [%s]. Remove unnecessary commas!' % key))
        # construct run information with one set of parameters (parameter.ini will be created in target directory when the setup
        # is executed), one set of command line options (e.g. mpirun information) and the info of how many times a parameter is
        # varied under the variable 'digits'
        run = Run(parameters, path, command_line, i, digits)
        # check if the run cannot be performed due to problems encountered when setting up the folder (e.g. not all files could
        # be create or copied to the target directory)
        if not run.skip :
            runs.append(run) # add/append the run to the list of runs
        i += 1
    return runs


def PerformCheck(start,builds,args,log) :
    """
    General workflow:
    1.   loop over alls builds
    1.1    compile the build if args.run is false and the binary is non-existent
    1.1    read all example directories in the check directory
    2.   loop over all example directories
    2.1    read the command line options in 'command_line.ini' for binary execution (e.g. number of threads for mpirun)
    2.2    read the analyze options in 'analyze.ini' within each example directory (e.g. L2 error analyze)
    3.   loop over all command_line options
    3.1    read the executable parameter file 'parameter.ini' (e.g. flexi.ini with which flexi will be started)
    4.   loop over all parameter combinations supplied in the parameter file 'parameter.ini'
    4.1    read the external options in 'externals.ini' within each example directory (e.g. eos, hopr, posti)
    (pre)  perform a preprocessing step: e.g. run hopr, eos, ...
           (1):   loop over all externals available in external.ini
           (1.1):   get the path and the parameterfiles to the i'th external
           (2):   loop over all parameterfiles available for the i'th external
           (2.1):   consider combinations
           (3):   loop over all combinations and parameter files for the i'th external
           (3.1):   run the external binary
    4.2    execute the binary file for one combination of parameters
    (post) perform a post processing step: e.g. run posti, ...
           (1):   loop over all externals available in external.ini
           (1.1):   get the path and the parameterfiles to the i'th external
           (2):   loop over all parameterfiles available for the i'th external
           (2.1):   consider combinations
           (3):   loop over all combinations and parameter files for the i'th external
           (3.1):   run the external binary
    4.3    remove unwanted files: run analysis directly after each run (as opposed to the normal analysis which is used for analyzing the created output)
    5.   loop over all successfully executed binary results and perform analyze tests
    6.   rename all run directories for which the analyze step has failed for at least one test
    7.   perform analyze tests comparing corresponding runs from different commands
    """

    build_number=0

    # compile and run loop
    try : # if compiling fails -> go to exception

        # 1.   loop over alls builds
        for build in builds :
            remove_build_when_successful = True
            build_number+=1 # count number of builds
            print("Build Cmake Configuration ",build_number," of ",len(builds)," ...", end=' ') # skip linebreak
            log.info(str(build))

            # 1.1    compile the build if args.run is false and the binary is non-existent
            build.compile(args.buildprocs)
            if not args.carryon : # remove examples folder if not carryon, in order to re-run all examples
                tools.remove_folder(os.path.join(build.target_directory,"examples"))

            # 1.1    read the example directories
            # get example folders: run_basic/example1, run_basic/example2 from check folder
            print(build)
            build.examples = getExamples(args.check, build,log)
            log.info("build.examples"+str(build.examples))

            if len(build.examples) == 0 :
                s = tools.yellow("No matching examples found for this build!")
                build.result += ", " + s
                print(s)
            # 2.   loop over all example directories
            for example in build.examples :
                log.info(str(example))
                print(str(example))

                # 2.1    read the command line options in 'command_line.ini' for binary execution
                #        (e.g. number of threads for mpirun)
                example.command_lines = \
                        getCommand_Lines(args, os.path.join(example.source_directory,'command_line.ini'), example)

                # 2.2    read the analyze options in 'analyze.ini' within each example directory (e.g. L2 error analyze)
                example.analyzes = \
                        getAnalyzes(os.path.join(example.source_directory,'analyze.ini'), example, args)

                # 3.   loop over all command_line options
                for command_line in example.command_lines :
                    log.info(str(command_line))
                    database_path = command_line.parameters.get('database',None)
                    if database_path is not None:
                        database_path = os.path.abspath(os.path.join(example.source_directory,database_path))
                        print(database_path)
                        if not os.path.exists(database_path) :
                            s=tools.red("command_line.ini: cannot find file=[%s] " % (database_path))
                            print(s)
                            exit(1)

                    # 3.1    read the executable parameter file 'parameter.ini' (e.g. flexi.ini with which
                    #        flexi will be started), N=, mesh=, etc.
                    command_line.runs = \
                            getRuns(os.path.join(example.source_directory,'parameter.ini' ), command_line)

                    # 4.   loop over all parameter combinations supplied in the parameter file 'parameter.ini'
                    for run in command_line.runs :
                        log.info(str(run))
                        if database_path is not None and os.path.exists(run.target_directory):
                            head, tail = os.path.split(database_path)
                            os.symlink(database_path, os.path.join(run.target_directory,tail))
                            print(tools.green('Preprocessing: Linked database [%s] to [%s] ... ' % (database_path, run.target_directory)))
                        # 4.1 read the external options in 'externals.ini' within each example directory (e.g. eos, hopr, posti)
                        #     distinguish between pre- and post processing
                        run.externals_pre, run.externals_post, run.externals_errors = \
                                getExternals(os.path.join(run.source_directory,'externals.ini'), run, build)

                        # (pre) externals (1): loop over all externals available in external.ini
                        external_failed = False
                        for external in run.externals_pre :
                            log.info(str(external))

                            print('-' * 132)
                            # (pre) externals (1.1): get the path and the parameterfiles to the i'th external
                            externaldirectory = external.parameters.get("externaldirectory")
                            if externaldirectory.endswith('.ini'):
                                external.directory  = run.target_directory
                                external.parameterfiles = [externaldirectory]
                            else:
                                external.directory  = run.target_directory + '/'+ externaldirectory
                                external.parameterfiles = [i for i in os.listdir(external.directory) if i.endswith('.ini')]

                            externalbinary = external.parameters.get("externalbinary")
                            print(tools.green('Preprocessing: Running pre-external [%s] in [%s] ... ' % (externalbinary, external.directory)))

                            # (pre) externals (2): loop over all parameterfiles available for the i'th external
                            for external.parameterfile in external.parameterfiles :
                                # (pre) externals (2.1): consider combinations
                                external.runs = \
                                        getExternalRuns(os.path.join(external.directory,external.parameterfile), external)

                                # (pre) externals (3): loop over all combinations and parameterfiles for the i'th external
                                for externalrun in external.runs :
                                    log.info(str(externalrun))

                                    # (pre) externals (3.1): run the external binary
                                    externalrun.execute(build,external,args)
                                    if not externalrun.successful :
                                        external_failed = True
                                        s = tools.red('Execution (pre) external failed')
                                        run.externals_errors.append(s)
                                        print("ExternalRun.total_errors = %s" % (ExternalRun.total_errors))
                                        ExternalRun.total_errors+=1 # add error if externalrun fails
                                        # Check if immediate stop is activated on failure
                                        if args.stop:
                                            s = tools.red('Stop on first error (-p, --stop) is activated! Execution (pre) external failed')
                                            print(s)
                                            exit(1)

                            print(tools.green('Preprocessing: External [%s] finished!' % externalbinary))
                            print('-' * 132)

                        # 4.2    execute the binary file for one combination of parameters
                        run.execute(build,command_line,args,external_failed)
                        if not run.successful :
                            Run.total_errors+=1 # add error if run fails
                            # Check if immediate stop is activated on failure
                            if args.stop:
                                s = tools.red('Stop on first error (-p, --stop) is activated! Execution of run failed')
                                print(s)
                                exit(1)

                        # (post) externals (1): loop over all externals available in external.ini
                        for external in run.externals_post :

                            log.info(str(external))

                            print('-' * 132)
                            # (post) externals (1.1): get the path and the parameterfiles to the i'th external
                            external.directory  = run.target_directory + '/'+ external.parameters.get("externaldirectory")
                            external.parameterfiles = [i for i in os.listdir(external.directory) if i.endswith('.ini')]

                            externalbinary = external.parameters.get("externalbinary")
                            print(tools.green('Postprocessing: Running post-external [%s] in [%s] ... ' % (externalbinary, external.directory)))

                            # (post) externals (2): loop over all parameterfiles available for the i'th external
                            for external.parameterfile in external.parameterfiles :

                                # (post) externals (2.1): consider combinations
                                external.runs = \
                                        getExternalRuns(os.path.join(external.directory,external.parameterfile), external)

                                # (post) externals (3): loop over all combinations and parameterfiles for the i'th external
                                for externalrun in external.runs :
                                    log.info(str(externalrun))

                                    # (post) externals (3.1): run the external binary
                                    externalrun.execute(build,external,args)
                                    if not externalrun.successful :
                                        #print(externalrun.return_code)
                                        s = tools.red('Execution (post) external failed')
                                        run.externals_errors.append(s)
                                        ExternalRun.total_errors+=1 # add error if externalrun fails
                                        # Check if immediate stop is activated on failure
                                        if args.stop:
                                            s = tools.red('Stop on first error (-p, --stop) is activated! Execution (post) external failed')
                                            print(s)
                                            exit(1)

                            print(tools.green('Postprocessing: External [%s] finished!' % externalbinary))
                            print('-' * 132)

                        # 4.3 Remove unwanted files: run analysis directly after each run (as opposed to the normal analysis which is used for analyzing the created output)
                        for analyze in example.analyzes :
                            if isinstance(analyze,Clean_up_files) :
                                analyze.execute(run)

                    # 5.   loop over all successfully executed binary results and perform analyze tests
                    runs_successful = [run for run in command_line.runs if run.successful]
                    if runs_successful : # do analysis only if runs_successful is not empty
                        for analyze in example.analyzes :
                            if isinstance(analyze,Clean_up_files) or isinstance(analyze,Analyze_compare_across_commands) :
                                # skip because either already called in the "run" loop under 4.2 or called later under cross-command comparisons in 7.
                                continue
                            print(tools.indent(tools.blue(str(analyze)),2))
                            analyze.perform(runs_successful)
                            # Check if immediate stop is activated on failure
                            if args.stop and Analyze.total_errors > 0:
                                s = tools.red('Stop on first error (-p, --stop) is activated! Analysis failed')
                                print(s)
                                exit(1)
                    else : # don't delete build folder after all examples/runs
                        remove_build_when_successful = False

                    # 6.   rename all run directories for which the analyze step has failed for at least one test
                    for run in runs_successful :         # all successful runs (failed runs are already renamed)
                        if not run.analyze_successful :  # if 1 of N analyzes fails: rename
                            run.rename_failed()

                    # Don't remove when run fails
                    if not all([run.analyze_successful for run in runs_successful]) : remove_build_when_successful = False # don't delete build folder after all examples/runs

                    # Don't remove when (pre) external fails
                    for run in runs_successful:
                        for external in run.externals_pre:
                            if not all([externalrun.successful for externalrun in external.runs]) : remove_build_when_successful = False # don't delete build folder after all examples/runs

                    # Don't remove when (post) external fails
                    for run in runs_successful:
                        for external in run.externals_post :
                            if not all([externalrun.successful for externalrun in external.runs]) : remove_build_when_successful = False # don't delete build folder after all examples/runs

                # 7.    perform analyze tests comparing corresponding runs from different commands
                for iRun in range( len( example.command_lines[0].runs ) ):  # loop over runs of first command
                    # collect corresponding runs from different commands, i.e. cmd_*/run_0001, cmd_*/run_0002, ...
                    runs_corresponding = [ command_line.runs[iRun] for command_line in example.command_lines ]
                    for analyze in example.analyzes :
                        # perform only cross-command comparisons
                        if isinstance(analyze,Analyze_compare_across_commands) :
                            print(tools.indent(tools.blue(str(analyze)),2))
                            analyze.perform(runs_corresponding)
                            # Check if immediate stop is activated on failure
                            if args.stop and Analyze.total_errors > 0:
                                s = tools.red('Stop on first error (-p, --stop) is activated! Analysis failed (cross-command comparisons)')
                                print(s)
                                exit(1)

            if remove_build_when_successful and not args.save :
                tools.remove_folder(build.target_directory)
            print('='*132)

    # catch exception if bulding fails
    except BuildFailedException as ex:
        # print table with summary of errors
        summary.SummaryOfErrors(builds, args)

        # display error message
        print(tools.red(str(ex))) # display error msg
        if hasattr(ex.build, 'cmake_cmd'):
            print(tools.indent(tools.yellow(str(" ".join(ex.build.cmake_cmd))),1))
        if hasattr(ex.build, 'make_cmd'):
            print(tools.indent(tools.yellow(str(" ".join(ex.build.make_cmd))),1))
        print(tools.indent("Build failed, see: "+str(ex.build.stdout_filename),1))
        print(tools.indent("                   "+str(ex.build.stderr_filename),1))
        print(tools.bcolors.RED)
        for line in ex.build.stderr[-20:] :
            print(tools.indent(line,4), end=' ') # skip linebreak
        print(tools.bcolors.ENDC)

        print("run 'reggie' with the command line option '-c/--carryon' to skip successful builds.")
        tools.finalize(start, 1, Run.total_errors, Analyze.total_errors, Analyze.total_infos)
        exit(1)


