import unittest
from datetime import datetime,timezone
from tools.mintaka_beacon_predictor import initial,advance,fit,ORGANS
def stamp(x):return datetime.fromtimestamp(x,timezone.utc).isoformat()
def snapshot(n=20,cutoff=100000):
    return {"observed_at":stamp(cutoff),"organs":{k:{"status":"OK","runs":[{"id":i+1,"event":"schedule","started_at":stamp(1000+i*900)} for i in range(n)]} for k in ORGANS}}
class Beacon(unittest.TestCase):
    def test_perfect_period(self):
        x=fit(snapshot()["organs"]["ESSENCE"]["runs"])
        self.assertEqual(x["predicted_gap_seconds"],900);self.assertEqual(x["mae_seconds"]["adaptive"],0)
        self.assertFalse(x["admitted"]) # equality is not superiority
    def test_cache_and_dedup(self):
        s,r=advance(initial(),snapshot(),"a");t,q=advance(s,snapshot(),"a")
        self.assertEqual(s,t);self.assertEqual(q["cache_hits"],4)
        u,z=advance(t,snapshot(),"b");self.assertEqual(z["cache_hits"],0)
        self.assertFalse(z["dispatch_authorized"])
    def test_future_receipt(self):
        s,r=advance(initial(),snapshot(20,18200),"a")
        self.assertIsNotNone(r["results"]["ESSENCE"]["forecast"])
        t,q=advance(s,snapshot(21,19100),"a")
        self.assertEqual(q["results"]["ESSENCE"]["live_error_n"],1)
        self.assertEqual(t["live_errors"]["ESSENCE"][0]["absolute_error_seconds"],0)
    def test_missing_source_does_not_score(self):
        x=snapshot();x["organs"]["BEETLE"]={"status":"HOLD","runs":[]}
        s,r=advance(initial(),x,"a")
        self.assertEqual(r["results"]["BEETLE"]["model"]["n"],0)
        self.assertTrue(r["results"]["BEETLE"]["mandatory_poll_unchanged"])
    def test_tamper(self):
        s=initial();s["production"]=True
        with self.assertRaises(ValueError):advance(s,snapshot(),"a")
