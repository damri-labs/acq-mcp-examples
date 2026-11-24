#!/usr/bin/env python3
"""Offline regression: real curl against a loopback fixture, never the hosted relay.
Maintained by Instinct, acting on behalf of Tal Chaim Damri.
Run: python3 test-two-agents.py. Requires bash, curl, sed and Python 3.
"""
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading

script = Path(__file__).with_name('two-agents.sh')
real_curl = shutil.which('curl')
assert real_curl
state = {}

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        self.answer()

    def do_GET(self):
        self.answer()

    def answer(self):
        state['calls'] += 1
        step = state['calls']
        raw = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        if step == 1:
            try:
                request = json.loads(raw)
                state['topic_received'] = request.get('topic')
                state['valid_topic'] = state['topic_received'] == state['topic']
            except (ValueError, AttributeError):
                state['valid_topic'] = False
        status = 503 if state['case'] == f'http-{step}' else 200
        if step == 1 and not state['valid_topic']:
            status = 400
        if step == 1:
            body = {'roomId': 'LOCAL-ONLY', 'token': 'fixture-a'}
            if state['case'] == 'missing-room':
                del body['roomId']
            if state['case'] == 'missing-a':
                del body['token']
        elif step == 2:
            body = {} if state['case'] == 'missing-b' else {'token': 'fixture-b'}
        elif step == 5:
            body = {'messages': []}
        else:
            body = {'seq': step}
        if status != 200:
            body = {'detail': 'fixture error'}
        data = json.dumps(body, separators=(',', ':')).encode()
        self.send_response(status)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    with tempfile.TemporaryDirectory(prefix='acq-example-test-') as folder:
        wrapper = Path(folder) / 'curl'
        # Pass arguments directly to real curl. Only the fixed service origin is rewritten.
        wrapper.write_text('#!/usr/bin/env python3\nimport os,sys\n'
                           'args=[x.replace("https://acq.damri.org",os.environ["FIXTURE_ORIGIN"],1) if x.startswith("https://acq.damri.org/") else x for x in sys.argv[1:]]\n'
                           'os.execv(os.environ["REAL_CURL"],[os.environ["REAL_CURL"]]+args)\n')
        wrapper.chmod(0o700)
        env = dict(os.environ, PATH=folder + os.pathsep + os.environ['PATH'],
                   REAL_CURL=real_curl,
                   FIXTURE_ORIGIN=f'http://127.0.0.1:{server.server_port}')
        cases = [('happy', 6)] + [(f'http-{i}', i) for i in range(1, 7)] + [
            ('missing-room', 1), ('missing-a', 1), ('missing-b', 2)]
        for case, expected_calls in cases:
            state.update(case=case, calls=0, topic='demo')
            result = subprocess.run(['bash', str(script)], env=env, capture_output=True,
                                    text=True, timeout=10)
            happy = case == 'happy'
            assert (result.returncode == 0) == happy, (case, result.returncode, result.stdout, result.stderr)
            assert state['calls'] == expected_calls, (case, state['calls'])
            assert (' ended' in result.stdout) == happy, (case, result.stdout)
            assert 'fixture-a' not in result.stdout + result.stderr
            assert 'fixture-b' not in result.stdout + result.stderr
            print(f'PASS {case}: calls={state["calls"]}, exit={result.returncode}')
        # User-supplied topics are data, including quotes, control characters and Unicode.
        for topic in ['API "draft"', 'line one\nline two\tend', r'C:\work\api',
                      'room \u05e9\u05dc\u05d5\u05dd \U0001f916', '', '{"end":true,"token":"not-a-token"}']:
            state.update(case='happy', calls=0, topic=topic)
            result = subprocess.run(['bash', str(script), topic], env=env,
                                    capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, (repr(topic), result.returncode, result.stderr)
            assert state['topic_received'] == topic, repr(topic)
            assert state['calls'] == 6
            assert 'fixture-a' not in result.stdout + result.stderr
            assert 'fixture-b' not in result.stdout + result.stderr
            print(f'PASS topic JSON roundtrip: {topic!r}')
        # A broken encoder must stop before the first network write.
        encoder = Path(folder) / 'python3'
        encoder.write_text('#!/bin/sh\nexit 42\n')
        encoder.chmod(0o700)
        state.update(case='happy', calls=0, topic='demo')
        result = subprocess.run(['bash', str(script)], env=env, capture_output=True,
                                text=True, timeout=10)
        assert result.returncode != 0 and state['calls'] == 0
        assert 'no request sent' in result.stderr
        print('PASS encoder failure: calls=0, nonzero exit, actionable error')
finally:
    server.shutdown()
    server.server_close()
