from __future__ import annotations
import argparse, hashlib, json, re, subprocess
from pathlib import Path
from typing import Iterable

from janus_model.eval_contract import contract_identity
from janus_model.keymaster import collect as collect_keymaster

SEMANTIC_EXTENSIONS={'.json','.md','.markdown','.txt','.py','.yml','.yaml','.toml','.ini','.cfg','.csv','.tsv','.html','.htm','.js','.ts','.tsx','.jsx','.css','.scss','.sh','.ps1','.xml','.jsonl','.ndjson'}
SECRETISH=re.compile(r'(?:^|[._-])(env|secret|token|credential|password|private[_-]?key)(?:$|[._-])',re.I)
TOKEN_PATTERNS=[re.compile(r'ghp_[A-Za-z0-9]{20,}'),re.compile(r'github_pat_[A-Za-z0-9_]{20,}'),re.compile(r'sk-[A-Za-z0-9_-]{20,}'),re.compile(r'AIza[A-Za-z0-9_-]{20,}')]
DEFAULT_KEYMASTER_CONFIG=Path(__file__).resolve().parent/'keymaster'/'PRIMARY_REPOSITORY_CONTRIBUTORS-v2.json'
REQUIRED_KEYMASTER_CONTRIBUTORS=8

def sha256_bytes(raw): return hashlib.sha256(raw).hexdigest()

def scrub(text):
    for p in TOKEN_PATTERNS: text=p.sub('[REDACTED_SECRET]',text)
    return text

def load_eye_exclusions(registry):
    obj=json.loads((registry/'EYE/training/EYE-META-REGISTRY-TRAINING-MANIFEST-v1.0.json').read_text(encoding='utf-8'))
    c=obj['corpus_contract']
    return list(c.get('excluded_generated_prefixes',[])),list(c.get('excluded_generated_exact_paths',[]))

def iter_source_files(registry:Path)->Iterable[Path]:
    prefixes,exact=load_eye_exclusions(registry)
    excluded_dirs={'.git','node_modules','__pycache__','.venv','venv','.mypy_cache','.pytest_cache'}
    for path in sorted(registry.rglob('*')):
        if not path.is_file(): continue
        rel=path.relative_to(registry).as_posix(); parts=path.relative_to(registry).parts
        if any(x in excluded_dirs for x in parts): continue
        if rel in exact or any(rel.startswith(p) for p in prefixes): continue
        if SECRETISH.search(path.name) or path.suffix.lower() not in SEMANTIC_EXTENSIONS: continue
        yield path

def _git_head(repo): return subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()

def _load_keymaster(training_path:Path,manifest_path:Path):
    pack=training_path.read_bytes()
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schema')!='janus.keymaster.learning_contribution_manifest.v2':
        raise RuntimeError('KEYMASTER_V2_MANIFEST_SCHEMA_REJECTED')
    if manifest.get('status')!='READY_8_OF_8' or manifest.get('contributor_count')!=REQUIRED_KEYMASTER_CONTRIBUTORS:
        raise RuntimeError('KEYMASTER_8_OF_8_REQUIRED')
    if manifest.get('required_contributor_count')!=REQUIRED_KEYMASTER_CONTRIBUTORS:
        raise RuntimeError('KEYMASTER_REQUIRED_COUNT_MISMATCH')
    contributors=manifest.get('contributors')
    if not isinstance(contributors,list) or len(contributors)!=REQUIRED_KEYMASTER_CONTRIBUTORS or any(not isinstance(row,dict) for row in contributors):
        raise RuntimeError('KEYMASTER_CONTRIBUTORS_REJECTED')
    if len({row.get('repository') for row in contributors})!=REQUIRED_KEYMASTER_CONTRIBUTORS:
        raise RuntimeError('KEYMASTER_REPOSITORY_UNIQUENESS_REJECTED')
    if sum(1 for row in contributors if row.get('cohort')=='CORE_5')!=5 or sum(1 for row in contributors if row.get('cohort')=='EXTENDED_3')!=3:
        raise RuntimeError('KEYMASTER_COHORT_PARTITION_REJECTED')
    if any(int(row.get('contributed_bytes',0))<=0 for row in contributors):
        raise RuntimeError('KEYMASTER_ZERO_BYTE_CONTRIBUTOR_REJECTED')
    if manifest.get('training_only') is not True:
        raise RuntimeError('KEYMASTER_TRAIN_ONLY_REQUIRED')
    if manifest.get('adaptive_holdout_inclusion') is not False or manifest.get('frozen_anchor_inclusion') is not False:
        raise RuntimeError('KEYMASTER_EVALUATION_LEAKAGE_REJECTED')
    if manifest.get('training_material_is_truth') is not False or manifest.get('contribution_grants_authority') is not False:
        raise RuntimeError('KEYMASTER_EPISTEMIC_FIREWALL_REJECTED')
    if manifest.get('source_execution') is not False or manifest.get('cross_repository_write') is not False:
        raise RuntimeError('KEYMASTER_EXECUTION_AUTHORITY_REJECTED')
    if manifest.get('authority_delta')!=0:
        raise RuntimeError('KEYMASTER_AUTHORITY_DELTA_REJECTED')
    if manifest.get('training_pack_sha256')!=sha256_bytes(pack):
        raise RuntimeError('KEYMASTER_TRAINING_PACK_HASH_MISMATCH')
    if manifest.get('training_bytes')!=len(pack) or len(pack)<=0:
        raise RuntimeError('KEYMASTER_TRAINING_BYTES_MISMATCH')
    return pack.decode('utf-8',errors='replace'),manifest

def _learning_cycle_digest(registry_digest:str,keymaster_digest:str,evaluation_contract_sha256:str)->str:
    raw=(
        'JANUS_LEARNING_CYCLE_V3_KEYMASTER8\n'
        f'registry={registry_digest}\n'
        f'keymaster={keymaster_digest}\n'
        f'evaluation_contract={evaluation_contract_sha256}\n'
    ).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def build_corpus(registry:Path,out_dir:Path,max_train_bytes=2_000_000,max_holdout_bytes=300_000,keymaster_training_path:Path|None=None,keymaster_manifest_path:Path|None=None,keymaster_config_path:Path|None=None):
    out_dir.mkdir(parents=True,exist_ok=True)
    train=[]; holdout=[]; records=[]; tb=hb=0
    registry_digest_hasher=hashlib.sha256(); source_file_count=0; source_total_bytes=0

    for path in iter_source_files(registry):
        rel=path.relative_to(registry).as_posix(); raw=path.read_bytes(); file_sha=sha256_bytes(raw)
        registry_digest_hasher.update(f'{rel}\0{file_sha}\0{len(raw)}\n'.encode())
        source_file_count += 1
        source_total_bytes += len(raw)
        text=scrub(raw.decode('utf-8',errors='replace'))
        envelope=f'\n<JANUS_REGISTRY_RECORD path={json.dumps(rel)} sha256={file_sha} authority="REGISTRY_SOURCE_REQUIRES_VERIFICATION">\n{text}\n</JANUS_REGISTRY_RECORD>\n'
        split='holdout' if int(file_sha[:8],16)%10==0 else 'train'; enc=envelope.encode('utf-8')
        if split=='holdout':
            remain=max_holdout_bytes-hb
            if remain<=0: continue
            enc=enc[:remain]; holdout.append(enc.decode('utf-8',errors='ignore')); hb+=len(enc)
        else:
            remain=max_train_bytes-tb
            if remain<=0: continue
            enc=enc[:remain]; train.append(enc.decode('utf-8',errors='ignore')); tb+=len(enc)
        records.append({'path':rel,'sha256':file_sha,'bytes':len(raw),'split':split})

    registry_train_text=''.join(train)
    (out_dir/'registry_train.txt').write_text(registry_train_text,encoding='utf-8')

    if (keymaster_training_path is None)!=(keymaster_manifest_path is None):
        raise RuntimeError('KEYMASTER_TRAINING_AND_MANIFEST_MUST_BE_PAIRED')
    if keymaster_training_path is None:
        keymaster_dir=out_dir.parent/'keymaster'
        collect_keymaster(keymaster_config_path or DEFAULT_KEYMASTER_CONFIG,keymaster_dir)
        keymaster_training_path=keymaster_dir/'training.txt'
        keymaster_manifest_path=keymaster_dir/'manifest.json'
    keymaster_text,keymaster_manifest=_load_keymaster(keymaster_training_path,keymaster_manifest_path)
    keymaster_bytes=len(keymaster_text.encode('utf-8'))
    train.append(keymaster_text)

    train_text=''.join(train); holdout_text=''.join(holdout)
    if len(train_text.encode())<50_000: raise RuntimeError('TRAIN_CORPUS_TOO_SMALL')
    if len(holdout_text.encode())<10_000: raise RuntimeError('HOLDOUT_CORPUS_TOO_SMALL')
    (out_dir/'train.txt').write_text(train_text,encoding='utf-8')
    (out_dir/'holdout.txt').write_text(holdout_text,encoding='utf-8')

    registry_source_digest=registry_digest_hasher.hexdigest()
    evaluation_contract=contract_identity()
    keymaster_digest=keymaster_manifest['contribution_sha256']
    learning_cycle_digest=_learning_cycle_digest(registry_source_digest,keymaster_digest,evaluation_contract['contract_sha256'])
    contributor_summary=[{
        'id':row['id'],'repository':row['repository'],'ref':row['ref'],'head_sha':row['head_sha'],
        'provenance':row['provenance'],'cohort':row['cohort'],'contributed_bytes':row['contributed_bytes'],
        'contribution_sha256':row['contribution_sha256'],'training_pack_sha256':row['training_pack_sha256'],
    } for row in keymaster_manifest['contributors']]

    manifest={
        'schema':'janus.model.registry_corpus.v4.keymaster8',
        'source_repository':'Hawkar-usls/janus-meta-registry',
        'source_commit':_git_head(registry),
        'source_digest':learning_cycle_digest,
        'source_digest_scope':'REGISTRY_MEMORY_PLUS_KEYMASTER_8_REPOS_PLUS_EVALUATION_CONTRACT_V3',
        'registry_source_digest':registry_source_digest,
        'registry_source_digest_scope':'ALL_ELIGIBLE_SOURCE_BEARING_FILES_BEFORE_CORPUS_BYTE_CAPS',
        'keymaster_contribution_sha256':keymaster_digest,
        'keymaster_training_pack_sha256':keymaster_manifest['training_pack_sha256'],
        'keymaster_contributor_count':REQUIRED_KEYMASTER_CONTRIBUTORS,
        'keymaster_contributors':contributor_summary,
        'keymaster_training_bytes':keymaster_bytes,
        'keymaster_training_only':True,
        'keymaster_adaptive_holdout_inclusion':False,
        'keymaster_frozen_anchor_inclusion':False,
        'keymaster_contribution_grants_authority':False,
        'keymaster_attribution_enabled':True,
        'evaluation_contract':evaluation_contract,
        'evaluation_contract_sha256':evaluation_contract['contract_sha256'],
        'anchor_is_training_source':False,
        'source_file_count':source_file_count,
        'source_total_bytes':source_total_bytes,
        'record_count':len(records),
        'selected_record_count':len(records),
        'registry_train_bytes':len(registry_train_text.encode()),
        'train_bytes':len(train_text.encode()),
        'holdout_bytes':len(holdout_text.encode()),
        'split':'REGISTRY_HASH_HOLDOUT_PLUS_KEYMASTER8_TRAIN_ONLY',
        'authority':'TRAINING_TEXT_IS_MEMORY_MATERIAL_NOT_AUTOMATIC_TRUTH',
        'eye_exclusions_enforced':True,
        'records':records
    }
    (out_dir/'corpus_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
    return manifest

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--registry',required=True); ap.add_argument('--out',required=True); ap.add_argument('--max-train-bytes',type=int,default=2_000_000); ap.add_argument('--max-holdout-bytes',type=int,default=300_000); ap.add_argument('--keymaster-training'); ap.add_argument('--keymaster-manifest'); ap.add_argument('--keymaster-config')
    a=ap.parse_args(); m=build_corpus(Path(a.registry),Path(a.out),a.max_train_bytes,a.max_holdout_bytes,Path(a.keymaster_training) if a.keymaster_training else None,Path(a.keymaster_manifest) if a.keymaster_manifest else None,Path(a.keymaster_config) if a.keymaster_config else None)
    keys=('source_commit','source_digest','registry_source_digest','keymaster_contribution_sha256','keymaster_contributor_count','keymaster_training_bytes','evaluation_contract_sha256','source_file_count','source_total_bytes','selected_record_count','registry_train_bytes','train_bytes','holdout_bytes')
    print(json.dumps({k:m[k] for k in keys},indent=2))

if __name__=='__main__': main()
