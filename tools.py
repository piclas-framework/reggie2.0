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
import logging
import shutil
import os
from timeit import default_timer as timer # noqa: F401: imported but unused (kept for performance measurements)
import time

class bcolors :
    """color and font style definitions for changing output appearance"""
    # Reset (user after applying a color to return to normal coloring)
    ENDC   ='\033[0m'

    # Regular Colors
    BLACK    = '\033[0;30m'
    RED      = '\033[0;31m'
    LIGHTRED = '\033[91m'
    GREEN    = '\033[0;32m'
    YELLOW   = '\033[0;33m'
    BLUE     = '\033[0;34m'
    PURPLE   = '\033[0;35m'
    CYAN     = '\033[0;36m'
    WHITE    = '\033[0;37m'
    PINK     = '\033[95m'

    # Text Style
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def cyan(text) :
    return bcolors.CYAN+text+bcolors.ENDC

def pink(text) :
    return bcolors.PINK+text+bcolors.ENDC

def purple(text) :
    return bcolors.PURPLE+text+bcolors.ENDC

def lightred(text) :
    return bcolors.LIGHTRED+text+bcolors.ENDC

def red(text) :
    return bcolors.RED+text+bcolors.ENDC

def green(text) :
    return bcolors.GREEN+text+bcolors.ENDC

def blue(text) :
    return bcolors.BLUE+text+bcolors.ENDC

def yellow(text) :
    return bcolors.YELLOW+text+bcolors.ENDC

def indent(text, amount, ch=' '):
    """Indent text line by amount times a white space """
    padding = amount * 2 * ch
    return ''.join(padding+line for line in text.splitlines(True))

def setup_logger(debug_level):
    """Setups a global logger with the name 'logger'.
    This logger can accessed in any function by "log = logging.getLogger('logger')".
    Three different logging levels:
        0 : print no logging messages
        1 : print information messages (i.e. print all messages invoked with "log.info(message)")
        2 : print debug + information messages (i.e. print all messages invoked with "log.info(message)" or "log.debug(message)")
    """

    if debug_level == 0   : # no logging
        formatter = logging.Formatter()
    elif debug_level == 1 : # info
        formatter = logging.Formatter(fmt='%(message)s')
    elif debug_level == 2 : # debug
        formatter = logging.Formatter(fmt='%(levelname)s - %(module)s: %(message)s')

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger('logger')
    if debug_level == 0 :   # no logging
        logger.setLevel(0)
    elif debug_level == 1 : # info
        logger.setLevel(logging.INFO)
    elif debug_level == 2 : # debug
        logger.setLevel(logging.DEBUG)

    logger.addHandler(handler)
    return logger

def find_basedir(basedir) :
    """Search 'CMakeLists.txt' in directories above current working directory.
    The directory containing the 'CMakeLists.txt' is the 'basedir'."""
    found = os.path.exists(os.path.join(basedir, "CMakeLists.txt")) # check if actual directory is the basedir
    if found :
        basedir = os.path.abspath(basedir)
    while not found :                                               # look upwards until basedir found
        basedir = os.path.dirname(basedir)                              # basedir = basedir/..
        found = os.path.exists(os.path.join(basedir, "CMakeLists.txt")) # check if actual directory is the basedir
        if basedir == "/": # check if root of filesystem is reached
            break

    if not found :
        raise Exception("No basedir found. Started searching for 'CMakeLists.txt' in '%s'" % os.getcwd())

    return basedir


def remove_folder(path) :
    print("deleting folder '%s'" % path)
    shutil.rmtree(path,ignore_errors=True)
    #shutil.rmtree(path)

def create_folder(path):
    if not os.path.exists(path) :
        i=0
        # try multiple times to create the directory (on some systems a
        # race condition might occur between creation and checking)
        while True:
            try:
                i+=1
                os.makedirs(path)
                if i>60:
                    print(red("OutputDirectory() : Tried creating a directory more than 60 times. Stop."))
                    exit(1)
                break
            except OSError as e:
                if e.errno != os.errno.EEXIST:
                    raise
                time.sleep(1) # wait 1 second before next try
                pass


def diff_lists(x,x_ref,tol,tol_type) :
    """
    determine diff of two lists of floats, either relative of absolute
    (if the reference value is zero, use absolute comparison)
    x        : vector of real values
    x_ref    : vector of real values (reference)
    tol      : tolerance value
    tol_type : tolerance type, relative or absolute
    """

    # check tolerance type: absolute/relative (is the reference value is zero, absolute comparison is used)
    if tol_type == 'absolute' :
        diff = [abs(a-b) for (a,b) in zip(x,x_ref)]
        executed_tol_type = ['absolute' for (b) in x_ref]
    else : # relative comparison
        # if the reference value is zero, use absolute comparison
        diff = [abs(a/b-1.0) if abs(b) > 0.0 else abs(a) for (a,b) in zip(x,x_ref) ]
        executed_tol_type = ['relative' if abs(b) > 0.0 else 'absolute' for (b) in x_ref]

    # determie success logical list for return variable
    success = [d <= tol for d in diff]

    # display information when a diff is not successful, display value+reference+difference
    if not all(success) :
        print("Differences in vector comparison:")
        print(5*"%25s" % ("x","x_ref","diff","tolerance","type"))
        for i in range(len(diff)) :
            if not success[i] :
                print(4*"%25.14e" % (x[i],x_ref[i],diff[i],tol), "%24s" % (executed_tol_type[i]))
    return success

def diff_value(x,x_ref,tol,tol_type) :
    """
    determine diff of two floats, either relative of absolute
    (if the reference value is zero, use absolute comparison)
    x        : scalar
    x_ref    : scalar (reference)
    tol      : tolerance value
    tol_type : tolerance type, relative or absolute
    """

    # check tolerance type: absolute/relative (is the reference value is zero, absolute comparison is used)
    if tol_type == 'absolute' :
        diff = abs(x-x_ref)
    else : # relative comparison
        # if the reference value is zero, use absolute comparison
        if abs(x_ref) > 0.0 :
            diff = abs(x/x_ref-1.0)
        else :
            diff = x

    # determie success logical list for return variable
    success = diff <= tol

    # display information when a diff is not successful, display value+reference+difference
    if not success :
        print("\nDifferences in vector comparison:")
        print(5*"%25s   " % ("x","x_ref","diff","tolerance","type"))
        print(4*"%25.14e   " % (x,x_ref,diff,tol), "%24s" % (tol_type))

    return success

def isKeyOf(a,key_IN) :
    """Check if the dictionary 'a' contains a key 'key_IN'"""
    found = False
    number = 0
    for key in a.keys() :
        if key == key_IN :
            number += 1
            found = True
    return found, number
