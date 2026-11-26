import unittest
from tools.essence_adaptive_repair_pulse import initial,advance,checked
class Pulse(unittest.TestCase):
    def fixture(self):
        t={"memory_sha":"a"*64,"legacy_feature_conflicts":5,"attempts":[{"id":"DIRECT_POSITION"},{"id":"TAGGED_MIRROR"}]}
        return {"schema":"janus.r84.h38n3.execution.v1","run_id":45847415226,"production":False,"receipts":[{"tag":"R84H38N3_TRAIN","data":t},{"tag":"R84H38N3_RESULT","data":{"repair":t,"quality_gate":"HOLD"}}]}
    def test_restart_dedup(self):
        a,b=advance(initial(),self.fixture(),"b"*40);self.assertEqual(b,"REPAIR_REQUEST_RECORDED")
        c,d=advance(a,self.fixture(),"c"*40);self.assertEqual(a,c);self.assertEqual(d,"NO_NEW_EVIDENCE_HOLD")
        self.assertFalse(checked(a)["records"][0]["training_authorized"])
    def test_tamper(self):
        a=initial();a["production"]=True
        with self.assertRaises(ValueError):advance(a,self.fixture(),"b"*40)
    def test_bad_receipt(self):
        r=self.fixture();r["receipts"][1]["data"]["quality_gate"]="PASS"
        with self.assertRaises(ValueError):advance(initial(),r,"b"*40)
