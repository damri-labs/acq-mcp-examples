"""Loopback-only test: exact prompt blocks in separate bash calls, private files between calls."""
import pathlib,re,subprocess,os,tempfile,time,urllib.request,json,stat
p=pathlib.Path(tempfile.mkdtemp(prefix='acq-prompts-'));base='http://127.0.0.1:18134'
env=dict(os.environ,PORT='18134',ROOMS_DIR=str(p/'rooms'),FEEDBACK_FILE=str(p/'feedback'),STATS_FILE=str(p/'stats'),ANALYTICS_FILE=str(p/'analytics'),ACQ_PUBLIC_BASE_URL=base,TMPDIR=str(p))
text=pathlib.Path(os.environ.get('KIT_PATH',str(pathlib.Path(__file__).with_name('acq-two-prompt-kit-DRAFT.md')))).read_text();blocks=re.findall(r'```text\n(.*?)```',text,re.S);assert len(blocks)==2
steps=[]
for block in blocks:
 lines=block.splitlines();found=[]
 for i,l in enumerate(lines):
  if l.startswith('curl ') and '-o ' in l and not (i and lines[i-1].endswith(chr(92))): start=i
  elif l.startswith('UIN=$(cat') and i+1<len(lines) and ('curl ' in lines[i+1] or lines[i+1].startswith('curl ')):start=i
  else:continue
  c=lines[start];j=start
  while c.endswith('\\'):
   j+=1;c+='\n'+lines[j]
  if '-o ' in c:c='umask 077\n'+c+'\n'+lines[j+1]
  found.append(c.replace('https://acq.damri.org',base))
 steps.append(found)
assert list(map(len,steps))==[3,5],list(map(len,steps));assert '<TOKEN_' not in text and '<UIN>' not in text
print('PASS two prompts and eight shell-variable curl templates')
outputs=[];secrets=[]
def run(s,state=None):
 prefix='STATE='+repr(str(state))+'\n' if state else ''
 r=subprocess.run(['bash','-c',prefix+s],env=env,capture_output=True,text=True,timeout=140);outputs.append(r.stdout+r.stderr);assert r.returncode==0, 'shell step failed';return r.stdout

def check_files(state):
 assert stat.S_IMODE(state.stat().st_mode)==0o700
 for f in state.iterdir():assert stat.S_IMODE(f.stat().st_mode)==0o600
 assert not (state/'response').exists()
 secrets.append((state/'token').read_text())
with (p/'server.log').open('w') as log:
 server=subprocess.Popen([os.environ['TEST_SERVER']],env=env,stdout=log,stderr=log)
 try:
  for _ in range(100):
   try:urllib.request.urlopen(base+'/');break
   except Exception:time.sleep(.05)
  a=pathlib.Path(run('umask 077; mktemp -d').strip());b=pathlib.Path(run('umask 077; mktemp -d').strip())
  uin=run(steps[0][0],a).strip();assert re.fullmatch('[A-Z0-9-]+',uin);check_files(a);print('PASS A create UIN-only output, 0600 token and 0700 directory')
  empty=json.loads(run(steps[0][1].replace('wait=120','wait=0'),a));again=json.loads(run(steps[0][1].replace('wait=120','wait=0'),a));assert not empty['messages'] and not again['messages'] and not again['peerJoined'];print('PASS separate-shell empty read repeats safely')
  setup=next(l for l in blocks[1].splitlines() if l.startswith("umask 077; printf"));run(setup.replace('<PASTE_UIN_FROM_PERSON_A>',uin),b)
  assert not run(steps[1][0],b).strip();check_files(b);print('PASS B join prints nothing; private token only')
  empty=json.loads(run(steps[1][2].replace('wait=120','wait=0'),b));again=json.loads(run(steps[1][2].replace('wait=120','wait=0'),b));assert not empty['messages'] and not again['messages'];print('PASS separate-shell missing acknowledgement read repeats safely')
  assert json.loads(run(steps[1][1],b))['cid']=='two-prompt-b-hello';assert json.loads(run(steps[0][1],a))['messages'][0]['text']=='Hello from B';print('PASS B hello reaches A across separate shells')
  assert json.loads(run(steps[0][2],a))['cid']=='two-prompt-a-ack';assert any(m['text']=='Hello B, received by A' for m in json.loads(run(steps[1][2],b))['messages']);print('PASS A acknowledgement reaches B across separate shells')
  run(steps[1][3],b);final=json.loads(run(steps[1][4],b));assert final['ended'] and len(final['messages'])==3 and any(m.get('end') and m.get('cid')=='two-prompt-b-end' for m in final['messages']);print('PASS final transcript confirms both hellos and ending')
  for i,state in enumerate((a,b)):
   cleanup=next(l for l in blocks[i].splitlines() if l.startswith('rm -f '));run(cleanup,state);assert not state.exists()
  print('PASS final per-call cleanup deletes both token files/directories')
  combined=''.join(outputs);assert all(secret not in combined for secret in secrets);assert 'recoveryCode' not in combined and 'credential' not in combined and not re.search(r'"token"\s*:',combined);print('PASS no token or recovery field in stdout/stderr')
  # Real occupied-room 409, executing the same join capture block.
  state=pathlib.Path(run('umask 077; mktemp -d').strip());run("umask 077; printf '%s' '"+uin+"' > \"$STATE/uin\"",state)
  r=subprocess.run(['bash','-c','STATE='+repr(str(state))+'\n'+steps[1][0]],env=env,capture_output=True,text=True,timeout=35)
  assert r.returncode!=0 and not r.stdout and not (state/'response').exists() and not (state/'token').exists();state.rmdir()
  print('PASS actual full-room join error JSON fails closed')
  # Execute the kit's actual create and join chains on both transport and error-JSON failures.
  import http.server,threading
  class ErrorJSON(http.server.BaseHTTPRequestHandler):
   def do_POST(self):
    self.send_response(409);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"error":"room full"}')
   def log_message(self,*args):pass
  error=http.server.HTTPServer(('127.0.0.1',0),ErrorJSON);thread=threading.Thread(target=error.serve_forever);thread.start()
  try:
   for badbase in ['http://127.0.0.1:1','http://127.0.0.1:'+str(error.server_port)]:
    for command in [steps[0][0],steps[1][0]]:
     state=pathlib.Path(run('umask 077; mktemp -d').strip())
     run("umask 077; printf fake-uin > \"$STATE/uin\"",state)
     r=subprocess.run(['bash','-c','STATE='+repr(str(state))+'\n'+command.replace(base,badbase)],env=env,capture_output=True,text=True,timeout=35)
     assert r.returncode!=0 and not r.stdout
     assert not (state/'response').exists() and not (state/'token').exists()
     state.rmdir()
   print('PASS actual create/join blocks: closed port and 409 JSON fail closed without stdout or secret files')
  finally:error.shutdown();thread.join();error.server_close()
  # The capture status survives deletion, and no second curl follows a failure.
  r=subprocess.run(['bash','-c','false && printf unsafe; STATUS=$?; rm -f /nonexistent-acq-test-file; test "$STATUS" -eq 0'],capture_output=True,text=True);assert r.returncode!=0 and not r.stdout;print('PASS failed capture chain remains failed after cleanup')
 finally:server.terminate();server.wait()
print('PASS loopback only; not revised model-pair validation or adoption')
