#!/usr/bin/env python3
"""Scoped maintenance for the dedicated MCA test account and missing public assets."""
import argparse
import getpass
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("play_ops", HERE.parent / "google-play/setup.py")
play = importlib.util.module_from_spec(spec)
spec.loader.exec_module(play)


def reset_test():
    play.pay.require(os.geteuid() == 0, "Existing root session required")
    path = play.PRIVATE / "google-play-test-login.json"
    play.safe_file(path)
    login = json.loads(path.read_text())
    email = "play-test@markacentrumacademy.eu"
    play.pay.require(login["email"] == email, "Unexpected test account")
    uid = play.psql("SELECT id FROM auth.users WHERE lower(email)=:'email' AND raw_user_meta_data->>'mca_play_account'='test';", email=email)
    import uuid
    uid = str(uuid.UUID(uid))
    admins = play.psql("SELECT count(*) FROM public.user_roles WHERE user_id=:'uid'::uuid AND role='admin';", uid=uid)
    play.pay.require(admins == "0", "Refusing administrator password change")
    password = getpass.getpass("New test password: ")
    play.pay.require(8 <= len(password) <= 64, "Use 8 to 64 characters")
    env = play.runtime_env()
    host = env["SUPABASE_URL"].rstrip("/")
    play.pay.require(host == "https://api.markacentrumacademy.eu", "Unexpected authentication endpoint")
    status, _ = play.http(host + "/auth/v1/admin/users/" + uid,
        json.dumps({"password": password}).encode(),
        {"Content-Type": "application/json", "apikey": env["SUPABASE_SERVICE_ROLE_KEY"],
         "Authorization": "Bearer " + env["SUPABASE_SERVICE_ROLE_KEY"]}, method="PUT")
    play.pay.require(status == 200, "Test password update failed")
    login["password"] = password
    play.write_private(path, json.dumps(login))
    status, session = play.http(host + "/auth/v1/token?grant_type=password", json.dumps(login).encode(),
        {"Content-Type": "application/json", "apikey": env["SUPABASE_PUBLISHABLE_KEY"]})
    play.pay.require(status == 200 and session["user"]["id"] == uid, "New test login validation failed")
    print("TEST_PASSWORD_UPDATED LOGIN_VERIFIED administrator=false")


def assets():
    names = ["e1-konstrukcja-drewniana.jpg", "e1-poszycie.jpg", "e1-stal-poszycie.jpg", "e1-stal-detal.jpg", "e1-beton.jpg"]
    for name in names:
        result = subprocess.run(["find", "/srv", "/var/www", "-type", "f", "-name", name],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
        print("ASSET", name)
        for found in result.stdout.splitlines():
            path = Path(found)
            print(str(path), path.stat().st_size)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["reset-test", "assets"])
    args = parser.parse_args()
    os.umask(0o077)
    try:
        (reset_test if args.mode == "reset-test" else assets)()
    except Exception as error:
        if isinstance(error, ValueError):
            print(str(error), file=sys.stderr)
        sys.exit("MCA scoped maintenance stopped; no secrets printed")
