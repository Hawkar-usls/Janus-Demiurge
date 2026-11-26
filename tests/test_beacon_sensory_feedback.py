import unittest
from datetime import datetime,timezone
from tools.beacon_sensory_feedback import initial,advance,BASE,SEED,LINES
from tools.beacon_external_receiver import seal
def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat().replace("+00:00","Z")
def base():
    return {"receipt_chain_sha256":BASE,"checkpoint_sha256":"a"*64,"last":100000,"production":False,"dispatch_authorized":False,"timing":{k:{"learned_state":{"last_completion_epoch":99000,"ewma_gap_seconds":3600,"recent_gaps_seconds":[3600]*12}} for k in LINES}}
def row(key,t,scheduled,completion):
    lines={k:{"status":"UNKNOWN"} for k in LINES};k=LINES[0]
    lines[k]={"status":"SCHEDULE_OK","run_id":completion,"completion_basis":"JOB_COMPLETED_AT","reported_at":iso(completion)}
    return {"authority":False,"mailbox_sha256":str(completion),"observation":{"schema":"janus.beacon.external_observation.v1","source":"EXTERNAL_SILENCE_WITNESS","origin_class":"RELAY_NORMALIZED_TASK_RESULT","run_id":key,"observed_at_utc":iso(t),"scheduled_for":iso(scheduled),"source_completed_at":iso(t),"coverage":{"pages":20,"records":200,"api_status":"OK"},"lines":lines,"authority":{"command":False,"runtime":False,"science":False},"production":False},"crosscheck":{j:{"status":"UNKNOWN_NO_LABEL"} if j!=k else {"status":"CORROBORATED_COMPLETION_ONLY","run_id":completion,"completed_at":iso(completion),"importer_receipt_sha256":"b"*64} for j in LINES}}
def receiver(rows):return seal({"schema":"janus.beacon.external.receiver.state.v1","records":rows,"production":False})
class Feedback(unittest.TestCase):
    def test_seed_not_counted(self):
        s,r=advance(initial(base()),receiver({SEED:row(SEED,100010,100000,99000)}),100020)
        self.assertEqual(r["new_distinct_completions_learned"],0)
        self.assertEqual(r["candidate_hourly_streak"],0)
    def test_future_learning_and_duplicate(self):
        s,_=advance(initial(base()),receiver({}),100020)
        key="00000000-0000-0000-0000-000000000001";x=receiver({key:row(key,103000,102000,102800)})
        t,r=advance(s,x,103010)
        self.assertEqual(r["new_distinct_completions_learned"],1)
        self.assertEqual(r["new_prospective_scores"],1)
        u,q=advance(t,x,103010)
        self.assertEqual(t,u);self.assertEqual(q["new_distinct_completions_learned"],0)
    def test_three_packets_not_three_distinct_completions(self):
        rows={}
        for i in range(3):
            key=f"00000000-0000-0000-0000-{i+1:012d}"
            rows[key]=row(key,103000+i*3600,102000+i*3600,102800)
        t,r=advance(initial(base()),receiver(rows),111000)
        self.assertEqual(r["candidate_hourly_streak"],3)
        self.assertEqual(r["new_distinct_completions_learned"],1)
        self.assertEqual(r["automatic_transfer_proof"],"REQUIRES_SEPARATE_RELAY_RUN_EVIDENCE")
    def test_tamper(self):
        s=initial(base());s["production"]=True
        with self.assertRaises(ValueError):advance(s,receiver({}),100020)
