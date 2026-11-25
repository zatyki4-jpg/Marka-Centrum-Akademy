#!/usr/bin/env python3
import importlib.util,json,subprocess,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('play',Path(__file__).resolve().parent.parent/'google-play/setup.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
def env(container):
 data=json.loads(subprocess.check_output(['docker','inspect',container],text=True))[0]
 return dict(x.split('=',1) for x in data['Config']['Env'] if '=' in x)
mca=env('mca-course-test')
private=p.env_read()
names=subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines()
auth=[name for name in names if name.startswith('mca-') and 'auth' in name]
print('STRIPE_KEY_PRESENT',bool(private.get('STRIPE_SECRET_KEY')))
print('MCA_SMTP_NAMES',[key for key in mca if 'SMTP' in key or key in ['MAIL_FROM','RESEND_API_KEY']])
for name in auth:
 values=env(name)
 print('AUTH_SERVICE',name,'SMTP_FIELDS',[(key,bool(value)) for key,value in values.items() if key.startswith('GOTRUE_SMTP_')])
try:
 import cryptography
 print('CRYPTOGRAPHY_AVAILABLE')
except ImportError:print('CRYPTOGRAPHY_NOT_INSTALLED')
