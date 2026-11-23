#!/usr/bin/env python3
"""Deploy the guarded Google Play integration without changing course materials."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
FILES = HERE / 'files'
spec = importlib.util.spec_from_file_location('mca_release', HERE.parent / 'checkout-120/release.py')
pay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pay)
APP = 'mca-course-test'
ENV = pay.PRIVATE / 'google-play.env'
MARKER = 'google-play-release.sha256'
CHECKOUT_SHA = '63597b782800bc32a6ce5a64d1372d8838b4688445d5ef9ea0e490a451b2b28d'
REPLACED = {
    'src/components/CourseCheckout.tsx': CHECKOUT_SHA,
    'src/lib/legal/privacy.html': '7e3e8c3707878ebd045a0dc6aa8879ebe4985029d4757db43aea2ebc39e78524',
}
MIGRATION = 'supabase/migrations/20261123090000_mca_google_play.sql'

def digest_files():
    h = hashlib.sha256()
    for file in sorted(FILES.rglob('*')):
        if file.is_file():
            h.update(str(file.relative_to(FILES)).encode())
            h.update(file.read_bytes())
    return h.hexdigest()

def runtime_fingerprint():
    data = json.loads(pay.run('docker','inspect',APP,capture=True))[0]
    env = dict(x.split('=',1) for x in data['Config']['Env'] if '=' in x)
    selected = {k:v for k,v in env.items() if k.startswith(('STRIPE_','SUPABASE_','MCA_CHECKOUT_'))}
    pay.require(all(selected.get(k) for k in ('STRIPE_SECRET_KEY','SUPABASE_SERVICE_ROLE_KEY','SUPABASE_URL')), 'Existing payment configuration unavailable')
    return hashlib.sha256(json.dumps(selected,sort_keys=True).encode()).hexdigest()

def private_environment():
    if not ENV.exists():
        with ENV.open('x') as f:
            f.write('MCA_PLAY_ENABLED=false\nMCA_PLAY_ACCOUNT_SECRET='+secrets.token_hex(32)+'\n')
        ENV.chmod(0o600)
    pay.require(ENV.is_file() and ENV.stat().st_uid==0 and ENV.stat().st_mode & 0o077==0,
                'Google Play settings must be root-owned and mode 0600')

def migrate(source):
    sql = source.read_text().strip()
    pay.require(sql.startswith('BEGIN;') and sql.endswith('COMMIT;'), 'Transactional migration required')
    marker = 'mca-google-play-' + hashlib.sha256(source.read_bytes()).hexdigest()
    psql = ['docker','exec','-i',pay.DB,'psql','-X','-v','ON_ERROR_STOP=1','-U','postgres','-d','postgres']
    state = pay.run(*psql,'-At','-c',"SELECT CASE WHEN to_regclass('public.mca_play_orders') IS NULL THEN 'absent' ELSE coalesce(obj_description(to_regclass('public.mca_play_orders'),'pg_class'),'unknown') END",capture=True).strip()
    if state==marker: return
    pay.require(state=='absent','Existing Play schema differs; stop for review')
    subprocess.run(psql,input=sql[:-7]+f"COMMENT ON TABLE public.mca_play_orders IS '{marker}';\nCOMMIT;\n",text=True,check=True)

def smoke():
    script = """
    (async()=>{
      for(const path of ['/','/privacy','/delete-account']){
        const r=await fetch('http://127.0.0.1:3000'+path);
        if(r.status!==200)throw Error('page');
      }
      const r=await fetch('http://127.0.0.1:3000/api/academy/google-play',{method:'POST'});
      if(r.status!==401||(await r.json()).error!=='authentication_required')throw Error('auth');
      console.log('PLAY_HTTP_SMOKE_OK');
    })().catch(()=>process.exit(1));
    """
    pay.run('docker','exec',APP,'node','-e',script)
    pay.run('docker','exec',APP,'node','--experimental-strip-types','/opt/mca-google-play/scripts/reconcile-google-play.ts')

def timer():
    service = Path('/etc/systemd/system/mca-google-play-reconcile.service')
    unit = '[Unit]\nDescription=Reconcile MCA Google Play purchases\nAfter=docker.service\n\n[Service]\nType=oneshot\nExecStart=/usr/bin/docker exec mca-course-test node --experimental-strip-types /opt/mca-google-play/scripts/reconcile-google-play.ts\nTimeoutStartSec=300\n'
    clock = Path('/etc/systemd/system/mca-google-play-reconcile.timer')
    schedule = '[Unit]\nDescription=Retry MCA purchase confirmation and refunds\n\n[Timer]\nOnBootSec=60\nOnUnitActiveSec=60\nAccuracySec=5\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n'
    for path,body in ((service,unit),(clock,schedule)):
        if path.exists(): pay.require(path.read_text()==body,'Unexpected existing reconciliation timer')
        else: path.write_text(body)
    pay.run('systemctl','daemon-reload')
    pay.run('systemctl','enable','--now',clock.name)

def deploy(mode):
    root,project,service,directory,files,envfiles,previous = pay.inspect_current(APP)
    fingerprint = runtime_fingerprint()
    expected = digest_files()
    if mode=='rollback':
        pay.require((root/MARKER).is_file(),'Current release is not a Google Play release')
        command=json.loads((root/'previous-compose.json').read_text())
        pay.require(command[:4]==['docker','compose','--project-name',project]
                    and command[-6:]==['up','-d','--no-build','--no-deps','--wait',service],'Invalid rollback command')
        pay.run('systemctl','stop','mca-google-play-reconcile.timer')
        pay.run(*command)
        pay.require(runtime_fingerprint()==fingerprint,'Existing payment settings changed')
        print('PLAY_ROLLBACK_OK'); return
    if (root/MARKER).is_file() and (root/MARKER).read_text().strip()==expected:
        smoke(); print('PLAY_RELEASE_ALREADY_ACTIVE'); return
    for relative,expected_sha in REPLACED.items():
        pay.require(hashlib.sha256((root/relative).read_bytes()).hexdigest()==expected_sha,
                    'Existing source changed; review before deploying: '+relative)
    pay.require(directory.is_relative_to(root),'Unexpected Compose directory')
    if mode=='check': print('PLAY_PREFLIGHT_OK'); return
    private_environment()
    target=Path(tempfile.mkdtemp(prefix='google-play-',dir=pay.RELEASES))
    try:
        shutil.copytree(root,target,dirs_exist_ok=True,symlinks=True,
          ignore=shutil.ignore_patterns('node_modules','.git','.output','.tanstack','.vinxi','dist'))
        target.chmod(0o700)
        for source in FILES.rglob('*'):
            if source.is_file():
                destination=target/source.relative_to(FILES)
                if destination.exists() and source.relative_to(FILES).as_posix() not in REPLACED:
                    pay.require(destination.read_bytes()==source.read_bytes(),'Unexpected Play source collision')
                destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source,destination)
        # An independent read-only mount keeps the retry command available in the production image.
        runtime=target/'play-runtime'
        for relative in ('scripts/reconcile-google-play.ts','src/lib/mca-play.server.ts','src/lib/mca-play-domain.ts','src/lib/mca-rpc.server.ts'):
            destination=runtime/relative; destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target/relative,destination)
        (runtime/'package.json').write_text('{"type":"module"}\n')
        for directory_path in [runtime,*[x for x in runtime.rglob('*') if x.is_dir()]]: directory_path.chmod(0o755)
        for file in runtime.rglob('*'):
            if file.is_file(): file.chmod(0o644)
        dest=pay.local_copy(root,target,directory)
        override=dest/'google-play.compose.json'
        override.write_text(json.dumps({'services':{service:{'build':{'context':str(target)},
          'image':'mca-google-play:'+target.name,'env_file':[str(ENV)],
          'volumes':[{'type':'bind','source':str(runtime),'target':'/opt/mca-google-play','read_only':True}]}}}))
        command=pay.compose(project,dest,[*[pay.local_copy(root,target,p) for p in files],override],
          [pay.local_copy(root,target,p) for p in envfiles])
        pay.run(*command,'build',service)
        migrate(target/MIGRATION)
    except BaseException:
        shutil.rmtree(target)
        raise
    up=['up','-d','--no-build','--no-deps','--wait',service]
    (target/'previous-compose.json').write_text(json.dumps(previous+up))
    (target/MARKER).write_text(expected+'\n')
    try:
        pay.run(*command,*up)
        pay.require(runtime_fingerprint()==fingerprint,'Existing Stripe or authentication settings changed')
        smoke()
        timer()
    except BaseException:
        pay.run(*previous,*up)
        raise
    print('PLAY_RELEASE_HEALTHY',target)
    print('Purchasing stays disabled until Google API credentials and Play products are verified.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',nargs='?',choices=('check','deploy','rollback'),default='check')
    args=parser.parse_args()
    os.umask(0o077)
    try:
        pay.require(os.geteuid()==0 and pay.PRIVATE.is_dir(),'Use the Academy server root terminal')
        with (pay.PRIVATE/'checkout-release.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            deploy(args.mode)
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as error:
        if isinstance(error,ValueError): print(str(error),file=sys.stderr)
        sys.exit('Google Play deployment stopped; no secrets printed.')
