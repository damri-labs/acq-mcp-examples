#!/usr/bin/env python3
"""Isolated input-boundary checks. Instinct for Tal Chaim Damri."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HELPER = Path(__file__).with_name('acq.py')
RUNNER = r'''
import io,json,pathlib,runpy,sys,urllib.request
helper,state,*args=sys.argv[1:]
class Response:
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def read(self,*a):return b'{"token":"fictional-seat-safe-input","seq":1}'
class Fake:
 def open(self,req,timeout):
  pathlib.Path(state+'.request').write_text(json.dumps({'url':req.full_url,'data':json.loads(req.data)}))
  return Response()
urllib.request.build_opener=lambda *a:Fake()
sys.argv=[helper,'--state',state,*args]
runpy.run_path(helper,run_name='__main__')
'''
SECRET = 'fictional-seat-safe-input'
with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    state = root / 'seat.json'
    text = root / 'text.txt'
    uin = root / 'uin.txt'
    request = Path(str(state)+'.request')
    def reset():
        state.write_text(json.dumps({'roomId':'AAAA-BBBB-CCCCC','token':SECRET,'since':0}))
        state.chmod(0o600)
        request.unlink(missing_ok=True)
    def run(*args):
        p = subprocess.run([sys.executable,'-c',RUNNER,str(HELPER),str(state),*args],capture_output=True,text=True)
        assert SECRET not in p.stdout+p.stderr
        return p
    reset(); text.write_bytes(b'Unapproved fictional contents')
    p = run('send','--text-file',str(text))
    assert p.returncode != 0 and not request.exists(), 'send without approved digest must reject before network'
    count = 1
    for raw in (b'Changed fictional text', b'\xff', b'', b' '*3, b'x'*65537):
        reset(); text.write_bytes(raw)
        p=run('send','--text-file',str(text),'--approved-sha256',hashlib.sha256(b'Original fictional text').hexdigest())
        assert p.returncode != 0 and not request.exists(), 'invalid/changed text must reject before network'
        count += 1
    for raw in (b'\xff', b'', b' '*3, b'x'*65537):
        reset(); text.write_bytes(raw)
        p=run('send','--text-file',str(text),'--approved-sha256',hashlib.sha256(raw).hexdigest())
        assert p.returncode != 0 and not request.exists(), 'matching digest cannot bypass UTF8/content/size checks'
        count += 1
    for digest in ('bad','0'*64):
        reset(); text.write_bytes(b'Fictional')
        p=run('send','--text-file',str(text),'--approved-sha256',digest)
        assert p.returncode != 0 and not request.exists()
        count += 1
    reset(); target=root/'target.txt'; target.write_text('Fictional'); text.unlink(); text.symlink_to(target)
    p=run('send','--text-file',str(text),'--approved-sha256',hashlib.sha256(target.read_bytes()).hexdigest())
    assert p.returncode != 0 and not request.exists(); count += 1
    text.unlink(); text.mkdir()
    p=run('send','--text-file',str(text),'--approved-sha256','0'*64)
    assert p.returncode != 0 and not request.exists(); count += 1
    text.rmdir()
    import os
    os.mkfifo(text)
    p=run('send','--text-file',str(text),'--approved-sha256','0'*64)
    assert p.returncode != 0 and not request.exists(); count += 1
    text.unlink()
    for raw in (b'Fictional\r\nline\r\n', 'Fictional café\n'.encode(), b'x'*65536):
        reset(); text.write_bytes(raw)
        p=run('send','--text-file',str(text),'--approved-sha256',hashlib.sha256(raw).hexdigest())
        assert p.returncode == 0, p.stderr
        assert json.loads(request.read_text())['data']['text'].encode('utf-8') == raw
        count += 1
    for raw in (b'AAAA-BBBB-CCCCC\n', b'aaaa-bbbb-ccccc'):
        reset(); state.unlink(); uin.write_bytes(raw)
        p=run('join','--uin-file',str(uin))
        assert p.returncode == 0, p.stderr
        assert json.loads(request.read_text()) == {'url':'https://acq.damri.org/room/AAAA-BBBB-CCCCC/join','data':{}}
        count += 1
    # Malicious-looking identifiers remain file data. Nothing is shell-evaluated.
    for raw in (b'$(touch NEVER)', b'AAAA-BBBB-CCCCC; echo NEVER', b'x'*65, b'\xff', b''):
        reset(); state.unlink(); uin.write_bytes(raw)
        p=run('join','--uin-file',str(uin))
        assert p.returncode != 0 and not request.exists() and not state.exists()
        count += 1
    uin.unlink(); uin.symlink_to(target)
    p=run('join','--uin-file',str(uin))
    assert p.returncode != 0 and not request.exists() and not state.exists(); count += 1
print('PASS',count,'safe-input cases: reject before network, exact UTF8 bytes, no shell interpolation')
