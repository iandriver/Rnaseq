import unittest, os, sys

sys.path.append(os.path.normpath(os.path.abspath(__file__)+"/../../../lib"))
from Rnaseq import *
from RnaseqGlobals import *
from warn import *

class TestInputs(unittest.TestCase):
    def setUp(self):
        argv=RnaseqGlobals.initialize(__file__, testing=True)       # not to be confused with sys.argv
        template_dir=RnaseqGlobals.abs_dir('testing', 'template_dir')
        templated.template_dir=template_dir
        self.readset=Readset(name='readset').load()
        self.pipeline=Pipeline(name='filter', readset=self.readset)
        self.pipeline.load_steps()

class TestListExpansion(TestInputs):
    def runTest(self):
        step=self.pipeline.stepWithName('export2fq')
        self.assertTrue(isinstance(step, Step))
        self.assertEqual(step.inputs()[0], self.readset.reads_file)
        self.assertEqual(step.outputs()[0], "%s.fq" % self.readset.reads_file)




if __name__=='__main__':
    unittest.main()

