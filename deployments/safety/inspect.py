#!/usr/bin/env python3
"""Read only, scoped Academy safety-course preflight; never output credentials."""
import importlib.util
from pathlib import Path

here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('play', here.parent / 'google-play/setup.py')
play = importlib.util.module_from_spec(spec)
spec.loader.exec_module(play)
root, *_ = play.pay.inspect_current('mca-course-test')
print('ROOT', root)
for relative in ['src/routes/kurs.$slug.tsx', 'src/components/CourseCard.tsx', 'src/components/CourseCheckout.tsx', 'src/components/PlayCourseCheckout.tsx', 'src/lib/queries.ts']:
    path = root / relative
    if not path.is_file():
        print('MISSING', relative)
        continue
    lines = path.read_text().splitlines()
    print('FILE', relative, len(lines))
    keys = ['export ', 'function ', 'course.', 'getCourseLevel', 'MasterPath', 'CourseCheckout', 'PlayCourseCheckout', 'fetchCourseBySlug', 'fetchStages', '.eq(', '.from(', 'createSignedUrl']
    for number, line in enumerate(lines, 1):
        if any(key in line for key in keys):
            print(str(number), line[:190])
print('SCHEMA')
print(play.psql("SELECT table_name||':'||string_agg(column_name||'='||data_type,',' ORDER BY ordinal_position) FROM information_schema.columns WHERE table_schema='public' AND (table_name LIKE '%course%' OR table_name LIKE '%stage%' OR table_name LIKE '%lesson%') GROUP BY table_name ORDER BY table_name;"))
print('BUCKETS', play.psql('SELECT id||\':\'||public::text FROM storage.buckets;'))
