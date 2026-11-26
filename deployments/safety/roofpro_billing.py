#!/usr/bin/env python3
"""Install Roof Pro scoped purchase verifier without exporting Google credentials."""
import importlib.util,json,os,pwd,secrets,subprocess
from pathlib import Path
ROOT=Path('/srv/roof-pro-billing')
RELAY=r'''#!/usr/bin/env python3
import base64,hashlib,hmac,json,re,subprocess,threading,time,urllib.request,urllib.error,urllib.parse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path('/srv/roof-pro-billing')
CONFIG=json.loads((ROOT/'config.json').read_text())
PACKAGE='be.markaconstruct.dachpro'
PRODUCTS={'roofpro_byok','roofpro_start_ai','roofpro_pro_ai'}
LOCK=threading.Lock();CACHE={};LIMIT={}
def oauth():
 with LOCK:
  if CACHE.get('expires',0)>time.time()+120:return CACHE['token']
  enc=lambda x:base64.urlsafe_b64encode(json.dumps(x,separators=(',',':')).encode()).rstrip(b'=')
  now=int(time.time());unsigned=enc({'alg':'RS256','typ':'JWT'})+b'.'+enc({'iss':CONFIG['email'],'scope':'https://www.googleapis.com/auth/androidpublisher','aud':'https://oauth2.googleapis.com/token','iat':now,'exp':now+3600})
  signed=subprocess.check_output(['openssl','dgst','-sha256','-sign',str(ROOT/'google-private.pem')],input=unsigned,timeout=10)
  assertion=unsigned+b'.'+base64.urlsafe_b64encode(signed).rstrip(b'=')
  body=urllib.parse.urlencode({'grant_type':'urn:ietf:params:oauth:grant-type:jwt-bearer','assertion':assertion.decode()}).encode()
  with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',data=body),timeout=15) as response:result=json.load(response)
  CACHE.update(token=result['access_token'],expires=time.time()+int(result.get('expires_in',3600)))
  return CACHE['token']
def verify(data):
 token=data.get('token');method=data.get('method');product=data.get('productId')
 if not isinstance(token,str) or not 1<=len(token)<=4096 or re.search(r'[\x00-\x20\x7f]',token):raise ValueError('token')
 if method not in ('GET','POST') or (method=='POST' and product not in PRODUCTS):raise ValueError('method')
 base='https://androidpublisher.googleapis.com/androidpublisher/v3/applications/'+PACKAGE
 if method=='GET':url=base+'/purchases/subscriptionsv2/tokens/'+urllib.parse.quote(token,safe='');body=None
 else:url=base+'/purchases/subscriptions/'+product+'/tokens/'+urllib.parse.quote(token,safe='')+':acknowledge';body=b'{}'
 request=urllib.request.Request(url,data=body,method=method,headers={'Authorization':'Bearer '+oauth(),'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=20) as response:
  raw=response.read(131073)
  if len(raw)>131072:raise ValueError('size')
  result=json.loads(raw) if raw else {}
 if method=='POST':return {}
 # Return only fields consumed by commerce.mjs. No purchaser name, email or order data.
 fields=('subscriptionState','acknowledgementState','startTime','testPurchase')
 out={k:result[k] for k in fields if k in result}
 external=result.get('externalAccountIdentifiers',{})
 out['externalAccountIdentifiers']={'obfuscatedExternalAccountId':external.get('obfuscatedExternalAccountId')}
 out['lineItems']=[{'productId':x.get('productId'),'expiryTime':x.get('expiryTime'),'offerDetails':{'basePlanId':x.get('offerDetails',{}).get('basePlanId')}} for x in result.get('lineItems',[])]
 return out
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,status,value=None):
  raw=json.dumps(value if value is not None else {'ok':False}).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):self.reply(404)
 def do_POST(self):
  if self.path!='/':self.reply(404);return
  try:
   size=int(self.headers.get('Content-Length','0'));stamp=self.headers.get('X-Roof-Pro-Timestamp','')
   if not 1<=size<=8192 or not stamp.isdigit() or abs(time.time()-int(stamp))>120:self.reply(403);return
   raw=self.rfile.read(size);signature=hmac.new(CONFIG['secret'].encode(),stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
   if not hmac.compare_digest(signature,self.headers.get('X-Roof-Pro-Signature','')):self.reply(403);return
   with LOCK:
    minute=int(time.time()//60)
    if LIMIT.get('minute')!=minute:LIMIT.update(minute=minute,count=0)
    LIMIT['count']+=1
    if LIMIT['count']>300:self.reply(429);return
   self.reply(200,verify(json.loads(raw)))
  except (ValueError,TypeError,KeyError):self.reply(400)
  except urllib.error.HTTPError as error:self.reply(error.code if error.code in (400,401,403,404,409,410,429) else 502)
  except Exception:
   print('purchase_verification_unavailable',flush=True);self.reply(502)
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',3132),Handler).serve_forever()
'''
def install():
 os.umask(0o077)
 here=Path(__file__).resolve().parent
 spec=importlib.util.spec_from_file_location('mca_play',here.parent/'google-play/setup.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
 ROOT.mkdir(mode=0o700,exist_ok=True)
 prior=json.loads((ROOT/'config.json').read_text()) if (ROOT/'config.json').exists() else {}
 secret=prior.get('secret') or secrets.token_hex(32)
 try:user=pwd.getpwnam('roofpro-billing')
 except KeyError:
  subprocess.run(['useradd','--system','--home-dir','/nonexistent','--shell','/usr/sbin/nologin','roofpro-billing'],check=True);user=pwd.getpwnam('roofpro-billing')
 (ROOT/'config.json').write_text(json.dumps({'email':p.EMAIL,'secret':secret}));(ROOT/'google-private.pem').write_text(p.KEY.read_text());(ROOT/'relay.py').write_text(RELAY)
 for file in [ROOT,*ROOT.iterdir()]:os.chown(file,user.pw_uid,user.pw_gid);file.chmod(0o700 if file.is_dir() else 0o600)
 unit='[Unit]\nDescription=Roof Pro scoped Google Play purchase verification\nAfter=network-online.target\n\n[Service]\nUser=roofpro-billing\nGroup=roofpro-billing\nExecStart=/usr/bin/python3 /srv/roof-pro-billing/relay.py\nRestart=on-failure\nNoNewPrivileges=true\nPrivateTmp=true\nPrivateDevices=true\nProtectSystem=strict\nProtectHome=true\nRestrictSUIDSGID=true\n\n[Install]\nWantedBy=multi-user.target\n'
 Path('/etc/systemd/system/roof-pro-billing.service').write_text(unit)
 subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','enable','--now','roof-pro-billing.service'],check=True);subprocess.run(['systemctl','restart','roof-pro-billing.service'],check=True)
 nginx=Path('/etc/nginx/sites-enabled/zz-marka-course-academy.conf');original=nginx.read_text();block='\n    location = /roof-pro-billing { proxy_pass http://127.0.0.1:3132/; client_max_body_size 8k; proxy_read_timeout 45s; access_log off; }\n'
 if block not in original:
  if original.count('    location / {')!=1:raise ValueError('Unexpected nginx structure')
  nginx.write_text(original.replace('    location / {',block+'\n    location / {',1))
  try:subprocess.run(['nginx','-t'],check=True);subprocess.run(['systemctl','reload','nginx'],check=True)
  except BaseException:nginx.write_text(original);raise
 print('ROOF_PRO_SCOPED_BILLING_READY',flush=True)
 return {'GOOGLE_PLAY_RELAY_URL':'https://markacentrumacademy.eu/roof-pro-billing','GOOGLE_PLAY_RELAY_SECRET':secret}
