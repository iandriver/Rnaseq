from Rnaseq import *

class test_step(Step):
    def __init__(self,**kwargs):
        Step.__init__(self,**kwargs)
        self.name='test_step'
        self.force=True
        self.skip_success_check=True

    def usage(self, context):
        return "echo "+self.name+"(test): "+' '.join(context.inputs)

    def output_list(self,*args):
        if self.paired_end():
            return ['${ID}_1.%s.${format}' % self.name, '${ID}_2.%s.${format}' % self.name]
        else:
            return ['${ID}.%s.${format}' % self.name]
