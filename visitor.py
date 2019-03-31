from pycparser import c_ast
import os
import re
from . import const

class ModuleCallNameException(Exception): pass
class DbioCallNameException(Exception): pass

class Call(object):
    def __init__(self, caller, callee=None, kind=None, more=None):
        self.caller = caller        
        self.callee = callee
        self.kind = kind
        self.more = more
        
    def __repr__(self):
        return "{} → {} [{}/{}]".format(self.caller, self.callee, self.kind, self.more)


class IDVisitor(c_ast.NodeVisitor):
    def __init__(self, headers):
        self.headers = headers
        self.dbio_ids = []
        
    def visit_ID(self, node):
        # DBIO define변수 추출
        for item in self.headers['dbio']:
            # pdb_zngm_comm_cd_dtl_s1324.h --> ZNGM_COMM_CD_DTL_S1324
            dbio_name = re.match('pdb_(\w+)\.h', item).group(1).upper()
            
            # pattern1 : LEN_ZNGM_COMM_CD_DTL_COMM_CD_ID_I
            # pattern2 : AS_ZNGM_COMM_CD_DTL_S1324
            # pattern3 : SQLSZ_ZNGM_COMM_CD_DTL_S1324
            pattern1 = re.compile(r'LEN_{}_[A-Z0-9_]+_[IO]'.format(dbio_name))
            pattern2 = 'AS_' + dbio_name
            pattern3 = 'SQLSZ_' + dbio_name
            
            if pattern1.match(node.name) or node.name in [pattern2, pattern3]:
                self.dbio_ids.append((item, node.name))

        # 구현필요
        for item in self.headers['module']:
            pass


class FuncCallVisitor(c_ast.NodeVisitor):
    decls = []
    calls = []
    unknown = []
        
    def __init__(self, decls):
        self.decls = decls
        self.calls = []
        self.unknown = []
        self.ids = []

    def visit_FuncCall(self, node):

        # add func call
        def add_call(callee, kind, more=None):
            obj = kind, callee, more
            if obj not in self.calls:
                self.calls.append(obj)
        
        # unknown func call
        def add_unknown(callee):
            if callee not in self.unknown:
                self.unknown.append(callee)

        # check func is common API
        def is_comm_func(callee):
            return len([item for item in const.HEADERS if item[0] == callee]) > 0
        
        # header file(s) of API
        def get_comm_func_hdr(callee):
            return [item[1] for item in const.HEADERS if item[0] == callee]
            
        # SKIP대상인지
        def should_be_skipped(callee):
            if callee in const.EXCLUDE_FUNCS:
                return True
            
            for prefix in const.EXCLUDE_FUNC_PREFIX:
                if name.startswith(prefix):
                    return True
            
            return False
            
        try:
            name = node.name.name
            
            # DBIO : 1번째 인자가 DBIO명
            if name in const.DBIO_CALL_FUNCS:
                # Constant
                if isinstance(node.args.exprs[0], c_ast.Constant):
                    callee = node.args.exprs[0].value.replace('"', '')
                    more = name, c_ast.Constant.__name__
                # StructRef
                elif isinstance(node.args.exprs[0], c_ast.StructRef):
                    struct_name = node.args.exprs[0].name.name
                    sturct_field = node.args.exprs[0].field.name
                    callee = "{}.{}".format(struct_name, sturct_field)
                    more = name, c_ast.StructRef.__name__
                # ID
                elif isinstance(node.args.exprs[0], c_ast.ID):
                    callee = node.args.exprs[0].name
                    more = name, c_ast.ID.__name__
                # undefined
                else:
                    klass = node.args.exprs[0].__class__.__name__
                    callee = "{}({})".format('undefined', klass)
                    more = name, klass
                
                add_call(callee, 'DBIO', more)
            # 모듈 dlcall : 1번째 인자가 모듈명
            elif name == 'mpfm_dlcall':
                # Constant
                if isinstance(node.args.exprs[0], c_ast.Constant):
                    callee = node.args.exprs[0].value.replace('"', '')
                    more = 'mpfm_dlcall', c_ast.Constant.__name__
                # StructRef
                elif isinstance(node.args.exprs[0], c_ast.StructRef):
                    struct_name = node.args.exprs[0].name.name
                    struct_field = node.args.exprs[0].field.name
                    callee = "{}.{}".format(struct_name, struct_field)
                    more = 'mpfm_dlcall', c_ast.StructRef.__name__
                # ID
                elif isinstance(node.args.exprs[0], c_ast.ID):
                    callee = node.args.exprs[0].name
                    more = 'mpfm_dlcall', c_ast.ID.__name__
                else:
                    klass = node.args.exprs[0].__class__.__name__
                    callee = "{}({})".format('undefined', klass)
                    more = name, klass
                    
                add_call(callee, 'MODULE', more)
            # 모듈 main함수 직접 호출
            elif re.match('z[a-z]{3}m[0-9a-z]{8}', name):
                add_call(name, 'MODULE', 'main_call')
            # 소스내 static 함수
            elif name in self.decls:
                add_call(name, 'FUNCTION')
            # 공통API
            elif is_comm_func(name):
                add_call(name, 'API', get_comm_func_hdr(name))
            # 제외함수(c기본 함수, SWING공통함수 등)
            elif should_be_skipped(name):
                pass
            # Unknown
            else:
                add_unknown(name)
        except AttributeError as e:
            print(node, e)
            
        if node.args:
            self.visit(node.args)

class FuncDefVisitor(c_ast.NodeVisitor):
    def __init__(self, decls, headers):
        self.decls = decls
        self.headers = headers
        self.defns = []
        self.calls = []
        self.unknown = []
        self.ids = []
        
    def visit_FuncDef(self, node):
        # function definitions
        if node.decl.name not in self.defns:
            self.defns.append(node.decl.name)
        
        # func call relation
        fcv = FuncCallVisitor(self.decls)
        fcv.visit(node)

        if fcv.calls:
            for item in fcv.calls:
                obj = Call(caller=node.decl.name, callee=item[1], kind=item[0], more=item[2])
                self.calls.append(obj)
        else:
            # obj = node.decl.name, None, None, None
            obj = Call(node.decl.name)
            self.calls.append(obj)
        
        # I don't know what this function is
        for item in fcv.unknown:
            obj =  node.decl.name, item
            self.unknown.append(obj)

        # id list
        iv = IDVisitor(self.headers)
        iv.visit(node)

        for item in set(iv.dbio_ids):
            self.ids.append((node.decl.name, item[0], item[1], 'DBIO'))

        # next node
        if node.decl.type.args:
            self.visit(node.decl.type.args)


class SwingCVisitor(object):
    def __init__(self, ast, basename, headers):
        self.main = os.path.splitext(basename)[0]
        self.decls = []
        self.defns = []
        self.calls = []
        self.unknown = []
        self.ids = []
        self.outsiders = []
        
        # prototype 리스트 : FuncDecl Visitor로 찾으면 FuncDef 안에것도 찾기 때문에 따로 찾음
        for item in ast.ext:
            if isinstance(item, c_ast.Decl) and isinstance(item.type, c_ast.FuncDecl):
                self.decls.append(item.name)

        # 함수 정의 순회
        v = FuncDefVisitor(self.decls, headers)
        v.visit(ast)
        
        self.defns = v.defns
        self.calls = v.calls
        self.unknown = v.unknown
        self.ids = v.ids
