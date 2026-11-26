import unittest
from datetime import datetime,timezone
from tools.mintaka_beacon_rhythm import advance,initial,fit,PERIOD,PHASE,ORGANS,slot
def stamp(x):return datetime.fromtimestamp(x,timezone.utc).isoformat()
def snapshot(n=20,now=100000):
    return {"observed_at":stamp(now),"organs":{k:{"status":"OK","runs":[{"id":i+1,"event":"schedule","created_at":stamp(PHASE[k]+i*PERIOD[k]),"started_at":stamp(PHASE[k]+i*PERIOD[k]+20)} for i in range(n)]} for k in ORGANS}}
class Rhythm(unittest.TestCase):
    def test_phase(self):
        self.assertEqual(slot(421,900,420),420)
        r=fit(snapshot()["organs"]["ESSENCE"]["runs"],"ESSENCE")
        self.assertEqual(r["median_queue_delay_seconds"],20)
        self.assertEqual(r["unobserved_nominal_slots_proxy"],0)
    def test_actual_skip(self):
        s,r=advance(initial(),snapshot(),"x",True)
        t,q=advance(s,snapshot(),"x")
        self.assertEqual(s,t);self.assertEqual(q["actual_fit_calls"],0);self.assertEqual(q["benchmark_extra_fit_calls"],0)
        self.assertEqual(q["mandatory_reads"],4)
    def test_event_separation(self):
        x=snapshot();z=x["organs"]["ESSENCE"];z["runs"].append({"id":100,"event":"workflow_run","created_at":stamp(19000),"started_at":stamp(19001)})
        s,r=advance(initial(),x,"x")
        self.assertEqual(r["organs"]["ESSENCE"]["model"]["scheduled_starts"],20)
        self.assertEqual(r["organs"]["ESSENCE"]["model"]["event_counts"]["workflow_run"],1)
    def test_future_error(self):
        x=snapshot(3,11000);s,r=advance(initial(),x,"x")
        t,q=advance(s,snapshot(10,40000),"x")
        self.assertEqual(q["organs"]["COSMOS"]["prospective_n"],1)
        self.assertFalse(q["dispatch_authorized"])
    def test_invalid_timestamp(self):
        x=snapshot();x["organs"]["ESSENCE"]["runs"][0]["created_at"]=stamp(99999)
        with self.assertRaises(ValueError):advance(initial(),x,"x")
