#!/usr/bin/env python3
"""Dedicated, authenticated verification mail API; no Academy source changes."""
import json,os,pwd,secrets,subprocess
from pathlib import Path
ROOT=Path('/srv/roof-pro-mail')
RELAY=r'''#!/usr/bin/env python3
import hashlib,hmac,json,re,smtplib,sqlite3,ssl,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path('/srv/roof-pro-mail')
CONFIG=json.loads((ROOT/'config.json').read_text())
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,status):
  self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"ok":true}' if status==200 else b'{"ok":false}')
 def do_GET(self):self.reply(404)
 def do_POST(self):
  if self.path!='/':self.reply(404);return
  try:
   length=int(self.headers.get('Content-Length','0'));stamp=self.headers.get('X-Roof-Pro-Timestamp','')
   if length<1 or length>2048 or not stamp.isdigit() or abs(time.time()-int(stamp))>300:self.reply(403);return
   body=self.rfile.read(length);expected=hmac.new(CONFIG['secret'].encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
   if not hmac.compare_digest(expected,self.headers.get('X-Roof-Pro-Signature','')):self.reply(403);return
   data=json.loads(body);email=data.get('to','');token=data.get('token','')
   if not re.fullmatch(r'[^\s@\r\n]{1,180}@[^\s@\r\n]{1,180}\.[^\s@\r\n]{2,63}',email) or not re.fullmatch(r'[a-f0-9]{64}',token):self.reply(400);return
   request_id=hashlib.sha256((email+':'+token).encode()).hexdigest()
   with sqlite3.connect(ROOT/'requests.sqlite',timeout=20) as db:
    db.execute('CREATE TABLE IF NOT EXISTS sends(id TEXT PRIMARY KEY,recipient TEXT NOT NULL,created_at REAL NOT NULL)')
    if db.execute('SELECT 1 FROM sends WHERE id=?',(request_id,)).fetchone():self.reply(200);return
    if db.execute('SELECT count(*) FROM sends WHERE recipient=? AND created_at>?',(email,time.time()-3600)).fetchone()[0]>=6:self.reply(429);return
    from email.message import EmailMessage
    message=EmailMessage();message['From']=CONFIG['from'];message['To']=email;message['Subject']='Roof Pro — potwierdź adres e-mail / confirm your email'
    message.set_content('Potwierdź konto Roof Pro. Link jest ważny 24 godziny:\nhttps://dachpro-production.up.railway.app/verify-email#'+token+'\nJeśli nie zakładano konta, zignoruj tę wiadomość.')
    port=int(CONFIG['port']);cls=smtplib.SMTP_SSL if port==465 else smtplib.SMTP
    with cls(CONFIG['host'],port,timeout=20) as smtp:
     if port!=465:smtp.ehlo();smtp.starttls(context=ssl.create_default_context());smtp.ehlo()
     smtp.login(CONFIG['user'],CONFIG['password']);smtp.send_message(message)
    db.execute('INSERT INTO sends VALUES(?,?,?)',(request_id,email,time.time()));db.commit()
   self.reply(200)
  except Exception:
   print('verification_delivery_failed',flush=True);self.reply(502)
ThreadingHTTPServer(('127.0.0.1',3131),Handler).serve_forever()
'''
def install():
 os.umask(0o077)
 auth=json.loads(subprocess.check_output(['docker','inspect','mca-sb-auth'],text=True))[0]
 env=dict(x.split('=',1) for x in auth['Config']['Env'] if '=' in x)
 ROOT.mkdir(mode=0o700,exist_ok=True)
 previous=json.loads((ROOT/'config.json').read_text()) if (ROOT/'config.json').exists() else {}
 config={'secret':previous.get('secret') or secrets.token_hex(32),'host':env['GOTRUE_SMTP_HOST'],'port':env.get('GOTRUE_SMTP_PORT','587'),'user':env['GOTRUE_SMTP_USER'],'password':env['GOTRUE_SMTP_PASS'],'from':env['GOTRUE_SMTP_ADMIN_EMAIL']}
 try:user=pwd.getpwnam('roofpro-mail')
 except KeyError:
  subprocess.run(['useradd','--system','--home-dir','/nonexistent','--shell','/usr/sbin/nologin','roofpro-mail'],check=True);user=pwd.getpwnam('roofpro-mail')
 (ROOT/'config.json').write_text(json.dumps(config));(ROOT/'relay.py').write_text(RELAY)
 for file in [ROOT,*ROOT.iterdir()]:os.chown(file,user.pw_uid,user.pw_gid);file.chmod(0o700 if file.is_dir() else 0o600)
 unit='[Unit]\nDescription=Roof Pro verification mail API\nAfter=network-online.target\n\n[Service]\nUser=roofpro-mail\nGroup=roofpro-mail\nExecStart=/usr/bin/python3 /srv/roof-pro-mail/relay.py\nRestart=on-failure\nNoNewPrivileges=true\nPrivateTmp=true\nPrivateDevices=true\nProtectSystem=strict\nProtectHome=true\nRestrictSUIDSGID=true\nReadWritePaths=/srv/roof-pro-mail\n\n[Install]\nWantedBy=multi-user.target\n'
 Path('/etc/systemd/system/roof-pro-mail.service').write_text(unit)
 subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','enable','--now','roof-pro-mail.service'],check=True);subprocess.run(['systemctl','restart','roof-pro-mail.service'],check=True)
 nginx=Path('/etc/nginx/sites-enabled/zz-marka-course-academy.conf');original=nginx.read_text();block='\n    location = /roof-pro-mail { proxy_pass http://127.0.0.1:3131/; client_max_body_size 2k; proxy_read_timeout 30s; }\n'
 if block not in original:
  if original.count('    location / {')!=1:raise ValueError('Unexpected nginx structure')
  nginx.write_text(original.replace('    location / {',block+'\n    location / {',1))
  try:subprocess.run(['nginx','-t'],check=True);subprocess.run(['systemctl','reload','nginx'],check=True)
  except BaseException:nginx.write_text(original);raise
 print('ROOF_PRO_VERIFICATION_MAIL_API_READY',flush=True)
 return {'MAIL_RELAY_URL':'https://markacentrumacademy.eu/roof-pro-mail','MAIL_RELAY_SECRET':config['secret']}
