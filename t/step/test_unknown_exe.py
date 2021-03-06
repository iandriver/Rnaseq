import unittest, os, re, sys

dir=os.path.normpath(os.path.dirname(os.path.abspath(__file__))+"/../..")
sys.path.append(os.path.join(dir+'/lib'))
sys.path.append(os.path.join(dir+'/ext_libs'))

from Rnaseq import *
from RnaseqGlobals import *
from warn import *

class TestBase(unittest.TestCase):
    def test_unknown_exe(self):
        templated.template_dir=os.path.normpath(os.path.abspath(__file__)+"/../../fixtures/templates")
        RnaseqGlobals.initialize(__file__, testing=True)
        #readset=Readset(reads_file=os.path.abspath(__file__+'/../../readset/s_1_export.txt'), label='label').resolve_working_dir().set_ID()
        readset_file=os.path.join(RnaseqGlobals.root_dir(),'t','fixtures','readsets','readset1.syml')
        readset=Readset.load(readset_file)[0]
        pipeline=Pipeline(name='juan', readset=readset).load_steps() # dying on badly configured i/o

        try:
            self.assertNotEqual(pipeline.context, None)
        except AttributeError:
            self.fail()

        try:
            step_factory=StepFactory()
            unknown_step=step_factory.new_step(pipeline, 'unknown')
            self.fail()
        except ConfigError as ce:
            # print "ce is %s" % ce
            self.assertTrue(re.search("error loading step 'unknown'", str(ce)))

suite = unittest.TestLoader().loadTestsFromTestCase(TestBase)
unittest.TextTestRunner(verbosity=2).run(suite)
