"""QUARANTINE is durable candidate custody, never a model admission decision."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from daddy_keymaster.broker import sha
from daddy_keymaster.champion_release import Hold
from daddy_keymaster.quarantine import build

REPO = 'Hawkar-usls/Janus-Demiurge'
COMMIT = 'f' * 40
RUN = '41141564656'
ATTEMPT = '1'
PARENT = 'a' * 64
SOURCE = 'b' * 64
CONTRACT = 'c' * 64


class WinnerQuarantineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inputs = self.root / 'inputs'
        self.inputs.mkdir()
        self.out = self.root / 'out'
        self.audit_path = self.root / 'AUDIT.json'
        self.candidate_bytes = b'fixture checkpoint payload (no torch execution)'
        self.candidate_sha = hashlib.sha256(self.candidate_bytes).hexdigest()

    def write_audit(self, *, winner=False):
        workers = [
            {'architecture':'X64', 'verdict':
                ('INDEPENDENTLY_VERIFIED_BETTER' if winner
                 else 'REJECTED_BY_ORIGINAL_GATE')},
            {'architecture':'ARM64','verdict':'REJECTED_BY_ORIGINAL_GATE'}]
        if winner:
            workers[0]['candidate_checkpoint_sha256'] = self.candidate_sha
        a = {
            'schema':'janus.daddy_keymaster.native_calibration_audit.v1',
            'status':('BEST_CANDIDATE_REVIEW_ONLY' if winner
                      else 'INCUMBENT_RETAINED'),
            'main_checkpoint_mutated':False,
            'automatic_production_promotion':False,
            'commit':COMMIT,'run_id':RUN,'attempt':ATTEMPT,
            'incumbent_checkpoint_sha256':PARENT,
            'source_digest':SOURCE,'evaluation_contract_sha256':CONTRACT,
            'workers':workers,
            'winner':({'architecture':'X64',
                       'candidate_checkpoint_sha256':self.candidate_sha}
                      if winner else None),
        }
        a['receipt_sha256'] = sha(a)
        self.audit_path.write_text(json.dumps(a))
        return a

    def add_worker(self):
        folder = self.inputs / 'native-calibration-x64'
        folder.mkdir()
        (folder / 'CANDIDATE.pt').write_bytes(self.candidate_bytes)
        train = {
            'status':'PROMOTED','candidate_checkpoint_sha256':self.candidate_sha,
            'parent_checkpoint_sha256':PARENT,
        }
        (folder / 'TRAINING.json').write_text(json.dumps(train))
        w = {
            'repository':REPO,'commit':COMMIT,'run_id':RUN,
            'attempt':ATTEMPT,'architecture':'X64',
            'status':'EXECUTED_NATIVE_WEIGHT_CALIBRATION',
            'candidate_status':'PROMOTED',
            'candidate_checkpoint_sha256':self.candidate_sha,
            'parent_checkpoint_sha256':PARENT,
            'source_digest':SOURCE,
            'evaluation_contract_sha256':CONTRACT,
            'worker_receipt_sha256':sha(train),
            'auto_write_main':False,'authority_delta':0,
        }
        w['receipt_sha256'] = sha(w)
        (folder / 'WORKER.json').write_text(json.dumps(w))
        return folder

    def invoke(self, output=None):
        return build(self.audit_path,self.inputs,output or self.out,
                     repository=REPO,commit=COMMIT,run_id=RUN,attempt=ATTEMPT)

    def test_rejected_results_never_export_candidate(self):
        self.write_audit(winner=False)
        r = self.invoke()
        self.assertEqual(r['status'],'NO_ACCEPTED_WINNER')
        self.assertFalse((self.out/'candidate.pt').exists())
        self.assertFalse(r['independent_blind_final_proven'])
        self.assertFalse(r['automatic_production_promotion'])

    def test_good_winner_quarantined_with_sha(self):
        self.write_audit(winner=True)
        self.add_worker()
        r = self.invoke()
        self.assertEqual(r['status'],'QUARANTINED_REVIEW_ONLY')
        self.assertEqual(r['candidate_checkpoint_sha256'],self.candidate_sha)
        self.assertEqual((self.out/'candidate.pt').read_bytes(),self.candidate_bytes)
        self.assertFalse(r['automatic_production_promotion'])
        self.assertFalse(r['independent_blind_final_proven'])
        with self.assertRaisesRegex(Hold,'OUTPUT_ALREADY_EXISTS'):
            self.invoke()

    def test_missing_candidate_is_hold_not_success(self):
        self.write_audit(winner=True)
        with self.assertRaisesRegex(Hold,'CANDIDATE_FILE_UNSAFE'):
            self.invoke()
        self.assertFalse(self.out.exists())

    def test_tampered_candidate_is_hold(self):
        self.write_audit(winner=True)
        folder=self.add_worker()
        (folder/'CANDIDATE.pt').write_bytes(b'tampered')
        with self.assertRaisesRegex(Hold,'WORKER_OR_CHECKPOINT_MISMATCH'):
            self.invoke()
        self.assertFalse(self.out.exists())

    def test_tampered_worker_receipt_is_hold(self):
        self.write_audit(winner=True)
        folder=self.add_worker()
        w=json.loads((folder/'WORKER.json').read_text())
        w['run_id']='999'
        (folder/'WORKER.json').write_text(json.dumps(w))
        with self.assertRaisesRegex(Hold,'WORKER_OR_CHECKPOINT_MISMATCH'):
            self.invoke()

    def test_wrong_run_or_bad_receipt_is_hold(self):
        self.write_audit(winner=True)
        with self.assertRaisesRegex(Hold,'RUN_NOT_BOUND'):
            build(self.audit_path,self.inputs,self.out,repository=REPO,
                  commit=COMMIT,run_id='123456',attempt=ATTEMPT)
        a=json.loads(self.audit_path.read_text())
        a['status']='INCUMBENT_RETAINED'
        self.audit_path.write_text(json.dumps(a))
        with self.assertRaisesRegex(Hold,'AUDIT_TAMPERED'):
            self.invoke()


if __name__=='__main__':
    unittest.main()
