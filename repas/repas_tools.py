import os
import fileinput
from timeit import default_timer as timer
import logging

# import reggie source code
# use reggie2.0 functions by adding the path
import settings
import sys
sys.path.append(settings.absolute_reggie_path)



from combinations import getCombinations
from externalcommand import ExternalCommand
from tools import red
from tools import blue
from tools import yellow
from combinations import readKeyValueFile
from combinations import isKeyOf

class bcolors :
    """color and font style definitions for changing output appearance"""
    # Reset (user after applying a color to return to normal coloring)
    ENDC   ='\033[0m'    

    # Regular Colors
    BLACK  ='\033[0;30m' 
    RED    ='\033[0;31m' 
    GREEN  ='\033[0;32m' 
    YELLOW ='\033[0;33m' 
    BLUE   ='\033[0;34m' 
    PURPLE ='\033[0;35m' 
    CYAN   ='\033[0;36m' 
    WHITE  ='\033[0;37m' 

    # Text Style
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class Case(ExternalCommand) :

    def __init__(self, cwd, command,names_file,names2_file,parameter_file) :
        ExternalCommand.__init__(self)
        self.target_directory = cwd
        self.nErrors          = 0
        self.command          = command
        self.failed           = False

        self.names_file       = os.path.join(cwd,names_file)
        # check if file exists
        if not os.path.exists(self.names_file) :
            print red("names.ini file not found under: '%s'" % self.names_file)
            exit(1)

        self.names2_file       = os.path.join(cwd,names2_file)
        # check if file exists
        if not os.path.exists(self.names2_file) :
            print red("names2.ini file not found under: '%s'" % self.names2_file)
            exit(1)

        self.parameter_file   = os.path.join(cwd,parameter_file)
        # check if file exists
        if not os.path.exists(self.parameter_file) :
            print red("parameter.ini file not found under: '%s'" % self.parameter_file)
            exit(1)

        # display used files
        print "Using the following input files"
        print "names_file".ljust(15)," = [",self.names_file,"]"
        print "names2_file".ljust(15)," = [",self.names2_file,"]"
        print "parameter_file".ljust(15)," = [",self.parameter_file,"]"
        print('='*132)

    def create(self, combi, digits) :

        # copy original parameter.ini file to backup parameter_backup.ini file
        os.system("cp parameter_backup.ini %s" % self.parameter_file)

        # create temorary parameter_tmp.ini file which will be edited
        tmp_file_name = "parameter_tmp.ini"
        os.system("cp %s %s" % (self.parameter_file, tmp_file_name)) # mv parameter file to tmp file

        # check each line; if a changable parameter is found, set the current key/value pair in the combi
        for line in fileinput.input('parameter_tmp.ini', inplace = True):
            line_written = False
            for key, value in combi.items() :
                if digits[key] >= 0 :
                    if line.startswith(key) :
                        print "%s = %s" % (key,value)
                        line_written = True
            if not line_written :
                print line.strip()

        # copy temorary parameter_tmp.ini to original file
        os.system("mv %s %s" % (tmp_file_name, self.parameter_file)) # mv tmp file to parameter file

    def names(self) :
        
        # read combinations in 'parameter.ini' for renaming the results
        combis, digits = getCombinations(self.parameter_file,CheckForMultipleKeys=True) 

        # set "suffix"
        logging.getLogger('logger').debug("")
        logging.getLogger('logger').debug("")
        logging.getLogger('logger').debug(yellow('='*132))
        logging.getLogger('logger').debug("Creating output name:")
        if not os.path.exists(self.names_file) :
            print red("names.ini file not found under: '%s'" % self.names_file)
            exit(1)
        options_names, exclusions, noCrossCombinations = readKeyValueFile(self.names_file)
        suffix=''
        for option in options_names :
            logging.getLogger('logger').debug("option.name=%s" %  str(option.name))
            found, number = isKeyOf(combis[0],option.name)
            if found:
                logging.getLogger('logger').debug(str(option.name)+" = "+blue(str(found))+" (%s)" % combis[0][option.name])
                suffix += "_"+str(option.values[0])+"%s" % (combis[0][option.name])
            else:
                print str(option.name)+" = "+red(str(found))+" (NOT FOUND!)"

        print "Name=[%s]" % red(suffix)
        logging.getLogger('logger').debug(yellow('='*132))
        logging.getLogger('logger').debug("")
        logging.getLogger('logger').debug("")

        self.suffix = suffix

    def run(self,i) :
        print "cmd=%s" % self.command
        try :
            if self.execute_cmd(self.command, self.target_directory) != 0 : # use uncolored string for cmake
                self.failed=True
        except : # this fails, if the supplied command line is corrupted
            print tools.red("Failed")
            self.failed=True

        # if self fails, add error to number of errors
        if self.failed :
            self.nErrors += 1

        # move the std.out file
        old_std=os.path.join(self.target_directory, 'std.out')
        new_std=os.path.join(self.target_directory, 'std-%04d.out' % i)
        if os.path.exists(os.path.abspath(old_std)) : # check if file exists
            os.rename(old_std,new_std)

        # move the err.out file
        old_err=os.path.join(self.target_directory, 'std.err')
        new_err=os.path.join(self.target_directory, 'std-%04d.err' % i)
        if os.path.exists(os.path.abspath(old_err)) : # check if file exists
            os.rename(old_err,new_err)


    def save_data(self) :
        for file in os.listdir("output_dir/standalone/examples/cmd_0001/"):
            if file.endswith(".pdf"):
                try :
                    if file.index('order') != -1 :
                        order = file[file.index('order')+5:-4]             # get string from 'order' + 5 to the end, but remove last 4 character ".pdf"
                        new_name = "L2"+self.suffix+"_order%s.pdf" % order # add suffix to name
                        os.system("mv output_dir/standalone/examples/cmd_0001/"+file+" "+new_name) # move file to upper most path
                except :
                    new_name = "L2"+self.suffix+".pdf" 
                    os.system("mv output_dir/standalone/examples/cmd_0001/"+file+" "+new_name) # move file to upper most path

            if file.endswith(".csv"):
                try :
                    if file.index('order') != -1 :
                        order = file[file.index('order')+5:-4]             # get string from 'order' + 5 to the end, but remove last 4 character ".pdf"
                        new_name = "L2"+self.suffix+"_order%s.csv" % order # add suffix to name
                        os.system("mv output_dir/standalone/examples/cmd_0001/"+file+" "+new_name) # move file to upper most path
                except :
                    new_name = "L2"+self.suffix+".csv" 
                    os.system("mv output_dir/standalone/examples/cmd_0001/"+file+" "+new_name) # move file to upper most path


def finalize(start, run_errors) :
    """Display if generate was successful or not and return the number of errors that were encountered"""
    if run_errors > 0 :
        print bcolors.RED + 132*'='
        print "generate tool  FAILED!",
        return_code = 1
    else :
        print bcolors.BLUE + 132*'='
        print "generate tool  successful!",
        return_code = 0

    if start > 0 : # only calculate run time and display output when start > 0
        end = timer()
        print "in [%2.2f sec]" % (end - start)
    else :
        print ""

    print "Number of run     errors: %d" % run_errors

    print '='*132 + bcolors.ENDC
    exit(return_code)
