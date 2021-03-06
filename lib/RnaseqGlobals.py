#-*-python-*-
import os, sys, optparse, yaml, re, glob
from Rnaseq import *
from warn import *
from user_config import *

from sqlalchemy import *
from sqlalchemy.orm import sessionmaker

# This should really be a singleton class
class RnaseqGlobals(object):
    parser=''                           # gets overwritten
    options={}
    config={}
    dbh={}
    usage=''


    @classmethod
    def initialize(self, usage, **args):
        self.usage=usage
        try: self.testing=args['testing']
        except: self.testing=False
            
        self.define_opts()
        opt_list=sys.argv
        try: opt_list.extend(args['opt_list'])
        except KeyError as ke:
            if str(ke) != "'opt_list'": raise ke

        if self.testing:
            opt_list.append('-d')
        (values,argv)=self.parse_cmdline(opt_list=opt_list)
        self.values=values


        # set option values in config, in specific order:
        try: config_file=args['config_file']
        except: config_file=values.config_file # blow up if this doesn't work, but shouldn't since there's a default value
        self.read_config(config_file)
        self.verify_root_dir()
        self.fix_align_params()         # ugh (fixme)
        self.add_options_to_conf(values) # converts "__" entries, et al
        self.get_session()
        self.read_user_config()
        td=self.set_templated_dir()
        self.load_pipeline_templates(td)
        
        return argv

    @classmethod
    def verify_root_dir(self):
        if not self.conf_value('rnaseq','root_dir'):
            root_dir=os.path.normpath(os.path.join(__file__,'../..'))
            self.config['rnaseq']['root_dir']=root_dir
        root_dir=self.conf_value('rnaseq','root_dir')
        if not os.access(root_dir, os.R_OK | os.W_OK | os.X_OK):
            raise ConfigError(root_dir+": not a viable path (doesn't exist or permissions error; all access (including executable) needed")

    # return parsed argv
    @classmethod
    def define_opts(self):                    
        parser=optparse.OptionParser(self.usage)
        
        default_config_file=os.path.normpath(os.path.abspath(__file__)+"/../../config/rnaseq.conf.yml")

        # special notation: presence of '__' in dest means that options will get assigned to lower sub-hash of config
        # eg 'rnaseq__aligner'->self.config['rnaseq']['aligner']='bowtie'
        parser.add_option('--aligner',       dest='rnaseq__aligner', help="specify aligner", default="bowtie", type="string")
        parser.add_option('--align_suffix',  dest='rnaseq__align_suffix', help="internal use")
        parser.add_option('--fq_cmd',        dest='rnaseq__fq_cmd',  help="internal use")
        parser.add_option('--cluster',       dest='use_cluster',     help="execute operations on a cluster (requires additional config settings)", action='store_true', default=False)
        parser.add_option("-c","--config",   dest="config_file",     help="specify alternative config file", default=os.path.normpath(default_config_file))
        parser.add_option('-d',              dest='debug',           help='toggle debugging', action='store_true', default=False)
        parser.add_option("-f","--force",    dest="force",           help="force execution of pipelines and steps even if targets are up to date", action='store_true', default=False)
        parser.add_option('-l','--label',    dest='label',           help='specify a label for a pipeline run')
        parser.add_option("-n","--no_run",   dest="no_run",          help="supress actuall running", default=False, action='store_true')
        parser.add_option("-p","--pipeline", dest="pipeline_name",   help="pipeline name")
        parser.add_option('-q',"--quiet",    dest="silent",          help="supress diagnostics and other messages", action='store_true', default=False)
        parser.add_option("-r","--readset",  dest="readset_file",    help="readset filename")
        parser.add_option("--pr", "--pipeline-run", dest="pipeline_run_id", help="pipeline run id")
        parser.add_option('-u', "--user_config", dest='user_config_file', help="additional user specified parameters (config file)")
        parser.add_option("--use_template",  dest="use_template",    help="force generate pipeline from template, not db", action="store_true", default=False)
        parser.add_option('--user',          dest='user',            help='specify alternate user', default=os.environ['USER'])
        parser.add_option('-v','--verbose',  dest='verbose',         help='print addition progress messages', action='store_true', default=False)

        self.parser=parser


    # returns (values,args)
    @classmethod
    def parse_cmdline(self, opt_list=sys.argv):
        return self.parser.parse_args(sys.argv)

    @classmethod
    def read_config(self, config_file):
        try:
            f=open(config_file)
            yml=f.read()
            f.close()
            self.config=yaml.load(yml)

        except IOError as ioe:
            warn("error trying to load global config file:")
            die(UserError(ioe))


    @classmethod
    def add_options_to_conf(self, values):
        for o in self.parser.option_list:
            if o.dest==None: continue
            dest=str(o.dest)
            val=getattr(values,dest)
            dest_path=re.split('__',dest)
            c=self.config
            for dp in dest_path[:-1]:   # find subhash
                c=c[dp]
            c[dest_path[-1]]=getattr(values, dest) # set the final value


    @classmethod
    def conf_value(self,*args):
        if len(args)==0:
            raise MissingArgsException('conf_value: no args')

        conf=self.config
        for a in args:
            try:
                conf=conf[a]
            except KeyError:
                return None

        return conf

    @classmethod
    def root_dir(self):
        try: return self.conf_value('rnaseq','root_dir')
        except:
            root_dir=os.path.abspath(os.path.join(__file__,"../.."))
            self.set_conf_value('rnaseq','root_dir',root_dir)
            return root_dir
    
    # concat the root_dir with another dir listed in the config:
    @classmethod
    def abs_dir(self,*args):
        if len(args)==0:
            raise MissingArgsException('conf_value: no args')

        conf=self.config
        for a in args:
            try: conf=conf[a]
            except KeyError: return None
            
        abspath=os.path.join(self.root_dir(), conf)
        return abspath

    @classmethod
    def set_conf_value(self,keyslist,value): 
        config=self.config
        if (type(keyslist)==type("string")):
            keyslist=[keyslist]
        for k in keyslist[:-1]:
            config=config[k]

        config[keyslist[-1]]=value
        return self

    @classmethod
    def option(self,opt):
        try: return self.options.opt
        except AttributeError: return None

    @classmethod
    def get_session(self):
        debug=self.conf_value('debug')
        try: 
            return self.session
        except AttributeError: 
            db_name=self.get_db_file()
            self.make_db_dir(db_name)
            engine=create_engine('sqlite:///%s' % db_name, echo=False)
            warn("connected to %s" % (db_name))
            metadata=MetaData()

            # have to import these explicitly because we're in a classmethod: (or something)
            from Rnaseq import Pipeline, Step, Readset, StepRun, PipelineRun, FileOutput 
            classes=[Pipeline,Readset,PipelineRun,StepRun,FileOutput] # omit step
            tables={}
            for cls in classes:
                tables[cls]=cls.create_table(metadata,engine)

            Session=sessionmaker(bind=engine)
            session=Session()
            self.engine=engine
            self.metadata=metadata
            self.session=session
            return session

    @classmethod
    def get_db_file(self):
        if not self.testing:
            db_file=os.path.join(os.path.expanduser('~'+self.conf_value('user')),'.rnaseq','prob.db')
        else:
            db_file=self.conf_value('testing','test_db')
        return db_file


        # below is the old code
        db_name=self.conf_value('db','db_name') if not self.testing else self.conf_value('testing','test_db')
        db_file=os.path.join(self.conf_value('rnaseq','root_dir'), db_name)
        #print "get_db_file() returning %s" % db_file
        return db_file

    @classmethod
    def make_db_dir(self, db_file):
        try: os.makedirs(os.path.dirname(db_file))
        except Exception as e:
            if not re.search('File exists', str(e)):
                raise UserError("Unable to create directory %s: %s" %(os.path.dirname(db_file),e))
                         

    @classmethod
    def fix_align_params(self):
        aligner=self.values.rnaseq__aligner
        try:
            hash={'bowtie': { 'aligner_suffix':'fq',
                              'fq_cmd': 'solexa2fastq',
                              },
                  'blat': {'aligner_suffix':'fa',
                           'fq_cmd': 'solexa2fasta',
                           },
                  }
            subhash=hash[aligner]
        except KeyError as ke:
            raise optparse.OptionValueError("Unknown aligner: %s" % ke)

        try:
            parser=self.parser
            suffix=subhash['aligner_suffix']
            setattr(self.values, 'rnaseq__align_suffix', subhash['aligner_suffix'])
            setattr(self.values, 'rnaseq__fq_cmd', subhash['fq_cmd'])
        except Exception as e:
            #print "caught an %s: %s" % (type(e),e)
            raise optparse.OptionValueError(str(e))



    # process the user config file.  Sections that correspond to step names get their
    # contents merged into the step's dict.  Otherwise the values are merged into the
    # global config hash.
    # Returns self.
    @classmethod
    def read_user_config(self):
        user_config=UserConfig()
        setattr(self,'user_config',user_config)

        try: user_config.read(self.conf_value('user_config_file'))
        except IOError: return self

    # 
    @classmethod
    def set_user_step_params(self, pipeline):
        # override any listed step attributes:
        for k,v in self.user_config.items():
            step=pipeline.stepWithName(k)
            if step==None: self.set_conf_value(k,v)
            else:
                if type(v) != type({}):
                    raise ConfigError("In section %s of %s, the value must be a hash (ie, an indented section); got %s instead"
                                      % (k, user_config_file, type(v)))
                step.update(v)
        return self
                                     
    @classmethod
    def user_runs(self):
        return self.user_config.user_runs()


    ########################################################################

    @classmethod
    def set_templated_dir(self):
        from templated import templated # has to be here because it's a class method

        if self.testing:
            template_dir=self.abs_dir('testing', 'template_dir')
        else:
            template_dir=os.path.join(self.root_dir(),'templates')
        
        templated.template_dir=template_dir
        return template_dir
        

    @classmethod
    def has_local_qsub(self):
        rc=os.system('which qsub &> /dev/null')
        return rc==0


    ########################################################################
    @classmethod
    def load_pipeline_templates(self, template_dir):
        pl_glob=os.path.join(template_dir, 'pipeline', '*.syml')
        from Rnaseq import Pipeline     # stupid class method
        for pl_temp in glob.iglob(pl_glob):
            pipeline_name=re.sub('\.\w+$','',os.path.basename(pl_temp))
            pipeline=Pipeline(name=pipeline_name, path=pl_temp)
            pipeline.store_db()
               
            

            
    
#print __file__,"checking in"
