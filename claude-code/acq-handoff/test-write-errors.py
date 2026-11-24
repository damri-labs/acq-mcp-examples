#!/usr/bin/env python3
"""Isolated subprocess outcome matrix. Fictional data only, no network.
Instinct, acting on behalf of Tal Chaim Damri.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HELPER = Path(__file__).with_name('acq.py')
SECRET = 'fictional-seat-secret-regression'
RECOVERY = 'fictional-recovery-secret-regression'
# Loading as __main__ exercises the real safe error-reporting boundary.
RUNNER = r'''
import io,json,pathlib,runpy,sys,urllib.error,urllib.request
helper,mode,state,*args=sys.argv[1:]
secret='fictional-seat-secret-regression'
class Response:
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,*args):return b'{broken'
class Fake:
 def open(self,req,timeout):
  p=pathlib.Path(state+'.calls');p.write_text(p.read_text()+'1' if p.exists() else '1')
  if mode=='timeout':raise TimeoutError(secret)
  if mode=='invalid200':return Response()
  data={'stored':'unknown','roomId':'AAAA-BBBB-CCCCC','token':secret,'recoveryCode':'fictional-recovery-secret-regression','seq':7}
  if mode=='false':data['stored']=False
  if mode=='missingtoken':del data['token']
  if mode=='wrongtype':data['token']=[secret]
  raw=json.dumps(data).encode()
  if mode=='malformed':raw=b'{broken'+secret.encode()
  if mode=='oversized':raw=b'x'*131073+secret.encode()
  if mode=='bare500':raw=b'<html>'+secret.encode()
  if mode=='redirect':
   raise urllib.error.HTTPError('https://untrusted.invalid/'+secret,302,secret,{'Location':'https://untrusted.invalid/'+secret},io.BytesIO(raw))
  raise urllib.error.HTTPError(req.full_url,500,secret,{},io.BytesIO(raw))
urllib.request.build_opener=lambda *args:Fake()
sys.argv=[helper,'--state',state,*args]
runpy.run_path(helper,run_name='__main__')
'''

cases = 0
for action in ('open', 'join', 'send'):
    for mode in ('unknown', 'false', 'timeout', 'bare500', 'malformed',
                 'oversized', 'missingtoken', 'wrongtype', 'invalid200', 'redirect'):
        with tempfile.TemporaryDirectory() as d:
            Path(d).chmod(0o700)
            state = Path(d) / 'seat.json'
            text = Path(d) / 'message.txt'
            text.write_text('Fictional task')
            if action == 'send':
                state.write_text(json.dumps({'roomId': 'AAAA-BBBB-CCCCC', 'token': SECRET, 'since': 0}))
                state.chmod(0o600)
            before = state.read_bytes() if state.exists() else None
            args = [action]
            if action == 'join':
                args += ['AAAA-BBBB-CCCCC']
            if action == 'send':
                args += ['--text-file', str(text)]
            proc = subprocess.run([sys.executable, '-c', RUNNER, str(HELPER), mode,
                                   str(state), *args], capture_output=True, text=True)
            label = action + '/' + mode
            assert proc.returncode == 1, (label, proc.returncode)
            assert SECRET not in proc.stdout + proc.stderr, label
            assert RECOVERY not in proc.stdout + proc.stderr, label
            assert not proc.stdout, label + ': no success or invitation output on failed write'
            calls = Path(str(state) + '.calls')
            assert calls.read_text() == '1', label + ': no automatic retry'
            if action == 'send':
                assert state.read_bytes() == before, label + ': do not change existing state'
            elif mode == 'false':
                assert not state.exists(), label + ': definite rejection releases reservation'
                assert 'not stored' in proc.stderr, label
            else:
                assert state.exists(), label + ': preserve guard after uncertain write'
                assert state.stat().st_mode & 0o777 == 0o600, label
                saved = json.loads(state.read_text())
                if mode == 'unknown':
                    assert saved['token'] == SECRET and saved['durabilityUnconfirmed'], label
                    assert 'Credential saved locally' in proc.stderr, label
                else:
                    assert saved == {'acquisition': 'unresolved', 'action': action}, label
                again = subprocess.run([sys.executable, '-c', RUNNER, str(HELPER), mode,
                                        str(state), *args], capture_output=True, text=True)
                assert again.returncode == 1 and calls.read_text() == '1', label + ': second acquisition blocked'
                assert SECRET not in again.stdout + again.stderr, label
            cases += 1
print('PASS', cases, 'write outcomes, no retries, private state, subprocess secret-output checks')
