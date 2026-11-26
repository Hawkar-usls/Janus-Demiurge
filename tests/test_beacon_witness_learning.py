import unittest
from datetime import datetime,timezone
from tools.beacon_witness_learning import validate,digest,examples,evaluate,external_crosscheck,LINES
def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
def fixture(i,age=60,status="SCHEDULE_OK"):
    now=1700000000+i*3600
    x={"schema":"janus.external_witness.import_receipt.v1","collector":{"type":"TRUSTED_META_REGISTRY_IMPORTER_NOT_EXTERNAL_WITNESS","run_id":str(i+1),"run_attempt":"1"},"authority":{"command_authority":False,"runtime_execution":False,"scientific_authority_delta":0,"scientific_proof":False},"observed_at_utc":iso(now),"observations":{k:{"status":status,"repository":r,"workflow":n,"active_schedule_run":None,"age_minutes":age,"last_schedule_run":{"run_id":i+1,"completed_at":iso(now-age*60)}} for k,(r,n) in LINES.items()}}
    return {**x,"receipt_sha256":digest(x)}
class WitnessLearning(unittest.TestCase):
    def test_hash_and_unknown(self):
        x=fixture(0);x["observations"]["genesis_home"]["status"]="UNKNOWN"
        with self.assertRaisesRegex(ValueError,"RECEIPT_HASH"):validate(x)
        x["receipt_sha256"]=digest({k:v for k,v in x.items() if k!="receipt_sha256"})
        a=validate(x);b=validate(fixture(1))
        self.assertEqual(len(examples([a,b])),4)
    def test_wrong_age_label_refused(self):
        with self.assertRaisesRegex(ValueError,"AGE_LABEL"):validate(fixture(0,age=360))
    def test_invalid_label_quarantined_not_trained(self):
        q=[];a=validate(fixture(0,age=360),q)
        self.assertEqual(len(q),5)
        self.assertEqual(len(examples([a,validate(fixture(1))])),0)
    def test_forward_only(self):
        rows=[validate(fixture(i)) for i in range(20)]
        ex=examples(rows);cut=rows[14]["time"]
        result=evaluate(ex,cut)
        self.assertEqual(result["test_n"],25)
        self.assertEqual(result["brier"]["persist"],0)
        self.assertEqual(result["gate"],"HOLD")
    def test_external_unknown(self):
        a=validate(fixture(0))
        ext={"observed_at_utc":iso(a["time"]+60),"lines":{"genesis_home":{"status":"UNKNOWN"}}}
        self.assertEqual(external_crosscheck([a],ext)["lines"]["genesis_home"],"EXTERNAL_UNKNOWN_NO_LABEL")
