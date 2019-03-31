from swingc.parser import SwingCParser
from itertools import chain
import re

class SwingCAnalyzer(object):
    def __init__(self, parser):
        self.parser = parser
        self.basename = parser.basename
        self.analyze()

    def analyze(self):
        self.track_unmatched_funcs()
        self.track_unreachable_funcs()
        self.track_gray_dbio()
        self.track_gray_module()

    def track_unmatched_funcs(self):
        v = self.parser.visit

        # 정의 <-> 선언간 정합성 체크
        self.only_decls = [item for item in v.decls if item not in v.defns]
        self.only_defns = [item for item in v.defns if item not in v.decls if item != v.main]

    def track_unreachable_funcs(self):
        # 호출되지 않는 static 함수
        v = self.parser.visit

        callees = []
        real_calls = []
        outsiders = []

        real_calls = v.calls.copy()

        # 호출안되는 함수가 없어질때까지 반복
        while True:
            callees = set([item.callee for item in real_calls if item.callee in v.defns])
            outsiders.extend([item for item in v.defns if item not in callees and item != v.main])

            # filter해도 동일하면 종료
            if len(real_calls) == len([item for item in real_calls if item.caller not in outsiders]):
                break
            # filter한 결과가 다르면 삭제된 call이 있으므로 갱신하고 다시 loop
            else:
                real_calls = [item for item in real_calls if item.caller not in outsiders]

        self.real_calls = real_calls
        self.outsiders = sorted(set(outsiders))

    def track_gray_dbio(self):
        # 호출안하는 DBIO리스트 확인
        v = self.parser.visit
        p = self.parser.pre

        inc_only_dbios = []
        zero_call_dbios = []
        len_only_dbios = []
        dynamic_dbio_calls = []

        for header_file in p.headers['dbio']:
            dbio_name = re.match(r'pdb_(\w+)\.h', header_file).group(1)

            all_dbio_calls = [item.callee for item in v.calls if item.kind == 'DBIO']
            real_dbio_calls = [item.callee for item in self.real_calls if item.kind == 'DBIO']

            dynamic_dbio_calls = [item.callee for item in self.real_calls if item.kind == 'DBIO' and item.more[1] != 'Constant']
            dbio_len_ids = [item[1] for item in v.ids if item[3] == 'DBIO' and item[0] not in self.outsiders]

            # DBIO 호출이 아예  없을 경우 : include만 해둔 경우
            if dbio_name not in all_dbio_calls:
                if header_file in dbio_len_ids:
                    len_only_dbios.append(dbio_name)
                else:
                    inc_only_dbios.append(dbio_name)
            # DBIO 호출부가 있지만, 실제 call tree에는 없는 경우 : 호출되지 않는 함수내부에 있거나...
            elif dbio_name not in real_dbio_calls:
                zero_call_dbios.append(dbio_name)

        # 중복 제거
        self.inc_only_dbios = sorted(set(inc_only_dbios))
        self.zero_call_dbios = sorted(set(zero_call_dbios))
        self.len_only_dbios = sorted(set(len_only_dbios))
        self.dynamic_dbio_calls = sorted(set(dynamic_dbio_calls))

    def track_gray_module(self):
        # 호출안하는 모듈리스트 확인
        v = self.parser.visit
        p = self.parser.pre

        inc_only_modules = []
        zero_call_modules = []
        dynamic_call_modules = []

        for item in p.headers['module']:
            all_api_modules = set(chain.from_iterable([item.more for item in v.calls if item.kind == 'API']))
            all_call_modules = set([item.callee + '.h' for item in v.calls if item.kind == 'MODULE'])

            real_api_modules = set(chain.from_iterable([item.more for item in self.real_calls if item.kind == 'API']))
            real_call_modules = set([item.callee + '.h' for item in self.real_calls if item.kind == 'MODULE'])
            
            dynamic_call_modules = set([item.callee for item in self.real_calls if item.kind == 'MODULE' and item.more[1] != 'Constant'])

            # if module's main header, skip
            if item.startswith(v.main):
                continue
                
            # API or 모듈 호출이 아예 없을 경우
            if item not in all_api_modules and item not in all_call_modules:
                inc_only_modules.append(item)
            # API or 모듈 호출은 있으나 call tree에 없는 경우
            elif item not in real_api_modules and item not in real_call_modules:
                zero_call_modules.append(item)

        # 중복 제거
        self.inc_only_modules = sorted(set(inc_only_modules))
        self.zero_call_modules = sorted(set(zero_call_modules))

    def show(self):
        def head(text):
            print('\n##', text)

        def iter_print(obj, title):
            if bool(obj):
                head(title)
                for idx, item in enumerate(obj):
                    print("-", item)

        iter_print(self.only_decls, '선언(prototype)만 있는 함수')
        iter_print(self.only_defns, '정의(definition)만 있는 함수')
        iter_print(self.outsiders, '호출되지 않는 static 함수')
        iter_print(self.inc_only_dbios, 'INCLUDE만 되어있는 DBIO')
        iter_print(self.len_only_dbios, 'LEN변수만 참조하고 있는 DBIO')
        iter_print(self.zero_call_dbios, '로직상 호출되지 않는 DBIO')
        iter_print(self.inc_only_modules, 'INCLUDE만 되어있는 모듈/API')
        iter_print(self.zero_call_modules, '로직상 호출되지 않는 모듈/API')
        
    def export(self):
        export_dict = {}
        
        def set(name, obj):
            if bool(obj):
                export_dict[name] = obj

        set('only_decls', self.only_decls)
        set('only_defns', self.only_defns)
        set('outsiders', self.outsiders)
        set('inc_only_dbios', self.inc_only_dbios)
        set('len_only_dbios', self.len_only_dbios)
        set('zero_call_dbios', self.zero_call_dbios)
        set('inc_only_modules', self.inc_only_modules)
        set('zero_call_modules', self.zero_call_modules)
        
        return export_dict
