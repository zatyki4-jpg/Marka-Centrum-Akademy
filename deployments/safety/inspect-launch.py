import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('play',Path(__file__).resolve().parent.parent/'google-play/setup.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
root,*_=p.pay.inspect_current('mca-course-test')
mode=sys.argv[1] if len(sys.argv)>1 else 'schema'
print('COURSE',p.psql("SELECT id::text||' price='||price_cents::text FROM public.courses WHERE slug='bezpieczenstwo-na-dachu';"))
if mode=='schema':
 print(p.psql("SELECT table_name||':'||string_agg(column_name||'='||data_type,',' ORDER BY ordinal_position) FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('final_exams','quizzes','quiz_questions','quiz_options','quiz_question_translations','quiz_option_translations','exam_attempts','certificates') GROUP BY table_name ORDER BY table_name;"))
 print('FUNCTIONS',p.psql("SELECT routine_name FROM information_schema.routines WHERE routine_schema='public' AND (routine_name LIKE '%exam%' OR routine_name LIKE '%certif%');"))
 print('EXAM_CONFIG',p.psql('SELECT row_to_json(f) FROM public.final_exams f LIMIT 2;'))
 print('QUIZ_CONFIG',p.psql('SELECT row_to_json(q) FROM public.quizzes q LIMIT 1;'))
elif mode=='files':
 print('EXAM_FILES',*[str(x.relative_to(root)) for x in (root/'src').rglob('*') if x.is_file() and any(t in x.name.lower() for t in ['exam','certif','quiz','lessoncontent'])],sep='\n')
 print('DEPENDENCIES',json.dumps(json.loads((root/'package.json').read_text()).get('dependencies',{})))
elif mode=='policies':
 print(p.psql("SELECT tablename||' '||policyname||' '||coalesce(qual,'') FROM pg_policies WHERE schemaname='public' AND tablename IN ('lessons','course_translations','lesson_translations','quiz_questions','quiz_options','final_exams');"))
elif mode=='columns':
 table=sys.argv[2]
 assert table in ['quizzes','quiz_questions','quiz_options','final_exams','certificates','exam_attempts']
 print(p.psql("SELECT column_name||':'||is_nullable||':'||coalesce(column_default,'') FROM information_schema.columns WHERE table_schema='public' AND table_name=:'table' ORDER BY ordinal_position;",table=table))
