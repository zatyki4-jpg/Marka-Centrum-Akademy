import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('play',Path(__file__).resolve().parent.parent/'google-play/setup.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
root,*_=p.pay.inspect_current('mca-course-test')
for name in ['src/routes/index.tsx','src/lib/i18n.tsx','src/lib/mca-purchase-surface.ts']:
 f=root/name
 if f.exists():
  print('FILE',name)
  for n,line in enumerate(f.read_text().splitlines(),1):
   if (name.endswith('index.tsx') and 40<=n<=60) or any(x in line for x in ['export function','interface ','type I18n','createContext','useI18n','lang:','language:','locale:','localStorage','isPlayPurchaseSurface']):print(str(n)+':'+line[:200])
