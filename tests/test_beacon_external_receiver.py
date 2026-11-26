import json,tempfile,unittest
from pathlib import Path
from tools.beacon_external_receiver import validate,process,seal,LINES
ID="6f26fdfe-b154-8333-b451-e7225e398801"
def fixture():
    return {"schema":"janus.beacon.external_observation.v1","source":"EXTERNAL_SILENCE_WITNESS","origin_class":"RELAY_NORMALIZED_TASK_RESULT","run_id":ID,"observed_at_utc":"2026-11-26T16:42:35Z","scheduled_for":"2026-11-26T16:39:09Z","source_completed_at":"2026-11-26T16:42:35.206Z","coverage":{"pages":20,"records":200,"api_status":"OK"},"lines":{k:{"status":"UNKNOWN"} for k in LINES},"authority":{"command":False,"runtime":False,"science":False},"production":False}
class Receiver(unittest.TestCase):
    def test_unknown_and_privilege(self):
        x=fixture();validate(x,ID+".json");x["authority"]["command"]=True
        with self.assertRaisesRegex(ValueError,"AUTHORITY"):validate(x,ID+".json")
    def test_partial_is_not_silence(self):
        x=fixture();x["coverage"]["api_status"]="PARTIAL";x["lines"]["genesis_home"]={"status":"SCHEDULE_SILENCE","run_id":7,"completion_basis":"UPDATED_AT","reported_at":"2026-11-26T08:00:00Z"}
        with self.assertRaisesRegex(ValueError,"INCOMPLETE_COVERAGE"):validate(x,ID+".json")
    def test_immutable_and_missing(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/(ID+".json");x=fixture();p.write_text(json.dumps(x));s,r=process([p],[],seal({"schema":"janus.beacon.external.receiver.state.v1","records":{},"production":False}))
            self.assertEqual(r["new"],1);self.assertEqual(r["status_counts"],{"UNKNOWN_NO_LABEL":5})
            s2,r2=process([p],[],s);self.assertEqual(s,s2);self.assertEqual(r2["new"],0)
            p.write_text(json.dumps(x,indent=2));s3,r3=process([p],[],s);self.assertEqual(s,s3);self.assertEqual(r3["rejected"][0]["reason"],"IMMUTABLE_CONFLICT")
            s4,r4=process([],[],s);self.assertEqual(s,s4);self.assertEqual(r4["missing_prior"],[ID])
    def test_time_order(self):
        x=fixture();x["lines"]["genesis_home"]={"status":"SCHEDULE_OK","run_id":7,"completion_basis":"JOB_COMPLETED_AT","reported_at":"2026-11-26T17:00:00Z"}
        with self.assertRaisesRegex(ValueError,"AGE_LABEL"):validate(x,ID+".json")
    def test_untrusted_extra_field(self):
        x=fixture();x["command"]="something"
        with self.assertRaisesRegex(ValueError,"FIELDS"):validate(x,ID+".json")
