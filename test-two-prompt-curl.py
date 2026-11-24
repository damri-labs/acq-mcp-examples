"""Local-only validation of exact curl templates extracted from the draft. No hosted request."""
import pathlib,re,subprocess,os,tempfile,time,urllib.request,json,shlex
p=pathlib.Path(tempfile.mkdtemp(prefix='acq-prompts-'));base='http://127.0.0.1:18134';env=dict(os.environ,PORT='18134',ROOMS_DIR=str(p/'rooms'),FEEDBACK_FILE=str(p/'feedback'),STATS_FILE=str(p/'stats'),ANALYTICS_FILE=str(p/'analytics'),ACQ_PUBLIC_BASE_URL=base)
text=pathlib.Path(os.environ.get('KIT_PATH',str(pathlib.Path(__file__).with_name('acq-two-prompt-kit-DRAFT.md')))).read_text();blocks=re.findall(r'```text\n(.*?)```',text,re.S);assert len(blocks)==2
commands=[[s for s in b.splitlines() if s.startswith('curl ')] for b in blocks];assert list(map(len,commands))==[3,5]
vals={}
def curl(s):
 s=s.replace('https://acq.damri.org',base)
 for k,v in vals.items():s=s.replace('<'+k+'>',v)
 assert not re.search(r'<[A-Z_]+>',s),s
 r=subprocess.run(shlex.split(s),capture_output=True,text=True,timeout=135);assert r.returncode==0,r.stderr;return json.loads(r.stdout)
with (p/'server.log').open('w') as f:
 server=subprocess.Popen([os.environ['TEST_SERVER']],env=env,stdout=f,stderr=f)
 try:
  for _ in range(100):
   try:urllib.request.urlopen(base+'/');break
   except:time.sleep(.05)
  a=curl(commands[0][0]);vals.update(UIN=a['roomId'],TOKEN_A=a['token']);print('PASS A creates one guest room')
  empty=curl(commands[0][1].replace('wait=120','wait=0'));assert not empty['messages'] and empty.get('peerJoined') is False;again=curl(commands[0][1].replace('wait=120','wait=0'));assert not again['messages'];print('PASS A empty read repeat leaves room unjoined')
  b=curl(commands[1][0]);vals['TOKEN_B']=b['token'];print('PASS B joins')
  empty=curl(commands[1][2].replace('wait=120','wait=0'));assert not empty['messages'];again=curl(commands[1][2].replace('wait=120','wait=0'));assert not again['messages'];print('PASS B missing-ack read repeat is read-only')
  curl(commands[1][1]);r=curl(commands[0][1]);assert any(x['text']=='Hello from B' for x in r['messages']);print('PASS A reads B hello')
  curl(commands[0][2]);r=curl(commands[1][2]);assert any(x['text']=='Hello B, received by A' for x in r['messages']);print('PASS B reads A acknowledgement')
  curl(commands[1][3]);r=curl(commands[1][4]);assert r['ended'] is True;assert any(x.get('cid')=='two-prompt-b-end' and x.get('end') is True for x in r['messages']);assert len(r['messages'])==3;print('PASS final self/peek transcript has both hellos and recorded end')
 finally:server.terminate();server.wait()
print('PASS exactly two prompts,8 curl templates, loopback only. NOT a model-pair test.')
