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
import os
import time
import tools

class OutputDirectory() :
    output_dir = "output_dir"
    def __init__(self, parent, name, number = -1, mkdir=True) :
        
        self.number = number
        self.parent = parent

        # set parent directory for subfolder creation
        if self.parent :
            parent_dir = self.parent.target_directory
        else :
            parent_dir = OutputDirectory.output_dir 

        # numbering of directory (if a number is supplied)
        if number >= 0 :
            self.target_directory = os.path.join(parent_dir, "%s_%04d" %(name, number))
        else :
            self.target_directory = os.path.join(parent_dir, name)

        # create directory if it is non-existent
        if mkdir :
            if not os.path.exists(os.path.dirname(self.target_directory)) :
                print "targt dir= ",os.path.dirname(self.target_directory)
                i=0
                # try multiple times to create the directory (on some systems a 
                # race condition might occur between creation and checking)
                while True:
                    mydir = os.path.dirname(self.target_directory)
                    try:
                        i+=1
                        os.makedirs(mydir)
                        if i>60:
                            print tools.red("OutputDirectory() : Tried creating a directory more than 60 times. Stop.")
                            exit(1)
                        break
                    except OSError, e:
                        if e.errno != os.errno.EEXIST:
                            raise   
                        time.sleep(1) # wait 1 second before next try
                        pass


