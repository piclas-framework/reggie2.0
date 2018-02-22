from externalcommand import ExternalCommand
from timeit import default_timer as timer

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

    def __init__(self, command) :
        self.command = command
        self.failed = False
        #self.source_directory = source_directory
        #self.configuration    = configuration
        #OutputDirectory.__init__(self, None, name, number)  
        ExternalCommand.__init__(self)



def finalize(start, run_errors) :
    """Display if gitlab_ci script check was successful or not and return the number of errors that were encountered"""
    if run_errors > 0 :
        print bcolors.RED + 132*'='
        print "gitlab-ci processing tool  FAILED!",
        return_code = 1
    else :
        print bcolors.BLUE + 132*'='
        print "gitlab-ci processing tool  successful!",
        return_code = 0

    if start > 0 : # only calculate run time and display output when start > 0
        end = timer()
        print "in [%2.2f sec]" % (end - start)
    else :
        print ""

    print "Number of run     errors: %d" % run_errors

    print '='*132 + bcolors.ENDC
    exit(return_code)
