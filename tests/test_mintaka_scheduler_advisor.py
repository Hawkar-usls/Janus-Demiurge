import unittest
from tools.mintaka_scheduler_advisor import initial,append,assess,extract
class MintakaTests(unittest.TestCase):
    def test_learning_and_dedup(self):
        obs=[{"id":str(i),"run_id":str(i),"stage":"persist","event":"schedule","created":f"2026-11-26T10:{i:02}:00Z","revision":"a","y":1} for i in range(12)]
        a=append(initial(),obs);self.assertEqual(a,append(a,obs))
        r=assess(a,True,True,3,False,0)
        self.assertGreater(r["metrics"]["persist"]["posterior"],.9)
        self.assertFalse(r["dispatch_authorized"])
        self.assertFalse(r["production"])
    def test_rotation_never_grants_permission(self):
        for i in range(3):
            r=assess(initial(),False,False,0,True,i)
            self.assertEqual(set(r["audit_rotation"].values()),{"RED","AMBER","GREEN"})
            self.assertEqual(set(r["hard_gate"].values()),{"RED"})
        a=[assess(initial(),False,False,3,False,i)["audit_rotation"]["wake"] for i in range(3)]
        self.assertEqual(set(a),{"RED","AMBER","GREEN"})
    def test_skipped_or_noop_is_not_training(self):
        x={"repair":[{"id":1,"event":"workflow_run","status":"completed","created_at":"2026","head_sha":"x","jobs":[{"id":2,"name":"execute-research","conclusion":"success"},{"id":3,"name":"persist","conclusion":"skipped"}]}]}
        self.assertEqual(extract(x),[])
    def test_tamper(self):
        s=initial();s["production"]=True
        with self.assertRaises(ValueError):append(s,[])
