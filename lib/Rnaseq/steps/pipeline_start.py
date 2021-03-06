from Rnaseq import *
class pipeline_start(Step):

    def __init__(self, **kwargs):
        Step.__init__(self,**kwargs)
        self.is_prov_step=True

    def usage(self, context):
        if RnaseqGlobals.conf_value('debug'): self.debug='-d'
        else: self.debug=''

        usage='''
python ${root_dir}/bin/provenance pipeline_start ${pipeline_run_id} ${next_step_run_id} ${debug}
'''

        if self.debug:
            print "pipeline start: pipeline_run_id is %d" % self.pipeline_run_id
            print "pipeline start: next_step_run_id is %d" % self.next_step_run_id
            print "pipeline start: usage is %s" % usage
        return usage

    def outputs(self, *args):
        return []
    
