#!/usr/bin/env python3
"""Verify both live prices without submitting payment. Run on the Academy host after deploy."""
import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, Request
from uuid import UUID, uuid4

from configure import docker_value

ORIGIN = "https://markacentrumacademy.eu"
STRIPE = "https://api.stripe.com/v1/checkout/sessions/"
COURSES = {
    "11111111-1111-4111-8111-111111111111": ("price_1Uej4hIcl2W7iMTxaiHPUqGo", "prod_Vg5FHXhIgknkrf"),
    "f166433e-5157-4341-9a38-800c62795ebd": ("price_1Uej5CIcl2W7iMTxLKxgp06s", "prod_Vg5F3UsBRpVARw"),
}


class CheckError(Exception):
    pass


def check(condition, message):
    if not condition:
        raise CheckError(message)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def request(label, url, headers, data=None):
    client = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with client.open(Request(url, data=data, headers=headers), timeout=30) as reply:
            return json.loads(reply.read(2_000_000))
    except HTTPError as e:
        raise CheckError(f"{label}: HTTP {e.code}") from None
    except (OSError, URLError, ValueError):
        raise CheckError(f"{label}: no verified response") from None


class Host:
    def __init__(self):
        project = '{{index .Config.Labels "com.docker.compose.project"}}'
        check(all(docker_value("inspect", "-f", project, name) == "mca-backend-staging"
                  for name in ("mca-sb-db", "mca-sb-gateway")), "Unknown Academy backend")
        ports = docker_value("port", "mca-sb-gateway", "8000/tcp").splitlines()
        local = next((s for s in ports if re.fullmatch(r"127\.0\.0\.1:[0-9]{1,5}", s)), "")
        check(local, "Academy gateway needs its loopback port")
        self.auth = "http://" + local + "/auth/v1/"
        app = "mca-course-test"
        self.key = docker_value("exec", app, "printenv", "STRIPE_SECRET_KEY")
        self.role = docker_value("exec", app, "printenv", "SUPABASE_SERVICE_ROLE_KEY")
        self.anon = docker_value("exec", app, "printenv", "SUPABASE_PUBLISHABLE_KEY")
        check(re.fullmatch(r"(?:sk|rk)_live_[A-Za-z0-9]+", self.key) and self.anon and self.role,
              "Active application's live payment configuration is incomplete")

    def auth_call(self, target, payload, key):
        headers = {"Content-Type": "application/json", "apikey": key}
        if not key.startswith("sb_"):
            headers["Authorization"] = "Bearer " + key
        return request("Academy authentication", self.auth + target, headers, json.dumps(payload).encode())

    def create(self, run):
        email, password = f"mca-checkout-{run}@example.invalid", secrets.token_urlsafe(36)
        self.auth_call("admin/users", {"email": email, "password": password, "email_confirm": True,
                                       "app_metadata": {"mca_checkout_smoke": str(run)}}, self.role)
        session = self.auth_call("token?grant_type=password", {"email": email, "password": password}, self.anon)
        check(session.get("user", {}).get("email") == email and session.get("access_token"), "QA login was not verified")
        return session["access_token"], str(UUID(session["user"]["id"]))

    def checkout(self, course, token):
        response = request("Academy checkout", ORIGIN + "/api/academy/checkout",
                           {"Origin": ORIGIN, "Authorization": "Bearer " + token, "Content-Type": "application/json"},
                           json.dumps({"courseId": course}).encode())
        url = response.get("url", "")
        check(response.get("status") == "open" and urlsplit(url).netloc == "checkout.stripe.com"
              and urlsplit(url).scheme == "https", "Academy did not return hosted checkout")
        return url

    def stripe(self, sid, action=""):
        check(re.fullmatch(r"cs_live_[A-Za-z0-9]+", sid), "Invalid live Stripe session ID")
        return request("Stripe " + (action or "session"), STRIPE + sid + ("/" + action if action else ""),
                       {"Authorization": "Bearer " + self.key}, b"" if action == "expire" else None)

    def sql(self, stmt):
        result = subprocess.run(["docker", "exec", "-i", "mca-sb-db", "psql", "-XqAt", "-U", "postgres",
                                 "-d", "postgres", "-v", "ON_ERROR_STOP=1"], input=stmt,
                                capture_output=True, text=True, timeout=20)
        check(result.returncode == 0, "Academy database check failed")
        return json.loads(result.stdout.strip() or "null")

    @staticmethod
    def predicate(run):
        # run is a validated UUID. The application metadata marker is written only by GoTrue admin.
        run = str(UUID(str(run)))
        return f"""u.raw_app_meta_data->>'mca_checkout_smoke'='{run}'
                   AND u.email='mca-checkout-{run}@example.invalid'"""

    def snapshot(self, run):
        return self.sql(f"""SELECT json_build_object('user',u.id,'orders',coalesce(
            (SELECT json_agg(json_build_object('id',o.id,'course',o.course_id,'session',o.session_id,'status',o.status,
             'payment',o.payment_intent,'live',o.live)) FROM public.mca_checkout_orders o WHERE o.user_id=u.id),'[]'),
             'enrolled',EXISTS(SELECT 1 FROM public.enrollments e WHERE e.user_id=u.id))
            FROM auth.users u WHERE {self.predicate(run)};""")

    def remove(self, run, confirmed):
        # Retain this user if any order changed, is unrecognized, or involved payment.
        ids = ",".join("'" + str(UUID(i)) + "'::uuid" for i in confirmed)
        allowed = "false" if not ids else f"o.id IN ({ids})"
        return self.sql(f"""WITH deleted AS (DELETE FROM auth.users u WHERE {self.predicate(run)}
          AND NOT EXISTS(SELECT 1 FROM public.enrollments e WHERE e.user_id=u.id)
          AND NOT EXISTS(SELECT 1 FROM public.mca_checkout_orders o WHERE o.user_id=u.id AND
             (NOT ({allowed}) OR o.status<>'expired' OR o.payment_intent IS NOT NULL OR NOT o.live))
          RETURNING 1)
          SELECT to_json(count(*)=1) FROM deleted;""")


def bound(session, user, order):
    meta = session.get("metadata") or {}
    return (session.get("id") == order["session"] and session.get("livemode") is True and order["live"] is True
            and order["course"] in COURSES and session.get("client_reference_id") == order["id"]
            and all(meta.get(k) == v for k,v in {"integration":"mca_courses_v1","mca_order_id":order["id"],
                                                 "user_id":user,"course_id":order["course"]}.items()))


def verify(host, run, user, course, url):
    snap = host.snapshot(run)
    check(snap and snap["user"] == user and not snap["enrolled"], "QA account check failed")
    rows = [order for order in snap["orders"] if order["course"] == course]
    check(len(rows) == 1 and rows[0]["session"], "QA order is not uniquely bound")
    order = rows[0]
    s = host.stripe(order["session"])
    check(bound(s,user,order) and s.get("mode") == "payment" and s.get("status") == "open"
          and s.get("payment_status") == "unpaid" and s.get("url") == url
          and (s.get("currency"),s.get("amount_total")) == ("eur",12000), "Live session mismatch")
    items = host.stripe(order["session"], "line_items")
    lines = items.get("data") or []
    check(items.get("has_more") is False and len(lines) == 1, "Unexpected cart size")
    item = lines[0]
    price = item.get("price") or {}
    check(item.get("quantity") == 1 and item.get("amount_total") == 12000
          and (price.get("id"),price.get("product")) == COURSES[course]
          and (price.get("type"),price.get("currency"),price.get("unit_amount")) == ("one_time","eur",12000),
          "Live price, quantity or product mismatch")


def cleanup(host, run, expected, wait=60):
    snap = host.snapshot(run)
    if not snap:
        # A timed-out Admin create might still be running. Retain the cleanup token for retry.
        return False
    confirmed = set()
    seen = set()
    safe = not snap["enrolled"]
    for o in snap["orders"]:
        seen.add(o["course"])
        if o["payment"] or o["status"] in ("paid","processing") or not o["session"]:
            safe = False
            continue
        try:
            s = host.stripe(o["session"])
            if not bound(s,snap["user"],o) or s.get("payment_status")!="unpaid" or s.get("payment_intent"):
                safe = False
                continue
            if s.get("status") == "open":
                host.stripe(o["session"],"expire")
                s = host.stripe(o["session"])
            if bound(s,snap["user"],o) and s["status"]=="expired" and s["payment_status"]=="unpaid" and not s.get("payment_intent"):
                confirmed.add(o["id"])
            else:
                safe = False
        except (CheckError, OSError, ValueError, KeyError, TypeError):
            safe = False
    if not safe or not expected.issubset(seen):
        return False
    # Allow the live webhook to acknowledge every expiration before CASCADE removes only QA data.
    until = time.monotonic()+wait
    while True:
        snap = host.snapshot(run)
        if snap and not snap["enrolled"] and all(o["id"] in confirmed and not o["payment"] and o["status"]=="expired"
                                                 for o in snap["orders"]):
            return host.remove(run, confirmed)
        if time.monotonic() >= until:
            return False
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cleanup", type=UUID, help="Retry cleanup of a previously printed random run marker")
    a = parser.parse_args()
    check(os.geteuid()==0, "Use the existing Academy root terminal")
    host, run, expected = Host(), a.cleanup or uuid4(), set()
    print(f"QA run {run}", flush=True)
    if a.cleanup and not host.snapshot(run):
        print("No QA account currently exists for that marker.")
        return
    try:
        if not a.cleanup:
            token,user = host.create(run)
            for index,course in enumerate(COURSES,1):
                expected.add(course)
                try:
                    url = host.checkout(course,token)
                except CheckError:
                    # The server may have created a session before its reply was interrupted.
                    url = host.checkout(course,token)
                verify(host,run,user,course,url)
                print(f"Course {index}: EUR 120.00, one-time, correct live product.", flush=True)
    finally:
        try:
            clean = cleanup(host,run,expected)
        except (Exception,KeyboardInterrupt):
            clean = False
        if not clean:
            print(f"Cleanup requires verification. Retry using python3 smoke.py --cleanup {run}",file=sys.stderr)
            raise CheckError("No account deletion was confirmed")
        print("All QA sessions verified expired and unpaid. Temporary QA account removed.",flush=True)


if __name__ == "__main__":
    try:
        main()
    except CheckError as e:
        sys.exit(str(e))
    except (Exception, KeyboardInterrupt):
        sys.exit("Verification stopped. No sensitive diagnostics were emitted.")
