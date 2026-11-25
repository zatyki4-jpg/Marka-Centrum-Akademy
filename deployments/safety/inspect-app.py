import importlib.util,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('play',Path(__file__).resolve().parent.parent/'google-play/setup.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
root,*_=p.pay.inspect_current('mca-course-test')
print('ACTIVE',root)
for name in ['src/routes/index.tsx','src/routes/__root.tsx','src/components/SiteFooter.tsx']:
 f=root/name
 if f.exists():
  print('FILE',name)
  for n,line in enumerate(f.read_text().splitlines(),1):
   if any(x in line for x in ['import ','<main','<Outlet','<body','<Scripts','</main>','<SiteFooter','function ','return (','manifest']):print(str(n)+':'+line[:220])
