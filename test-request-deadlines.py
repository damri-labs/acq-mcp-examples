#!/usr/bin/env python3
"""Offline request-budget checks, using real curl and a stalled loopback server.
Instinct, acting on behalf of Tal Chaim Damri.
The wrapper checks the production 30s flag, then scales it to 0.2s for tests.
This verifies option wiring and curl timeout behavior, not a measured 30s wait.
Run: python3 test-request-deadlines.py. Requires bash, curl, sed and Python 3.
"""
import http.server,json,os,subprocess,tempfile,threading,time,shutil
from pathlib import Path
state={}
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*_): pass
    def do_GET(self): self.answer()
    def do_POST(self): self.answer()
    def answer(self):
        incoming=self.rfile.read(int(self.headers.get('Content-Length',0)))
        cleanup=b'cleanup:' in incoming
        if cleanup:
            state['cleanup']+=1
        else:
            state['steps']+=1
        step=state['steps']
        if (not cleanup and step==state['stall']) or (cleanup and state['stall_cleanup']):
            time.sleep(0.6);return
        if cleanup:
            status,body=200,{}
        elif state['script']=='two-agents.sh':
            status=200
            body={1:{'roomId':'LOCAL-ONLY','token':'fixture-a'},2:{'token':'fixture-b'}}.get(step,{'messages':[]})
        else:
            status=404 if step==4 else 200
            body={1:{'roomId':'LOCAL-ONLY','token':'fixture-a','pairCode':'111111'},2:{'token':'fixture-b','recoveryCode':'222222'},3:{'token':'fixture-b2'},6:{'peerRekeyedAt':123},7:{'token':'fixture-a2'}}.get(step,{})
            if state['stall_cleanup'] and step==2: body={}
        data=json.dumps(body,separators=(',',':')).encode()
        self.send_response(status);self.send_header('Content-Length',str(len(data)));self.end_headers()
        try:self.wfile.write(data)
        except BrokenPipeError:pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 with tempfile.TemporaryDirectory(prefix='acq-deadline-') as folder:
    wrapper=Path(folder)/'curl';log=Path(folder)/'flags'
    wrapper.write_text('#!/usr/bin/env python3\nimport os,sys\na=sys.argv[1:]\nassert a.count("--max-time")==1,a\ni=a.index("--max-time")\nassert a[i+1]=="30",a\nopen(os.environ["FLAG_LOG"],"a").write("30\\n")\na[i+1]="0.2"\na=[x.replace("https://acq.damri.org",os.environ["ORIGIN"],1) if x.startswith("https://acq.damri.org/") else x for x in a]\nos.execv(os.environ["CURL"],[os.environ["CURL"]]+a)\n');wrapper.chmod(0o700)
    env=dict(os.environ,PATH=folder+os.pathsep+os.environ['PATH'],CURL=shutil.which('curl'),ORIGIN=f'http://127.0.0.1:{server.server_port}',FLAG_LOG=str(log))
    for script,total in [('two-agents.sh',6),('recover-seat.sh',8)]:
        for stall in range(total+1):
            log.write_text('');state.update(script=script,stall=stall,stall_cleanup=False,steps=0,cleanup=0)
            start=time.monotonic();r=subprocess.run(['bash',str(Path(__file__).with_name(script))],env=env,capture_output=True,text=True,timeout=4)
            assert (r.returncode==0)==(stall==0),(script,stall,r.stdout,r.stderr)
            assert state['steps']==(stall or total),(script,stall,state)
            assert (' ended' in r.stdout)==(stall==0)
            assert len(log.read_text().splitlines())==state['steps']+state['cleanup']
            assert not any(s in r.stdout+r.stderr for s in ('fixture-a','fixture-b','111111','222222'))
            print(f'PASS {script}/stall-{stall}: steps={state["steps"]}, cleanup={state["cleanup"]}, exit={r.returncode}, elapsed={time.monotonic()-start:.2f}s')
    log.write_text('');state.update(script='recover-seat.sh',stall=0,stall_cleanup=True,steps=0,cleanup=0)
    start=time.monotonic();r=subprocess.run(['bash',str(Path(__file__).with_name('recover-seat.sh'))],env=env,capture_output=True,text=True,timeout=4)
    assert r.returncode!=0 and state['steps']==2 and state['cleanup']==1
    assert ' ended' not in r.stdout
    assert len(log.read_text().splitlines())==3
    print(f'PASS recover-seat.sh/stalled-cleanup: original failure exits, elapsed={time.monotonic()-start:.2f}s')
finally:
 server.shutdown();server.server_close()
