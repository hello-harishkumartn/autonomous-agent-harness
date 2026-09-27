"""Source fixtures for the public benchmark.

Hidden tests are kept out of the materialized agent repository until evaluation.
They are public in this open-source project so results remain auditable; "hidden"
describes the agent-time boundary, not secrecy from benchmark maintainers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    source: str
    public_test: str
    hidden_test: str


CASES: dict[str, Case] = {
    "bug-001": Case(
        "def clamp(value, minimum, maximum):\n    if value > maximum:\n        return minimum\n    return max(minimum, value)\n",
        "from solution import clamp\n\ndef test_inside(): assert clamp(5, 0, 10) == 5\n",
        "from solution import clamp\n\ndef test_edges():\n assert clamp(-1,0,10)==0\n assert clamp(11,0,10)==10\n assert clamp(0,0,10)==0\n",
    ),
    "bug-002": Case(
        "def normalize_email(value):\n    return value.lower()\n",
        "from solution import normalize_email\n\ndef test_case(): assert normalize_email('A@B.COM') == 'a@b.com'\n",
        "from solution import normalize_email\n\ndef test_space(): assert normalize_email('  A@B.COM \\n') == 'a@b.com'\n",
    ),
    "bug-003": Case(
        "def mean(values):\n    if not list(values): raise ValueError('empty')\n    return sum(values) / len(list(values))\n",
        "from solution import mean\n\ndef test_list(): assert mean([2,4]) == 3\n",
        "import pytest\nfrom solution import mean\n\ndef test_generator(): assert mean(x for x in [1,2,6]) == 3\ndef test_empty():\n with pytest.raises(ValueError): mean(iter([]))\n",
    ),
    "bug-004": Case(
        "def parse_bool(value):\n    return bool(value)\n",
        "from solution import parse_bool\n\ndef test_true(): assert parse_bool('true') is True\n",
        "import pytest\nfrom solution import parse_bool\n\ndef test_false():\n for value in ['false','0','no','off']: assert parse_bool(value) is False\ndef test_unknown():\n with pytest.raises(ValueError): parse_bool('maybe')\n",
    ),
    "feature-001": Case(
        "def chunked(items, size):\n    raise NotImplementedError\n",
        "from solution import chunked\n\ndef test_even(): assert chunked([1,2,3,4],2) == [[1,2],[3,4]]\n",
        "import pytest\nfrom solution import chunked\n\ndef test_remainder(): assert chunked(iter(range(5)),2)==[[0,1],[2,3],[4]]\ndef test_bad():\n with pytest.raises(ValueError): chunked([],0)\n",
    ),
    "feature-002": Case(
        "def unique(items):\n    raise NotImplementedError\n",
        "from solution import unique\n\ndef test_numbers(): assert unique([2,1,2]) == [2,1]\n",
        "from solution import unique\n\ndef test_unhashable(): assert unique([[1],[1],[2]]) == [[1],[2]]\n",
    ),
    "feature-003": Case(
        "def get_in(mapping, dotted_path, default=None):\n    raise NotImplementedError\n",
        "from solution import get_in\n\ndef test_nested(): assert get_in({'a':{'b':2}},'a.b') == 2\n",
        "from solution import get_in\n\ndef test_missing_and_immutable():\n data={'a':{}}\n assert get_in(data,'a.x',9)==9\n assert data=={'a':{}}\n",
    ),
    "feature-004": Case(
        "def retry_delays(attempts, base=1.0, cap=60.0):\n    raise NotImplementedError\n",
        "from solution import retry_delays\n\ndef test_basic(): assert retry_delays(3) == [1.0,2.0,4.0]\n",
        "import pytest\nfrom solution import retry_delays\n\ndef test_cap(): assert retry_delays(5,10,25)==[10,20,25,25,25]\ndef test_invalid():\n with pytest.raises(ValueError): retry_delays(-1)\n with pytest.raises(ValueError): retry_delays(2,0)\n",
    ),
    "refactor-001": Case(
        "import re\ndef slugify(value):\n value=value.strip().lower(); value=re.sub(r'[^a-z0-9]+','-',value); value=re.sub(r'-+','-',value); return value.strip('-')\n",
        "from solution import slugify\n\ndef test_slug(): assert slugify(' Hello,  World! ') == 'hello-world'\n",
        "import inspect\nimport solution\n\ndef test_behavior_and_helper():\n assert solution.slugify('A---B')=='a-b'\n helpers=[n for n,v in vars(solution).items() if n.startswith('_') and callable(v)]\n assert helpers, 'extract a private helper'\n",
    ),
    "refactor-002": Case(
        "def collect_errors(error, errors=[]):\n    errors.append(error)\n    return errors\n",
        "from solution import collect_errors\n\ndef test_collect(): assert collect_errors('a',[]) == ['a']\n",
        "from solution import collect_errors\n\ndef test_isolated():\n assert collect_errors('a')==['a']\n assert collect_errors('b')==['b']\n",
    ),
    "refactor-003": Case(
        "from dataclasses import dataclass\n@dataclass\nclass User:\n username:str\n email:str\n password_hash:str\n def to_dict(self): return {'username':self.username,'email':self.email}\n",
        "from solution import User\n\ndef test_safe(): assert User('u','e','secret').to_dict()=={'username':'u','email':'e'}\n",
        "from solution import User\n\ndef test_no_secret(): assert 'password_hash' not in User('u','e','x').to_dict()\n",
    ),
    "refactor-004": Case(
        "def status_label(code):\n if code==200:return 'ok'\n if code==400:return 'bad request'\n if code==404:return 'not found'\n if code==500:return 'server error'\n return 'unknown'\n",
        "from solution import status_label\n\ndef test_ok(): assert status_label(200)=='ok'\n",
        "import ast,inspect\nimport solution\n\ndef test_labels():\n assert solution.status_label(404)=='not found'\n assert solution.status_label(999)=='unknown'\n assert isinstance(next(v for v in vars(solution).values() if isinstance(v,dict)),dict)\n",
    ),
    "tests-001": Case(
        "def clamp(value, minimum, maximum):\n if minimum>maximum: raise ValueError('inverted')\n return min(maximum,max(minimum,value))\n",
        "from solution import clamp\n\ndef test_smoke(): assert clamp(2,0,3)==2\n",
        "from pathlib import Path\n\ndef test_added_boundaries():\n text=''.join(p.read_text() for p in Path('tests').glob('test*.py') if p.name!='test_public.py')\n assert text.count('assert')>=4\n assert 'ValueError' in text\n",
    ),
    "tests-002": Case(
        "def parse_port(value):\n port=int(value)\n if not 1<=port<=65535: raise ValueError('range')\n return port\n",
        "from solution import parse_port\n\ndef test_smoke(): assert parse_port('80')==80\n",
        "from pathlib import Path\n\ndef test_added_table():\n text=''.join(p.read_text() for p in Path('tests').glob('test*.py') if p.name!='test_public.py')\n assert '65535' in text and ('parametrize' in text or text.count('assert')>=4)\n",
    ),
    "tests-003": Case(
        "class TTLCache:\n def __init__(self,ttl,clock): self.ttl=ttl;self.clock=clock;self.data={}\n def set(self,k,v): self.data[k]=(v,self.clock())\n def get(self,k):\n  value,created=self.data[k]\n  if self.clock()-created>=self.ttl: raise KeyError(k)\n  return value\n",
        "def test_import():\n from solution import TTLCache\n assert TTLCache\n",
        "from pathlib import Path\n\ndef test_deterministic_tests_added():\n text=''.join(p.read_text() for p in Path('tests').glob('test*.py') if p.name!='test_public.py')\n assert 'sleep' not in text\n assert 'clock' in text and ('KeyError' in text or 'raises' in text)\n",
    ),
    "tests-004": Case(
        "import copy\ndef redact(value):\n out=copy.deepcopy(value)\n if isinstance(out,dict):\n  for k,v in out.items(): out[k]='***' if k.lower() in {'password','token','api_key'} else redact(v)\n return out\n",
        "from solution import redact\n\ndef test_simple(): assert redact({'password':'x'})=={'password':'***'}\n",
        "from pathlib import Path\n\ndef test_nested_immutable_tests_added():\n text=''.join(p.read_text() for p in Path('tests').glob('test*.py') if p.name!='test_public.py')\n assert 'api_key' in text and 'token' in text\n assert 'copy' in text or '==' in text\n",
    ),
    "api-001": Case(
        "def request(url, timeout):\n return {'url':url,'timeout':timeout}\n",
        "from solution import request\n\ndef test_call(): assert request('x',2)['timeout']==2\n",
        "import inspect,pytest\nfrom solution import request\n\ndef test_contract():\n assert request('x')['timeout']==5.0\n assert inspect.signature(request).parameters['timeout'].kind.name=='KEYWORD_ONLY'\n with pytest.raises(TypeError): request('x',2)\n",
    ),
    "api-002": Case(
        "def paginate(items,page,page_size):\n start=(page-1)*page_size\n return items[start:start+page_size]\n",
        "from solution import paginate\n\ndef test_items(): assert list(paginate([1,2,3],1,2))==[1,2]\n",
        "from solution import paginate\n\ndef test_page():\n p=paginate(list(range(7)),2,3)\n assert list(p)==[3,4,5] and p.page==2 and p.page_size==3 and p.total==7 and p.items==[3,4,5]\n",
    ),
    "api-003": Case(
        "def create_user(name): return {'username':name}\n",
        "from solution import create_user\n\ndef test_old(): assert create_user('a')['username']=='a'\n",
        "import pytest\nfrom solution import create_user\n\ndef test_contract():\n assert create_user(username='a')['username']=='a'\n assert create_user(name='b')['username']=='b'\n with pytest.raises(TypeError): create_user(username='a',name='b')\n",
    ),
    "api-004": Case(
        "def divide(a,b):\n return None if b==0 else a/b\n",
        "from solution import divide\n\ndef test_success(): assert divide(6,2)==3\n",
        "from solution import divide\n\ndef test_result():\n ok=divide(6,2); assert ok.ok and ok.value==3 and ok.error is None\n bad=divide(1,0); assert not bad.ok and bad.value is None and bad.error\n",
    ),
    "validation-001": Case(
        "def parse_host_port(value):\n host,port=value.split(':')\n return host,int(port)\n",
        "from solution import parse_host_port\n\ndef test_ipv4(): assert parse_host_port('localhost:80')==('localhost',80)\n",
        "import pytest\nfrom solution import parse_host_port\n\ndef test_ipv6(): assert parse_host_port('[::1]:443')==('::1',443)\ndef test_bad():\n for x in ['',':80','host:x','host:0','host:65536']:\n  with pytest.raises(ValueError): parse_host_port(x)\n",
    ),
    "validation-002": Case(
        "def validate_username(value): return True\n",
        "from solution import validate_username\n\ndef test_valid(): assert validate_username('alice_2') is True\n",
        "import pytest\nfrom solution import validate_username\n\ndef test_invalid():\n for x in ['ab','1alice','a-b','a'*33,'álfa']:\n  with pytest.raises(ValueError): validate_username(x)\n",
    ),
    "validation-003": Case(
        "def is_safe_archive_path(value): return '..' not in value\n",
        "from solution import is_safe_archive_path\n\ndef test_safe(): assert is_safe_archive_path('a/b.txt')\n",
        "from solution import is_safe_archive_path\n\ndef test_unsafe():\n for x in ['/etc/passwd','../x','a/../../x','C:/x','..\\\\x','C:\\\\x']: assert not is_safe_archive_path(x)\n",
    ),
    "validation-004": Case(
        "from datetime import datetime\ndef parse_date(value): return datetime.fromisoformat(value).date()\n",
        "from solution import parse_date\n\ndef test_date(): assert str(parse_date('2024-02-29'))=='2024-02-29'\n",
        "import pytest\nfrom solution import parse_date\n\ndef test_strict():\n for x in ['2023-02-29','2024-2-09','2024-02-9','2024-02-01T00:00:00']:\n  with pytest.raises(ValueError): parse_date(x)\n",
    ),
    "perf-001": Case(
        "def first_duplicate(values):\n for i,value in enumerate(values):\n  if value in values[:i]: return value\n return None\n",
        "from solution import first_duplicate\n\ndef test_dup(): assert first_duplicate([1,2,3,2])==2\n",
        "import time\nfrom solution import first_duplicate\n\ndef test_linear():\n values=list(range(30000))+[29999]\n start=time.monotonic(); assert first_duplicate(values)==29999\n assert time.monotonic()-start<1.0\n",
    ),
    "perf-002": Case(
        "import re\ndef extract_tags(text): return re.compile(r'<([a-zA-Z][^ >/]*)').findall(text)\n",
        "from solution import extract_tags\n\ndef test_tags(): assert extract_tags('<a><section>')==['a','section']\n",
        "import re,solution\n\ndef test_compiled_once():\n assert any(isinstance(v,type(re.compile(''))) for v in vars(solution).values())\n assert solution.extract_tags('<x></x>')==['x']\n",
    ),
    "perf-003": Case(
        "def count_nonempty_lines(lines): return len([line for line in list(lines) if line.strip()])\n",
        "from solution import count_nonempty_lines\n\ndef test_count(): assert count_nonempty_lines(['a',' ','b'])==2\n",
        "from solution import count_nonempty_lines\n\nclass OneShot:\n def __iter__(self):\n  yield from ('x\\n' if i%2 else '\\n' for i in range(100000))\ndef test_stream(): assert count_nonempty_lines(OneShot())==50000\n",
    ),
    "config-001": Case(
        "def load_config(defaults,config,environ):\n out=dict(config);out.update(defaults);return out\n",
        "from solution import load_config\n\ndef test_defaults(): assert load_config({'PORT':1},{},{})['PORT']==1\n",
        "import pytest\nfrom solution import load_config\n\ndef test_precedence(): assert load_config({'PORT':1,'X':'d'},{'PORT':2},{'ADEV_PORT':'3'})=={'PORT':3,'X':'d'}\ndef test_bad():\n with pytest.raises(ValueError): load_config({}, {}, {'ADEV_PORT':'x'})\n",
    ),
    "config-002": Case(
        "def configure_logging(level): raise NotImplementedError\n",
        "import logging\nfrom solution import configure_logging\n\ndef test_info(): configure_logging('INFO'); assert logging.getLogger().level==logging.INFO\n",
        "import logging,pytest\nfrom solution import configure_logging\n\ndef test_levels():\n configure_logging('debug');assert logging.getLogger().level==logging.DEBUG\n with pytest.raises(ValueError): configure_logging('verbose')\n",
    ),
    "config-003": Case(
        "def feature_enabled(name,environ,default=False): return bool(environ.get(name,default))\n",
        "from solution import feature_enabled\n\ndef test_true(): assert feature_enabled('X',{'X':'true'}) is True\n",
        "import pytest\nfrom solution import feature_enabled\n\ndef test_contract():\n assert feature_enabled('X',{},True) is True\n for x in ['false','0','no','off']: assert feature_enabled('X',{'X':x}) is False\n with pytest.raises(ValueError): feature_enabled('X',{'X':'maybe'})\n",
    ),
}
