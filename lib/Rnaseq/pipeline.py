#-*-python-*-

# step_object version

import sys, yaml, re, os, re

from Rnaseq import *
from step_run import *                  # why isn't this already included in above line???
from step_factory import *
from RnaseqGlobals import RnaseqGlobals
import path_helpers
from sqlalchemy import *
from sqlalchemy.orm import mapper, relationship, backref
from hash_helpers import obj2dict

from pipeline_run import PipelineRun
from context import Context

class Pipeline(templated):
    def __init__(self,*args,**kwargs):
        templated.__init__(self,*args,**kwargs)
        self.set_defaults()

    def set_defaults(self):
        self.type='pipeline'
        self.suffix='syml'
        self.steps=[]
        self.step_exports={}


    @classmethod
    def get_pipeline(self,**kwargs):
        session=RnaseqGlobals.get_session()
        use_template=RnaseqGlobals.conf_value('use_template')
        found=False

        assert(kwargs['name'])
        assert(kwargs['readset'])
        db_pipeline=session.query(Pipeline).filter_by(name=kwargs['name']).first()
        found=db_pipeline!=None

        if use_template or not found:   # build pipeline using template
            t_pipeline=Pipeline(name=kwargs['name'], readset=kwargs['readset']).load()

        if found:
            if use_template:      # replace existing template with newly generated one:
                assert(db_pipeline.id != None)
                session.delete(db_pipeline)
                session.commit()
                session.add(t_pipeline)
                session.commit()
                pipeline=t_pipeline
            else:
                pipeline=db_pipeline
                pipeline.readset=kwargs['readset']

        else:                           # found==False
            t_pipeline.template_file()    # sets pipeline.path
            session.add(t_pipeline)
            session.commit()
            pipeline=t_pipeline

        assert(hasattr(pipeline,'readset'))
        pipeline.set_defaults()
        return pipeline    
        
    def __str__(self):
        return "%s" % self.name

    ########################################################################

    __tablename__='pipeline'
        
    @classmethod
    def create_table(self, metadata, engine):
        pipeline_table=Table(self.__tablename__, metadata,
                             Column('id', Integer, primary_key=True, autoincrement=True),
                             Column('name', String, nullable=False, index=True, unique=True),
                             Column('description', String),
                             Column('path',String,nullable=False),
                             useexisting=True
                             )
        metadata.create_all(engine)

        sa_properties={'pipeline_runs':relationship(PipelineRun, backref='pipeline', cascade='all, delete, delete-orphan'),
                       }
        mapper(Pipeline, pipeline_table, sa_properties)
        return pipeline_table
    

    ########################################################################

    # return the step with the given step name, or None if not found:
    def step_with_name(self,stepname):
        for step in self.steps:
            if step.name==stepname: return step
        return None

    # return the step after the given step (by name), or None if not found:
    def step_after(self,stepname):
        if stepname==None:
            return self.steps[0]
        prev_step=self.steps[0]
        for step in self.steps[1:]:
            if prev_step.name==stepname: return step
            prev_step=step
        return None

    def step_names(self):               # not sure this is actually called by anyone
        l=[s.name for s in self.steps]
        return l

    ########################################################################
    # load all the steps
    # return self
    def load_steps(self):
        assert(hasattr(self,'readset'))
        debug='debug' in os.environ
        
        name=self.name
        self.load_template()            # this barfs (in ID()) if no self.readset
        assert(hasattr(self,'stepnames'))
        # check to see if we need to change the name back:
        if self.name!=name: # loading the template changed the name: bad
            old_name=self.name
            self.name=name
            if debug: print >>sys.stderr, "Changed pipeline name back to %s (from %s)" % (name, old_name)
        
        # split up the stepnames field:
        try:
            self.stepnames=re.split('[,\s]+',self.stepnames)
        except AttributeError:
            raise ConfigError("pipeline %s does not define stepnames" % self.name)
        except TypeError as te:
            if type(self.stepnames)!=type([]):
                raise te

        # for each step, create a Step object and append to self.steps:
        step_factory=StepFactory()
        errors=[]
        for stepname in self.stepnames:
            step=step_factory.new_step(self, stepname)
            if not stepname in self:
                errors.append("missing step section for '%s'" % stepname)
                continue
            step.update_o(self[stepname])
            self.steps.append(step)
        
        errors.extend(self.convert_io())

        # Check to see that the list of step names and the steps themselves match; dies on errors
        errors.extend(self.verify_steps()) 
        errors.extend(self.verify_exes())
        if len(errors)>0:
            raise ConfigError("\n".join(errors))
        
        return self


    
    ########################################################################
    # read the pipeline's .syml file and call templated.load on it:
    def load_template(self):
        vars={}
        vars.update(self.__dict__)
        vars.update(RnaseqGlobals.config)
        vars['ID']=self.ID()


        ev=evoque_dict()
        ev.update(vars)
        templated.load(self, vars=ev, final=False)
        
        return self

    ########################################################################
    # Write the pipeline's shell script to disk.
    # Returns full path of script name.
    def write_sh_script(self, **kwargs):
        script=self.sh_script(**kwargs)

        script_filename=os.path.join(self.readset.working_dir, self.scriptname())
        try:
            os.makedirs(self.readset.working_dir)
        except OSError:
            pass                    # already exists, that's ok (fixme: could be permissions error)
        with open(script_filename, "w") as f:
            f.write(script)
            if RnaseqGlobals.conf_value('verbose'): print "%s written" % script_filename
        return script_filename




    ########################################################################
    # return an entire shell script that runs the pipeline
    def sh_script(self, **kwargs):

        script="#!/bin/sh\n\n"
        session=RnaseqGlobals.get_session()
        verbose=RnaseqGlobals.conf_value('verbose')
        
        # determine if provenance is desired:
        try:
            pipeline_run=kwargs['pipeline_run']
            step_runs=kwargs['step_runs']
            include_provenance=True
        except KeyError:
            include_provenance=False
        
        # create auxillary steps:
        if include_provenance:
            step_factory=StepFactory()

            pipeline_start=step_factory.new_step(self,
                                                 'pipeline_start',
                                                 pipeline_run_id=pipeline_run.id,
                                                 step_run_id=None,
                                                 next_step_run_id=self.context.step_runs[self.steps[0].name].id)
            mid_step=step_factory.new_step(self, 'mid_step', pipeline_run_id=pipeline_run.id)
            pipeline_end=step_factory.new_step(self, 'pipeline_end', pipelinerun_id=pipeline_run.id,
                                               step_run_id=None, next_step_run_id=None)
            script+=pipeline_start.sh_script(self.context)

        # iterate through steps; 
        errors=[]
        for step in self.steps:
            try:
                if step.skip:
                    if verbose: print "skipping step %s (already current)" % step.name
                    continue  # in a try block in case step.skip doesn't even exist
            except:                     # really? step.skip doesn't exist, so assume it's True???
                pass
                
            
            # append step.sh_script(self.context)
            step_script=step.sh_script(self.context, echo_name=True)
            try: step_script=step.sh_script(self.context, echo_name=True)
            except Exception as e:
                errors.append("%s: %s" % (step.name,str(e)))
                errors.append("Exception in pipeline.sh_script(step %s): %s (%s)" % (step.name, e, type(e)))
                continue

            script+=step_script
            script+="\n"

            # insert check success step:
            if include_provenance:
                try: skip_check=step['skip_success_check'] 
                except: skip_check=False
                if not skip_check:
                    step_run=step_runs[step.name]
                    step_run.cmd=step_script
                    mid_step.stepname=step.name
                    mid_step.step_run_id=step_run.id
                    next_step=self.step_after(step.name)
                    if next_step:
                        mid_step.next_step_run_id=self.context.step_runs[next_step.name].id
                    else:
                        mid_step.next_step_run_id=0
                        
                    script+=mid_step.sh_script(self.context)

            if RnaseqGlobals.conf_value('verbose'):
                print "step %s added" % step.name

        # record finish:
        if include_provenance:
            pipeline_end.last_step_id=step_runs[self.steps[-1].name].id
            script+=pipeline_end.sh_script(self.context)

        # check for continuity and raise exception on errors:
        errors.extend(self.verify_continuity(self.context))
        if len(errors)>0:
            raise ConfigError("\n".join(errors))
            

        session.commit()

        return script

    ########################################################################
    
    # combine working_dir, self.name, and readset.label to form the script filename:
    def scriptname(self):
        return path_helpers.sanitize(os.path.join(self.working_dir(), '.'.join([self.name, self.readset.label, 'sh'])))

    def working_dir(self):
        return self.readset.working_dir


    def ID(self):
        try: return self.readset.ID
        except AttributeError: return None
    

    ########################################################################
    #  check to see that all defined steps are listed, and vice verse:
    def verify_steps(self):
        try: debug=os.environ['DEBUG']
        except: debug=False
        
        step_factory=StepFactory()
        a=set(self.stepnames)
        b=set([x for x in self.keys() if type(self[x])==type({}) and step_factory.is_step(x)])
        if debug: print >>sys.stderr, "a: %s" % a
        if debug: print >>sys.stderr, "b: %s" % b
        
        if a==b: return []            # set equality! we just love over-ridden operators

        errors=[]
        name_no_step=a-b                # set subtraction!
        if debug: print "name_no_step: %s" % name_no_step
        if len(name_no_step)>0:
            errors.append("The following steps were listed as part of %s, but no defining section was found: %s" % (self.name, ", ".join(list(name_no_step))))
            #print >>sys.stderr, "The following steps were listed as part of %s, but no defining section was found: %s" % (self.name, ", ".join(list(name_no_step)))
            
        step_no_name=b-a                # more set subtraction!
        if debug: print "step_no_name: %s" % step_no_name
        if len(step_no_name)>0:
            errors.append("The following steps were defined as part of %s, but not listed: %s" % (self.name, ", ".join(list(step_no_name))))
            #print >>sys.stderr, "The following steps were defined as part of %s, but not listed: %s" % (self.name, ", ".join(list(step_no_name)))
        
        return errors


    ########################################################################
    # check to see that all inputs and outputs connect up correctly and are accounted for
    # outputs also include files defined by "create"
    def verify_continuity(self, context):
        step=self.steps[0]
        errors=[]
        dataset2stepname={}
        
        # first step: check that inputs exist on fs, prime dataset2stepname:
        for input in context.inputs[step.name]:
            if not os.path.exists(input):
                errors.append("missing inputs for %s: %s" % (step.name, input))
        for output in context.outputs[step.name]:
            dataset2stepname[output]=step.name

        # subsequent steps: check inputs exist in dataset2stepname, add outputs to dataset2stepname:
        for step in self.steps[1:]:        # skip first step
            for input in context.inputs[step.name]:
                if input not in dataset2stepname and not os.path.exists(input):
                    errors.append("pipeline '%s':\n  input %s \n  (in step '%s') is not produced by any previous step and does not currently exist" % (self.name, input, step.name))
            for output in context.outputs[step.name]:
                dataset2stepname[output]=step.name

        return errors
            
            

    ########################################################################
    def verify_exes(self):
        dirs=RnaseqGlobals.conf_value('rnaseq', 'path').split(":")
        dirs.extend([os.path.join(RnaseqGlobals.conf_value('rnaseq','root_dir'),'programs')])
            
        errors=[]
        for step in self.steps:
            if not step.verify_exe():
                errors.append("Missing executable in step %s: %s" %(step.name, step.exe))
                
        if len(errors)>0:
            errors.append("Please link these executables from the %s/programs directory, or make sure they are on the path defined in the config file." \
                          % RnaseqGlobals.conf_value('rnaseq', 'root_dir'))

        return errors
        


    ########################################################################


    def out_filename(self):
        return path_helpers.sanitize(os.path.join(self.readset.working_dir, "%s.out" % self.name))
    def err_filename(self):
        return path_helpers.sanitize(os.path.join(self.readset.working_dir, "%s.err" % self.name))
        

    ########################################################################
    # create the qsub script using a template:
    def qsub_script(self, script_filename, out_filename=None, err_filename=None):
        if out_filename==None: out_filename=self.out_filename()
        if err_filename==None: err_filename=self.err_filename()
        qsub=templated(name='qsub', type='sh_template', suffix='tmpl')
        vars={}
        vars.update(self.__dict__)
        vars['name']=path_helpers.sanitize(self.name)
        vars['cmd']=script_filename
        vars['out_filename']=out_filename
        vars['err_filename']=err_filename
        qsub_script=qsub.eval_tmpl(vars=vars)

        qsub_script_file=path_helpers.sanitize(os.path.join(self.readset.working_dir, "%s.%s.qsub" % (self.name, self.readset.label)))
        f=open(qsub_script_file,"w")
        f.write(qsub_script)
        f.close()
        if RnaseqGlobals.conf_value('verbose'): print("%s written" % qsub_script_file)
        return qsub_script_file

    
    ########################################################################
    # lookup self in db; if not found, store.  Same for all steps.
    # this should be obsolete now if the new code in __init__() works
    # but it is called by load_pipeline.py
    def store_db(self):
        session=RnaseqGlobals.get_session()
        other_self=session.query(Pipeline).filter_by(name=self.name).first()

        if other_self==None:
            session.add(self)
            session.commit()
            #if RnaseqGlobals.conf_value('debug'): warn("s_db: added pipeline %s: id=%d" % (self.name, self.id))
            #if RnaseqGlobals.conf_value('debug'): warn("s_db: %s.path: %s" % (self.name, self.path))
            
        else:
            #if RnaseqGlobals.conf_value('debug'): warn("s_db: found pipeline %s: id=%d" % (self.name, other_self.id))
            self.id=other_self.id
            self=other_self

        return self
        


    ########################################################################
    # return a tuple containing a pipeline_run object and a dict of step_run objects (keyed by step name):
    def make_run_objects(self, session):
        #self=self.store_db()
        try: verbose=os.environ['DEBUG']
        except: debug=False
        
        # create the pipeline_run object:
        try: 
            label=RnaseqGlobals.conf_value('label') or self.readset.label
        except AttributeError as ae:
            raise UserError("No label defined.  Please specify a label for the pipeline run, either in the readset or using the '--label' command line option")

        pipeline_run=PipelineRun(status='standby',
                                 input_file=', '.join(self.readset.reads_files),
                                 user=RnaseqGlobals.conf_value('user'),
                                 label=label,
                                 working_dir=self.readset.working_dir)

        self.pipeline_runs.append(pipeline_run)
#        print "mro: self.pipeline_runs is %s" % ", ".join(str(x.id) for x in self.pipeline_runs)
#        try: warn("pipeline.id is %s" % pipeline.id)
#        except: warn("pipeline has no id")
        self=session.merge(self)
        session.commit()                
        if pipeline_run.id==None:
            raise ProgrammerGoof("no id in %s" % pipeline_run)

        self.context.pipeline_run_id=pipeline_run.id
        RnaseqGlobals.set_conf_value('pipeline_run_id',pipeline_run.id)
        
        # create step_run objects:
        step_runs={}
        for step in self.steps:
            if step.is_prov_step: continue
            step_run=StepRun(step_name=step.name, status='standby')
            for output in step.output_list():
                output=evoque_template(output, step, self.readset)
                step_run.file_outputs.append(FileOutput(path=output))

            if step.skip:               # as set by self.set_steps_current()
                if debug: print "step %s is current, skipping" % step.name
                step_run.status='skipped'
                step_run.success=True

            pipeline_run.step_runs.append(step_run)
            session.commit()
            pipeline_run.step_runs.append(step_run) # maintains list in db as well
            step_runs[step.name]=step_run
            self.context.step_runs[step.name]=step_run

        session.commit()
        return (pipeline_run, step_runs)


    ########################################################################
    # check uniqueness of label:
    def check_label_unique(self, session, label):
        other_pr=session.query(PipelineRun).filterBy(label=label).first()
        if other_pr:
            if RnaseqGlobals.conf_value('force'):
                session.delete(other_pr) # delete existing run, will get over written
                session.commit()
            else:
                raise UserError("The label '%s' is already in use.\n  Please provide a new label (either in the readset or by use of the '--label' command line option), or use the '--force' option to fully override the old pipeline run.  \n  This will cause all steps to be run, also." % label)

        

    ########################################################################
    # for each step, set an attribute 'skip' indicating whether or not to skip the step when creating the sh script:
    # fixme: convoluted logic, needs testing!
    def set_steps_current(self, global_force=False):
        force_rest=False
        try: debug=os.environ['DEBUG']
        except: debug=False
        
        for step in self.steps:
            skip=not (global_force or step.force or force_rest) and step.is_current()
            setattr(step, 'skip', skip)

            # once one step is out of date, all following steps will be, too:
            if not step.skip and not step.force:
                force_rest=True
                if debug:
                    print "pipeline: step %s not current, adding all following steps" % step.name


    ########################################################################
    # convert the pipeline's depiction of a step's inputs into an array of input names:
    # Note: the inputs to a step (noted here as 'inputs') are supposed to be the outputs of a previous step.
    # for this function, everything is in the context of the step denoted by 'stepname'
    # called by context.load_io().
    # returns the updated context object.
    def convert_io(self):
        context=Context(self.readset)
        debug='DEBUG' in os.environ
        
        errors=[]
        outputs_deferred=[]
        
        for step in self.steps:
            if debug: print "convert_io: step is %s" % step.name
            
            try: stephash=self[step.name]
            except KeyError: errors.append("In pipeline '%s', step %s has no defining section" % (self.name, step.name))

            # attempt to set outputs:
            context.outputs[step.name]=step.output_list(stephash)
            try:
                context.outputs[step.name]=step.output_list(stephash)
                if debug: print "convert: outputs[%s] is %s" % (step.name, context.outputs[step.name])
            except AttributeError as ae: # what attribute is missing?
                if debug: print "pipeline.convert_io: caught ae: %s" % ae
                if re.search("no attribute 'context'", str(ae)):
                    outputs_deferred.append(step)
                    print "deferring outputs for step %s" % step.name
                else: raise ae
                    
            # get the input specifier from the stephash; if not listed, assume no inputs, set outputs according to step, and continue:
            try: inputs=stephash['inputs']
            except KeyError:
                context.inputs[step.name]=[]
                if debug: print "no inputs for step '%s', skipping" % step.name
                continue

            names=re.split('[\s,]+', inputs)
            input_list=[]
            for term in names:
                mg=re.search('([\w/${}]+)(\[\d+\])?$', term) # looking for 'abcd' or 'abcd[1]' or something like that
                if mg==None:
                    errors.append("step %s: malformed input term '%s'" % (step.name, term))
                    continue
                
                # get the "previous" step name and optional index
                output_step=mg.group(1)
                index=mg.group(2)      # can be None

                # get the source of the inputs; can be the readset or the output of another step:
                if output_step == 'readset':
                    outputs=self.readset.reads_files # really? doesn't take into account link to working_dir...

                else:
                    try:
                        outputs=context.outputs[output_step]
                    except KeyError:
                        if debug: print "context is %s" % yaml.dump(context)
                        raise ConfigError("pipeline %s: unknown step '%s' for inputs '%s'" % (self.name, output_step, step.name))
            
                if index == None:
                    input_list.extend(outputs)
                else:
                    index=int(re.sub('[[\]]','',index))
                    try:
                        input_list.append(outputs[index])
                    except IndexError:
                        raise ConfigError("step %s: outputs '%s': index %d out of range" % (step.name, outputs, index))

                context.inputs[step.name]=input_list

        #warn("context is %s" % yaml.dump(context))
        self.context=context

        # set context.outputs[] for each step:
        for step in outputs_deferred:
            try:
                stephash=self[step.name]
                context.outputs[step.name]=step.output_list(stephash)
            except KeyError:
                continue   # already checked for this error above
            

        return errors




#print "%s checking in: Pipeline.__name__ is %s" % (__file__,Pipeline.__name__)


