#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import copy,json,shutil,subprocess,sys,tempfile
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from straight_purifier import lock
with tempfile.TemporaryDirectory(prefix='straight-invalid-') as tmp:
 root=Path(tmp)/'config';shutil.copytree(REPO/'examples/config',root,ignore=shutil.ignore_patterns('.straight-purifier'))
 sidecar=root/'straight-purifier.lock.json';original=sidecar.read_text();data=json.loads(original)
 expression='let f = builtins.getFlake '+json.dumps(str(REPO))+'; in (f.lib.straight-purifier.readLock { src = /. + '+json.dumps(str(root))+'; }).problems'
 def evaluate(invalid):
  result=subprocess.run(['nix','eval','--impure','--json','--expr',expression],text=True,capture_output=True)
  if result.returncode:
   assert invalid and 'straight-purifier' in result.stderr,result.stderr
  else:assert bool(json.loads(result.stdout))==invalid,result.stdout
 evaluate(False)
 for mutation in ('hash','missing-git-hash','scalar','native-pin','configuration','malformed'):
  sidecar.write_text(original);native=root/'straight/versions/default.el';native_original=native.read_text();config=root/'init.el';config_original=config.read_text();changed=copy.deepcopy(data)
  if mutation=='hash':changed['contentHash']='bad'
  elif mutation=='missing-git-hash':del changed['repositories']['straight.el']['hash'];changed=lock.seal(changed)
  elif mutation=='scalar':changed=3
  elif mutation=='native-pin':native.write_text(native_original.replace(changed['repositories']['straight.el']['rev'],'0'*40));changed['nativeHash']=lock.digest(native);changed=lock.seal(changed)
  elif mutation=='configuration':config.write_text(config_original+'\n;; changed\n')
  if mutation=='malformed':sidecar.write_text('invalid JSON')
  else:sidecar.write_text(json.dumps(changed))
  evaluate(True);native.write_text(native_original);config.write_text(config_original)
 sidecar.unlink();evaluate(True)
print('PASS invalid-lock evaluation')
