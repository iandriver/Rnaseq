#-*-python-*-

import yaml, socket, os, glob
from sqlalchemy import *
from warn import *

class Readset(dict):
    required_attrs=['reads_file']
    def __init__(self,*args,**kwargs):
        self.suffix='syml'
        self.type='readset'
        for k,v in kwargs.items():
            setattr(self,k,v)
            self[k]=v
        
        
    ########################################################################
        
    __tablename__='readset'

    @classmethod
    def create_table(self, metadata, engine):
        readset_table=Table(self.__tablename__, metadata,
                            Column('id',Integer, primary_key=True),
                            Column('name',String,nullable=False),
                            Column('reads_file', String),
                            Column('org', String),
                            Column('readlen', Integer),
                            Column('working_dir', String),
                            useexisting=True,
                         )
        metadata.create_all(engine)
        return readset_table
        
    ########################################################################

    def load(self):
        try: filename=self.filename
        except AttributeError: filename=self.name+'.syml'
            
        try:
            f=open(filename)
            yml=yaml.load(f)
            f.close()
        except IOError as ioe:
            raise UserError(str(ioe))
        except AttributeError as ae:
            raise ProgrammerGoof(ae)
        except yaml.scanner.ScannerError as se:
            msg='''
There was an error in the readset file %s:\n%s.
This file must be in correct YAML format.  Please carefully check the file and correct the error.
See http://en.wikipedia.org/wiki/YAML#Sample_document for details and examples.
'''
            msg = msg % (filename, str(se))
            raise ConfigError(msg)
        
        self.update(yml)
        for k,v in yml.items():
            setattr(self,k,v)

        self.verify_complete(filename)          # throws UserException
        return self

    def verify_complete(self, filename):
        missing=[]
        for attr in self.required_attrs:
            if not hasattr(self,attr): missing.append(attr)
        if len(missing) > 0:
            raise UserError(("The readset in %s is missing required fields:\n\t - " % filename) + "\n\t - ".join(missing))


    ########################################################################

    def get_email(self):
        try:
            return self.email
        except AttributeError:
            user=os.environ['USER']
            suffix=".".join(socket.gethostname().split('.')[-2:])
            return "@".join((user,suffix))

    def path_iterator(self):
        try:
            l=glob.glob(self['reads_files'])
        except Exception:
            l=glob.glob(self['reads_file']) # danger! will get overwritten!

        l.sort()
        return l


    def readsfile(self,*args):
        try: self['reads_file']=args[0]
        except IndexError: pass
        return self['reads_file']

    def next_reads_file(self):
        try: path_it=self.current_path_list
        except AttributeError: setattr(self,'current_path_list',self.path_iterator())

        try: next_rf=self.current_path_list[0]
        except IndexError: return None

        del self.current_path_list[0]
        return next_rf
