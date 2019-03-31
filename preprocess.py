import re

class Preprocessor(object):
    basename = ''
    text = ''
    headers = {}
    
    def __init__(self, basename, text):
        self.basename = basename
        self.text = text
                
        self.process()        
        
        
    def process(self):
        self.strip()
        
        # 불필요한 부분 삭제부터
        self.remove_comments()
        self.remove_if0_block()
        
        # 코드보정
        # self.correct_macro_funccall()
        
        # parsing을 위한 삭제 및 추출
        self.replace_extract_header()
        self.replace_extract_define()
        
        # 코드정리
        self.strip()
        
    # 주석제거
    def remove_comments(self):        
        def replacer(match):
            s = match.group(0)
            if s.startswith('/'):
                return " " # note: a space and not an empty string
            else:
                return s

        pattern = re.compile(r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"', re.DOTALL | re.MULTILINE)        
        self.text = re.sub(pattern, replacer, self.text)

    # 전처리 제거(#if0 ~ #endif)
    def remove_if0_block(self):
        rifa_pattern = re.compile('\s*#\s*if')
        rif0_pattern = re.compile('\s*#\s*if\s+0')    
        else_pattern = re.compile('\s*#\s*else')
        endif_pattern = re.compile('\s*#\s*endif')

        ifx_phrs_lv = -1
        
        # max depth : 5
        suppress = [None, None, None, None, None]
        results = []

        for i, line in enumerate(self.text.split('\n')):
            # ************************************
            # meet '#if' then level+1
            # ************************************
            if rifa_pattern.match(line):
                ifx_phrs_lv += 1
                suppress[ifx_phrs_lv] = False
                
                # ***********************************************
                # if nested, follow parent
                # ***********************************************
                if ifx_phrs_lv > 0 and suppress[ifx_phrs_lv-1]:
                    suppress[ifx_phrs_lv] = True
                    
                # ************************************
                # meet '#if 0' then suppress
                # ************************************
                elif rif0_pattern.match(line):
                    suppress[ifx_phrs_lv] = True
                
                #print(i, ifx_phrs_lv, suppress, ':', line)
                continue
            
            # ****************************************************
            # meet '#else' then toggle suppress
            # but, if nested, don't toggle
            # ****************************************************
            elif else_pattern.match(line):
                if ifx_phrs_lv > 0 and suppress[ifx_phrs_lv-1]:
                    pass
                else:
                    suppress[ifx_phrs_lv] = not suppress[ifx_phrs_lv]
                
                #print(i, ifx_phrs_lv, suppress, ':', line)
                continue
            
            # ****************************************************************
            # meet '#endif' then suppress Off and level-1
            # ****************************************************************
            elif endif_pattern.match(line):
                #print(i, ifx_phrs_lv, suppress, ':', line)
                suppress[ifx_phrs_lv] = None
                ifx_phrs_lv -= 1
                continue

            #print(i, ifx_phrs_lv, suppress, ':', line)
            
            if not suppress[ifx_phrs_lv]:
                results.append(line.rstrip())
                
        self.text = '\n'.join(results)
        
    # 원래 헤더는 따로 빼네고, 가짜 헤더를 넣어둠
    def replace_extract_header(self):
        dbio_header = []
        trxio_header = []
        module_header = []
        etc_header = []
        
        # 헤더 리스트 추출
        for item in re.findall('#\s*include\s*["<](\w+\.h)[">]', self.text):
            # pfm* 은 제외
            if item.startswith('pfm'):
                continue
            
            # dbio
            if item.startswith('pdb_'):
                dbio_header.append(item)
            # io header
            elif item.startswith('pio_'):
                trxio_header.append(item)
            # module, API
            elif re.match(r'z\w{3}[mb]\w{8}\.h', item):
                module_header.append(item)
            else:
                etc_header.append(item)
                
        self.headers = {
            'dbio': sorted(dbio_header),
            'trxio': sorted(trxio_header),
            'module': sorted(module_header),
            'etc': sorted(etc_header),
        }
        
        # 원래 헤더들은 모두 삭제하고, fake header만 추가해둠
        header_name = self.basename.replace('.c', '_fake.h')
        fake_header = ''
        fake_header += "#include <common_fake.h>\n"
        fake_header += "#include <{}>\n".format(header_name)
        
        self.text = fake_header + re.sub(r'#\s*include.*', '', self.text)
        
    # define 구문 삭제
    def replace_extract_define(self):
        def replacer(match):
            s = match.group(1)
            # TP INPUT 예약어는 skip
            if 'XXXINPT_1' in s or 'INPUT->' in s:
                return ''
            else:
                return match.group(0)
            
        # TODO : 매크로 함수 어떻게 처리할지...            
        self.text = re.sub(r'#\s*define\s+(.*)', replacer, self.text)
        
    # 매크로함수 ;으로 끝나지 않는거 보정 (컴파일시 오류는 안나지만, parsing하면 오류)
    def correct_macro_funccall(self):
        '''
        def replacer(match):
            print('asis', match.group(1))
            print('tobe', match.group(1) + ';')
            return match.group(1) + ';\n'
        
        pattern = re.compile(r'(\s*[A-Z]+[A-Z0-9_]*[A-Z]\s*\(.*?\)\s*)\n\s*[^,]')
        self.text = re.sub(pattern, replacer, self.text)
        '''
        lines = self.text.split('\n')
        results = []
        
        # ;로 없는 매크로 함수 호출코드 보정
        for i in range(len(lines) - 1):
            curr_line = lines[i].strip()
            next_line = lines[i+1].strip()
            
            if re.match(r'[A-Z][A-Z0-9_]+[A-Z]\s*\(.*?\)', curr_line) and not curr_line.endswith(';') and not next_line.startswith(','):
                result.append(curr_line + ';')
            else:
                results.append(curr_line)
        
    # \로 끝나는 라인들 하나로 합치기
    def merge_multiline_code(self):
        self.text = re.sub(r'\\\n', ' ', self.text)
    
    # 빈줄, 후행공백 제거
    def strip(self):
        self.text = '\n'.join([item.rstrip() for item in self.text.split('\n') if item.strip()])
        
    # 파일로 내보내기
    def export(self):
        with open(os.path.join('res/preproc', self.basename), 'w') as fp:
            fp.write(self.text)