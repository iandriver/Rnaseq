from Rnaseq import *
from Rnaseq.steps.test_step import test_step

class step2(test_step):
    def __init__(self,**kwargs):
        Step.__init__(self,**kwargs)
        self.name='step2'

    def outputs(self):
        return ['${ID}.step2a.${format}','${ID}.step2b.${format}']
        
        
