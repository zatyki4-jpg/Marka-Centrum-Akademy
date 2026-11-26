#!/usr/bin/env python3
"""Provision the approved shared services for Roof Pro; never print secrets."""
import base64, importlib.util, json, os, smtplib, ssl, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path
sys.path = [entry for entry in sys.path if entry and Path(entry).resolve() != Path(__file__).resolve().parent]
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('play',HERE.parent/'google-play/setup.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
ORIGIN='https://dachpro-production.up.railway.app'
PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\nMIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEAslSrJjuVO2s/e881wvPj\nTgDvFcWiMwdmIc3rnM/U+isA4f7g4PEbXzqe4I2LJttBXv7S4TLZABe3ndb1ICHe\nDeQ6SvTv5xh9P2lV76PJeddcA20unlBkUC5J3c84eovKeM/iOXLB+LYdUQtgvZgh\nogq4AJMlA38Fd1CuGD5rr9es3ZWuVZaeUOXKHBwLF2RKz1X/WLnsKaYcFoB2MRy8\naQA9jYRULTaK/MOCQ2gu9/7o8oySalaZjq5Yo5fnUPDelfF8WZwXvxNzXVpU5GJI\nrh4o0Fl1byImhKoQq89SPqvd6xbup8WHAMFin6KzS7wz+75r2sHSWd8bi3Ph4luo\nvCj4h9HJY3lAaqVcEO9VKfCGuvwyz1Ti7mq5/RCgEhKono5uk9LOgno32o7sRmfN\nl9hIRpJwExnXlD0eRix417PcI60osxXP63gXJj5k3LVhL9v8n/HBBgnJ09DKy5ft\nhxmmnlf4r7QdF9818JQzNdR3XRzurAL12emh3s2uQhENAgMBAAE=\n-----END PUBLIC KEY-----\n"
TRANSFER='roofpro-transfer-5795be8d063545feab90aa51154eeecd'
NGINX=Path('/etc/nginx/sites-enabled/zz-marka-course-academy.conf')
DIR=Path('/var/www/roof-pro-transfer')
FILE=DIR/(TRANSFER+'.json')
BLOCK='\n    location = /'+TRANSFER+'.json { alias '+str(FILE)+'; default_type application/json; add_header Cache-Control "no-store" always; }\n'
STATE=p.pay.PRIVATE/'roofpro-services.json'
def env(container):
 d=json.loads(subprocess.check_output(['docker','inspect',container],text=True))[0]
 return dict(x.split('=',1) for x in d['Config']['Env'] if '=' in x)
def save(value):
 p.write_private(STATE,json.dumps(value))
def cleanup():
 original=NGINX.read_text()
 if BLOCK in original:
  NGINX.write_text(original.replace(BLOCK,''))
  try: p.pay.run('nginx','-t');p.pay.run('systemctl','reload','nginx')
  except BaseException: NGINX.write_text(original);raise
 FILE.unlink(missing_ok=True)
 print('PRIVATE_TRANSFER_REMOVED')
def main():
 os.umask(0o077)
 if len(sys.argv)>1 and sys.argv[1]=='cleanup':cleanup();return
 relay_spec=importlib.util.spec_from_file_location('roofpro_billing',HERE/'roofpro_billing.py')
 relay=importlib.util.module_from_spec(relay_spec);relay_spec.loader.exec_module(relay)
 variables=relay.install()
 payload=json.dumps({'service_id':'49bc6414-6a6f-417e-83cc-b00e5d9c53c6','variables':variables}).encode()
 symmetric=os.urandom(32);nonce=os.urandom(12)
 public=serialization.load_pem_public_key(PUBLIC_KEY.encode())
 wrapped=public.encrypt(symmetric,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
 aad=TRANSFER.encode();cipher=AESGCM(symmetric).encrypt(nonce,payload,aad)
 b64=lambda x:base64.b64encode(x).decode()
 sealed=json.dumps({'key':b64(wrapped),'nonce':b64(nonce),'ciphertext':b64(cipher),'aad':TRANSFER})
 DIR.mkdir(mode=0o755,exist_ok=True);DIR.chmod(0o755);FILE.write_text(sealed);FILE.chmod(0o644)
 original=NGINX.read_text()
 if BLOCK not in original:
  p.pay.require(original.count('    location / {')==1,'Unexpected nginx structure')
  NGINX.write_text(original.replace('    location / {',BLOCK+'\n    location / {',1))
  try:p.pay.run('nginx','-t');p.pay.run('systemctl','reload','nginx')
  except BaseException:NGINX.write_text(original);raise
 print('ENCRYPTED_CONFIGURATION_READY https://markacentrumacademy.eu/'+TRANSFER+'.json')
if __name__=='__main__':
 try:main()
 except Exception as error:
  print(str(error) if isinstance(error,ValueError) else type(error).__name__,file=sys.stderr)
  sys.exit(1)
