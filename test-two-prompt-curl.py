"""Loopback-only real bash validation of the prompt setup and curl blocks. No hosted requests."""
import pathlib,re,subprocess,os,tempfile,time,urllib.request,json
p=pathlib.Path(tempfile.mkdtemp(prefix='acq-prompts-'));base='http://127.0.0.1:18134'
env=dict(os.environ,PORT='18134',ROOMS_DIR=str(p/'rooms'),FEEDBACK_FILE=str(p/'feedback'),STATS_FILE=str(p/'stats'),ANALYTICS_FILE=str(p/'analytics'),ACQ_PUBLIC_BASE_URL=base,TMPDIR=str(p))
text=pathlib.Path(os.environ.get('KIT_PATH',str(pathlib.Path(__file__).with_name('acq-two-prompt-kit-DRAFT.md')))).read_text()
blocks=re.findall(r'```text\n(.*?)```',text,re.S);assert len(blocks)==2
commands=[];setups=[]
for block in blocks:
 lines=block.splitlines();cs=[]
 for i,line in enumerate(lines):
  if line.startswith('curl '):
   c=line
   while c.endswith('\\'):
    i+=1;c+='\n'+lines[i]
   cs.append(c.replace('https://acq.damri.org',base))
 commands.append(cs)
 setups.append('\n'.join(l for l in lines if l.startswith(('umask ','RESPONSE=','UIN=\''))))
assert list(map(len,commands))==[3,5]
assert '<TOKEN_' not in text and '<UIN>' not in text
assert 'separate shell for each command' in text and 'never paste a token into a command' in text
print('PASS exactly two prompts and eight variable-based curl templates')
def run_script(s):
 return subprocess.Popen(['bash','-c',s],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
def check_output(out,err):
 assert 'recoveryCode' not in out+err and 'credential' not in out+err
 assert not re.search(r'"token"\s*:',out+err)
 # Compare actual stored secret values without displaying any of them.
 def secrets(v):
  if isinstance(v,dict):
   for k,x in v.items():
    if any(t in k.lower() for t in ('token','recovery','credential')) and isinstance(x,str) and len(x)>12:yield x
    else:yield from secrets(x)
  elif isinstance(v,list):
   for x in v:yield from secrets(x)
 for f in (p/'rooms').rglob('*.json'):
  try: raw=json.loads(f.read_text())
  except (ValueError,OSError):continue
  for secret in secrets(raw):assert secret not in out+err
with (p/'server.log').open('w') as log:
 server=subprocess.Popen([os.environ['TEST_SERVER']],env=env,stdout=log,stderr=log)
 try:
  for _ in range(100):
   try:urllib.request.urlopen(base+'/');break
   except Exception:time.sleep(.05)
  # Run literal setup and multiline create/parser/cleanup in one real bash process.
  a=run_script(setups[0]+'\n'+commands[0][0]+'''\nstatus=$?; if [ "$status" -ne 0 ]; then printf 'STOP create\n'; else
printf '%s\n' "$UIN"
'''+commands[0][1]+ '\n'+commands[0][2]+'\nfi')
  uin=a.stdout.readline().strip();assert re.fullmatch(r'[A-Z0-9-]+',uin), 'no safe UIN from A'
  print('PASS real bash A creates room with UIN-only handoff')
  bsetup=setups[1].replace('<PASTE_UIN_FROM_PERSON_A>',uin)
  b=run_script(bsetup+'\n'+commands[1][0]+'''\nstatus=$?; if [ "$status" -ne 0 ]; then printf 'STOP join\n'; else
'''+ '\n'.join(commands[1][1:])+'\nfi')
  bout,berr=b.communicate(timeout=140);aout,aerr=a.communicate(timeout=140)
  assert a.returncode==b.returncode==0,(a.returncode,b.returncode)
  adec=json.JSONDecoder();bdec=json.JSONDecoder()
  def objs(s):
   out=[]
   while s.strip():
    x,n=json.JSONDecoder().raw_decode(s.lstrip());out.append(x);s=s.lstrip()[n:]
   return out
  ar=objs(aout);br=objs(bout)
  assert ar[0]['peerJoined'] and ar[0]['messages'][0]['text']=='Hello from B'
  print('PASS real bash A reads B hello using shell token')
  assert ar[1]['cid']=='two-prompt-a-ack';print('PASS real bash A acknowledgement accepted')
  assert br[0]['cid']=='two-prompt-b-hello';print('PASS real bash B joins and sends hello')
  assert any(m['text']=='Hello B, received by A' for m in br[1]['messages']);print('PASS real bash B reads A acknowledgement')
  assert br[2]['cid']=='two-prompt-b-end';print('PASS real bash B ends once')
  final=br[3];assert final['ended'] and len(final['messages'])==3 and any(m.get('cid')=='two-prompt-b-end' and m.get('end') for m in final['messages'])
  print('PASS final transcript confirms both hellos and ending')
  check_output(aout+uin+bout,aerr+berr);print('PASS stdout/stderr contain no token or recovery secret')
  assert not list(p.glob('tmp.*'));print('PASS real bash response files deleted by normal cleanup/EXIT traps')
  # Inject failure before any curl: EXIT trap cleans file, no write retry.
  failed=run_script(setups[0]+'\nfalse && '+commands[0][0]);fo,fe=failed.communicate();assert failed.returncode!=0 and not list(p.glob('tmp.*'));check_output(fo,fe)
  print('PASS failed command chain stops and EXIT trap deletes response file')
 finally:server.terminate();server.wait()
print('PASS loopback only. Not a revised model-pair trial or adoption.')
