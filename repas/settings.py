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
# settings.py
import os
import sys

def init():
    global absolute_reggie_path
    absolute_reggie_path=os.path.abspath(os.path.join(__file__ ,"../.."))
    if not os.path.exists(absolute_reggie_path) :
        print "Reggie repository not found under: '%s'" % absolute_reggie_path
        exit(1)

