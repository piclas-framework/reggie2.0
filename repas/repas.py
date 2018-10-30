#==================================================================================================================================
# Copyright (c) 2017 - 2018 Stephen Copplestone
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
# import general functions
import os
import fileinput
import logging
import argparse
import shutil

# import reggie source code
# use reggie2.0 functions by adding the path
import settings
settings.init() # Call only once
import sys
sys.path.append(settings.absolute_reggie_path)
reggie_exe_path = os.path.join(settings.absolute_reggie_path,'reggie.py')
if not os.path.exists(reggie_exe_path) :
    print "Reggie main file not found in reggie repository under: '%s'" % reggie_exe_path
    exit(1)

from repas_tools import finalize
import repas_tools

from combinations import getCombinations
from combinations import isKeyOf
from combinations import readKeyValueFile
from tools import red
from timeit import default_timer as timer

import tools
import args_parser

"""
General workflow:
1.  FIX THIS: ------------------ get the command line arguments 'args' with path to ".gitlab-ci.yml" file
2.  FIX THIS: ------------------ set the logger 'log' with the debug level from 'args' to determine the level of logging which displays output to the user
3.  FIX THIS: ------------------ perform the regression check by a) building executables
                                    ------------------ b) running the code
                                    ------------------ c) performing the defined analyzes
4.  FIX THIS: ------------------ display the summary table with information for each build, run and analysis step
5.  FIX THIS: ------------------ display if regression check was successful or not and return the corresponding error code
"""

print 
print tools.red('==============================================================================================================================')
print tools.red('         _____                    _____                    _____                    _____                    _____            ')
print tools.red('         /\    \                  /\    \                  /\    \                  /\    \                  /\    \          ')
print tools.red('        /::\    \                /::\    \                /::\    \                /::\    \                /::\    \         ')
print tools.red('       /::::\    \              /::::\    \              /::::\    \              /::::\    \              /::::\    \        ')
print tools.red('      /::::::\    \            /::::::\    \            /::::::\    \            /::::::\    \            /::::::\    \       ')
print tools.red('     /:::/\:::\    \          /:::/\:::\    \          /:::/\:::\    \          /:::/\:::\    \          /:::/\:::\    \      ')
print tools.red('    /:::/__\:::\    \        /:::/__\:::\    \        /:::/__\:::\    \        /:::/__\:::\    \        /:::/__\:::\    \     ')
print tools.red('   /::::\   \:::\    \      /::::\   \:::\    \      /::::\   \:::\    \      /::::\   \:::\    \       \:::\   \:::\    \    ')
print tools.red('  /::::::\   \:::\    \    /::::::\   \:::\    \    /::::::\   \:::\    \    /::::::\   \:::\    \    ___\:::\   \:::\    \   ')
print tools.red(' /:::/\:::\   \:::\____\  /:::/\:::\   \:::\    \  /:::/\:::\   \:::\____\  /:::/\:::\   \:::\    \  /\   \:::\   \:::\    \  ')
print tools.red('/:::/  \:::\   \:::|    |/:::/__\:::\   \:::\____\/:::/  \:::\   \:::|    |/:::/  \:::\   \:::\____\/::\   \:::\   \:::\____\ ')
print tools.red('\::/   |::::\  /:::|____|\:::\   \:::\   \::/    /\::/    \:::\  /:::|____|\::/    \:::\  /:::/    /\:::\   \:::\   \::/    / ')
print tools.red(' \/____|:::::\/:::/    /  \:::\   \:::\   \/____/  \/_____/\:::\/:::/    /  \/____/ \:::\/:::/    /  \:::\   \:::\   \/____/  ')
print tools.red('       |:::::::::/    /    \:::\   \:::\    \               \::::::/    /            \::::::/    /    \:::\   \:::\    \      ')
print tools.red('       |::|\::::/    /      \:::\   \:::\____\               \::::/    /              \::::/    /      \:::\   \:::\____\     ')
print tools.red('       |::| \::/____/        \:::\   \::/    /                \::/____/               /:::/    /        \:::\  /:::/    /     ')
print tools.red('       |::|  ~|               \:::\   \/____/                  ~~                    /:::/    /          \:::\/:::/    /      ')
print tools.red('       |::|   |                \:::\    \                                           /:::/    /            \::::::/    /       ')
print tools.red('       \::|   |                 \:::\____\                                         /:::/    /              \::::/    /        ')
print tools.red('        \:|   |                  \::/    /                                         \::/    /                \::/    /         ')
print tools.red('         \|___|                   \/____/                                           \/____/                  \/____/          ')
print tools.red('                                                                                                                              ')
print tools.red('==============================================================================================================================')
print

start = timer()

# argument parser
parser = argparse.ArgumentParser(description='DESCRIPTION:\nScript for executing the regression checker for NRG codes multiple times with for parameter studies.', formatter_class=argparse.RawTextHelpFormatter)
#parser.add_argument('gitlab_ci', help='Path to gitlab-ci.yml which also contains a /regressioncheck/checks/... structure')
#parser.add_argument('-s', '--stage', default='DO_NIGHTLY', help='Supply DO_NIGHTLY, DO_WEEKLY, etc. flag for extracting the command from gitlab-ci.yml.')
#parser.add_argument('-b', '--begin', type=int, default=1,  help='Number of the case: where to start with the run (from the list that this tools creates)')
parser.add_argument('-d', '--debug', type=int, default=0, help='Debug level for this program. Dumps all info to the screen.')
#parser.add_argument('-i', '--info', type=int, default=1, help='Debug level for the subsequent program execution (e.g. flexi).')
#parser.add_argument('-o', '--only', action='store_true',help='Only run one case and exit afterwards (from the list that this tools creates).')
#parser.add_argument('-n', '--dryrun', action='store_true',help='Simply list all possible cases without performing any run.')
parser.add_argument('-e', '--exe', help='Path to executable of code that should be tested.')

# get reggie command line arguments
args = parser.parse_args()

# set the logger 'log' with the debug level from 'args' to determine the level of logging which displays output to the user
tools.setup_logger(args.debug)
log = logging.getLogger('logger')

# display all command line arguments
print "Running with the following command line options"
for arg in args.__dict__ :
    print arg.ljust(15)," = [",getattr(args,arg),"]"
print('='*132)

# define command that is usually run in a shell
if args.exe is None :
  cmd = ['python',reggie_exe_path,'-e','./boltzplatz','.','-s','-d1']
else :
  cmd = ['python',reggie_exe_path,'-e',str(args.exe),'.','-s','-d1']
#cmd = ["ls","-l"] # for testing some other commands

# initialize central object and run in current working dir
cwd   = os.getcwd()
repas = repas_tools.Case(cwd,cmd,'parameter_rename.ini','parameter_change.ini','parameter.ini') # and the case to the list of cases

# read the combinations for running the setups from parameter_change.ini
combis, digits = getCombinations(os.path.join(cwd,repas.names2_file))

# Edit parameter.ini for multiple parameters, subsequently, the reggie will change a set of variables 
#      and produce output which must be collected
# loop all runs
i=0
for combi in combis :

    # print setup info
    print 132*'-'
    for key, value in combi.items() :
        print "[%25s=%25s] digit=%3s" % (key, value, digits[key])

    # create parameter file for current combi
    repas.create(combi,digits)
    
    # read 'parameter_rename.ini' for renaming the results file
    repas.names()
    
    # run the code and repas output
    repas.run(i)
    i += 1

    # save data: check output directory for .pdf and .csv files and rename according to info in 'parameter_rename.ini'
    repas.save_data()

print 132*'-'
print " "
finalize(start, repas.nErrors)












