"""Offline smoke verification fixtures. Run with python3 -m unittest test_smoke."""
import contextlib
import io
import unittest
from uuid import uuid4
from unittest.mock import patch
import smoke


class Fixture:
    def __init__(self):
        self.run = None
        self.user = str(uuid4())
        self.orders = {}
        self.sessions = {}
        self.deleted = False
        self.paid = set()
        self.webhook = True
        self.fail_course = None

    def create(self, run):
        self.run = run
        return "private-fixture-token", self.user

    def checkout(self, course, token):
        assert token == "private-fixture-token"
        if course == self.fail_course:
            raise smoke.CheckError("Simulated interrupted checkout")
        if course not in self.orders:
            order = {"id":str(uuid4()), "course":course, "status":"pending",
                     "payment":None,"live":True,"session":"cs_live_Fixture"+str(len(self.orders))}
            self.orders[course] = order
            self.sessions[order["session"]] = {
                "id":order["session"],"livemode":True,"mode":"payment","status":"open","payment_status":"unpaid",
                "client_reference_id":order["id"],"metadata":{"integration":"mca_courses_v1","user_id":self.user,
                    "course_id":course,"mca_order_id":order["id"]},"currency":"eur","amount_total":12000,
                "url":"https://checkout.stripe.com/c/private-fixture-"+course}
        return self.sessions[self.orders[course]["session"]]["url"]

    def snapshot(self, run):
        if run != self.run or self.deleted:
            return None
        return {"user":self.user,"orders":list(self.orders.values()),"enrolled":bool(self.paid)}

    def stripe(self, sid, action=""):
        s = self.sessions[sid]
        order = next(row for row in self.orders.values() if row["session"] == sid)
        if action == "expire":
            assert s["payment_status"] == "unpaid"
            s["status"] = "expired"
            if self.webhook:
                order["status"] = "expired"
        if action == "line_items":
            price,product = smoke.COURSES[order["course"]]
            return {"has_more":False,"data":[{"quantity":1,"amount_total":12000,"price":{
                  "id":price,"product":product,"currency":"eur","type":"one_time","unit_amount":12000}}]}
        return dict(s)

    def remove(self, run, ids):
        assert run == self.run and not self.paid
        assert {r["id"] for r in self.orders.values()} == ids
        assert all(r["status"]=="expired" and not r["payment"] for r in self.orders.values())
        self.deleted = True
        return True


class SmokeTest(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.run = uuid4()
        token,self.user = self.f.create(self.run)
        self.urls = {course:self.f.checkout(course,token) for course in smoke.COURSES}
        self.first,self.second = smoke.COURSES

    def clean(self, expected=None):
        return smoke.cleanup(self.f,self.run,set(smoke.COURSES) if expected is None else expected,wait=0)

    def test_two_sessions(self):
        for course,url in self.urls.items():
            smoke.verify(self.f,self.run,self.user,course,url)
        self.assertTrue(self.clean())

    def test_price_or_wrong_hosted_session(self):
        s = self.f.sessions[self.f.orders[self.first]["session"]]
        s["amount_total"] = 8900
        with self.assertRaises(smoke.CheckError):
            smoke.verify(self.f,self.run,self.user,self.first,self.urls[self.first])
        s["amount_total"] = 12000
        with self.assertRaises(smoke.CheckError):
            smoke.verify(self.f,self.run,self.user,self.first,self.urls[self.second])
        self.assertTrue(self.clean())

    def test_unrelated_or_paid_sessions_never_expire(self):
        s = self.f.sessions[self.f.orders[self.first]["session"]]
        s["metadata"]["user_id"] = "different"
        o = self.f.orders[self.second]
        self.f.sessions[o["session"]]["payment_status"] = "paid"
        self.assertFalse(self.clean())
        self.assertTrue(all(s["status"]=="open" for s in self.f.sessions.values()))
        self.assertFalse(self.f.deleted)

    def test_delayed_webhook_then_cleanup(self):
        self.f.webhook = False
        self.assertFalse(self.clean())
        self.assertFalse(self.f.deleted)
        self.assertTrue(all(s["status"]=="expired" for s in self.f.sessions.values()))
        for o in self.f.orders.values():
            o["status"] = "expired"
        self.assertTrue(self.clean())

    def test_ambiguous_unbound_or_missing_checkout(self):
        self.f.orders[self.first]["session"] = None
        self.assertFalse(self.clean())
        self.assertFalse(self.f.deleted)
        del self.f.orders[self.first]
        self.assertFalse(self.clean())

    def test_main_releases_sessions_on_interrupted_second_checkout(self):
        f = Fixture()
        f.fail_course = self.second
        output = io.StringIO()
        with patch("smoke.Host",return_value=f),patch("smoke.os.geteuid",return_value=0),patch("sys.argv",["smoke.py"]), \
                contextlib.redirect_stdout(output),contextlib.redirect_stderr(output),self.assertRaises(smoke.CheckError):
            smoke.main()
        self.assertEqual(next(iter(f.sessions.values()))["status"],"expired")
        self.assertFalse(f.deleted)
        self.assertIn("--cleanup",output.getvalue())
        self.assertNotIn("private-fixture",output.getvalue())

    def test_main_no_sensitive_output(self):
        f = Fixture()
        output = io.StringIO()
        with patch("smoke.Host",return_value=f),patch("smoke.os.geteuid",return_value=0),patch("sys.argv",["smoke.py"]), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            smoke.main()
        self.assertTrue(f.deleted)
        self.assertEqual(output.getvalue().count("EUR 120.00"),2)
        self.assertNotIn("private-fixture",output.getvalue())
        self.assertNotIn("@",output.getvalue())


if __name__ == "__main__":
    unittest.main()
