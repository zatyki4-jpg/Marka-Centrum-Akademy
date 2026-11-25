#!/usr/bin/env python3
"""Add the MCA safety listing with correct scope; preserve all existing checkout flows."""
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ops',HERE.parent/'checkout-120/release.py')
ops=importlib.util.module_from_spec(spec);spec.loader.exec_module(ops)
APP='mca-course-test'

def fingerprint():
    data=json.loads(ops.run('docker','inspect',APP,capture=True))[0]
    return hashlib.sha256(json.dumps(sorted(data['Config']['Env'])).encode()).hexdigest()

def replace(path,before,after):
    text=path.read_text()
    ops.require(text.count(before)==1,'Unexpected source layout: '+path.name)
    path.write_text(text.replace(before,after,1))

def deploy():
    ops.require(os.geteuid()==0,'Existing root session required')
    root,project,service,directory,files,envfiles,previous=ops.inspect_current(APP)
    active=root/'src/components/SafetyCourse.tsx'
    component=HERE/'SafetyCourse.tsx'
    ops.require(component.is_file() and '__MCA_PREVIEW_IMAGE__' not in component.read_text(),'Complete component required')
    if active.exists() and active.read_bytes()==component.read_bytes():
        print('MCA_SAFETY_LISTING_ALREADY_ACTIVE');return
    ops.require(directory.is_relative_to(root),'Unexpected compose directory')
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target=Path(tempfile.mkdtemp(prefix='mca-safety-'+stamp+'-',dir=ops.RELEASES));target.chmod(0o700)
    shutil.copytree(root,target,dirs_exist_ok=True,symlinks=True,ignore=shutil.ignore_patterns('node_modules','.git','.output','.tanstack','.vinxi','dist'))
    card=target/'src/components/CourseCard.tsx'
    route=target/'src/routes/kurs.$slug.tsx'
    if not active.exists():
        replace(card,'export function CourseCard({ course }: { course: Course }) {','function ExistingCourseCard({ course }: { course: Course }) {')
        card.write_text('import { SafetyCourseCard } from "@/components/SafetyCourse";\n'+card.read_text()+'\nexport function CourseCard({ course }: { course: Course }) {\n  return course.slug === "bezpieczenstwo-na-dachu" ? <SafetyCourseCard course={course} /> : <ExistingCourseCard course={course} />;\n}\n')
        replace(route,'function CoursePublicPage() {','function ExistingCoursePublicPage() {')
        route.write_text('import { SafetyCoursePublicPage } from "@/components/SafetyCourse";\n'+route.read_text()+'\nfunction CoursePublicPage() {\n  const { slug } = Route.useParams();\n  return slug === "bezpieczenstwo-na-dachu" ? <SafetyCoursePublicPage /> : <ExistingCoursePublicPage />;\n}\n')
    else:
        ops.require('SafetyCourseCard course={course}' in card.read_text() and '<SafetyCoursePublicPage />' in route.read_text(),'Existing safety routing changed')
    shutil.copyfile(component,target/'src/components/SafetyCourse.tsx')
    target_dir=ops.local_copy(root,target,directory)
    next_files=[ops.local_copy(root,target,p) for p in files]
    next_envs=[ops.local_copy(root,target,p) for p in envfiles]
    override=target_dir/'mca-safety.compose.json'
    override.write_text(json.dumps({'services':{service:{'build':{'context':str(target)},'image':'mca-safety:'+target.name}}}))
    command=ops.compose(project,target_dir,[*next_files,override],next_envs)
    old=json.loads(ops.run(*previous,'config','--format','json',capture=True))
    new=json.loads(ops.run(*command,'config','--format','json',capture=True))
    ops.require(old['services'][service].get('environment')==new['services'][service].get('environment'),'Runtime environment changed')
    before=fingerprint()
    rollback=previous+['up','-d','--no-build','--no-deps','--wait',service]
    (target/'mca-safety-rollback.json').write_text(json.dumps(rollback))
    ops.run(*command,'build',service)
    try:
        ops.run(*command,'up','-d','--no-build','--no-deps','--wait',service)
        ops.require(fingerprint()==before,'Running environment changed')
        for host in ['markacentrumacademy.eu','www.markacentrumacademy.eu']:
            for path in ['/','/katalog','/kurs/bezpieczenstwo-na-dachu','/kurs/bitumiczne-dachy-plaskie','/kurs/renowacja-dachow-plaskich','/privacy']:
                with urllib.request.urlopen('https://'+host+path,timeout=25) as response:
                    ops.require(response.status==200,'HTTP verification failed')
                    if path=='/kurs/bezpieczenstwo-na-dachu':
                        html=response.read().decode()
                        ops.require('Szkolenie MCA: Bezpieczeństwo na dachu' in html and 'Zapisy w przygotowaniu' in html,'Safety page verification failed')
        print('MCA_SAFETY_LISTING_ACTIVE',target)
        print('PRICE_59_BRUTTO THEORY_ONLY ENROLMENT_NOT_OPEN EXISTING_CHECKOUT_UNCHANGED HTTP_OK')
    except BaseException:
        ops.run(*rollback);raise

if __name__=='__main__':
    os.umask(0o077)
    try:
        with (ops.PRIVATE/'checkout-release.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);deploy()
    except Exception as error:
        if isinstance(error,ValueError):print(str(error),file=sys.stderr)
        print('MCA_SAFETY_DEPLOY_STOPPED',type(error).__name__,file=sys.stderr);sys.exit(1)
