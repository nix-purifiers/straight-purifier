#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise native Git resolution, pin retention and real Emacs startup."""
import functools,http.server,json,os,shutil,subprocess,sys,tempfile,threading
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
def run(args,**kw):return subprocess.run(list(map(str,args)),check=True,text=True,**kw)
case=sys.argv[1]
with tempfile.TemporaryDirectory(prefix='straight-conformance-') as tmp:
 temp=Path(tmp);cli=temp/'cli'
 run(['nix','build',str(REPO)+'#cli','--out-link',cli])
 purifier=cli/'bin/straight-purifier';emacs=cli/'bin/emacs'
 if case=='native':
  root=temp/'config';shutil.copytree(REPO/'examples/config',root,ignore=shutil.ignore_patterns('.straight-purifier'))
  before=(root/'straight/versions/default.el').read_bytes()
  env={**os.environ,'HOME':str(temp/'home')};Path(env['HOME']).mkdir()
  run([emacs,'--batch','-Q','--init-directory',root,'--load',root/'init.el','--eval','(unless (equal (s-trim " locked ") "locked") (kill-emacs 1))'],env=env,cwd=root)
  # A normal daemon startup loads site-start before the user's init.el.
  run([emacs,'--fg-daemon=purifier-'+str(os.getpid()),'--init-directory',root,'--eval','(progn (unless (featurep \'s) (error "Init did not run")) (kill-emacs 0))'],env=env,cwd=root,timeout=120)
  assert (root/'straight/versions/default.el').read_bytes()==before
  config=root/'init.el';original=config.read_text();config.write_text(original+'\n;; stale configuration\n')
  stale=subprocess.run([str(emacs),'--batch','-Q','--init-directory',str(root),'--eval','(princ \"must-not-run\")'],env=env,cwd=root,text=True,capture_output=True)
  assert stale.returncode and 'must-not-run' not in stale.stdout and 'ordinary impure Emacs' not in stale.stderr
  config.write_text(original)
  (root/'straight-purifier.lock.json').unlink()
  fallback=run([emacs,'--batch','-Q','--eval','(princ "native-fallback")'],env=env,cwd=root,capture_output=True)
  assert fallback.stdout=='native-fallback' and 'ordinary impure Emacs' in fallback.stderr
 else:
  served=temp/'served';served.mkdir();root=temp/'config';root.mkdir()
  repos={}
  def commit(name,value):
   repo=repos[name];(repo/(name+'.el')).write_text(';;; '+name+'.el --- Fixture -*- lexical-binding: t -*-\n;; Version: 1.0\n(defun '+name+'-value () "'+value+'")\n(provide \''+name+')\n')
   run(['git','-C',repo,'add','.'],capture_output=True)
   run(['git','-C',repo,'-c','user.name=Purifier fixture','-c','user.email=fixture@example.invalid','commit','-m',value],capture_output=True)
   run(['git','-C',repo,'push',served/(name+'.git'),'HEAD:refs/heads/main'],capture_output=True)
   run(['git','-C',served/(name+'.git'),'update-server-info'])
   return run(['git','-C',repo,'rev-parse','HEAD'],capture_output=True).stdout.strip()
  for name in ('first','second'):
   repos[name]=temp/(name+'-work');run(['git','init','-b','main',repos[name]],capture_output=True)
   run(['git','init','--bare','-b','main',served/(name+'.git')],capture_output=True);commit(name,'one')
  class Quiet(http.server.SimpleHTTPRequestHandler):
   def log_message(self,*_):pass
  server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=served))
  worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
  try:
   config=';;; -*- lexical-binding: t -*-\n(setq straight-initial-recipe-repositories nil)\n(load (expand-file-name "straight/repos/straight.el/bootstrap.el" (or (bound-and-true-p straight-base-dir) user-emacs-directory)) nil t)\n'
   for name in repos:config+='(straight-use-package \'('+name+' :type git :repo "http://127.0.0.1:'+str(server.server_port)+'/'+name+'.git" :branch "main"))\n'
   (root/'init.el').write_text(config)
   native=root/'straight/versions/default.el';sidecar=root/'straight-purifier.lock.json'
   if case=='external':
    native=temp/'external/versions.el';sidecar=temp/'external/straight.json'
   args=[purifier,'--project',root,'--native-lock',native,'--lockfile',sidecar]
   run([*args,'lock']);first=sidecar.read_bytes();native_first=native.read_bytes()
   run([*args,'lock']);assert sidecar.read_bytes()==first and native.read_bytes()==native_first
   original=json.loads(first)['repositories']
   for name in repos:commit(name,'two')
   run([*args,'lock']);assert sidecar.read_bytes()==first
   if case=='update':
    run([*args,'update','first']);changed=json.loads(sidecar.read_text())['repositories']
    assert changed['first']['rev']!=original['first']['rev']
    assert changed['second']['rev']==original['second']['rev']
    run([*args,'update']);changed=json.loads(sidecar.read_text())['repositories']
    assert changed['second']['rev']!=original['second']['rev']
   if case=='relock':
    native.write_text('broken native lock')
    run([*args,'lock']);assert json.loads(sidecar.read_text())['repositories']['first']['rev']==original['first']['rev']
    damaged=json.loads(sidecar.read_text());damaged['contentHash']='damaged';sidecar.write_text(json.dumps(damaged))
    run([*args,'lock'])
   run([*args,'prefetch'])
   if case=='external':assert not (root/'straight-purifier.lock.json').exists() and not (root/'straight/versions/default.el').exists()
  finally:server.shutdown();server.server_close();worker.join()
  env={**os.environ,'STRAIGHT_PURIFIER_NATIVE_LOCKFILE':str(native),'STRAIGHT_PURIFIER_LOCKFILE':str(sidecar)}
  expected='two' if case=='update' else 'one'
  expression=f"(progn (require 'first) (unless (equal (first-value) {json.dumps(expected)}) (kill-emacs 1)))"
  run([emacs,'--batch','-Q','--init-directory',root,'--load',root/'init.el','--eval',expression],env=env,cwd=root)
 print('PASS',case)
