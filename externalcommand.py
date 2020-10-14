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
import subprocess
import logging
import tools
import select
from timeit import default_timer as timer
import sys

class ExternalCommand() :
    def __init__(self) :
        self.stdout = []
        self.stderr = []
        self.stdout_filename = None
        self.stderr_filename = None
        self.return_code = 0
        self.result = ""
        self.walltime = 0

    def execute_cmd(self, cmd, target_directory, name="std", string_info = None, environment = None):
        """Execute an external program specified by 'cmd'. The working directory of this program is set to target_directory.
        Returns the return_code of the external program.

        cmd                    : command given as list of strings (the command is split at every white space occurrence)
        target_directory       : path to directory where the cmd command is to be executed
        name (optional)        : [name].std and [name].err files are created for storing the std and err output of the job
        string_info (optional) : Print info regarding the command that is executed before execution
        environment (optional) : run cmd command with environment variables as given by environment=os.environ (and possibly modified)
        """
        # Display string_info
        if string_info is not None:
            print(string_info)

        # check that only cmd arguments of type 'list' are supplied to this function
        if type(cmd) != type([]) :
            print(tools.red("cmd must be of type 'list'\ncmd=")+str(cmd)+tools.red(" and type(cmd)="),type(cmd))
            exit(1)

        sys.stdout.flush() # flush output here, because the subprocess will force buffering until it is finished
        log = logging.getLogger('logger')

        workingDir = os.path.abspath(target_directory)
        log.debug(workingDir)
        log.debug(cmd)
        start = timer()
        (pipeOut_r, pipeOut_w) = os.pipe()
        (pipeErr_r, pipeErr_w) = os.pipe()
        if environment is None :
            self.process = subprocess.Popen(cmd, stdout=pipeOut_w, \
                                            stderr=pipeErr_w, \
                                            universal_newlines=True, cwd=workingDir)
        else :
            self.process = subprocess.Popen(cmd, stdout=pipeOut_w, \
                                            stderr=pipeErr_w, \
                                            universal_newlines=True, cwd=workingDir, \
                                            env = environment)

        self.stdout = []
        self.stderr = []

        bufOut = ""
        bufErr = ""
        while self.process.poll() is None:
            # Loop long as the selct mechanism indicates there
            # is data to be read from the buffer

            # 1.   std.out
            while len(select.select([pipeOut_r], [], [], 0)[0]) == 1:
                # Read up to a 1 KB chunk of data
                out_s = os.read(pipeOut_r, 1024)
                if not isinstance(out_s, str):
                    out_s = out_s.decode("utf-8")
                bufOut = bufOut + out_s
                tmp = bufOut.split('\n') 
                for line in tmp[:-1] :
                    self.stdout.append(line+'\n')
                    log.debug(line)
                bufOut = tmp[-1]

            # 1.   err.out
            while len(select.select([pipeErr_r], [], [], 0)[0]) == 1:
                # Read up to a 1 KB chunk of data
                out_s = os.read(pipeErr_r, 1024)
                if not isinstance(out_s, str):
                    out_s = out_s.decode("utf-8", 'ignore')
                bufErr = bufErr + out_s
                tmp = bufErr.split('\n') 
                for line in tmp[:-1] :
                    self.stderr.append(line+'\n')
                    log.info(line)
                bufErr = tmp[-1]

        os.close(pipeOut_w)
        os.close(pipeOut_r)
        os.close(pipeErr_w)
        os.close(pipeErr_r)


        self.return_code = self.process.returncode

        end = timer()
        self.walltime = end - start

        # write std.out and err.out to disk
        self.stdout_filename = os.path.join(target_directory,name+".out")
        with open(self.stdout_filename, 'w') as f :
            for line in self.stdout :
                f.write(line)
        if self.return_code != 0 :
            self.result=tools.red("Failed")
            self.stderr_filename = os.path.join(target_directory,name+".err")
            with open(self.stderr_filename, 'w') as f :
                for line in self.stderr :
                    f.write(line)
        else :
            self.result=tools.blue("Successful")

        # Display result (Successful or Failed)
        if string_info is not None:
            # display result and wall time in previous line and shift the text by ncols columns to the right
            # Note that f-strings in print statements, e.g. print(f"...."), only work in python 3
            # print(f"\033[F\033[{ncols}G "+str(self.result)+" [%.2f sec]" % self.walltime)
            ncols = len(string_info)+1
            print("\033[F\033[%sG " % ncols +str(self.result)+" [%.2f sec]" % self.walltime)
        else :
            print(self.result+" [%.2f sec]" % self.walltime)

        # Display error information if the code has failed to run: the last 15 lines of std.out and the last 15 lines of std.err
        if log.getEffectiveLevel() != logging.DEBUG:
            if self.return_code != 0 :
                for line in self.stdout[-15:] :
                    print(tools.red("%s" % line.strip()))
                for line in self.stderr[-15:]:
                    print(tools.red("%s" % line.strip()))

        return self.return_code
    
    def kill(self):
        self.process.kill()
