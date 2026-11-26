import unittest,hashlib
from tools.essence_adaptive_learning_executor import cycle,initial,digest
from tools.essence_adaptive_repair_pulse import seal
class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.queue=seal({"schema":"janus.essence.adaptive_repair.pulse.v1","records":[{"evidence_sha256":"a"*64,"production":False}],"seen":["a"*64],"production":False})
        self.bank=[{"text":"evone depends entirely on evtwo","y":8},{"text":"evone prohibits occurrence of evtwo","y":12}]
        self.exam=[{"text":"evone depends entirely upon evtwo","y":8},{"text":"evone prohibits the occurrence of evtwo","y":12}]
    def manifest(self,b=None,e=None):
        b=b if b is not None else self.bank;e=e if e is not None else self.exam
        return {"schema":"janus.essence.approved_role_bank.v1","authorization":"BOUNDED_RESEARCH_ONLY","production":False,"queue_evidence_sha256":"a"*64,"bank_sha256":digest(b),"exam_sha256":digest(e),"preflight":{"overlap":[],"forbidden_normalized_sha256":[]}}
    def test_actual_gradient_and_pulse_dedup(self):
        s=initial();n,r=cycle(s,self.queue,self.manifest(),self.bank,self.exam,"1","2")
        self.assertTrue(r["training_executed"]);self.assertNotEqual(r["candidate_weights_sha256"],r["parent_weights_sha256"])
        self.assertEqual(r["parent_state_sha256"],s["sha256"])
        n2,r2=cycle(n,self.queue,self.manifest(),self.bank,self.exam,"3","4")
        self.assertEqual(n,n2);self.assertFalse(r2["training_executed"])
    def test_overlap_refused(self):
        with self.assertRaisesRegex(ValueError,"OVERLAP"):cycle(initial(),self.queue,self.manifest(self.bank,self.bank),self.bank,self.bank,"1","2")
    def test_queue_pin_and_tamper(self):
        m=self.manifest();m["queue_evidence_sha256"]="b"*64
        with self.assertRaisesRegex(ValueError,"QUEUE_BINDING"):cycle(initial(),self.queue,m,self.bank,self.exam,"1","2")
        s=initial();s["production"]=True
        with self.assertRaisesRegex(ValueError,"STATE_HASH"):cycle(s,self.queue,self.manifest(),self.bank,self.exam,"1","2")
    def test_forbidden_historical_text(self):
        m=self.manifest();m["preflight"]["forbidden_normalized_sha256"]=[hashlib.sha256(self.bank[0]["text"].encode()).hexdigest()]
        with self.assertRaisesRegex(ValueError,"OVERLAP"):cycle(initial(),self.queue,m,self.bank,self.exam,"1","2")
