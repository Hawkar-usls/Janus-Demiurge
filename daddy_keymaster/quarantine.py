"""DADDY_KEYMASTER R2: read-only winner quarantine, never a promotion issuer.

Only materializes a reviewed winner into a bounded GitHub Actions artifact.
No authentication of GitHub identity or independent blind data is implied.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil

from daddy_keymaster.broker import canonical, sha
from daddy_keymaster.champion_release import Hold, hash_file, read_json, require

SCHEMA = 'janus.daddy_keymaster.native_candidate_quarantine.v1'
HEX64 = re.compile(r'^[0-9a-f]{64}$')
ARCH = {'X64', 'ARM64'}
MAX_SIZE = 5_000_000


def build(audit_path: Path, inputs_root: Path, output_root: Path, *,
          repository: str, commit: str, run_id: str, attempt: str):
    audit = read_json(audit_path)
    require(audit.get('schema') == 'janus.daddy_keymaster.native_calibration_audit.v1' and
            audit.get('receipt_sha256') ==
            sha({k: v for k, v in audit.items() if k != 'receipt_sha256'}),
            'QUARANTINE_AUDIT_TAMPERED')
    require(audit.get('commit') == commit and
            str(audit.get('run_id')) == run_id and
            str(audit.get('attempt')) == attempt and
            audit.get('main_checkpoint_mutated') is False and
            audit.get('automatic_production_promotion') is False,
            'QUARANTINE_RUN_NOT_BOUND')
    require(audit.get('status') in ('BEST_CANDIDATE_REVIEW_ONLY', 'INCUMBENT_RETAINED'),
            'QUARANTINE_INVALID_DECISION')
    require(repository == 'Hawkar-usls/Janus-Demiurge',
            'QUARANTINE_WRONG_REPOSITORY')
    require(bool(HEX64.fullmatch(str(audit.get('incumbent_checkpoint_sha256', '')))) and
            bool(HEX64.fullmatch(str(audit.get('source_digest', '')))) and
            bool(HEX64.fullmatch(str(audit.get('evaluation_contract_sha256', '')))),
            'QUARANTINE_SOURCE_INVALID')
    workers = audit.get('workers')
    require(isinstance(workers, list) and len(workers) == 2 and
            {w.get('architecture') for w in workers if isinstance(w, dict)} == ARCH,
            'QUARANTINE_MISSING_WORKERS')
    output_root = Path(output_root)
    require(not output_root.exists(), 'QUARANTINE_OUTPUT_ALREADY_EXISTS')
    result = {
        'schema': SCHEMA, 'status': 'NO_ACCEPTED_WINNER',
        'repository': repository, 'source_commit': commit,
        'run_id': run_id, 'attempt': attempt,
        'audit_sha256': hash_file(audit_path),
        'audit_receipt_sha256': audit['receipt_sha256'],
        'parent_checkpoint_sha256': audit['incumbent_checkpoint_sha256'],
        'source_digest': audit['source_digest'],
        'evaluation_contract_sha256': audit['evaluation_contract_sha256'],
        'candidate_checkpoint_sha256': None,
        'candidate_architecture': None,
        'automatic_production_promotion': False,
        'independent_blind_final_proven': False,
        'authority_delta': 0,
    }
    if audit['status'] == 'INCUMBENT_RETAINED':
        require(audit.get('winner') is None, 'QUARANTINE_REJECTED_HAS_WINNER')
    else:
        winner = audit.get('winner')
        require(isinstance(winner, dict) and winner.get('architecture') in ARCH,
                'QUARANTINE_UNRECOGNIZED_WINNER')
        arch = winner['architecture']
        candidate_sha = winner.get('candidate_checkpoint_sha256')
        require(isinstance(candidate_sha, str) and bool(HEX64.fullmatch(candidate_sha)) and
                candidate_sha != audit['incumbent_checkpoint_sha256'],
                'QUARANTINE_CANDIDATE_DIGEST_INVALID')
        require(any(w.get('architecture') == arch and
                    w.get('verdict') == 'INDEPENDENTLY_VERIFIED_BETTER' and
                    w.get('candidate_checkpoint_sha256') == candidate_sha
                    for w in workers), 'QUARANTINE_WINNER_NOT_IN_AUDIT')
        folder = Path(inputs_root) / ('native-calibration-' + arch.lower())
        candidate = folder / 'CANDIDATE.pt'
        wpath, tpath = folder / 'WORKER.json', folder / 'TRAINING.json'
        require(not candidate.is_symlink() and not wpath.is_symlink() and
                not tpath.is_symlink() and candidate.is_file() and
                0 < candidate.stat().st_size <= MAX_SIZE,
                'QUARANTINE_CANDIDATE_FILE_UNSAFE')
        w, train = read_json(wpath, maximum=30_000), read_json(tpath)
        require(w.get('receipt_sha256') ==
                sha({k:v for k,v in w.items() if k != 'receipt_sha256'}) and
                w.get('worker_receipt_sha256') == sha(train) and
                w.get('repository') == repository and
                w.get('commit') == commit and
                str(w.get('run_id')) == run_id and str(w.get('attempt')) == attempt and
                w.get('architecture') == arch and
                w.get('candidate_status') == 'PROMOTED' and
                w.get('candidate_checkpoint_sha256') == candidate_sha and
                w.get('parent_checkpoint_sha256') ==
                    audit['incumbent_checkpoint_sha256'] and
                w.get('source_digest') == audit['source_digest'] and
                w.get('evaluation_contract_sha256') ==
                    audit['evaluation_contract_sha256'] and
                w.get('auto_write_main') is False and w.get('authority_delta') == 0 and
                train.get('candidate_checkpoint_sha256') == candidate_sha and
                train.get('parent_checkpoint_sha256') ==
                    audit['incumbent_checkpoint_sha256'] and
                train.get('status') == 'PROMOTED' and
                hash_file(candidate) == candidate_sha,
                'QUARANTINE_WORKER_OR_CHECKPOINT_MISMATCH')
        result['status'] = 'QUARANTINED_REVIEW_ONLY'
        result['candidate_checkpoint_sha256'] = candidate_sha
        result['candidate_architecture'] = arch
        result['candidate_bytes'] = candidate.stat().st_size
        result['worker_receipt_sha256'] = w['receipt_sha256']
        result['training_receipt_sha256'] = sha(train)
        output_root.mkdir(parents=True)
        shutil.copyfile(candidate, output_root / 'candidate.pt')
        require(hash_file(output_root / 'candidate.pt') == candidate_sha,
                'QUARANTINE_COPY_DIGEST_MISMATCH')
    if not output_root.exists():
        output_root.mkdir(parents=True)
    result['receipt_sha256'] = sha(result)
    (output_root / 'QUARANTINE.json').write_bytes(canonical(result) + b'\n')
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--audit', type=Path, required=True)
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    try:
        r = build(a.audit, a.inputs, a.output,
                  repository=os.environ['GITHUB_REPOSITORY'],
                  commit=os.environ['GITHUB_SHA'],
                  run_id=os.environ['GITHUB_RUN_ID'],
                  attempt=os.environ['GITHUB_RUN_ATTEMPT'])
        print(json.dumps({'status': r['status'],
                          'receipt_sha256': r['receipt_sha256']}, sort_keys=True))
    except Hold as e:
        raise SystemExit('QUARANTINE_HOLD:' + str(e)) from e


if __name__ == '__main__':
    main()
