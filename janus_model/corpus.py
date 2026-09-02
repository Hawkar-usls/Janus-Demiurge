from __future__ import annotations
import argparse, hashlib, json, re, subprocess
from pathlib import Path
from typing import Iterable

from janus_model.eval_contract import combine_learning_cycle_digest, contract_identity

SEMANTIC_EXTENSIONS={'.json','.md','.markdown','.txt','.py','.yml','.yaml','.toml','.ini','.cfg','.csv','.tsv','.html','.htm','.js','.ts','.tsx','.jsx','.css','.scss','.sh','.ps1','.xml','.jsonl','.ndjson'}
SECRETISH=re.compile(r'(?:^|[._-])(env|secret|token|credential|password|private[_-]?key)(?:$|[._-])',re.I)
TOKEN_PATTERNS=[re.compile(r'ghp_[A-Za-z0-9]{20,}'),re.compile(r'github_pat_[A-Za-z0-9_]{20,}'),re.compile(r'sk-[A-Za-z0-9_-]{20,}'),re.compile(r'AIza[A-Za-z0-9_-]{20,}')]

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

def build_corpus(registry:Path,out_dir:Path,max_train_bytes=2_000_000,max_holdout_bytes=300_000):
    out_dir.mkdir(parents=True,exist_ok=True)
    train=[]; holdout=[]; records=[]; tb=hb=0
    registry_digest_hasher=hashlib.sha256(); source_file_count=0; source_total_bytes=0

    for path in iter_source_files(registry):
        rel=path.relative_to(registry).as_posix(); raw=path.read_bytes(); file_sha=sha256_bytes(raw)

        # Full-memory identity is independent of the bounded neural text window.
        # Every eligible source-bearing file participates in the registry digest,
        # even when the train/holdout byte caps are already full.
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

    train_text=''.join(train); holdout_text=''.join(holdout)
    if len(train_text.encode())<50_000: raise RuntimeError('TRAIN_CORPUS_TOO_SMALL')
    if len(holdout_text.encode())<10_000: raise RuntimeError('HOLDOUT_CORPUS_TOO_SMALL')
    (out_dir/'train.txt').write_text(train_text,encoding='utf-8')
    (out_dir/'holdout.txt').write_text(holdout_text,encoding='utf-8')

    registry_source_digest=registry_digest_hasher.hexdigest()
    evaluation_contract=contract_identity()
    learning_cycle_digest=combine_learning_cycle_digest(
        registry_source_digest,
        evaluation_contract['contract_sha256'],
    )

    manifest={
        'schema':'janus.model.registry_corpus.v2',
        'source_repository':'Hawkar-usls/janus-meta-registry',
        'source_commit':_git_head(registry),
        # Backward-compatible wake key: it now binds both memory identity and
        # evaluation identity. The pure registry digest is preserved separately.
        'source_digest':learning_cycle_digest,
        'source_digest_scope':'REGISTRY_MEMORY_IDENTITY_PLUS_EVALUATION_CONTRACT_V1',
        'registry_source_digest':registry_source_digest,
        'registry_source_digest_scope':'ALL_ELIGIBLE_SOURCE_BEARING_FILES_BEFORE_CORPUS_BYTE_CAPS',
        'evaluation_contract':evaluation_contract,
        'evaluation_contract_sha256':evaluation_contract['contract_sha256'],
        'anchor_is_training_source':False,
        'source_file_count':source_file_count,
        'source_total_bytes':source_total_bytes,
        'record_count':len(records),
        'selected_record_count':len(records),
        'train_bytes':len(train_text.encode()),
        'holdout_bytes':len(holdout_text.encode()),
        'split':'FILE_SHA256_MOD_10_BUCKET_0_HOLDOUT',
        'authority':'TRAINING_TEXT_IS_MEMORY_MATERIAL_NOT_AUTOMATIC_TRUTH',
        'eye_exclusions_enforced':True,
        'records':records
    }
    (out_dir/'corpus_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
    return manifest

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--registry',required=True); ap.add_argument('--out',required=True); ap.add_argument('--max-train-bytes',type=int,default=2_000_000); ap.add_argument('--max-holdout-bytes',type=int,default=300_000)
    a=ap.parse_args(); m=build_corpus(Path(a.registry),Path(a.out),a.max_train_bytes,a.max_holdout_bytes)
    print(json.dumps({k:m[k] for k in ('source_commit','source_digest','registry_source_digest','evaluation_contract_sha256','source_file_count','source_total_bytes','selected_record_count','train_bytes','holdout_bytes')},indent=2))

if __name__=='__main__': main()
