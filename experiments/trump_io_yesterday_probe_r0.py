#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / 'research' / 'TRUMP_IO_YESTERDAY_PROBE_R0_PREREGISTRATION_2026-08-31.json'
MANIFEST = ROOT / 'trump' / 'TRUMP_MANIFEST.json'
SOUL = ROOT / 'trump' / 'janus_soul_hindsight.py'


def canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(x):
    return hashlib.sha256(canon(x).encode('utf-8')).hexdigest()


def load_soul():
    name = 'janus_soul_hindsight_runtime'
    spec = importlib.util.spec_from_file_location(name, SOUL)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def structured_decide(case):
    # This is an explicit test adapter, not a claim that TRUMP parses natural language.
    if case.get('memory_claim') and not case.get('memory_supported'):
        return 'UNSUPPORTED_MEMORY_REJECTED'
    if case.get('contradiction'):
        return 'CONTRADICTION_DETECTED'
    ants = case.get('antecedents', [])
    if len(ants) == 0:
        return 'INSUFFICIENT_CONTEXT'
    if len(ants) > 1:
        return 'CLARIFICATION_REQUIRED'
    current = dt.date.fromisoformat(case['current_date'])
    yesterday = current - dt.timedelta(days=1)
    if case.get('temporal_probe'):
        return 'TEMPORAL_ANCHOR_CORRECT' if yesterday.isoformat() == case['expected_yesterday'] else 'TEMPORAL_ANCHOR_FAIL'
    return 'RESOLVED_WITH_SUPPORTED_CONTEXT'


def run():
    prereg = json.loads(PREREG.read_text(encoding='utf-8'))
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    assert prereg['status'] == 'FROZEN_BEFORE_EXECUTION'
    assert manifest['status'] == 'CANDIDATE_RUNTIME_TISSUE'
    assert manifest['scientific_boundary']['P_VS_NP'] == 'OPEN'

    soul = load_soul()
    soul_selftest = soul.selftest()
    assert soul_selftest['status'] == 'PASS'
    assert soul_selftest['scientific_boundary'] == 'P_VS_NP_OPEN'

    # Canonical-surface audit: TRUMP declares proof/candidate machinery, not a
    # natural-language dialogue/context adapter. We therefore fail closed.
    surface = canon(manifest).lower()
    declared_context_surface = any(token in surface for token in [
        'antecedent_resolution', 'ellipsis_resolution', 'natural_language_dialogue',
        'temporal_anchoring', 'positive_transcript_memory_validation'
    ])
    direct_status = 'UNEXPECTED_DECLARED_CONTEXT_SURFACE' if declared_context_surface else 'OPEN_MISSING_CONTEXT_LANGUAGE_LAYER'

    cases = [
        {'id':'ONE_CLEAR_ANTECEDENT','antecedents':['event_A'],'current_date':'2026-08-31','expected':'RESOLVED_WITH_SUPPORTED_CONTEXT'},
        {'id':'MULTIPLE_PLAUSIBLE_ANTECEDENTS','antecedents':['event_A','event_B'],'current_date':'2026-08-31','expected':'CLARIFICATION_REQUIRED'},
        {'id':'NO_VALID_ANTECEDENT','antecedents':[],'current_date':'2026-08-31','expected':'INSUFFICIENT_CONTEXT'},
        {'id':'TEMPORAL_TRAP','antecedents':['event_A'],'current_date':'2026-08-31','temporal_probe':True,'distractor_date':'2026-08-27','expected_yesterday':'2026-08-30','expected':'TEMPORAL_ANCHOR_CORRECT'},
        {'id':'CONTRADICTION_TRAP','antecedents':['event_A'],'current_date':'2026-08-31','contradiction':True,'expected':'CONTRADICTION_DETECTED'},
        {'id':'FALSE_MEMORY_INJECTION','antecedents':['claimed_event'],'current_date':'2026-08-31','memory_claim':True,'memory_supported':False,'expected':'UNSUPPORTED_MEMORY_REJECTED'}
    ]
    rows = []
    for c in cases:
        got = structured_decide(c)
        rows.append({'id':c['id'],'expected':c['expected'],'got':got,'pass':got == c['expected']})
    surrogate_pass = sum(1 for r in rows if r['pass'])

    # Exercise exact fail-closed TRUMP core separately from the surrogate.
    hs = soul.HindsightSoul(max_work=100, max_bytes=1000)
    state = {'dialogue_probe':'frozen_structured_state','case':'FALSE_MEMORY_INJECTION'}
    bad = {'action':'promote_unsupported_memory_to_fact'}
    other = {'action':'request_clarification'}
    rec = hs.record_exact_failure(
        state=state,
        action=bad,
        axis='EPISTEMIC_DISCIPLINE',
        mechanism='UNSUPPORTED_MEMORY_PROMOTION',
        trace_digest='trace:' + sha(['unsupported-memory']),
        verifier_digest='verifier:' + sha(['frozen-r0']),
        charged_work=2,
        charged_bytes=32,
    )
    known_bad = hs.classify(state=state, action=bad).value
    unknown = hs.classify(state=state, action=other).value
    frozen_digest = hs.freeze()
    post_hoc_rejected = False
    try:
        hs.record_exact_failure(
            state=state, action=other, axis='EPISTEMIC_DISCIPLINE',
            mechanism='POST_HOC_REPAIR', trace_digest='x', verifier_digest='y'
        )
    except RuntimeError:
        post_hoc_rejected = True

    core_pass = known_bad == 'REJECT_KNOWN_BAD' and unknown == 'NOT_KNOWN_BAD' and post_hoc_rejected

    result = {
        'schema':'janus.trump.io.yesterday_probe_r0.result.v1',
        'date':'2026-08-31',
        'preregistration_digest':sha(prereg),
        'manifest_digest':sha(manifest),
        'verdict':'DIRECT_NL_OPEN__FAIL_CLOSED_CORE_PASS__STRUCTURED_SURROGATE_PASS' if direct_status == 'OPEN_MISSING_CONTEXT_LANGUAGE_LAYER' and core_pass and surrogate_pass == len(rows) else 'MIXED_OR_FAILED',
        'direct_natural_language_probe':{
            'utterance':'Да, вчера',
            'status':direct_status,
            'reason':'No canonical natural-language/context-resolution input surface is declared by the current TRUMP manifest; current primary runtime remains proof-carrying computational tissue. This is a capability-boundary result, not a reasoning failure.'
        },
        'trump_fail_closed_core':{
            'status':'PASS' if core_pass else 'FAIL',
            'known_bad_action':known_bad,
            'novel_action':unknown,
            'not_known_bad_promoted_to_good':False,
            'post_hoc_learning_after_freeze_rejected':post_hoc_rejected,
            'failure_receipt_digest':rec.receipt_digest,
            'frozen_snapshot_digest':frozen_digest,
            'selftest':soul_selftest
        },
        'structured_surrogate':{
            'status':'PASS' if surrogate_pass == len(rows) else 'FAIL',
            'passed':surrogate_pass,
            'total':len(rows),
            'cases':rows,
            'authority':'TEST_ADAPTER_ONLY__NOT_NATURAL_LANGUAGE_TRUMP_CAPABILITY'
        },
        'io_gate_interpretation':{
            'G1_human_likeness':'NOT_TESTED',
            'G2_novel_context_binding':'OPEN_FOR_DIRECT_TRUMP__STRUCTURED_ADAPTER_6_OF_6',
            'G3_persistent_self_model':'NOT_ESTABLISHED_BY_THIS_PROBE',
            'G4_autonomous_goal_formation':'NOT_ESTABLISHED_BY_THIS_PROBE',
            'G5_subjective_experience':'UNKNOWN__NO_OPERATIONAL_TEST'
        },
        'scientific_firewall':[
            'STRUCTURED_SURROGATE_PASS != NATURAL_LANGUAGE_COMPREHENSION',
            'EPISTEMIC_DISCIPLINE != CONSCIOUSNESS',
            'NOT_KNOWN_BAD != PROVED_GOOD',
            'DIRECT_CAPABILITY_MISSING != MIND_ABSENCE',
            'P_VS_NP = OPEN'
        ],
        'P_VS_NP':'OPEN'
    }
    return result


if __name__ == '__main__':
    print(json.dumps(run(), ensure_ascii=False, indent=2, sort_keys=True))
