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
import subprocess
import sys
import urllib.request

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
    # Only the PUBLIC certificate is copied out of the private server directory.
    pay.run('docker','cp',CERT,APP+':/app/.output/public/'+CERT_NAME)
    pay.run('docker','exec','-u','0',APP,'chmod','644','/app/.output/public/'+CERT_NAME)
    print('PLAY_KEY_PREPARED_PRIVATE_ON_SERVER')
    print('PUBLIC_CERTIFICATE_SHA256', hashlib.sha256(CERT.read_bytes()).hexdigest())
    try:
        with urllib.request.urlopen('https://markacentrumacademy.eu/'+CERT_NAME,timeout=15) as r:
            public = r.read(8192)
        pay.require(public == CERT.read_bytes(), 'Public certificate endpoint differs')
        print('PUBLIC_CERTIFICATE_URL https://markacentrumacademy.eu/'+CERT_NAME)
    except Exception:
        print('PUBLIC_CERTIFICATE_NOT_SERVED')
        print('NGINX_ACADEMY_CONFIG_FILES')
        for path in Path('/etc/nginx/sites-enabled').glob('*'):
            if path.is_file() and 'markacentrumacademy.eu' in path.read_text():
                print(str(path))
                # Inspect only the public web routing, never print unrelated upstream settings.
                for line in path.read_text().splitlines():
                    if any(s in line for s in ('server_name','location','root ','alias ','include ')):
                        print(line.strip())

def inspect():
    root,*_ = pay.inspect_current(APP)
    print('ACTIVE_RELEASE',root)
    print('PLAY_ENV_PRESENT',release.ENV.exists())
    print('CERTIFICATE_PRESENT',CERT.exists())

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','inspect'])
    args = parser.parse_args()
    os.umask(0o077)
    try:
        pay.require(os.geteuid()==0 and PRIVATE.is_dir(),'Use the approved Academy server root terminal')
        with (PRIVATE/'checkout-release.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            {'prepare':prepare,'inspect':inspect}[args.mode]()
    except Exception as error:
        if isinstance(error,ValueError): print(str(error),file=sys.stderr)
        sys.exit('MCA Play setup stopped; no secrets printed.')
