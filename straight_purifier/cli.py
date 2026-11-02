# SPDX-License-Identifier: MIT
import argparse,base64,hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
from . import lock
EMACS=os.environ.get('STRAIGHT_PURIFIER_EMACS','emacs')
BOOTSTRAP='3ad4414072ba512e39e19e8a7101bdfcb8318410'
def run(args,**kw):return subprocess.run(list(map(str,args)),check=True,**kw)
def read(p):return json.loads(p.read_text())
def write(p,text):
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('w',dir=p.parent,delete=False) as f:f.write(text);tmp=Path(f.name)
 tmp.replace(p)
def checked(root,config,native,sidecar):
 data=read(sidecar)
 if errors:=lock.problems(root,config,native,data):raise ValueError('\n'.join(errors))
 return data
def do_lock(root,config,native,sidecar,update=False,names=()):
 previous=None
 if sidecar.exists():
  try:
   candidate=read(sidecar)
   if candidate.get('contentHash')==lock.seal(candidate)['contentHash']:previous=candidate
   if not update and candidate.get('emacsVersion')==os.environ.get('STRAIGHT_PURIFIER_EMACS_VERSION',candidate.get('emacsVersion')) and not lock.problems(root,config,native,candidate):print('Existing native resolution retained');return
  except (ValueError,OSError,TypeError):pass
 if names and not previous:raise ValueError('named updates need an existing valid lock'+lock.FIX)
 if names and set(names)-{p['name'] for p in previous['recipes']}:raise ValueError('update names are not locked'+lock.FIX)
 with tempfile.TemporaryDirectory(prefix='straight-purifier-') as temp:
  temp=Path(temp);stage=temp/'profile'
  shutil.copytree(root,stage,ignore=shutil.ignore_patterns(*lock.IGNORED))
  staged_config=stage/config.relative_to(root) if config.is_relative_to(root) else stage/'packages.el'
  staged_config.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(config,staged_config)
  staged_native=stage/'straight/versions/default.el';staged_native.parent.mkdir(parents=True,exist_ok=True)
  seed=native if native.exists() else root/'straight/versions/default.el'
  if seed.exists():shutil.copyfile(seed,staged_native)
  try:pins=lock.versions(staged_native) if staged_native.exists() else {}
  except ValueError:
   pins={name:m['rev'] for name,m in (previous or {}).get('repositories',{}).items()}
   staged_native.unlink()
   if pins:write(staged_native,'('+ '\n '.join('("'+name+'" . "'+rev+'")' for name,rev in sorted(pins.items()))+')\n:epsilon\n')
  url=(previous or {}).get('repositories',{}).get('straight.el',{}).get('url','https://github.com/radian-software/straight.el.git')
  working=root/'straight/repos/straight.el'
  if not previous and (working/'.git').exists():url=run(['git','-C',working,'remote','get-url','origin'],text=True,capture_output=True).stdout.strip()
  checkout=stage/'straight/repos/straight.el';checkout.parent.mkdir(parents=True,exist_ok=True)
  run(['git','clone','--quiet','--no-checkout',url,checkout])
  run(['git','-C',checkout,'checkout','--quiet',pins.get('straight.el',BOOTSTRAP)])
  env={**os.environ,'HOME':str(temp/'home'),'STRAIGHT_PURIFIER_LOCKING':'1','STRAIGHT_PURIFIER_STAGE':str(stage),'STRAIGHT_PURIFIER_CONFIG':str(staged_config),'STRAIGHT_PURIFIER_RESOLUTION':str(temp/'resolution.json')}
  Path(env['HOME']).mkdir();env.pop('EMACSLOADPATH',None)
  if update:env['STRAIGHT_PURIFIER_UPDATE']=json.dumps(list(names))
  run([EMACS,'--batch','-Q','--load',os.environ['STRAIGHT_PURIFIER_RESOLVER']],env=env)
  data=read(temp/'resolution.json')
  for name,m in data['repositories'].items():
   cached=(previous or {}).get('repositories',{}).get(name)
   if cached and all(cached.get(k)==m[k] for k in ('url','rev')):
    m.update(hash=cached['hash'],commitObject=cached['commitObject']);continue
   result=json.loads(run(['nix-prefetch-git','--url',m['url'],'--rev',m['rev'],'--fetch-submodules'],text=True,capture_output=True).stdout)
   m['hash']=run(['nix','hash','convert','--hash-algo','sha256','--to','sri',result['sha256']],text=True,capture_output=True).stdout.strip()
   repo=stage/'straight/repos'/name
   obj=run(['git','-C',repo,'cat-file','commit',m['rev']],capture_output=True).stdout
   tree=run(['git','-C',repo,'ls-tree','-rz',m['rev']],capture_output=True).stdout
   links=[]
   for record in tree.split(b'\0'):
    if record:
     header,path=record.split(b'\t',1);mode,kind,rev=header.split()
     if mode==b'160000':links.append({'path':path.decode(),'rev':rev.decode()})
   m['commitObject']={'object':base64.b64encode(obj).decode(),'gitlinks':links}
  data.update(version=1,nativeHash=lock.digest(staged_native),configHash=lock.digest(config),inputs=lock.inputs(root));data=lock.seal(data)
  write(native,staged_native.read_text())
  if errors:=lock.problems(root,config,native,data):raise ValueError('\n'.join(errors))
  write(sidecar,json.dumps(data,sort_keys=True,indent=2)+'\n')
 print('Locked native Straight repositories')
def prepare(root,config,native,sidecar):
 checked(root,config,native,sidecar)
 state=sidecar.parent/'.straight-purifier'/hashlib.sha256(str(sidecar).encode()).hexdigest()[:12];state.mkdir(parents=True,exist_ok=True)
 for target in ('environment','runtime'):
  run(['nix','build','--impure','--file',os.environ['STRAIGHT_PURIFIER_REALIZE'],'--argstr','project',root,'--argstr','configFile',config,'--argstr','nativeLock',native,'--argstr','lockFile',sidecar,'--argstr','target',target,'--out-link',state/target])
 return (state/'environment').resolve()
def configuration_root(args):
 for i,a in enumerate(args):
  if a.startswith('--init-directory='):return Path(a.split('=',1)[1]).expanduser().resolve()
  if a=='--init-directory' and i+1<len(args):return Path(args[i+1]).expanduser().resolve()
 cwd=Path.cwd()
 if (cwd/'straight-purifier.lock.json').exists() or (cwd/'packages.el').exists():return cwd
 legacy=Path.home()/'.emacs.d'
 return legacy if legacy.exists() else Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'emacs'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--project');parser.add_argument('--config');parser.add_argument('--lockfile',default=os.environ.get('STRAIGHT_PURIFIER_LOCKFILE'));parser.add_argument('--native-lock',default=os.environ.get('STRAIGHT_PURIFIER_NATIVE_LOCKFILE'))
 sub=parser.add_subparsers(dest='command',required=True);sub.add_parser('lock');p=sub.add_parser('update');p.add_argument('names',nargs='*');p=sub.add_parser('prefetch');p.add_argument('--json',action='store_true');p=sub.add_parser('native');p.add_argument('args',nargs=argparse.REMAINDER)
 args=parser.parse_args();native_args=(args.args[1:] if args.args[:1]==['--'] else args.args) if args.command=='native' else []
 root=Path(args.project).expanduser().resolve() if args.project else configuration_root(native_args)
 config=Path(args.config).expanduser().resolve() if args.config else root/('init.el' if (root/'init.el').exists() else 'packages.el')
 native=Path(args.native_lock).expanduser().resolve() if args.native_lock else root/'straight/versions/default.el'
 sidecar=Path(args.lockfile).expanduser().resolve() if args.lockfile else root/'straight-purifier.lock.json'
 if args.command=='native':
  if not sidecar.exists() or os.environ.get('STRAIGHT_PURIFIER_LOCKING'):
   print('straight-purifier: no lockfile; using ordinary impure Emacs',file=sys.stderr);os.execv(EMACS,[EMACS,*native_args])
  if '--no-site-file' in native_args and not any(x in native_args for x in ('-Q','--quick','-q','--no-init-file','--batch')):raise ValueError('--no-site-file prevents activation before init; omit it for locked startup')
  environment=prepare(root,config,native,sidecar)
  os.environ['STRAIGHT_PURIFIER_ROOT']=str(root)
  os.environ['EMACSLOADPATH']=str(environment/'site-lisp')+':'+os.environ.get('EMACSLOADPATH','')
  os.execv(EMACS,[EMACS,'--load',str(environment/'site-lisp/site-start.el'),*native_args])
 elif args.command in ('lock','update'):do_lock(root,config,native,sidecar,args.command=='update',getattr(args,'names',()))
 else:
  environment=prepare(root,config,native,sidecar)
  if args.json:print(json.dumps({'environment':str(environment)}))
  else:print(environment)
if __name__=='__main__':
 try:main()
 except (ValueError,OSError,subprocess.CalledProcessError) as error:print('straight-purifier: '+str(error),file=sys.stderr);sys.exit(1)
