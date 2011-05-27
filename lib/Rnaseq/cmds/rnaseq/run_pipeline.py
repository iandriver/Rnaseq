#-*-python-*-
from warn import *
from Rnaseq import *
from Rnaseq.command import *
import sys, yaml, subprocess, os


class RunPipeline(Command):
    def usage(self):
        return "usage: run [output_file] -p <pipeline> -r <readset> [options]"

    def description(self):
        return "load and run a pipeline"
    
    def run(self, *argv, **args):
        try:
            config=args['config']
            readset_file=config['readset_file']
            missing=[]
            if readset_file==None: missing.append('readset (-r)')
            pipeline_name=config['pipeline_name']
            if pipeline_name==None: missing.append('pipeline (-p)')

            if len(missing)>0:
                msg="Missing items from command line: %s" % ", ".join(missing)
                raise UserError(msg)
            
        except KeyError as e:
            raise MissingArgError(str(e))
            
        try:
            argv=argv[0]
        except IndexError as e:
            raise ProgrammerGoof(e)

        # Create the pipeline and readset objects:
        readset=Readset(filename=readset_file).load() 

        session=RnaseqGlobals.get_session()

        # Iterate through reads files defined in readset:
        # fixme: condense this loop
        for reads_path in readset.path_iterator():

            # set up the pipeline:
            readset['reads_file']=reads_path
            pipeline=Pipeline(name=pipeline_name, readset=readset).load_steps()
            pipeline.update(RnaseqGlobals.config)
            if (RnaseqGlobals.conf_value('user_config')):
                RnaseqGlobals.set_user_step_params(pipeline) # fixme: not exactly what's needed here

            user_runs=RnaseqGlobals.user_config['pipeline_runs']
            print "user_runs(%s, len=%d) is %s" %(type(user_runs), len(user_runs), user_runs)
            
            # create pipeline_run and step_run objects (unless not running):
            if not RnaseqGlobals.conf_value('no_run'):
                (pipeline_run, step_runs)=pipeline.make_run_objects()
                script_filename=pipeline.write_sh_script(pipeline_run=pipeline_run, step_runs=step_runs)
            else:
                script_filename=pipeline.write_sh_script()


            # create and store the pipeline's shell script:

            # if running on the cluster, generate a calling (qsub) script and invoke that;
            # if not a cluster job, just assemble cmd[].
            (cmd,output,err)=self.write_qsub_script(pipeline, script_filename)
            print "launch cmd%s is '%s'" % (('(skipped)' if RnaseqGlobals.conf_value('no_run') else ''), " ".join(cmd))

            # launch the subprocess and check for success:
            if not RnaseqGlobals.conf_value('no_run'):
                self.launch(cmd, output, err)


    ########################################################################

    # write the qsub script.  Return cmd[], which can be passed to subprocess.Popen()
    def write_qsub_script(self,pipeline, script_filename):
        out_filename=pipeline.out_filename()
        err_filename=pipeline.err_filename()
        if RnaseqGlobals.conf_value('use_cluster'):
            script_filename=pipeline.qsub_script(script_filename) # script_filename becomes name of qsub script
            cmd=self.qsub_launcher()
            cmd.append(script_filename)
            output=sys.stdout
            err=sys.stderr
        else:
            # otherwise, just execute as a subprocess
            cmd=['sh', script_filename]
            output=open(out_filename, 'w')
            err=open(err_filename, 'w')
        return (cmd, output, err)

        

    ########################################################################


    # returns a list comprising the qsub command.  List is suitable for passing to subprocess.Popen()
    def qsub_launcher(self):
        # want to build list that looks like "ssh user@host /bin/qsub /working_dir/qsub_file
        launcher=[]
        launcher.append(RnaseqGlobals.conf_value('qsub','ssh_cmd'))

        user=RnaseqGlobals.conf_value('qsub','user') or os.environ['USER']
        host=RnaseqGlobals.conf_value('qsub','host')
        launcher.append("%s@%s" % (user,host))
                                   
        launcher.append(RnaseqGlobals.conf_value('qsub','exe'))
        return launcher

        
    def launch(self, cmd, output, err):
        pipe=subprocess.Popen(cmd, stdout=output, stderr=err)
        retcode=pipe.wait()
        if cmd[0]=="sh":
            output.close()
            err.close()
            retcode=0   # why???
            if retcode != 0:
                raise UserError("pipeline failed with return code %d\nsee %s.out and %s.err for diagnostics (in %s)" % \
                                (retcode, pipeline.name, pipeline.name, pipeline.working_dir()))
            



#print __file__, "checking in"
