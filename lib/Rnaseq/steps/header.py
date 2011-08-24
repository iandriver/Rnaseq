from Rnaseq import *

class header(Step):
    def __init__(self,**kwargs):
        Step.__init__(self,**kwargs)
        self.name='header'
        self.force=True
        self.skip_success_check=False

    def usage(self, context):
        path=RnaseqGlobals.conf_value('rnaseq','path')

        readset=self.pipeline.readset
        export_block=''
        for attr in readset.exports:
            try: export_block+="export %s=%s\n" % (attr, getattr(readset, attr))
            except AttributeError: pass

        if RnaseqGlobals.conf_value('debug'): self.debug='-d'
        else: self.debug=''
        
        template='''
echo
echo '****************************************************************'
echo starting ${pipeline.name}
date
echo

echo 1>&2
echo 1>&2 '****************************************************************'
echo 1>&2 starting ${pipeline.name}
date 1>&2
echo 1>&2


# exit script if any variable unset:
set -u


root_dir=${root_dir}
programs=$${root_dir}/programs
export PATH=%(path)s:$${root_dir}/programs
export PYTHONPATH=$${PYTHONPATH:-}:$${root_dir}/lib


# readset exports:
%(readset_exports)s

cd $${working_dir}

exit_on_failure()
{
  retcode=$$1
  pipelinerun_id=$$2
  step_id=$$3
  next_step_id=$$4

  python $${root_dir}/bin/provenance mid_step $${pipelinerun_id} $${step_id} $${next_step_id} $${retcode} ${debug}


  if [ $$retcode != 0 ]; then
    echo step $${step_id} failed 1>&2
    exit $$retcode
  else
    echo step $${step_id} passed 1>&2
  fi
}

''' % {'path':path, 'readset_exports':export_block}
        restore_indent=True

        # add link part if necessary:
        # Is necessary if original location of data is different from working_dir:
        link_part=''
        if os.path.dirname(readset.reads_files[0]) != readset.working_dir:
            for rf in readset.reads_files:
                link_part+="ln -fs %s %s" % (rf, readset.working_dir)
        template+=link_part
            
        return template
        
    ########################################################################

    # This shouldn't call self.input_list(), because it sets up a circular dependency
    # in conjunction with pipeline.convert_io().  
    def output_list(self,*args):
        readset=self.pipeline.readset
        list=[]
        if self.paired_end():
            list.extend(['${ID}_1.${format}', '${ID}_2.${format}'])
        else:
            working_dir=readset.working_dir
            for rf in readset.reads_files:
                basename=os.path.basename(rf)
                list.append(os.path.join(working_dir, basename))

        return list
        
