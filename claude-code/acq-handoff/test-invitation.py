#!/usr/bin/env python3
"""Local-only invitation tests, fictional state. Instinct for Tal Chaim Damri."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HELPER = Path(__file__).with_name('acq.py')
RUNNER = r'''
import runpy,sys,urllib.request
helper,state,*args=sys.argv[1:]
class NoNetwork:
 def open(self,*a,**kw):raise AssertionError('network forbidden')
urllib.request.build_opener=lambda *a:NoNetwork()
sys.argv=[helper,'--state',state,*args]
runpy.run_path(helper,run_name='__main__')
'''
SECRET = 'fictional-seat-invitation-test'
INVITE = 'https://acq.damri.org/room/AAAA-BBBB-CCCCC'
with tempfile.TemporaryDirectory() as d:
    path = Path(d) / 'seat.json'
    base = {'roomId': 'AAAA-BBBB-CCCCC', 'token': SECRET, 'since': 0,
            'creator': True, 'durabilityUnconfirmed': False}
    cases = [(base, 0, True), (dict(base, durabilityUnconfirmed=True), 1, True),
             (dict(base, creator=False), 1, False),
             ({k:v for k,v in base.items() if k != 'creator'}, 1, False),
             (dict(base, roomId=SECRET), 1, False),
             (dict(base, token=[]), 1, False),
             (dict(base, durabilityUnconfirmed='false'), 1, False),
             ({'acquisition':'unresolved','action':'open'}, 1, False)]
    for state, code, visible in cases:
        path.write_text(json.dumps(state)); path.chmod(0o600)
        before = path.read_bytes()
        proc = subprocess.run([sys.executable, '-c', RUNNER, str(HELPER), str(path),
                               'invitation'], capture_output=True, text=True)
        assert proc.returncode == code, (state, proc.stderr)
        assert SECRET not in proc.stdout + proc.stderr
        assert path.read_bytes() == before
        assert 'AssertionError' not in proc.stderr, 'no network request allowed'
        if visible:
            result = json.loads(proc.stdout)
            assert result == {'secretInvitation': INVITE, 'localOnly': True,
                              'durabilityUnconfirmed': state['durabilityUnconfirmed']}
            assert 'Secret invitation' in proc.stderr
            assert ('durable storage is unconfirmed' in proc.stderr) == state['durabilityUnconfirmed']
        else:
            assert not proc.stdout and INVITE not in proc.stderr
    path.chmod(0o644)
    proc = subprocess.run([sys.executable, '-c', RUNNER, str(HELPER), str(path), 'invitation'],
                          capture_output=True, text=True)
    assert proc.returncode == 1 and not proc.stdout and SECRET not in proc.stderr
print('PASS 9 explicit invitation cases: creator-only, no network, no seat output, unchanged private state, distinct uncertainty')
