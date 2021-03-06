#!/usr/bin/env python
#-*-python-*-

# The main rnaseq entry point

import sys, os
if sys.version < '2.6.2':
    print "version 2.6.2 or better of python required.  You are running %s.  Please see your system administrator about upgrading" % sys.version
    sys.exit(1)

dir=os.path.normpath(os.path.dirname(os.path.abspath(__file__))+"/..")
sys.path.append(os.path.join(dir+'/lib'))
sys.path.append(os.path.join(dir+'/ext_libs'))

from Rnaseq import *

########################################################################

def main():
    usage="usage: %s <cmd> [-p <pipeline>] [-r <readset_file>] [options]" % sys.argv[0] # fixme: form might be different; might be more like git
    testing='-d' in sys.argv
    argv=RnaseqGlobals.initialize(usage, testing=testing)       # not to be confused with sys.argv

    # get the command:
    try:
        cmd=argv[1]
    except IndexError as ie:
        cmd='help'
        
    cf=CmdFactory(program='rnaseq')
    cf.add_cmds(RnaseqGlobals.conf_value('rnaseq','cmds'))
    cmd=cf.new_cmd(cmd)

    # run the command 
    cmd.run(argv, config=RnaseqGlobals.config)


########################################################################

try:
    main()

except UserError as ue:
    die(ue)

except ProgrammerGoof as pg:
    warn("An internal error occured:\n")
    import traceback
    traceback.print_exc()
    sys.exit(1)

except ConfigError as ce:
   warn("A configuration error (or errors) occured:\n")
   die(ce)

except RnaseqException as re:
    warn("An unexpected rnaseq exception has occured: %s\n" % re)
    if re.show_traceback:
        import traceback
        traceback.print_exc()
    die(re)


