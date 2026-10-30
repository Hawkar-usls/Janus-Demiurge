"""JANUS Champion Release: fail-closed receipts and real local Git rollback."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from daddy_keymaster.broker import sha
from daddy_keymaster.champion_release import (
    Hold, CHECKPOINT, STATE, ROLLBACK, authoritative_state,
    digest, journaled_state, rollback_latest, source_preflight,
    verify_audit, publish,
)


def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True,
                                   stderr=subprocess.STDOUT).strip()


class ChampionAuditTests(unittest.TestCase):
    def audit(self):
        c = 'a' * 64
        x = {'schema': 'janus.daddy_keymaster.native_calibration_audit.v1',
             'status': 'BEST_CANDIDATE_REVIEW_ONLY',
             'main_checkpoint_mutated': False,
             'automatic_production_promotion': False,
             'incumbent_checkpoint_sha256': 'b' * 64,
             'commit': 'c' * 40,
             'source_digest': 'd' * 64,
             'evaluation_contract_sha256': 'e' * 64,
             'workers': [
                 {'architecture': 'X64', 'verdict': 'INDEPENDENTLY_VERIFIED_BETTER',
                  'candidate_checkpoint_sha256': c},
                 {'architecture': 'ARM64', 'verdict': 'REJECTED_BY_ORIGINAL_GATE'}],
             'winner': {'architecture': 'X64', 'candidate_checkpoint_sha256': c}}
        x['receipt_sha256'] = sha(x)
        return x

    def test_review_receipt_is_not_production_authority(self):
        verify_audit(self.audit(), 'b' * 64, 'a' * 64)

    def test_rejected_audit_refused(self):
        x = self.audit()
        x['status'] = 'INCUMBENT_RETAINED'
        x['winner'] = None
        x['receipt_sha256'] = sha({k: v for k, v in x.items()
                                  if k != 'receipt_sha256'})
        with self.assertRaisesRegex(Hold, 'NO_VERIFIED_WINNER'):
            verify_audit(x, 'b' * 64, 'a' * 64)

    def test_altered_receipt_refused(self):
        x = self.audit()
        x['winner']['architecture'] = 'ARM64'
        with self.assertRaisesRegex(Hold, 'AUDIT_DIGEST_INVALID'):
            verify_audit(x, 'b' * 64, 'a' * 64)

    def test_wrong_parent_refused(self):
        with self.assertRaisesRegex(Hold, 'SOURCE_OR_PARENT_DRIFT'):
            verify_audit(self.audit(), '0' * 64, 'a' * 64)

    def test_unproven_winner_refused(self):
        x = self.audit()
        x['workers'][0]['verdict'] = 'REJECTED_BY_ORIGINAL_GATE'
        x['receipt_sha256'] = sha({k: v for k, v in x.items()
                                  if k != 'receipt_sha256'})
        with self.assertRaisesRegex(Hold, 'WINNER_NOT_PROVEN'):
            verify_audit(x, 'b' * 64, 'a' * 64)

    def test_journal_preserves_history_counters(self):
        old = {'schema': 'janus.model.state.v1', 'checkpoint_sha256': 'b' * 64,
               'promotion_count': 5, 'rejection_count': 99,
               'history': [{'status': 'old'}]}
        report = {'candidate_checkpoint_sha256': 'a' * 64,
                  'parent_checkpoint_sha256': 'b' * 64,
                  'calibration_run_id': '41139181887',
                  'source_digest': 'd' * 64,
                  'final_corpus_sha256': 'f' * 64}
        new = journaled_state(old, report)
        self.assertEqual(new['promotion_count'], 6)
        self.assertEqual(new['rejection_count'], 99)
        self.assertEqual(new['history'][0]['status'], 'old')
        self.assertEqual(new['checkpoint_sha256'], 'a' * 64)
        self.assertEqual(old['checkpoint_sha256'], 'b' * 64)


class GitCASRollbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.remote = self.base / 'remote.git'
        self.repo = self.base / 'writer'
        run('git', 'init', '--bare', '--initial-branch=main', str(self.remote))
        run('git', 'clone', str(self.remote), str(self.repo))
        run('git', 'switch', '-c', 'main', cwd=self.repo)
        run('git', 'config', 'user.name', 'JANUS TEST', cwd=self.repo)
        run('git', 'config', 'user.email', 'test@example.invalid', cwd=self.repo)
        (self.repo / CHECKPOINT).parent.mkdir(parents=True)
        (self.repo / STATE).parent.mkdir(parents=True)
        (self.repo / CHECKPOINT).write_bytes(b'previous verified checkpoint')
        self.base_sha = digest((self.repo / CHECKPOINT).read_bytes())
        st = {'schema': 'janus.model.state.v1',
              'checkpoint_sha256': self.base_sha,
              'promotion_count': 5, 'history': []}
        (self.repo / STATE).write_text(json.dumps(st))
        run('git', 'add', '.', cwd=self.repo)
        run('git', 'commit', '-m', 'old champion', cwd=self.repo)
        run('git', 'push', 'origin', 'HEAD:main', cwd=self.repo)
        self.original_commit = run('git', 'rev-parse', 'HEAD', cwd=self.repo)

    def new_champion_commit(self):
        (self.repo / CHECKPOINT).write_bytes(b'new, externally admitted candidate')
        self.new_sha = digest((self.repo / CHECKPOINT).read_bytes())
        st = json.loads((self.repo / STATE).read_text())
        st['checkpoint_sha256'] = self.new_sha
        (self.repo / STATE).write_text(json.dumps(st))
        rec = {'schema': 'janus.daddy_keymaster.rollback.v1',
               'status': 'AVAILABLE',
               'to_git_commit': self.original_commit,
               'to_checkpoint_sha256': self.base_sha,
               'from_checkpoint_sha256': self.new_sha}
        (self.repo / ROLLBACK).write_text(json.dumps(rec))
        run('git', 'add', '.', cwd=self.repo)
        run('git', 'commit', '-m', 'new champion', cwd=self.repo)
        run('git', 'push', 'origin', 'HEAD:main', cwd=self.repo)
        return run('git', 'rev-parse', 'HEAD', cwd=self.repo)

    def test_clean_head_required(self):
        source_preflight(self.repo, self.original_commit)
        (self.repo / STATE).write_text('{}')
        with self.assertRaisesRegex(Hold, 'WORKTREE_DIRTY'):
            source_preflight(self.repo, self.original_commit)

    def test_stale_head_fails_closed(self):
        self.new_champion_commit()
        with self.assertRaisesRegex(Hold, 'STALE_LOCAL_HEAD'):
            source_preflight(self.repo, self.original_commit)

    def test_rollback_compensating_commit_preserves_history(self):
        current = self.new_champion_commit()
        back = rollback_latest(self.repo, current, enable=True)
        self.assertNotEqual(back, self.original_commit)
        self.assertEqual(run('git', 'rev-parse', 'HEAD^', cwd=self.repo), current)
        self.assertEqual(run('git', 'rev-parse', 'origin/main', cwd=self.repo), back)
        state, state_sha = authoritative_state(self.repo)
        self.assertEqual(state_sha, self.base_sha)
        self.assertEqual(state['rollback_count'], 1)
        self.assertEqual(state['status'], 'NATIVE_MODEL_ROLLED_BACK')
        self.assertEqual(json.loads((self.repo / ROLLBACK).read_text())['status'],
                         'CONSUMED')
        with self.assertRaisesRegex(Hold, 'ROLLBACK_NOT_APPLICABLE'):
            rollback_latest(self.repo, back, enable=True)

    def test_rollback_without_enable_denied(self):
        current = self.new_champion_commit()
        with self.assertRaisesRegex(Hold, 'ROLLBACK_DISABLED'):
            rollback_latest(self.repo, current)
        self.assertEqual(run('git', 'rev-parse', 'origin/main', cwd=self.repo),
                         current)

    def test_report_cannot_publish_without_trusted_issuer(self):
        candidate = self.base / 'candidate.pt'
        candidate.write_bytes(b'potential candidate')
        report = {'status': 'BLIND_GATE_PASS__READY_FOR_SEPARATE_CAS',
                  'parent_checkpoint_sha256': self.base_sha,
                  'candidate_checkpoint_sha256': digest(candidate.read_bytes()),
                  'source_authentication': 'REQUIRES_TRUSTED_INDEPENDENT_WORKFLOW'}
        with self.assertRaisesRegex(Hold, 'UNTRUSTED_OR_STALE_RELEASE'):
            publish(self.repo, candidate, report, self.original_commit, enable=True)
        self.assertEqual((self.repo / CHECKPOINT).read_bytes(),
                         b'previous verified checkpoint')


if __name__ == '__main__':
    unittest.main()
