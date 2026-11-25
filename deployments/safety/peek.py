import importlib.util
from pathlib import Path
import sys
spec=importlib.util.spec_from_file_location('play',Path(__file__).resolve().parent.parent/'google-play/setup.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
root,*_=p.pay.inspect_current('mca-course-test')
files={'card':'src/components/CourseCard.tsx','format':'src/lib/format.ts','route':'src/routes/kurs.$slug.tsx','checkout':'src/components/CourseCheckout.tsx','queries':'src/lib/queries.ts'}
path=root/files[sys.argv[1]]
start=int(sys.argv[2]) if len(sys.argv)>2 else 1
lines=path.read_text().splitlines()
print('FILE',files[sys.argv[1]],'TOTAL',len(lines))
for i,line in enumerate(lines[start-1:start+39],start):print(str(i)+':'+line)
