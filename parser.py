import os
import re
from pycparser import parse_file
from pycparser.plyparser import ParseError
from subprocess import CalledProcessError

from swingc.preprocess import Preprocessor
from swingc.visitor import SwingCVisitor

PREPROC_PATH = 'res/preproc'
AST_PATH = 'res/ast'

class SwingCParser(object):
    def __init__(self, filename):
        self.filename = filename
        self.basename = os.path.basename(self.filename)

        self.process()
            
    def process(self):
        # preprocess and export
        with open(self.filename, 'r', encoding='cp949') as fp:
            self.pre = Preprocessor(self.basename, fp.read())
            
        self.generate_fake_header()
        self.export_src_text()
        
        # build ast and traverse        
        try:
            self.ast = parse_file(os.path.join(PREPROC_PATH, self.basename), use_cpp=True, cpp_path='clang', cpp_args=['-E', r'-Iheaders'])
            self.visit = SwingCVisitor(self.ast, self.basename, self.pre.headers)
        except ParseError as e:
            print(self.basename, e)
        except CalledProcessError as e:
            print(self.basename, e)
            
    def get_struct_list(self):
        struct_list = list(set(re.findall(r'\s*(\w+_t)\s+', self.pre.text)))
        typedef_list = re.findall(r'\n\s*typedef\s+struct\s+\w+\s+(\w+_t);\s+', self.pre.text)
        struct_def_list = re.findall(r'\n\s*struct\s+\w+\s*\{.*?\}\s*(\w+_t)\s*;', self.pre.text, re.MULTILINE | re.DOTALL)

        self.structs = sorted([item for item in struct_list if item not in typedef_list and item not in struct_def_list])
            
    def generate_fake_header(self):
        self.get_struct_list()
        self.fake_header = os.path.join('headers', os.path.splitext(self.basename)[0] + '_fake.h')
        
        # generate fake header for pycparser
        with open(self.fake_header, 'w') as fp:
            # typdef struct statement
            for struct in self.structs:
                fp.write("typedef int {};\n".format(struct))
                
    def export_src_text(self):
        with open(os.path.join(PREPROC_PATH, self.basename), 'w') as fp:
            fp.write(self.pre.text)