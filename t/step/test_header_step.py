import unittest, os, sys, re

dir=os.path.normpath(os.path.dirname(os.path.abspath(__file__))+"/../..")
sys.path.append(os.path.join(dir+'/lib'))
sys.path.append(os.path.join(dir+'/ext_libs'))


from Rnaseq import *
from RnaseqGlobals import *
from warn import *


class TestHeaderStep(unittest.TestCase):
    def setUp(self):
        argv=RnaseqGlobals.initialize(__file__, testing=True)       # not to be confused with sys.argv

        readset_file=RnaseqGlobals.root_dir()+'/t/fixtures/readsets/readset1.syml'
        rlist=Readset.load(readset_file)
        self.readset=rlist[0]
        self.pipeline=Pipeline.get_pipeline(name='link', readset=self.readset).load_steps()

    def test_setup(self):
        self.assertEqual(self.readset.name, 'readset1.syml')
        self.assertEqual(self.pipeline.name, 'link')
        self.assertTrue(self.pipeline.context != None)
        
    #def test_header_script(self):
        #header_step=self.pipeline.step_with_name('header')
        

    def test_readset_exports(self):
        header_step=self.pipeline.step_with_name('header')
        script=header_step.sh_script(self.pipeline.context)
        for ex in self.readset.exports:
            target='export %s=%s' % (ex, getattr(self.readset, ex))
            self.assertRegexpMatches(script, target)
            #print >>sys.stderr, "got %s" % target


    def test_links(self):
        header_step=self.pipeline.step_with_name('header')
        script=header_step.sh_script(self.pipeline.context)
        for rf in self.readset.reads_files:
            target='ln -fs %s %s' % (rf, self.readset.working_dir)
            self.assertRegexpMatches(script, target)
            #print >>sys.stderr, "got %s" % target

suite = unittest.TestLoader().loadTestsFromTestCase(TestHeaderStep)
unittest.TextTestRunner(verbosity=2).run(suite)
