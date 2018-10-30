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
from timeit import default_timer as timer
import logging
import tools
import check
import args_parser
"""
General workflow:
1.  get the command line arguments 'args' and all valid build combinations in the check directory from 'builds.ini'
2.  set the logger 'log' with the debug level from 'args' to determine the level of logging which displays output to the user
3.  perform the regression check by a) building executables
                                    b) running the code
                                    c) performing the defined analyzes
4.  display the summary table with information for each build, run and analysis step
5.  display if regression check was successful or not and return the corresponding error code
"""

print 
print tools.red('       oooooooo      ====================')+tools.yellow('=====================================')+tools.green('====================      oooooooo       ')
print tools.red('    ooo   oo   ooo      _____    ______  ')+tools.yellow('  _____    _____   _____   ______    ')+tools.green(' ___         ___       ooo   oo   ooo    ')
print tools.red('   oo     oo     oo    |  __ \  |  ____| ')+tools.yellow(' / ____|  / ____| |_   _| |  ____|   ')+tools.green('|__ \       / _ \     oo     oo     oo   ')
print tools.red('  oo      oo      oo   | |__) | | |__    ')+tools.yellow('| |  __  | |  __    | |   | |__      ')+tools.green('   ) |     | | | |   oo      oo      oo  ')
print tools.red('  oo     oooo     oo   |  _  /  |  __|   ')+tools.yellow('| | |_ | | | |_ |   | |   |  __|     ')+tools.green('  / /      | | | |   oo     oooo     oo  ')
print tools.red('  oo    oooooo    oo   | | \ \  | |____  ')+tools.yellow('| |__| | | |__| |  _| |_  | |____    ')+tools.green(' / /_   _  | |_| |   oo    oooooo    oo  ')
print tools.red('   oo oo  oo  oo oo    |_|  \_\ |______| ')+tools.yellow(' \_____|  \_____| |_____| |______|   ')+tools.green('|____| (_)  \___/     oo oo  oo  oo oo   ')
print tools.red('    ooo   oo   ooo                       ')+tools.yellow('                                     ')+tools.green('                       ooo   oo   ooo    ')
print tools.red('       oooooooo      ====================')+tools.yellow('=====================================')+tools.green('====================      oooooooo       ')
print 


start = timer()

# 1.  get the command line arguments 'args' and all valid build combinations in the check directory from 'builds.ini'
args, builds = args_parser.getArgsAndBuilds()

# 2.  set the logger 'log' with the debug level from 'args' to determine the level of logging which displays output to the user
tools.setup_logger(args.debug)
log = logging.getLogger('logger')

# 3.  perform the regression check by a) building executables
#                                     b) running the code
#                                     c) performing the defined analyzes
check.PerformCheck(start,builds,args,log)

# 4.  display the summary table with information for each build, run and analysis step
check.SummaryOfErrors(builds)

# 5.  display if regression check was successful or not and return the corresponding error code
tools.finalize(start, 0, check.Run.total_errors, check.Analyze.total_errors)
