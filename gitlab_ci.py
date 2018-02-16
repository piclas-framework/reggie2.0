from timeit import default_timer as timer
import logging
import tools
import argparse
import args_parser
import os
import re
import gitlab_ci_tools
import shutil

"""
General workflow:
1.  get the command line arguments 'args' with path to ".gitlab-ci.yml" file
2.  FIX THIS: set the logger 'log' with the debug level from 'args' to determine the level of logging which displays output to the user
3.  FIX THIS: perform the regression check by a) building executables
                                    b) running the code
                                    c) performing the defined analyzes
4.  FIX THIS: display the summary table with information for each build, run and analysis step
5.  FIX THIS: display if regression check was successful or not and return the corresponding error code
"""

print(132*'='+"\n"+"gitlab-ci processing tool, add nice ASCII art here"+"\n"+132*'=')
start = timer()


parser = argparse.ArgumentParser(description='Script for executing the regression checker for NRG codes multiple times with gitlab-ci.yml.', formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('gitlab_ci', help='Path to gitlab-ci.yml')
parser.add_argument('-s', '--stage', default='DO_NIGHTLY', help='Supply DO_NIGHTLY, DO_WEEKLY, etc. flag.')
parser.add_argument('-i', '--i_start', type=int, default=1,  help='Number of the case: where to start with the run')
parser.add_argument('-d', '--debug', type=int, default=0, help='Debug level.')
parser.add_argument('-o', '--only', action='store_true',help='only run one case and exit afterwards')

# get reggie command line arguments
args = parser.parse_args()

# display all command line arguments
print "Running with the following command line options"
for arg in args.__dict__ :
    print arg.ljust(15)," = [",getattr(args,arg),"]"
print('='*132)

# set the logger 'log' with the debug level from 'args' to determine the level of logging which displays output to the user
tools.setup_logger(args.debug)
log = logging.getLogger('logger')

# check if file exists
if not os.path.exists(args.gitlab_ci) :
    print tools.red("gitlab-ci.yml file not found under: '%s'" % args.gitlab_ci)
    exit(1)

# set the basedir (where the code is) and the reggiedir (where the reggie.py is)
basedir = os.path.abspath(os.path.dirname(args.gitlab_ci))
reggiedir = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))

print tools.blue("Using code under      [basedir]: "+str(basedir))
print tools.blue("Using reggie under  [reggiedir]: "+str(reggiedir))
print tools.blue("Running checks for [args.stage]: "+str(args.stage))

reggie_path = os.path.join(reggiedir, 'reggie.py')
if not os.path.exists(reggie_path) : # check if file exists
    print tools.red("reggie not found in reggie directory: '%s'" % reggie_path)
    exit(1)

cases = []
commands = []
with open(args.gitlab_ci, 'rb') as f :        # read file as "f"
    for line in f :                           # read every line
        s=str(line.strip())                   # remove whitespaces
        if s.find("if") > 0 :                 # find lines which contain "if"
            if re.search(r'\[(.*?)\]',s) :    # find lines with "[....]" in it, meaning opening "[" and closing "]" parenthesis
                if s.find("python") > 0 :     # find lines which contain "python"
                    c=s[s.find("python"):]    # create string "c" starting at "python"
                    if c.find(";") > 0 :      # find lines which contain ";"
                        c=c[:c.find(";")]     # remove everything aver ";"
                    if c not in commands:     # add the new command line only if it is unique
                        commands.append(c)    # add command line to list
                        cases.append(gitlab_ci_tools.Case(c)) # and the case to the list of cases

print(132*'=')

#switch to basedir+/output_dir_gitlab_tool
target_directory=os.path.join(basedir, 'output_dir_gitlab_tool')
shutil.rmtree(target_directory,ignore_errors=True)
os.makedirs(target_directory)
os.chdir(target_directory)
print "Creating output under %s" % target_directory


print " "
i=1
nErrors=0
for case in cases :
    # extract the reggie case from the command in the gitlay-ci.yml line by looking for "reggie.py" and "/regressioncheck/checks"
    c = case.command[case.command.find("reggie.py")+9:].strip()
    c = c[c.find("/regressioncheck/checks"):].strip()
    c = str(basedir+c).strip()
    case_dir=c.split(" ")[0]
    if not os.path.exists(case_dir) : # check if folder exists: use only the part of the string up to the first (whitespace (" ")
        print tools.red("case directory not found under: '%s'" % case_dir2)
        exit(1)

    # set the command line "cmd"
    cmd=["python", reggie_path]
    for x in c.split(" ") :
        cmd.append(str(x).strip())
    cmd_string=" ".join(cmd)
    #cmd = ["ls","-l"] # for testing some other commands

    # run case depending on supplied (or default) number "i_start"
    if i >= args.i_start : # run this case
        print str("[%5d] Running  " % i)+cmd_string,
        if args.debug > 0 :
            print " "

        # run the code and generate output
        try :
            if case.execute_cmd(cmd, target_directory) != 0 : # use unclolored string for cmake
                case.failed=True
        except : # this fails, if the supplied command line is corrupted
            print tools.red("Failed")
            case.failed=True

        # if case fails, add error to number of errors
        if case.failed :
            nErrors += 1

        # move the std.out file
        old_std=os.path.join(target_directory, 'std.out')
        new_std=os.path.join(target_directory, 'std-%s.out' % i)
        os.rename(old_std,new_std)

        # exit, if user wants to
        if args.only : # if only one case is to be run -> exit(0)
            gitlab_ci_tools.finalize(start, nErrors)
            exit(0)
    else : # skip this case
        print tools.yellow(str("[%5d] Skipping " % i)+cmd_string)

    i += 1

gitlab_ci_tools.finalize(start, nErrors)
