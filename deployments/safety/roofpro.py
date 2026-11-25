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
 mca=env('mca-course-test')
 key=mca.get('STRIPE_SECRET_KEY') or p.env_read().get('STRIPE_SECRET_KEY')
 if not key:
  f=p.pay.PRIVATE/'stripe-checkout.env'
  if f.exists():
   p.safe_file(f)
   values=dict(line.split('=',1) for line in f.read_text().splitlines() if line and not line.startswith('#'))
   key=values.get('STRIPE_SECRET_KEY')
 if not key or not key.startswith(('sk_live_','rk_live_')):raise ValueError('MCA_STRIPE_RUNTIME_KEY_MISSING')
 auth=env('mca-sb-auth')
 smtp={'SMTP_HOST':auth.get('GOTRUE_SMTP_HOST',''),'SMTP_PORT':auth.get('GOTRUE_SMTP_PORT','587'),'SMTP_USER':auth.get('GOTRUE_SMTP_USER',''),'SMTP_PASS':auth.get('GOTRUE_SMTP_PASS',''),'MAIL_FROM':auth.get('GOTRUE_SMTP_ADMIN_EMAIL','')}
 if not all(smtp.values()):raise ValueError('MCA_SMTP_CONFIGURATION_INCOMPLETE')
 port=int(smtp['SMTP_PORT'])
 cls=smtplib.SMTP_SSL if port==465 else smtplib.SMTP
 with cls(smtp['SMTP_HOST'],port,timeout=20) as mail:
  if port!=465:mail.ehlo();mail.starttls(context=ssl.create_default_context());mail.ehlo()
  mail.login(smtp['SMTP_USER'],smtp['SMTP_PASS'])
 print('SMTP_AUTHENTICATION_VERIFIED',flush=True)
 smtp['SMTP_SECURE']='true' if port==465 else 'false'
 state=json.loads(STATE.read_text()) if STATE.exists() else {}
 def stripe(path,data=None,idem=None):
  headers={'Authorization':'Bearer '+key,'Stripe-Version':'2026-11-18.endive'}
  if idem:headers['Idempotency-Key']=idem
  encoded=urllib.parse.urlencode(data,doseq=True).encode() if data is not None else None
  req=urllib.request.Request('https://api.stripe.com/v1/'+path,data=encoded,headers=headers)
  try:
   with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read())
  except urllib.error.HTTPError as error:
   body=json.loads(error.read())
   raise ValueError('Stripe '+str(error.code)+' '+str(body.get('error',{}).get('code','request_failed')))
 prices=state.setdefault('prices',{})
 for plan,amount,name in [('byok',2500,'Własne API'),('start-ai',4900,'Start AI'),('pro-ai',9900,'Pro AI')]:
  lookup='roof_pro_'+plan.replace('-','_')+'_monthly_v1'
  existing=stripe('prices?'+urllib.parse.urlencode({'lookup_keys[]':lookup,'limit':1}))
  if existing.get('data'):
   price=existing['data'][0]
  else:
   product=stripe('products',{'name':'Roof Pro — '+name,'metadata[product]':'roof-pro','metadata[plan]':plan},'roofpro-product-v1-'+plan)
   price=stripe('prices',{'product':product['id'],'unit_amount':amount,'currency':'eur','recurring[interval]':'month','tax_behavior':'exclusive','lookup_key':lookup,'metadata[product]':'roof-pro'},'roofpro-price-v1-'+plan)
  if price.get('unit_amount')!=amount or price.get('currency')!='eur' or price.get('tax_behavior')!='exclusive' or price.get('recurring',{}).get('interval')!='month':raise ValueError('STRIPE_PRICE_MISMATCH')
  prices[plan]=price['id'];save(state)
 events=['checkout.session.completed','customer.subscription.updated','customer.subscription.deleted','invoice.paid','invoice.payment_failed','charge.refunded','charge.dispute.created','charge.dispute.closed','refund.updated']
 if not state.get('webhook'):
  state['webhook']=stripe('webhook_endpoints',{'url':ORIGIN+'/api/billing/stripe/webhook','enabled_events[]':events,'api_version':'2026-11-18.endive','description':'Roof Pro subscriptions','metadata[product]':'roof-pro'},'roofpro-webhook-v1')
  save(state)
 if not state.get('portal'):
  state['portal']=stripe('billing_portal/configurations',{'business_profile[headline]':'Roof Pro — abonament','features[subscription_cancel][enabled]':'true','features[subscription_cancel][mode]':'at_period_end','features[payment_method_update][enabled]':'true','features[invoice_history][enabled]':'true','metadata[product]':'roof-pro'},'roofpro-portal-v1')
  save(state)
 probe=stripe('checkout/sessions',{'mode':'subscription','automatic_tax[enabled]':'true','billing_address_collection':'required','tax_id_collection[enabled]':'true','line_items[0][price]':prices['byok'],'line_items[0][quantity]':1,'success_url':ORIGIN+'/?billing=setup','cancel_url':ORIGIN+'/?billing=cancelled','metadata[roofpro_setup]':'true'})
 if not probe.get('url','').startswith('https://checkout.stripe.com/'):raise ValueError('STRIPE_CHECKOUT_NOT_READY')
 stripe('checkout/sessions/'+probe['id']+'/expire',{})
 print('STRIPE_PRICES_WEBHOOK_PORTAL_CHECKOUT_VERIFIED',flush=True)
 variables={**smtp,'APP_ORIGIN':ORIGIN,'EMAIL_VERIFICATION_REQUIRED':'true','COMMERCIAL_SIGNUP':'true','STRIPE_SECRET_KEY':key,'STRIPE_WEBHOOK_SECRET':state['webhook']['secret'],'STRIPE_PRICES_JSON':json.dumps(prices,separators=(',',':')),'STRIPE_PORTAL_CONFIGURATION':state['portal']['id'],'STRIPE_BILLING_ENABLED':'true','STRIPE_AUTOMATIC_TAX':'true','BILLING_PRICES_REVIEWED':'true','GOOGLE_PLAY_BILLING_ENABLED':'false','GOOGLE_PLAY_PACKAGE':'be.markaconstruct.dachpro'}
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
