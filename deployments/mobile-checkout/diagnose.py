#!/usr/bin/env python3
"""Read-only MCA sign-in diagnosis; prints no credentials, tokens or IP addresses."""
import importlib.util
import json
from pathlib import Path
import subprocess
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("play",HERE.parent/"google-play/setup.py")
play=importlib.util.module_from_spec(spec)
spec.loader.exec_module(play)
root,*_=play.pay.inspect_current(play.APP)
print("AUTH_FORM")
for path in sorted((root/"src/routes").glob("*auth*.tsx")):
    print("FILE",path.name)
    lines=path.read_text().splitlines()
    selected=set()
    for i,line in enumerate(lines):
        if any(key in line for key in ["signInWithPassword","type=\"email\"","type=\"password\"","autoComplete","setEmail","setPassword","email:","password:"]):
            selected.update(range(max(0,i-2),min(len(lines),i+4)))
    for i in sorted(selected):
        print(str(i+1)+":",lines[i])
print("AUTH_SERVICE_EVENTS")
containers=subprocess.check_output(["docker","ps","--format","{{.Names}}"],text=True).splitlines()
for container in containers:
    if "mca" not in container or "auth" not in container:
        continue
    result=subprocess.run(["docker","logs","--since","40m","--tail","400",container],capture_output=True,text=True)
    for line in (result.stdout+"\n"+result.stderr).splitlines():
        try: event=json.loads(line)
        except json.JSONDecodeError: continue
        if "/token" not in str(event.get("path","")) and "invalid" not in str(event.get("error_code","")):
            continue
        print(json.dumps({key:event[key] for key in ["time","timestamp","level","path","method","status","error_code","duration"] if key in event}))
print("TEST_ACCOUNT_STATUS")
print(play.psql("SELECT json_build_object('confirmed',email_confirmed_at IS NOT NULL,'banned',banned_until>now(),'last_sign_in',last_sign_in_at,'identities',(SELECT count(*) FROM auth.identities i WHERE i.user_id=u.id)) FROM auth.users u WHERE lower(email)=:'email';",email="play-test@markacentrumacademy.eu"))
