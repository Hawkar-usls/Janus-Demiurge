"""Fail-closed JANUS champion admission and fast-forward-only release/rollback.

This is NOT a calibration worker and has no scheduled or automatic authority.
Blind-final data must be furnished by an independently controlled evaluator;
the caller must independently authenticate its origin and separation. A JSON
claim that a corpus is blind is not proof of that separation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

from daddy_keymaster.broker import canonical, sha

CHECKPOINT = Path('janus_model/checkpoints/promoted.pt')
STATE = Path('janus_model/state/JANUS_MODEL_STATE.json')
ROLLBACK = Path('janus_model/state/CHAMPION_ROLLBACK.json')
SCHEMA = 'janus.daddy_keymaster.champion_release.v1'
AUDIT_SCHEMA = 'janus.daddy_keymaster.native_calibration_audit.v1'
MAX_WEIGHT_BYTES = 5_000_000
HEX40 = re.compile(r'^[0-9a-f]{40}$')
HEX64 = re.compile(r'^[0-9a-f]{64}$')


class Hold(ValueError):
    """Prevent release on stale, incomplete, untrusted, or degraded evidence."""


def require(cond, code):
    if not cond:
        raise Hold(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def hash_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_json(path, maximum=100_000):
    raw = Path(path).read_bytes()
    require(len(raw) <= maximum, 'CHAMPION_METADATA_TOO_LARGE')
    obj = json.loads(raw)
    require(type(obj) is dict, 'CHAMPION_METADATA_NOT_OBJECT')
    return obj


def git(root, *args, binary=False):
    p = subprocess.run(['git', *args], cwd=root, check=True, capture_output=True,
                       text=not binary)
    return p.stdout if binary else p.stdout.strip()


def source_preflight(root, expected_head):
    """Exact HEAD and remote CAS: unrelated pushes also invalidate a release."""
    require(bool(HEX40.fullmatch(expected_head)), 'CHAMPION_HEAD_NOT_SHA')
    require(git(root, 'branch', '--show-current') == 'main', 'CHAMPION_NOT_ON_MAIN')
    require(not git(root, 'status', '--porcelain'), 'CHAMPION_WORKTREE_DIRTY')
    local = git(root, 'rev-parse', 'HEAD')
    require(local == expected_head, 'CHAMPION_STALE_LOCAL_HEAD')
    git(root, 'fetch', '--no-tags', 'origin', 'main')
    require(git(root, 'rev-parse', 'origin/main') == expected_head,
            'CHAMPION_STALE_REMOTE_HEAD')
    return local


def authoritative_state(root):
    state = read_json(root / STATE, maximum=1_000_000)
    ck = root / CHECKPOINT
    require(ck.is_file() and 0 < ck.stat().st_size <= MAX_WEIGHT_BYTES,
            'CHAMPION_INCUMBENT_MISSING_OR_UNBOUNDED')
    actual = hash_file(ck)
    require(state.get('schema') == 'janus.model.state.v1' and
            state.get('checkpoint_sha256') == actual,
            'CHAMPION_INCUMBENT_STATE_MISMATCH')
    return state, actual


def verify_audit(audit, incumbent_sha, candidate_sha):
    """Check the original x64/ARM64 receipt; NOT an identity signature."""
    require(audit.get('schema') == AUDIT_SCHEMA and
            audit.get('receipt_sha256') == sha({k: v for k, v in audit.items()
                                                 if k != 'receipt_sha256'}),
            'CHAMPION_AUDIT_DIGEST_INVALID')
    require(audit.get('status') == 'BEST_CANDIDATE_REVIEW_ONLY' and
            audit.get('main_checkpoint_mutated') is False and
            audit.get('automatic_production_promotion') is False,
            'CHAMPION_NO_VERIFIED_WINNER')
    require(audit.get('incumbent_checkpoint_sha256') == incumbent_sha and
            bool(HEX40.fullmatch(str(audit.get('commit', '')))) and
            bool(HEX64.fullmatch(str(audit.get('source_digest', '')))) and
            bool(HEX64.fullmatch(str(audit.get('evaluation_contract_sha256', '')))),
            'CHAMPION_SOURCE_OR_PARENT_DRIFT')
    workers = audit.get('workers')
    require(isinstance(workers, list) and
            {w.get('architecture') for w in workers if isinstance(w, dict)} ==
            {'X64', 'ARM64'}, 'CHAMPION_WORKER_QUORUM_INVALID')
    w = audit.get('winner')
    require(isinstance(w, dict) and
            w.get('candidate_checkpoint_sha256') == candidate_sha and
            w.get('architecture') in ('X64', 'ARM64') and
            any(x.get('architecture') == w['architecture'] and
                x.get('verdict') == 'INDEPENDENTLY_VERIFIED_BETTER' and
                x.get('candidate_checkpoint_sha256') == candidate_sha
                for x in workers if isinstance(x, dict)),
            'CHAMPION_WINNER_NOT_PROVEN')


def assess(root, candidate_path, audit_path, corpus_manifest_path,
           adaptive_holdout_path, final_holdout_path, final_manifest_path):
    """Recompute both original gates and a separate withheld final evaluation.

    Final manifest provenance must be established by the independent workflow,
    OUTSIDE this function. Candidate workers must not see final_holdout_path.
    """
    from janus_model.eval_contract import (contract_identity, DEFAULT_ANCHOR,
                                           EVAL_BATCHES, EVAL_BATCH_SIZE,
                                           MIN_MEANINGFUL_IMPROVEMENT_FRACTION)
    from janus_model.train_registry import (load_checkpoint, eval_loss,
                                            tokens, promotion_gate)
    state, parent_sha = authoritative_state(root)
    candidate_path = Path(candidate_path)
    require(candidate_path.is_file() and
            0 < candidate_path.stat().st_size <= MAX_WEIGHT_BYTES,
            'CHAMPION_CANDIDATE_MISSING_OR_UNBOUNDED')
    candidate_sha = hash_file(candidate_path)
    audit = read_json(audit_path)
    verify_audit(audit, parent_sha, candidate_sha)
    corpus = read_json(corpus_manifest_path)
    contract = contract_identity()
    require(corpus.get('source_digest') == audit['source_digest'] and
            corpus.get('evaluation_contract_sha256') ==
            audit['evaluation_contract_sha256'] == contract['contract_sha256'] and
            corpus.get('anchor_is_training_source') is False,
            'CHAMPION_CORPUS_OR_CONTRACT_DRIFT')
    adaptive_path = Path(adaptive_holdout_path)
    require(adaptive_path.is_file() and
            adaptive_path.stat().st_size == corpus.get('holdout_bytes') and
            adaptive_path.stat().st_size >= 10000,
            'CHAMPION_ADAPTIVE_HOLDOUT_MISMATCH')
    final = read_json(final_manifest_path)
    path = Path(final_holdout_path)
    require(final.get('schema') == 'janus.daddy_keymaster.blind_final.v1' and
            final.get('training_excluded') is True and
            final.get('selection_excluded') is True and
            final.get('checkpoint_source_sha256') == parent_sha and
            final.get('corpus_source_digest') == corpus['source_digest'] and
            bool(HEX64.fullmatch(str(final.get('sha256', '')))) and
            path.is_file() and 4096 <= path.stat().st_size <= 2_000_000 and
            hash_file(path) == final['sha256'] and
            hash_file(path) != hash_file(adaptive_path) and
            hash_file(path) != hash_file(DEFAULT_ANCHOR),
            'CHAMPION_FINAL_HOLDOUT_NOT_VERIFIABLE')
    # External CI provenance is required: self-asserted flags do not prove blindness.
    incumbent, _ = load_checkpoint(root / CHECKPOINT)
    challenger, _ = load_checkpoint(candidate_path)
    require(challenger.config == incumbent.config and
            state.get('config') == challenger.config.to_dict(),
            'CHAMPION_INCOMPATIBLE_ARCHITECTURE')
    adaptive = tokens(adaptive_holdout_path)
    anchor = tokens(DEFAULT_ANCHOR)
    final_tokens = tokens(path)
    sa, sb = contract['adaptive']['seed'], contract['anchor']['seed']
    fc = sb + 19_991
    a0 = eval_loss(incumbent, adaptive, EVAL_BATCHES, EVAL_BATCH_SIZE, sa)
    a1 = eval_loss(challenger, adaptive, EVAL_BATCHES, EVAL_BATCH_SIZE, sa)
    b0 = eval_loss(incumbent, anchor, EVAL_BATCHES, EVAL_BATCH_SIZE, sb)
    b1 = eval_loss(challenger, anchor, EVAL_BATCHES, EVAL_BATCH_SIZE, sb)
    f0 = eval_loss(incumbent, final_tokens, EVAL_BATCHES, EVAL_BATCH_SIZE, fc)
    f1 = eval_loss(challenger, final_tokens, EVAL_BATCHES, EVAL_BATCH_SIZE, fc)
    gate = promotion_gate(candidate_loss=a1, incumbent_loss=a0,
                          candidate_anchor_loss=b1, incumbent_anchor_loss=b0)
    final_ok = all(map(math.isfinite, (f0, f1))) and f0 > 0 and (
        f1 <= f0 * (1 - MIN_MEANINGFUL_IMPROVEMENT_FRACTION))
    require(gate['promote'] and final_ok, 'CHAMPION_NO_REPRODUCIBLE_BLIND_GAIN')
    import torch
    from janus_model.model import ByteTokenizer
    with torch.no_grad():
        torch.manual_seed(1729)
        challenger.generate(torch.tensor([ByteTokenizer.encode('JANUS:', bos=True)]),
                            max_new_tokens=8)
    return {
        'schema': SCHEMA, 'status': 'BLIND_GATE_PASS__READY_FOR_SEPARATE_CAS',
        'parent_checkpoint_sha256': parent_sha,
        'candidate_checkpoint_sha256': candidate_sha,
        'source_digest': corpus['source_digest'],
        'evaluation_contract_sha256': contract['contract_sha256'],
        'audit_receipt_sha256': audit['receipt_sha256'],
        'calibration_run_id': audit['run_id'],
        'calibration_run_attempt': audit['attempt'],
        'calibration_commit': audit['commit'],
        'final_corpus_sha256': final['sha256'],
        'final_corpus_manifest_sha256': hash_file(final_manifest_path),
        'adaptive_losses': {'incumbent': a0, 'candidate': a1},
        'anchor_losses': {'incumbent': b0, 'candidate': b1},
        'final_losses': {'incumbent': f0, 'candidate': f1},
        'original_promotion_gate': gate,
        'final_gate_pass': True,
        'source_authentication': 'REQUIRES_TRUSTED_INDEPENDENT_WORKFLOW',
    }


def journaled_state(old, report):
    state = dict(old)
    state['checkpoint_sha256'] = report['candidate_checkpoint_sha256']
    state['promotion_count'] = int(old.get('promotion_count', 0)) + 1
    state['status'] = 'NATIVE_MODEL_PROMOTED'
    state['last_training_status'] = 'PROMOTED_DADDY_KEYMASTER_BLIND'
    state['last_promotion_reason'] = 'CHAMPION_VERIFIED_DUAL_AND_FINAL_GATES'
    state['history'] = [*old.get('history', []), {
        'status': 'PROMOTED', 'event': 'DADDY_KEYMASTER_BLIND_ADMISSION',
        'run_id': str(report['calibration_run_id']),
        'source_digest': report['source_digest'],
        'checkpoint_sha256': report['candidate_checkpoint_sha256'],
        'parent_checkpoint_sha256': report['parent_checkpoint_sha256'],
        'final_corpus_sha256': report['final_corpus_sha256'],
        'promotion_reason': 'CHAMPION_VERIFIED_DUAL_AND_FINAL_GATES',
    }][-64:]
    return state


def publish(root, candidate_path, report, expected_head, *, enable=False):
    """Only a separate authenticated issuer may invoke this in an isolated checkout.

    Commit holds weights, state, receipt and rollback data in one Git tree.
    Normal fast-forward push is the final remote CAS. No force push.
    """
    root = Path(root).resolve()
    require(enable is True, 'CHAMPION_PUBLISH_DISABLED_BY_DEFAULT')
    source_preflight(root, expected_head)
    state, parent_sha = authoritative_state(root)
    require(parent_sha == report.get('parent_checkpoint_sha256') and
            report.get('status') == 'BLIND_GATE_PASS__READY_FOR_SEPARATE_CAS' and
            report.get('source_authentication') == 'TRUSTED_WORKFLOW_VERIFIED',
            'CHAMPION_UNTRUSTED_OR_STALE_RELEASE')
    candidate_path = Path(candidate_path)
    require(candidate_path.is_file() and
            hash_file(candidate_path) == report.get('candidate_checkpoint_sha256') and
            candidate_path.stat().st_size <= MAX_WEIGHT_BYTES,
            'CHAMPION_CANDIDATE_BYTES_CHANGED')
    receipt_path = root / 'janus_model/receipts' / (
        'champion-' + str(report['calibration_run_id']) + '-' +
        str(report['calibration_run_attempt']) + '.json')
    require(not receipt_path.exists(), 'CHAMPION_RECEIPT_ALREADY_EXISTS')
    # Writes happen only in an isolated, clean checkout after the first CAS.
    shutil.copyfile(candidate_path, root / CHECKPOINT)
    (root / STATE).write_text(json.dumps(journaled_state(state, report),
                                         ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    rollback = {'schema': 'janus.daddy_keymaster.rollback.v1',
                'from_checkpoint_sha256': report['candidate_checkpoint_sha256'],
                'to_checkpoint_sha256': parent_sha,
                'to_git_commit': expected_head, 'status': 'AVAILABLE'}
    (root / ROLLBACK).write_bytes(canonical(rollback) + b'\n')
    receipt = dict(report)
    receipt['status'] = 'PROMOTION_COMMIT_PREPARED'
    receipt['receipt_sha256'] = sha(receipt)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_bytes(canonical(receipt) + b'\n')
    git(root, 'add', '-f', str(CHECKPOINT), str(STATE), str(ROLLBACK),
        str(receipt_path.relative_to(root)))
    git(root, 'diff', '--cached', '--check')
    git(root, 'commit', '-m', 'JANUS champion: verified blind promotion ' +
        str(report['calibration_run_id']))
    source_preflight_postcommit(root, expected_head)
    git(root, 'push', 'origin', 'HEAD:main')
    return git(root, 'rev-parse', 'HEAD')


def source_preflight_postcommit(root, expected_parent):
    require(git(root, 'rev-parse', 'HEAD^') == expected_parent,
            'CHAMPION_PARENT_CHANGED_BEFORE_PUBLISH')
    git(root, 'fetch', '--no-tags', 'origin', 'main')
    require(git(root, 'rev-parse', 'origin/main') == expected_parent,
            'CHAMPION_REMOTE_CHANGED_BEFORE_PUBLISH')


def rollback_latest(root, expected_head, *, enable=False):
    """Emergency compensating commit: never reset, rewrite or force-push."""
    root = Path(root).resolve()
    require(enable is True, 'CHAMPION_ROLLBACK_DISABLED_BY_DEFAULT')
    source_preflight(root, expected_head)
    current, current_sha = authoritative_state(root)
    record = read_json(root / ROLLBACK)
    old_ref = record.get('to_git_commit')
    old_sha = record.get('to_checkpoint_sha256')
    require(record.get('schema') == 'janus.daddy_keymaster.rollback.v1' and
            record.get('status') == 'AVAILABLE' and
            current_sha == record.get('from_checkpoint_sha256') and
            isinstance(old_ref, str) and bool(HEX40.fullmatch(old_ref)) and
            isinstance(old_sha, str) and bool(HEX64.fullmatch(old_sha)),
            'CHAMPION_ROLLBACK_NOT_APPLICABLE')
    require(git(root, 'merge-base', '--is-ancestor', old_ref, 'HEAD') == '',
            'CHAMPION_ROLLBACK_NOT_ANCESTOR')
    old_bytes = git(root, 'show', f'{old_ref}:{CHECKPOINT.as_posix()}', binary=True)
    old_state = json.loads(git(root, 'show', f'{old_ref}:{STATE.as_posix()}'))
    require(digest(old_bytes) == old_sha and
            old_state.get('checkpoint_sha256') == old_sha and
            0 < len(old_bytes) <= MAX_WEIGHT_BYTES,
            'CHAMPION_ROLLBACK_OLD_CHAMPION_INVALID')
    (root / CHECKPOINT).write_bytes(old_bytes)
    current['checkpoint_sha256'] = old_sha
    current['status'] = 'NATIVE_MODEL_ROLLED_BACK'
    current['last_promotion_reason'] = 'VERIFIED_CHAMPION_ROLLBACK'
    current['rollback_count'] = int(current.get('rollback_count', 0)) + 1
    current['history'] = [*current.get('history', []), {
        'event': 'DADDY_KEYMASTER_ROLLBACK', 'status': 'ROLLED_BACK',
        'checkpoint_sha256': old_sha, 'parent_checkpoint_sha256': current_sha,
        'rollback_source_commit': old_ref}][-64:]
    (root / STATE).write_text(json.dumps(current, ensure_ascii=False,
                                         sort_keys=True, indent=2) + '\n')
    record['status'] = 'CONSUMED'
    record['rollback_of_sha256'] = current_sha
    (root / ROLLBACK).write_bytes(canonical(record) + b'\n')
    git(root, 'add', '-f', str(CHECKPOINT), str(STATE), str(ROLLBACK))
    git(root, 'diff', '--cached', '--check')
    git(root, 'commit', '-m', 'JANUS champion: verified compensating rollback')
    source_preflight_postcommit(root, expected_head)
    git(root, 'push', 'origin', 'HEAD:main')
    return git(root, 'rev-parse', 'HEAD')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('operation', choices=('assess', 'publish', 'rollback'))
    ap.add_argument('--root', type=Path, default=Path('.'))
    ap.add_argument('--candidate', type=Path)
    ap.add_argument('--audit', type=Path)
    ap.add_argument('--corpus-manifest', type=Path)
    ap.add_argument('--adaptive-holdout', type=Path)
    ap.add_argument('--final-holdout', type=Path)
    ap.add_argument('--final-manifest', type=Path)
    ap.add_argument('--expected-head')
    ap.add_argument('--report', type=Path)
    ap.add_argument('--enable-local-publisher', action='store_true')
    a = ap.parse_args()
    root = a.root.resolve()
    try:
        if a.operation == 'assess':
            for x in (a.candidate, a.audit, a.corpus_manifest,
                      a.adaptive_holdout, a.final_holdout,
                      a.final_manifest, a.report):
                require(x is not None, 'CHAMPION_MISSING_EVALUATION_INPUT')
            result = assess(root, a.candidate, a.audit, a.corpus_manifest,
                            a.adaptive_holdout, a.final_holdout, a.final_manifest)
            a.report.parent.mkdir(parents=True, exist_ok=True)
            a.report.write_bytes(canonical(result) + b'\n')
            print(json.dumps({'status': result['status'], 'receipt_sha256': sha(result)}))
        elif a.operation == 'publish':
            # A source-authenticating CI adapter must invoke publish() separately.
            raise Hold('CHAMPION_PUBLISH_CLI_SEALED_UNTIL_TRUSTED_BLIND_ISSUER')
        else:
            require(a.expected_head is not None, 'CHAMPION_EXPECTED_HEAD_REQUIRED')
            print(json.dumps({'status': 'ROLLED_BACK', 'commit': rollback_latest(
                root, a.expected_head, enable=a.enable_local_publisher)}))
    except (Hold, subprocess.CalledProcessError) as exc:
        raise SystemExit('CHAMPION_HOLD:' + str(exc)) from exc


if __name__ == '__main__':
    main()
