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
import argparse
import os
from sys import platform
import socket
import re
import subprocess
from reggie import tools
from reggie import check
from reggie.outputdirectory import OutputDirectory

try:
    # Python 2.7
    import commands
except Exception:
    pass


def getMaxCPUCores():
    """
    Get the total number of available physical cores, ignore hyper threading or SMT etc.

    The affinity is ignored at the moment, e.g., if the total number of processes is artificially limited,
    see https://docs.python.org/3/library/os.html#os.sched_getaffinity.
    """
    # Linux
    try:
        MaxCores = open('/proc/cpuinfo').read().count('processor\t:')

        cpuCores = None
        with open('/proc/cpuinfo') as file:
            for line in file:
                line_parts = line.rstrip()
                line_parts = line_parts.split(":")
                if 'cpu cores\t' in line_parts[0]:
                    # Convert to integer
                    cpuCores = int(line_parts[1])
                    break

        if cpuCores is not None and cpuCores > 0 and MaxCores > cpuCores:
            return cpuCores
        else:
            return 0
    except Exception:
        pass

    # Python 2.6+
    try:
        import multiprocessing

        # This yields the hyper threading or SMT cores (hence, not the physical cores), but serves as a fallback
        MaxCores = multiprocessing.cpu_count()
        print(tools.yellow('getMaxCPUCores() fallback has returned the number of hyper threading or SMT cores (hence, not the physical cores)'))
        return MaxCores
    except Exception:
        pass


def getArgsAndBuilds():
    """Get command line arguments and builds in check directory from 'builds.ini'"""
    # fmt: off
    parser = argparse.ArgumentParser(description='DESCRIPTION:\nRegression checker for NRG codes.\nSupply the path to a /regressioncheck/checks/ directory within a repository containing a CMakeLists.txt file which can automatically be build using cmake. ', formatter_class=argparse.RawTextHelpFormatter)  # noqa: E501 Line too long
    parser.add_argument('-c', '--carryon', action='store_true', help='''Continue build/run process.
      --carryon         : build non-existing binary-combinations and run all examples for thoses builds
      --carryon --run   : run all failed examples''')
    parser.add_argument('-e', '--exe'        , help='Path to executable of code that should be tested.')
    parser.add_argument('-m', '--MPIexe'     , help='Path to mpirun executable. The correct MPI lib must be used, i.e. the one which which the executable (e.g. flexi) was compiled, e.g., /opt/openmpi/2.0.2/bin/mpirun.', default='mpirun')  # noqa: E501
    parser.add_argument('-d', '--debug'      , help='Debug level.', type=int, default=0)
    parser.add_argument('-j', '--buildprocs' , help='Number of processors used for compiling (make -j XXX).', type=int, default=0)
    parser.add_argument('-b', '--basedir'    , help='Path to basedir of code that should be tested (contains CMakeLists.txt).')
    parser.add_argument('-y', '--dummy'      , help='Use dummy_basedir and dummy_checks for fast testing on dummy code.', action='store_true')
    parser.add_argument('-n', '--singledir'  , help='Use a single build directory for all combinations', action='store_true')
    parser.add_argument('-r', '--run'        , help='Run all binaries for all examples with all run-combinations for all existing binaries.', action='store_true' )
    parser.add_argument('-s', '--save'       , help='Do not remove output directories buildsXXXX in output_dir after successful run.', action='store_true')
    parser.add_argument('-t', '--compiletype', help='Override all CMAKE_BUILD_TYPE settings by ignoring the value set in builds.ini (e.g. DEBUG or RELEASE).')
    parser.add_argument('-a', '--hlrs'       , help='Run on with aprun (24-core hlrs system).', action='store_true')
    parser.add_argument('-z', '--rc'         , help='Create/Replace reference files that are required for analysis. After running the program, the output files are stored in the check-/example-directory.', action='store_true', dest='referencescopy')        # noqa: E501
    parser.add_argument('-f', '--fc'         , help='Create/Replace required restart files (if defined in command_line.ini). After running the program, the output files are stored in the check-/example-directory.', action='store_true', dest='restartcopy')  # noqa: E501
    parser.add_argument('-i', '--noMPI'      , help='Run program without "mpirun" (single thread execution).', action='store_true')
    parser.add_argument('-p', '--stop'       , help='Stop on first error.', action='store_true')
    parser.add_argument('-l', '--limitprocs' , help='Limit the number of processes to be used for the rune.', type=int, default=0)
    parser.add_argument('check', help='Path to check-/example-directory.')
    parser.add_argument('-v', '--coverage'   , help='Compile code with code coverage option, always returns output in json format. Additional values (resulting in additional output formats): 1=HTML output, 2=Cobertura XML, 3=both formats. Default=0 if flag used without value.', nargs='?', const='0', default=None) # noqa: E501
    parser.add_argument('--meshesdir'        , help='When hopr is used as external: Only run hopr once for each example and store meshes in separate directory to use symbolic links.', action='store_true')
    # fmt: on
    # parser.set_defaults(carryon=False)
    # parser.set_defaults(dummy=False)
    # parser.set_defaults(run=False)
    # parser.set_defaults(save=False)
    # parser.set_defaults(hlrs=False)
    # parser.set_defaults(referencescopy=False)
    # parser.set_defaults(restartcopy=False)
    # parser.set_defaults(noMPI=False)

    # get reggie command line arguments
    args = parser.parse_args()

    # Set default values
    args.noMPIautomatic = False

    # ENV variable for meshesdir
    meshesdir_env = os.getenv('MESHESDIR')
    if meshesdir_env:
        args.meshesdir = True

    # Check OS
    if re.search('^linux', platform):
        hostname = socket.gethostname()
        print("platform: %s, hostname: %s" % (platform, hostname))
        if re.search('^mom[0-9]+$', hostname):
            print(tools.yellow('Automatic detection of hlrs system: Assuming aprun is used and setting args.hlrs = True'))
            args.hlrs = True
        elif re.search('^eslogin[0-9]+$', hostname):
            if args.hlrs:
                raise Exception('Running with -a or --hlrs. Cannot run this program on a login node. Get interactive job and run on mom node!')

    # setup basedir
    if args.dummy:
        # For testing reggie during reggie-developement:
        # Overwrite basedir and check directory with dummy directories.
        reggieDir = os.path.dirname(os.path.realpath(__file__))
        args.basedir = os.path.join(reggieDir, 'dummy_basedir')
        args.check = os.path.join(reggieDir, 'dummy_checks/test')
        print("Basedir directory switched to '%s'" % args.basedir)
        print("Check   directory switched to '%s'" % args.check)
    else:
        # For real reggie-execution:
        # Setup basedir (containing CMakeLists.txt) by searching upward from current working directory
        if args.basedir is None:  # start with current working directory
            args.basedir = os.getcwd()
        try:
            if args.exe is None:  # only get basedir if no executable is supplied
                args.basedir = tools.find_basedir(args.basedir)
        except Exception:
            print(tools.red("Basedir (containing 'CMakeLists.txt') not found!\nEither specify the basedir on the command line or execute reggie within a project with a 'CMakeLists.txt'."))
            exit(1)

        # Check if directory exists
        if not os.path.exists(args.check):
            print(tools.red("Check directory not found: '%s'" % args.check))
            exit(1)
        else:
            # Check if file or link path was supplied
            if os.path.isfile(args.check):
                print(tools.red("Check directory supplied is a file: '%s'. Please supply a directory path" % args.check))
                exit(1)
            # Check if directory path was supplied
            elif os.path.isdir(args.check):
                pass
            # Check rest
            else:
                print(tools.red("Check directory supplied is not a directory path: '%s'. Please supply a directory path" % args.check))
                exit(1)

    # delete the building directory when [carryon = False] and [run = False] before getBuilds is called
    if not args.carryon and not args.run:
        # keep the output directory if coverage option is enabled since the data over all builds is needed
        if not args.coverage:
            tools.remove_folder(OutputDirectory.output_dir)
        else:
            # check if this is the first time the reggie is run with coverage (that means the last output directory does not contain directories for coverage reports)
            if 'combined_report' not in os.listdir(OutputDirectory.output_dir) and 'single_reports' not in os.listdir(OutputDirectory.output_dir):
                tools.remove_folder(OutputDirectory.output_dir)

    # ENV variable for code coverage
    coverage_env = os.getenv('CODE_COVERAGE')
    if coverage_env:
        args.coverage = True
        args.coverage_output_html = False
        args.coverage_output_cobertura = True
    elif args.coverage:  # check for command line argument when executed locally
        args.coverage_output_html = False
        args.coverage_output_cobertura = False
        if '1' in args.coverage:
            args.coverage_output_html = True
        if '2' in args.coverage:
            args.coverage_output_cobertura = True
        if '3' in args.coverage:
            args.coverage_output_html = True
            args.coverage_output_cobertura = True
        elif args.coverage != '0':
            print(tools.red("Invalid value for --coverage: '%s'. Use 1, 2, 3 or leave empty." % args.coverage))
            exit(1)
        args.coverage = True

    # get builds from checks directory if no executable is supplied
    if args.exe is None:  # if not exe is supplied, get builds
        # read build combinations from checks/XX/builds.ini
        builds = check.getBuilds(args.basedir, args.check, args.compiletype, args.singledir)
    else:
        if not os.path.exists(args.exe):  # check if executable exists
            print(tools.red("No executable found under '%s'" % args.exe))
            exit(1)
        else:
            builds = [check.Standalone(args.exe, args.check)]  # set builds list to contain only the supplied executable
            args.noMPIautomatic = check.StandaloneAutomaticMPIDetection(args.exe)  # Check possibly existing userblock.txt to find out if the executable was compiled with MPI=ON or MPI=OFF
            args.run = True  # set 'run-mode' do not compile the code
            args.basedir = None  # since code will not be compiled, the basedir is not required

    # Try to detect MPICH
    args.detectedMPICH = False
    try:
        if args.MPIexe == 'mpirun':
            try:
                status, result = subprocess.getstatusoutput("%s -h | grep -i mpich" % args.MPIexe)
            except Exception:
                # Fallback for python2.7
                status, result = commands.getstatusoutput("%s -h | grep -i mpich" % args.MPIexe)
            if len(result) > 0 and status == 0:
                args.detectedMPICH = True
    except Exception:
        pass

    args.MaxCores = args.limitprocs  # set the maximum number of processes to be used for the run
    # Set maximum number of processes/cores for mpich as over-subscription results in a massive performance drop
    if args.detectedMPICH:
        args.MaxCores = getMaxCPUCores()
        print(tools.yellow('WARNING: MPICH detected, which limits the total number of processes that can be used to %s as over-subscription results in a massive performance drop' % args.MaxCores))

    if args.run:
        print("args.run -> skip building")
        # in 'run-mode' remove all build from list of builds if their binaries do not exist (build.binary_exists() == False)
        builds = [build for build in builds if build.binary_exists()]

    if len(builds) == 0:
        print(tools.red("List of 'builds' is empty! Maybe switch off '--run'."))
        exit(1)

    # display all command line arguments
    print("Running with the following command line options")
    for arg in list(args.__dict__):
        print(arg.ljust(15) + " = [ " + str(getattr(args, arg)) + " ]")
    print('=' * 132)

    return args, builds
