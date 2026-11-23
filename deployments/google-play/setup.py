#!/usr/bin/env python3
"""Server-only MCA Play provisioning. Never print private keys or API tokens."""
import argparse
import base64
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('play_release', HERE / 'release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
pay = release.pay
PRIVATE = pay.PRIVATE
KEY = PRIVATE / 'google-play-private.pem'
CERT = PRIVATE / 'google-play-public.pem'
CERT_NAME = 'mca-play-public-certificate.pem'
EMAIL = 'mca-play-verifier@mca-play-billing-583789026013.iam.gserviceaccount.com'
PROJECT = 'mca-play-billing-583789026013'
APP = release.APP
CERT_DIR = Path('/var/www/mca-play-public')
NGINX = Path('/etc/nginx/sites-enabled/zz-marka-course-academy.conf')
BLOCK = '\n    # MCA temporary public certificate exchange\n    location = /'+CERT_NAME+' {\n        alias '+str(CERT_DIR/CERT_NAME)+';\n        default_type text/plain;\n        add_header Cache-Control "no-store" always;\n    }\n'
COURSES = ['11111111-1111-4111-8111-111111111111','f166433e-5157-4341-9a38-800c62795ebd']
SKUS = ['mca_bitumen_basic_lifetime','mca_bitumen_renovation_lifetime']
BASE = 'https://androidpublisher.googleapis.com/androidpublisher/v3/applications/eu.markacentrumacademy.app'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('Unexpected HTTP redirect')

def http(url, data=None, headers=None, method=None):
    pay.require(urllib.parse.urlsplit(url).hostname in
                ['oauth2.googleapis.com','androidpublisher.googleapis.com','api.markacentrumacademy.eu','markacentrumacademy.eu'],
                'Unexpected API host')
    request = urllib.request.Request(url,data=data,headers=headers or {},method=method)
    try:
        with urllib.request.build_opener(NoRedirect).open(request,timeout=25) as r:
            body=r.read(1048576)
            return r.status,json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        try: body=json.loads(error.read(16384))
        except Exception: body=None
        return error.code, body

def psql(sql, **params):
    command=['docker','exec','-i',pay.DB,'psql','-XAtq','-v','ON_ERROR_STOP=1','-U','postgres','-d','postgres']
    for key,value in params.items(): command += ['-v',key+'='+str(value)]
    return subprocess.check_output(command,input=sql,text=True).strip()

def safe_file(path):
    pay.require(path.is_file() and not path.is_symlink() and path.stat().st_uid == 0
                and path.stat().st_mode & 0o077 == 0, 'Private file permissions invalid')

def write_private(path, body):
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('x') as f:
        f.write(body)
    temp.chmod(0o600)
    os.replace(temp, path)

def env_read():
    safe_file(release.ENV)
    return dict(line.split('=', 1) for line in release.ENV.read_text().splitlines()
                if line and not line.startswith('#'))

def env_write(values):
    write_private(release.ENV, ''.join(k+'='+v+'\n' for k,v in values.items()))

def prepare():
    release.private_environment()
    if not KEY.exists() and not CERT.exists():
        subprocess.run(['openssl','req','-x509','-nodes','-newkey','rsa:2048','-days','365',
                        '-keyout',str(KEY),'-out',str(CERT),'-subj','/CN=unused'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        KEY.chmod(0o600)
        CERT.chmod(0o600)
    safe_file(KEY)
    safe_file(CERT)
    # Verify the certificate belongs to this server key without exposing either key.
    a = pay.run('openssl','pkey','-in',KEY,'-pubout',capture=True)
    b = pay.run('openssl','x509','-in',CERT,'-pubkey','-noout',capture=True)
    pay.require(a == b, 'Public/private key mismatch')
    values = env_read()
    credential = {'type':'service_account','project_id':PROJECT,'client_email':EMAIL,
                  'private_key':KEY.read_text(),'token_uri':'https://oauth2.googleapis.com/token'}
    encoded = base64.b64encode(json.dumps(credential).encode()).decode()
    pay.require(not values.get('GOOGLE_PLAY_SERVICE_ACCOUNT_B64') or
                values['GOOGLE_PLAY_SERVICE_ACCOUNT_B64'] == encoded, 'Unexpected existing credential')
    values['GOOGLE_PLAY_SERVICE_ACCOUNT_B64'] = encoded
    env_write(values)
    # Publish only a validated public certificate through one exact temporary URL.
    public = CERT.read_bytes()
    pay.require(public.startswith(b'-----BEGIN CERTIFICATE-----') and b'PRIVATE KEY' not in public,
                'Only a public certificate may leave the private directory')
    CERT_DIR.mkdir(mode=0o755,exist_ok=True)
    CERT_DIR.chmod(0o755)
    (CERT_DIR/CERT_NAME).write_bytes(public)
    (CERT_DIR/CERT_NAME).chmod(0o644)
    original=NGINX.read_text()
    if BLOCK not in original:
        pay.require('markacentrumacademy.eu' in original and original.count('location / {') == 1,
                    'Unexpected MCA nginx configuration')
        if not (PRIVATE/'play-certificate-nginx-before.conf').exists():
            write_private(PRIVATE/'play-certificate-nginx-before.conf',original)
        modified=original.replace('    location / {',BLOCK+'\n    location / {',1)
        pay.require(modified != original,'Unexpected nginx indentation')
        NGINX.write_text(modified)
        try:
            pay.run('nginx','-t')
            pay.run('systemctl','reload','nginx')
        except BaseException:
            NGINX.write_text(original)
            raise
    print('PLAY_KEY_PREPARED_PRIVATE_ON_SERVER')
    print('PUBLIC_CERTIFICATE_SHA256', hashlib.sha256(CERT.read_bytes()).hexdigest())
    try:
        with urllib.request.urlopen('https://markacentrumacademy.eu/'+CERT_NAME,timeout=15) as r:
            public = r.read(8192)
        pay.require(public == CERT.read_bytes(), 'Public certificate endpoint differs')
        print('PUBLIC_CERTIFICATE_URL https://markacentrumacademy.eu/'+CERT_NAME)
    except Exception:
        raise ValueError('Public certificate HTTPS verification failed')

def google_token():
    safe_file(KEY)
    enc=lambda value:base64.urlsafe_b64encode(json.dumps(value,separators=(',',':')).encode()).rstrip(b'=')
    now=int(time.time())
    unsigned=enc({'alg':'RS256','typ':'JWT'})+b'.'+enc({'iss':EMAIL,
        'scope':'https://www.googleapis.com/auth/androidpublisher','aud':'https://oauth2.googleapis.com/token',
        'iat':now,'exp':now+3600})
    signature=subprocess.check_output(['openssl','dgst','-sha256','-sign',str(KEY)],input=unsigned)
    assertion=unsigned+b'.'+base64.urlsafe_b64encode(signature).rstrip(b'=')
    status,body=http('https://oauth2.googleapis.com/token',
        urllib.parse.urlencode({'grant_type':'urn:ietf:params:oauth:grant-type:jwt-bearer','assertion':assertion.decode()}).encode(),
        {'Content-Type':'application/x-www-form-urlencoded'})
    pay.require(status==200 and body.get('access_token'),'Google OAuth verification failed: '+str(status))
    return body['access_token']

def probe():
    token=google_token()
    for sku in SKUS:
        status,body=http(BASE+'/oneTimeProducts/'+sku,headers={'Authorization':'Bearer '+token})
        pay.require(status==200,'Google product API failed: '+str(status))
        options=[o for o in body.get('purchaseOptions',[]) if o.get('purchaseOptionId')=='lifetime']
        pay.require(len(options)==1 and options[0].get('state')=='ACTIVE' and 'buyOption' in options[0],
                    'Expected active lifetime purchase option')
        regions=options[0].get('regionalPricingAndAvailabilityConfigs',[])
        be=[r for r in regions if r.get('regionCode')=='BE']
        pay.require(len(be)==1 and be[0].get('availability')=='AVAILABLE','Belgian product unavailable')
        price=be[0].get('price',{})
        pay.require(price.get('currencyCode')=='EUR' and int(price.get('units',0))==120 and int(price.get('nanos',0))==0,
                    'Belgian Google Play gross price differs from EUR 120')
        print('PLAY_PRODUCT_VERIFIED',sku,'ACTIVE BE EUR 120.00')
    status,body=http(BASE+'/purchases/voidedpurchases?maxResults=1',headers={'Authorization':'Bearer '+token})
    pay.require(status==200,'Google purchases permission check failed: '+str(status))
    status,body=http(BASE+'/purchases/productsv2/tokens/mca-configuration-invalid-token',headers={'Authorization':'Bearer '+token})
    # The request contains a deliberately invalid, non-secret token. Print only its error classification.
    error=(body or {}).get('error',{})
    print('PLAY_INVALID_TOKEN_RESPONSE',status,error.get('status'),
          [e.get('reason') for e in error.get('errors',[])])
    pay.require(status in (400,401,404),'Unexpected invalid-token result: '+str(status))
    print('PLAY_GOOGLE_API_READY')

def activate():
    probe()
    values=env_read()
    original=release.ENV.read_text()
    fingerprint=release.runtime_fingerprint()
    root,project,service,directory,files,envfiles,command=pay.inspect_current(APP)
    pay.require((root/release.MARKER).is_file(),'Google Play release required')
    values['MCA_PLAY_ENABLED']='true'
    env_write(values)
    try:
        pay.run(*command,'up','-d','--force-recreate','--no-build','--no-deps','--wait',service)
        pay.require(release.runtime_fingerprint()==fingerprint,'Existing Stripe/auth settings changed')
        release.smoke()
    except BaseException:
        write_private(release.ENV,original)
        pay.run(*command,'up','-d','--force-recreate','--no-build','--no-deps','--wait',service)
        raise
    print('PLAY_PURCHASING_ENABLED')

def runtime_env():
    data=json.loads(pay.run('docker','inspect',APP,capture=True))[0]
    return dict(x.split('=',1) for x in data['Config']['Env'] if '=' in x)

def student(kind):
    pay.require(kind in ('review','test'),'Unknown student type')
    env=runtime_env()
    url=env['SUPABASE_URL'].rstrip('/')
    pay.require(url=='https://api.markacentrumacademy.eu','Unexpected authentication service')
    storage=PRIVATE/('google-play-'+kind+'-login.json')
    email='play-'+kind+'@markacentrumacademy.eu'
    if storage.exists():
        safe_file(storage)
        login=json.loads(storage.read_text())
        pay.require(login['email']==email,'Unexpected saved student account')
    else:
        existing=psql("SELECT id FROM auth.users WHERE lower(email)=:'email';",email=email)
        pay.require(not existing,'Existing student account requires review')
        login={'email':email,'password':'MCA-'+kind+'-'+secrets.token_hex(12)}
        write_private(storage,json.dumps(login))
    uid=psql("SELECT id FROM auth.users WHERE lower(email)=:'email';",email=email)
    if not uid:
        status,user=http(url+'/auth/v1/admin/users',json.dumps({**login,'email_confirm':True,
            'user_metadata':{'full_name':'Google Play '+kind.title(),'mca_play_account':kind}}).encode(),
            {'Content-Type':'application/json','apikey':env['SUPABASE_SERVICE_ROLE_KEY'],
             'Authorization':'Bearer '+env['SUPABASE_SERVICE_ROLE_KEY']})
        pay.require(status in (200,201),'Student creation failed: '+str(status))
        uid=str(uuid.UUID(user['id']))
    user_id=str(uuid.UUID(uid))
    marked=psql("SELECT (raw_user_meta_data->>'mca_play_account') FROM auth.users WHERE id=:'uid'::uuid;",uid=user_id)
    pay.require(marked==kind,'Existing user is not the dedicated Play account')
    admins=psql("SELECT count(*) FROM public.user_roles WHERE user_id=:'uid'::uuid AND role='admin';",uid=user_id)
    pay.require(admins=='0','Review/test accounts must not be administrators')
    status,session=http(url+'/auth/v1/token?grant_type=password',json.dumps(login).encode(),
        {'Content-Type':'application/json','apikey':env['SUPABASE_PUBLISHABLE_KEY']})
    pay.require(status==200 and session['user']['id']==user_id,'Student sign-in failed: '+str(status))
    headers={'Authorization':'Bearer '+session['access_token'],'Content-Type':'application/json',
             'Origin':'https://markacentrumacademy.eu'}
    for course,sku in zip(COURSES,SKUS):
        status,body=http('https://markacentrumacademy.eu/api/academy/google-play',
            json.dumps({'action':'config','courseId':course}).encode(),headers)
        pay.require(status==200 and body.get('ok') is True,'Authenticated billing config failed: '+str(status))
        if body.get('status')=='ready':
            pay.require(body.get('sku')==sku and re.fullmatch('[a-f0-9]{64}',body.get('accountId','')),
                        'Invalid billing identity or SKU')
        else:
            pay.require(kind=='review' and body.get('status')=='already_enrolled','Test student must be unenrolled')
    status,body=http('https://markacentrumacademy.eu/api/academy/google-play',
        json.dumps({'action':'verify','courseId':COURSES[0],'purchaseToken':'mca-configuration-invalid-token'}).encode(),headers)
    pay.require(status in (409,503) and body.get('error') in ('purchase_not_found','billing_unavailable'),
                'Invalid purchase was not rejected')
    orders=psql("SELECT count(*) FROM public.mca_play_orders WHERE user_id=:'uid'::uuid;",uid=user_id)
    pay.require(orders=='0','Unexpected purchase recorded for the new Play account')
    if kind=='review':
        psql("""BEGIN;
INSERT INTO public.enrollments(user_id,course_id,status,activation_date,expiry_date,promo_access)
SELECT :'uid'::uuid,id,'active',now(),NULL,true FROM public.courses
WHERE id IN (:'basic'::uuid,:'renovation'::uuid)
ON CONFLICT(user_id,course_id) DO UPDATE SET status='active',expiry_date=NULL,promo_access=true;
COMMIT;""",uid=user_id,basic=COURSES[0],renovation=COURSES[1])
        count=psql("SELECT count(*) FROM public.enrollments WHERE user_id=:'uid'::uuid AND status='active' AND expiry_date IS NULL;",uid=user_id)
        pay.require(count=='2','Reviewer needs both courses')
    print('PLAY_STUDENT_READY',kind,email,'administrator=false','courses=2' if kind=='review' else 'courses=0')
    print('PLAY_AUTHENTICATED_CONFIG_OK INVALID_PURCHASE_REJECTED')

def cleanup():
    original=NGINX.read_text()
    if BLOCK in original:
        NGINX.write_text(original.replace(BLOCK,''))
        try:
            pay.run('nginx','-t')
            pay.run('systemctl','reload','nginx')
        except BaseException:
            NGINX.write_text(original)
            raise
    (CERT_DIR/CERT_NAME).unlink(missing_ok=True)
    print('PUBLIC_CERTIFICATE_EXCHANGE_REMOVED')

def show(kind):
    path=PRIVATE/('google-play-'+kind+'-login.json')
    safe_file(path)
    login=json.loads(path.read_text())
    print('PLAY_'+kind.upper()+'_LOGIN',login['email'])
    print('PASSWORD',login['password'])

def inspect():
    root,*_ = pay.inspect_current(APP)
    print('ACTIVE_RELEASE',root)
    print('PLAY_ENV_PRESENT',release.ENV.exists())
    print('CERTIFICATE_PRESENT',CERT.exists())

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','inspect','probe','activate','review','test','cleanup','show-review','show-test'])
    args = parser.parse_args()
    os.umask(0o077)
    try:
        pay.require(os.geteuid()==0 and PRIVATE.is_dir(),'Use the approved Academy server root terminal')
        with (PRIVATE/'checkout-release.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            {'prepare':prepare,'inspect':inspect,'probe':probe,'activate':activate,
             'review':lambda:student('review'),'test':lambda:student('test'),'cleanup':cleanup,
             'show-review':lambda:show('review'),'show-test':lambda:show('test')}[args.mode]()
    except Exception as error:
        if isinstance(error,ValueError): print(str(error),file=sys.stderr)
        sys.exit('MCA Play setup stopped; no secrets printed.')
