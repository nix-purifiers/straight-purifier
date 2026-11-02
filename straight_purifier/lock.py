# SPDX-License-Identifier: MIT
import hashlib,json,re,os
from pathlib import Path
FIX='; run straight-purifier lock'
NAME=r'[A-Za-z0-9][A-Za-z0-9_.+-]*'
IGNORED={'.git','straight','.straight-purifier','eln-cache','auto-save-list','__pycache__','result'}
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def seal(data):
 data={k:v for k,v in data.items() if k!='contentHash'}
 return {**data,'contentHash':hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()}
def inputs(root):
 result={}
 for directory,dirs,files in os.walk(root):
  dirs[:]=sorted(d for d in dirs if d not in IGNORED)
  for name in sorted(files):
   if name.endswith('.el'):
    p=Path(directory)/name;result[p.relative_to(root).as_posix()]=digest(p)
 return dict(sorted(result.items()))
def versions(path):
 text=Path(path).read_text();pattern=r'\("('+NAME+r')"\s*\.\s*"([0-9a-f]{40})"\)'
 pairs=re.findall(pattern,text);remaining=re.sub(pattern,'',text)
 if not re.fullmatch(r'\s*\(\s*\)\s*:epsilon\s*',remaining):raise ValueError('unsupported native Straight lock format'+FIX)
 result=dict(pairs)
 if len(result)!=len(pairs):raise ValueError('duplicate native repository'+FIX)
 return result
def problems(root,config,native,data):
 try:
  pins=versions(native)
  if not isinstance(data,dict) or data.get('version')!=1:return ['unsupported companion format'+FIX]
  if data.get('contentHash')!=seal(data)['contentHash']:return ['contentHash mismatch'+FIX]
  if data.get('nativeHash')!=digest(native) or data.get('configHash')!=digest(config) or data.get('inputs')!=inputs(root):return ['configuration or native lock changed'+FIX]
  repos=data.get('repositories')
  if not isinstance(repos,dict) or set(repos)!=set(pins) or 'straight.el' not in repos:return ['missing native repository metadata'+FIX]
  for name,m in repos.items():
   if not re.fullmatch(NAME,name) or name in ('.','..') or m.get('rev')!=pins[name]:return ['invalid native repository pin'+FIX]
   if not isinstance(m.get('url'),str) or not re.fullmatch(r'(https?://|ssh://|git@|file://|/)[^\s]+',m['url']):return ['unsupported Git URL'+FIX]
   if not re.fullmatch(r'sha256-[A-Za-z0-9+/]{43}=',m.get('hash','')):return ['missing Git NAR hash'+FIX]
   c=m.get('commitObject',{})
   if not isinstance(c.get('object'),str) or not isinstance(c.get('gitlinks'),list):return ['missing native Git commit metadata'+FIX]
  recipes=data.get('recipes')
  if not isinstance(recipes,list) or not all(isinstance(p,dict) and re.fullmatch(NAME,p.get('name','')) and isinstance(p.get('form'),str) for p in recipes):return ['invalid native recipes'+FIX]
  if len({p['name'] for p in recipes})!=len(recipes):return ['duplicate recipe'+FIX]
  if not isinstance(data.get('emacsVersion'),str) or not isinstance(data.get('recipeRepositories'),list):return ['missing native environment metadata'+FIX]
  return []
 except (OSError,ValueError,TypeError,KeyError) as error:return [str(error)+FIX]
