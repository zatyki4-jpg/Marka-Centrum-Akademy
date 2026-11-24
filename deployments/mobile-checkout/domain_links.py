#!/usr/bin/env python3
"""Publish the Google Play Console-provided MCA domain association, with rollback."""
import datetime
import fcntl
import json
import os
from pathlib import Path
import subprocess
import urllib.request
CONFIG=Path("/etc/nginx/sites-enabled/zz-marka-course-academy.conf")
PRIVATE=Path("/srv/marka-course-academy/private")
ROOT=Path("/var/www/mca-digital-asset-links")
FILE=ROOT/"assetlinks.json"
FINGERPRINT="31:9B:ED:7F:5A:DC:82:A5:B3:51:C7:F8:30:8D:92:45:7B:AA:18:C2:0A:C4:AD:22:9A:FA:24:AA:08:2C:20:01"
STATEMENTS=[{"relation":["delegate_permission/common.handle_all_urls"],"target":{"namespace":"android_app","package_name":"eu.markacentrumacademy.app","sha256_cert_fingerprints":[FINGERPRINT]}}]
BLOCK='''    # MCA Google Play domain verification, independent of app releases
    location = /.well-known/assetlinks.json {
        alias /var/www/mca-digital-asset-links/assetlinks.json;
        default_type application/json;
        add_header Cache-Control "public, max-age=300" always;
    }

'''
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise RuntimeError("Domain association must not redirect")
def check():
    opener=urllib.request.build_opener(NoRedirect)
    for host in ("markacentrumacademy.eu","www.markacentrumacademy.eu"):
        with opener.open("https://"+host+"/.well-known/assetlinks.json",timeout=25) as response:
            if response.status!=200 or response.headers.get_content_type()!="application/json":
                raise RuntimeError("Invalid association response")
            data=json.loads(response.read(65536))
        if data!=STATEMENTS:
            raise RuntimeError("Unexpected public association")
        print("DOMAIN_VERIFIED",host,"HTTP_200 JSON NO_REDIRECT PLAY_SIGNING_MATCH")
def main():
    if os.geteuid()!=0 or not PRIVATE.is_dir() or CONFIG.is_symlink():
        raise RuntimeError("Existing root-owned MCA host configuration required")
    original=CONFIG.read_text()
    if "server_name markacentrumacademy.eu www.markacentrumacademy.eu;" not in original:
        raise RuntimeError("Unexpected domain configuration")
    if "location = /.well-known/assetlinks.json" in original and BLOCK not in original:
        raise RuntimeError("Review the existing domain association location")
    if original.count("    location / {")!=1:
        raise RuntimeError("Unexpected application routing")
    old_file=FILE.read_bytes() if FILE.exists() else None
    if old_file is not None and json.loads(old_file)!=STATEMENTS:
        raise RuntimeError("Refusing to replace a different existing association")
    with (PRIVATE/"checkout-release.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup=PRIVATE/("assetlinks-nginx-before-"+stamp+".conf")
        backup.write_text(original)
        backup.chmod(0o600)
        ROOT.mkdir(mode=0o755,parents=True,exist_ok=True)
        ROOT.chmod(0o755)
        temp=ROOT/"assetlinks.json.tmp"
        temp.write_text(json.dumps(STATEMENTS,indent=2)+"\n")
        temp.chmod(0o644)
        os.replace(temp,FILE)
        try:
            if BLOCK not in original:
                CONFIG.write_text(original.replace("    location / {",BLOCK+"    location / {",1))
            subprocess.run(["nginx","-t"],check=True)
            subprocess.run(["systemctl","reload","nginx"],check=True)
            check()
        except BaseException:
            CONFIG.write_text(original)
            if old_file is None:
                FILE.unlink(missing_ok=True)
            else:
                FILE.write_bytes(old_file)
                FILE.chmod(0o644)
            subprocess.run(["nginx","-t"],check=True)
            subprocess.run(["systemctl","reload","nginx"],check=True)
            raise
    print("MCA_DOMAIN_ASSOCIATION_ACTIVE COURSE_CONTENT_UNCHANGED")
if __name__=="__main__":
    main()
