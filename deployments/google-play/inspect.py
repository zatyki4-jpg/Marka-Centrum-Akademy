#!/usr/bin/env python3
"""Read-only Google Play readiness audit; never print environment values."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import hashlib

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('mca_release', HERE.parent / 'checkout-120/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

root, *_ = release.inspect_current('mca-course-test')
print('ACTIVE_SOURCE', root)
data = json.loads(subprocess.check_output(['docker', 'inspect', 'mca-course-test'], text=True))[0]
keys = [value.split('=', 1)[0] for value in data['Config']['Env']]
print('GOOGLE_ENV_NAMES', sorted(key for key in keys if any(part in key for part in ('GOOGLE', 'PLAY', 'GCP', 'BILLING'))))
if len(sys.argv) > 1 and sys.argv[1] == 'error':
    print((root / 'src/lib/lovable-error-reporting.ts').read_text())
else:
    for name in ('src/components/CourseCheckout.tsx', 'src/lib/mca-rpc.server.ts'):
        print('SOURCE_SHA256', name, hashlib.sha256((root / name).read_bytes()).hexdigest())
    package = json.loads((root / 'package.json').read_text())
    print('NODE_DEPS', {key: value for key, value in package.get('dependencies', {}).items() if key in ('react','@tanstack/react-start','@tanstack/react-router','@supabase/supabase-js')})
sql = "SELECT table_name || ' ' || string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position) FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('enrollments','courses') GROUP BY table_name ORDER BY 1"
print(subprocess.check_output(['docker','exec','mca-sb-db','psql','-XAt','-v','ON_ERROR_STOP=1','-U','postgres','-d','postgres','-c',sql],text=True))
print('PLAY_READ_ONLY_AUDIT_OK')
