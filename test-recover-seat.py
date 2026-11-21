#!/usr/bin/env python3
"""Offline recovery example status regression, real curl and loopback HTTP only.
Instinct, acting on behalf of Tal Chaim Damri.
Run: python3 test-recover-seat.py. Requires bash, curl, sed and Python 3.
"""
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading

state = {}
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass
    def do_POST(self):
        self.answer()
    def do_GET(self):
        self.answer()
    def answer(self):
        body_in = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        if b'cleanup:' in body_in:
            state['cleanup'] += 1
            status, body = 200, {}
        else:
            state['steps'] += 1
            step = state['steps']
            bodies = {
                1: {'roomId': 'LOCAL-ONLY', 'token': 'fixture-a', 'pairCode': '111111'},
                2: {'token': 'fixture-b', 'recoveryCode': '222222'},
                3: {'token': 'fixture-b2'}, 4: {}, 5: {},
                6: {'peerRekeyedAt': 123}, 7: {'token': 'fixture-a2'}, 8: {},
            }
            status, body = (404 if step == 4 else 200), bodies[step]
            # A non-success response must fail even if its JSON has expected fields.
            if state['case'] == f'http-{step}':
                status = 503
            if state['case'] == 'read-error-marker' and step == 6:
                status, body = 503, {'detail': 'could not read peerRekeyedAt'}
            if state['case'] == 'missing-token' and step == 3:
                body = {}
        data = json.dumps(body, separators=(',', ':')).encode()
        self.send_response(status)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with tempfile.TemporaryDirectory(prefix='acq-recovery-test-') as folder:
        wrapper = Path(folder) / 'curl'
        wrapper.write_text('#!/usr/bin/env python3\nimport os,sys\n'
                           'args=[x.replace("https://acq.damri.org",os.environ["FIXTURE_ORIGIN"],1) if x.startswith("https://acq.damri.org/") else x for x in sys.argv[1:]]\n'
                           'os.execv(os.environ["REAL_CURL"],[os.environ["REAL_CURL"]]+args)\n')
        wrapper.chmod(0o700)
        env = dict(os.environ, PATH=folder+os.pathsep+os.environ['PATH'],
                   REAL_CURL=shutil.which('curl'),
                   FIXTURE_ORIGIN=f'http://127.0.0.1:{server.server_port}')
        for case, expected in [('happy', 8), ('read-error-marker', 6)] + [(f'http-{i}', i) for i in range(1,9)] + [('missing-token',3)]:
            state.update(case=case, steps=0, cleanup=0)
            result = subprocess.run(['bash', str(Path(__file__).with_name('recover-seat.sh'))],
                                    capture_output=True, text=True, env=env, timeout=10)
            happy = case == 'happy'
            assert (result.returncode == 0) == happy, (case, result.returncode, result.stdout, result.stderr)
            assert state['steps'] == expected, (case, state)
            assert (' ended' in result.stdout) == happy, (case, result.stdout)
            assert state['cleanup'] <= 1, (case, state)
            assert not any(s in result.stdout+result.stderr for s in ('fixture-a','fixture-b','111111','222222'))
            print(f'PASS {case}: steps={state["steps"]}, cleanup={state["cleanup"]}, exit={result.returncode}')
finally:
    server.shutdown()
    server.server_close()
