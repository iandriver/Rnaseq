#-*-python-*-

import yaml, re, time, os

from warn import *
from dict_like import *
from templated import *
from step import *

class Pipeline(dict_like, templated):
    attrs={'name':None,
           'type':'pipeline',
           'steps':[],
           'readset':None,
           }

    def __init__(self,**args):
        dict_like.__init__(self,**args)
        templated.__init__(self,**args)
        self.type='pipeline'


    def stepWithName(self,stepname):
        for step in self.steps:
            if step.name==stepname: return step 
        return None

    def load(self,readset):
        templated.load(self, vars=readset)

        # load steps.  (We're going to replace the current steps field, which holds a string of stepnames,
        # with a list of step objects
        stepnames=re.split('[,\s]+',self.steps)
        steps=[]                   # just to make sure
        for sn in stepnames:
            step=Step(name=sn, pipeline=self)
            
            # load the step's template and self.update with the values:
            try:
                step.load()
            except IOError as ioe:
                die("Unable to load step %s" % sn, ioe)
            step.merge(readset)
            # print "pipeline.load: step after merge(readset) is %s" % step

            # add in items from step sections in <pipeline.syml>
            if not self.has_attr(step.name) or self[step.name] == None:
                die(ConfigError("Missing section: '%s' is listed as a step name in %s, but section with that name is absent." %
                                (step.name, self.template_file())))

            try:
                # print "pipeline: self[%s] is\n%s" % (step.name, self[step.name])
                step.update(self[step.name])
                # print "pipeline: step %s is\n%s" %(step.name, step)
            except KeyError as e:
                die("no %s in\n%s" % (step.name, yaml.dump(self.__dict__)))
                
            # print "pipeline: step %s:\n%s" % (step.name, yaml.dump(step))
            
            steps.append(step)
            
        self.steps=steps

        return self
    
    # return an entire shell script that runs the pipeline
    def sh_script(self):
        script="#!/bin/sh\n\n"
        for step in self.steps:
            script+="# %s\n" % step.name
            script+=step.sh_cmd()
            script+="\n"
        return script

    # get the working directory for the pipeline.
    # first ,check to see if the readset defines a working_dir
    # second, see if the pipeline itself defines a pipeline (it shouldn't)
    # each of the first two can be a directory, or a "policy".
    # valid policies include "timestamp" (and nothing else, for the moment)
    # If nothing found, use default found in config file under "default_working_dir"
    def working_dir(self):
        try:
            readset=self.readset
            readsfile=readset.reads_file
            base_dir=os.path.dirname(readsfile)
        except KeyError as ke:
            raise UserError(ke)

        try:
            wd=os.path.join(working_dir, self.working_dir)
            return wd
        except:
            pass

        try:
            wd=os.path.join(working_dir, readset.working_dir)
            return wd
        except:
            pass

        default='rnaseq_'+time.strftime("%d%b%y.%H%M%S")
        return os.path.join(base_dir, default)
