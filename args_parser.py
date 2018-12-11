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
import argparse
import os
import tools
import check
from outputdirectory import OutputDirectory

def getArgsAndBuilds() :
    """get command line arguments and builds in check directory from 'builds.ini'"""
    parser = argparse.ArgumentParser(description='DESCRIPTION:\nRegression checker for NRG codes.\nSupply the path to a /regressioncheck/checks/ directory within a repository containing a CMakeLists.txt file which can automatically be build using cmake. ', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-c', '--carryon', action='store_true', help='''Continue build/run process. 
      --carryon         : build non-existing binary-combinations and run all examples for thoses builds
      --carryon --run   : run all failed examples''')
    parser.add_argument('-e', '--exe', help='Path to executable of code that should be tested.')
    parser.add_argument('-d', '--debug', type=int, default=0, help='Debug level.')
    parser.add_argument('-j', '--buildprocs', type=int, default=0, help='Number of processors used for compiling (make -j XXX).')
    parser.add_argument('-b', '--basedir', help='Path to basedir of code that should be tested (contains CMakeLists.txt).')
    parser.add_argument('-y', '--dummy', action='store_true',help='Use dummy_basedir and dummy_checks for fast testing on dummy code.')
    parser.add_argument('-r', '--run', action='store_true' ,help='Run all binaries for all examples with all run-combinations for all existing binaries.')
    parser.add_argument('-s', '--save', action='store_true',help='Do not remove output directories buildsXXXX in output_dir after successful run.')
    parser.add_argument('-t', '--compiletype', help='Override all CMAKE_BUILD_TYPE settings by ignoring the value set in builds.ini (e.g. DEBUG or RELEASE).')
    parser.add_argument('-z', '--rc', dest='referencescopy', help='Create/Replace reference files that are required for analysis. After running the program, the output files are stored in the check-/example-directory.', action='store_true')
    parser.set_defaults(referencescopy=False)
    parser.add_argument('check', help='Path to check-/example-directory.')
    
    # get reggie command line arguments
    args = parser.parse_args()
    
    # setup basedir
    if args.dummy : 
        # For testing reggie during reggie-developement: 
        # Overwrite basedir and check directory with dummy directories.
        reggieDir = os.path.dirname(os.path.realpath(__file__))
        args.basedir = os.path.join(reggieDir, 'dummy_basedir')
        args.check =   os.path.join(reggieDir, 'dummy_checks/test')
        print "Basedir directory switched to '%s'" % args.basedir
        print "Check   directory switched to '%s'" % args.check
    else :
        # For real reggie-execution:
        # Setup basedir (containing CMakeLists.txt) by searching upward from current working directory 
        if args.basedir is None : args.basedir = os.getcwd() # start with current working directory
        try :
            if args.exe is None : # only get basedir if no executbale is supplied
                args.basedir = tools.find_basedir(args.basedir)
        except Exception,ex :
            print tools.red("Basedir (containing 'CMakeLists.txt') not found!\nEither specify the basedir on the command line or execute reggie within a project with a 'CMakeLists.txt'.")
            exit(1)
    
        if not os.path.exists(args.check) : # check if directory exists
            print tools.red("Check directory not found: '%s'" % args.check)
            exit(1)
    
    
    # delete the building directory when [carryon = False] and [run = False] before getBuilds is called
    if not args.carryon and not args.run : tools.remove_folder(OutputDirectory.output_dir)
    
    # get builds from checks directory if no executable is supplied
    if args.exe is None : # if not exe is supplied, get builds
        # read build combinations from checks/XX/builds.ini
        builds = check.getBuilds(args.basedir, args.check,args.compiletype)
    else :
        if not os.path.exists(args.exe) : # check if executable exists
            print tools.red("No executable found under '%s'" % args.exe)
            exit(1)
        else :
            builds = [check.Standalone(args.exe,args.check)] # set builds list to contain only the supplied executable
            args.run = True      # set 'run-mode' do not compile the code
            args.basedir = None  # since code will not be compiled, the basedir is not needed
    
    if args.run :
        print "args.run -> skip building"
        # in 'run-mode' remove all build from list of builds if their binaries do not exist (build.binary_exists() == False)
        builds = [build for build in builds if build.binary_exists()]
    
    if len(builds) == 0 :
        print tools.red("List of 'builds' is empty! Maybe switch off '--run'.")
        exit(1)
    
    # display all command line arguments
    print "Running with the following command line options"
    for arg in args.__dict__ :
        print arg.ljust(15)," = [",getattr(args,arg),"]"
    print('='*132)
    
    
    return args, builds
