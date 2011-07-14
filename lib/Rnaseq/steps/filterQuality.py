from Rnaseq import *
class filterQuality(Step):
    def __init__(self,**kwargs):
        Step.__init__(self,**kwargs)
        self.name='filterQuality'
        self.description='Remove sequences with low quality scores'
        self.args='-v'

    def usage(self, context):
        if self.paired_end():
            i0=context.inputs[self.name][0]
            i1=context.inputs[self.name][1]
            print "filterQuality: i0=%s" % i0
            print "filterQuality: i1=%s" % i1
            
            usage='''
perl $${programs}/filterQuality.pl ${args} -f ${format} -i %s -o ${ID}.qual_OK_1.${format} -b ${ID}.qual_BAD_1.${format}
perl $${programs}/filterQuality.pl ${args} -f ${format} -i %s -o ${ID}.qual_OK_2.${format} -b ${ID}.qual_BAD_2.${format}
            ''' % (i0, i1)

        else:
            i0=context.inputs[self.name][0]
            print "i0=%s" % i0

            usage='''
perl $${programs}/filterQuality.pl ${args} -f $${format} -i %s -o ${ID}.qual_OK.${format} -b ${ID}.qual_BAD.${format}
            ''' % i0
            

        return usage

    def outputs(self):
        if self.paired_end():
            return ['${ID}.qual_BAD_1.${format}','${ID}.qual_BAD_1.${format}']
        else:
            return ['${ID}.qual_BAD.${format}']
    
