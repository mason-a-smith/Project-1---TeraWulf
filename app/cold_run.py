"""Fresh-venv, copied-bundle test, including live local HTTP behavior."""
import hashlib,json,os,shutil,subprocess,sys,tempfile,time,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    started=datetime.now(timezone.utc).isoformat()
    testroot=Path(tempfile.mkdtemp(prefix='wulf_cold_',dir=ROOT.parent))
    bundle=testroot/'bundle';bundle.mkdir()
    shutil.copytree(ROOT/'app',bundle/'app',ignore=shutil.ignore_patterns('__pycache__'))
    for d in ['evidence','validation','outputs']:(bundle/d).mkdir()
    shutil.copy2(ROOT/'validation/AI_DIRECTIONAL_PRECOMMIT.md',bundle/'validation/AI_DIRECTIONAL_PRECOMMIT.md')
    env=dict(os.environ);env.pop('PYTHONPATH',None);env['PYTHONUTF8']='1'
    commands=[]
    def execute(args):
        proc=subprocess.run(args,cwd=bundle,env=env,capture_output=True,text=True,encoding='utf-8')
        commands.append(dict(command=args,exit_code=proc.returncode,stdout=proc.stdout,stderr=proc.stderr))
        if proc.returncode:raise RuntimeError(proc.stdout+proc.stderr)
    execute([sys.executable,'-m','venv','--without-pip',str(testroot/'venv')])
    python=testroot/'venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    execute([str(python),'-sE','app/validate.py'])
    execute([str(python),'-sE','app/build.py'])
    execute([str(python),'-sE','-c','import sys; print("Fresh venv:",sys.prefix != sys.base_prefix); assert sys.prefix != sys.base_prefix'])
    log=(testroot/'server.log').open('w',encoding='utf-8')
    proc=subprocess.Popen([str(python),'-sE','app/server.py','--port','8766'],cwd=bundle,env=env,stdout=log,stderr=log)
    root='http://127.0.0.1:8766';http=[]
    try:
        for _ in range(50):
            try:
                with urllib.request.urlopen(root+'/api/config',timeout=2) as response: config=json.load(response)
                break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Server did not start')
        with urllib.request.urlopen(root,timeout=3) as response: page=response.read().decode()
        assert 'Demonstrate funding failure' in page and 'Reset base' in page
        assert all(f'id="r{i}"' in page for i in range(1,10))
        assert 'Favorable / improved financing (9% WACC)' in str(config['analysis']['scenarios'])
        http.append('GET / and /api/config: 200; driver panel, base and all nine requirement sections present.')
        with urllib.request.urlopen(root+'/assumptions',timeout=3) as response: assumptions=response.read().decode()
        assert response.status==200 and 'Evidence that would change it' in assumptions
        http.append('GET /assumptions: 200; full saved assumption-challenge record present.')
        def post(data):
            req=urllib.request.Request(root+'/api/evaluate',data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=3) as response:return json.load(response)
        b=post({});changed=post({'capex_multiplier':1.01});fail=post({'project_debt_limit':0});restored=post({})
        assert b['valid'] and changed['valuation']['equity_value']<b['valuation']['equity_value']
        assert not fail['valid'] and fail['valuation'] is None and restored==b
        http.append('POST base / changed capex / no funding / restored base: correct output; failure withholds valuation; reset identical.')
        try:post({'wacc':.99})
        except urllib.error.HTTPError as e:assert e.code==400
        else:raise AssertionError('Bounds endpoint did not reject')
        http.append('Out-of-bounds request returns HTTP400; raw client cannot bypass bounded controls.')
        hashes={name:hashlib.sha256((bundle/'outputs'/name).read_bytes()).hexdigest() for name in ['results.json','peer_results.json','statements.csv','VISIBLE_OUTPUT.md']}
        for name,h in hashes.items():assert hashlib.sha256((ROOT/'outputs'/name).read_bytes()).hexdigest()==h
        http.append('Generated finance outputs match main bundle byte-for-byte.')
    finally:
        proc.terminate();proc.wait(timeout=10);log.close()
    result=dict(started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),fresh_environment=str(testroot),commands=commands,http_checks=http,hashes=hashes,
                visual_status='Primary workbench browser QA separately passed: driver run, funding failure and reset; 390px mobile viewport had no horizontal overflow. The isolated copy was HTTP-tested only; on-camera rehearsal remains a student submission item.')
    (ROOT/'validation/cold_run_details.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# Cold-run log','',f"Started UTC: {started}",f"Finished UTC: {result['finished_utc']}",f'Fresh environment: {testroot}',
           'A new venv without pip was created and an independent copy of the app was used. No imports from the original coursework directory; no external packages or online data.',
           '## Executed commands']
    lines += [f"- `{subprocess.list2cmdline(c['command'])}` — exit {c['exit_code']}" for c in commands]
    lines += ['## Results']+['- '+x for x in http]+['','## Visual verification limitation',result['visual_status'],
        '','Full actual stdout, stderr and hashes: cold_run_details.json. This is an AI-executed clean run, not a claim that the student personally performed it.']
    (ROOT/'validation/COLD_RUN_LOG.md').write_text('\n\n'.join(lines),encoding='utf-8')
    print('PASS: fresh venv; finance checks; build; all nine sections; assumption route; HTTP base/change/failure/reset/bounds; output hashes. Browser controls/mobile QA recorded separately.')

if __name__=='__main__':main()
