import unittest, os, sys, yaml

sys.path.append(os.path.normpath(os.path.abspath(__file__)+"/../../../lib"))
from Rnaseq import *
from RnaseqGlobals import *
from warn import *

class TestShScript(unittest.TestCase):
    def setUp(self):
        argv=RnaseqGlobals.initialize(__file__, testing=True)       # not to be confused with sys.argv
        RnaseqGlobals.set_conf_value('silent', True)
        template_dir=RnaseqGlobals.abs_dir('testing', 'template_dir')
        templated.template_dir=template_dir
        readset_file=RnaseqGlobals.root_dir()+'/t/fixtures/readsets/paired1.syml'
        self.readset=Readset.load(filename=readset_file)[0]
        self.pipeline=Pipeline(name='cufflinks', readset=self.readset).load_steps()



    def test_setup(self):
        self.assertIsInstance(self.pipeline, Pipeline)


    # test to see if there is exactly one instance of 'exit_on_failure' in the script
    # I guess it assumes we're not including provenance calls between steps...
    def test_exit_func(self):
        reads_path=self.readset.reads_file
        
        self.readset['reads_file']=reads_path
        pipeline=Pipeline(name='filter', readset=self.readset)            
        pipeline.load_steps()
        script=pipeline.sh_script(force=True)

        mg=re.search('exit_on_failure',script)
        self.assertEqual(mg.group(0),'exit_on_failure') # this is from the header, should be only one
        try:
            mg.group(1)
            self.Fail()
        except Exception as e:
            self.assertEqual(str(e),'no such group')






suite = unittest.TestLoader().loadTestsFromTestCase(TestShScript)
unittest.TextTestRunner(verbosity=2).run(suite)
