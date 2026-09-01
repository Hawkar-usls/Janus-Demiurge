from __future__ import annotations
import argparse,json
from pathlib import Path
import torch
from janus_model.model import ByteTokenizer
from janus_model.train_registry import load_checkpoint,sha256_file

ALLOWED_ORGAN_CONTEXT_STATUSES={"READ_ONLY_ORGAN_CONTEXT","READ_ONLY_MODULAR_ORGAN_CONTEXT"}

def _augment_prompt(prompt:str, organ_context_path:str|None)->str:
    if not organ_context_path:
        return prompt
    path=Path(organ_context_path)
    if not path.exists():
        raise SystemExit('JANUS_ORGAN_CONTEXT_MISSING')
    obj=json.loads(path.read_text(encoding='utf-8'))
    if obj.get('status') not in ALLOWED_ORGAN_CONTEXT_STATUSES:
        raise SystemExit('JANUS_ORGAN_CONTEXT_NOT_READ_ONLY')
    firewalls=obj.get('firewalls') or {}
    if firewalls.get('read_only') is not True or firewalls.get('terminal_authority')!='VERIFY':
        raise SystemExit('JANUS_ORGAN_CONTEXT_FIREWALL_FAIL')
    if obj.get('status')=='READ_ONLY_MODULAR_ORGAN_CONTEXT':
        if int(obj.get('module_count') or 0) < 2:
            raise SystemExit('JANUS_MODULAR_ORGAN_COUNT_INVALID')
        if firewalls.get('module_observation_grants_mutation') is not False:
            raise SystemExit('JANUS_MODULE_OBSERVATION_AUTHORITY_FAIL')
        if firewalls.get('raw_self_reflection_is_training_source') is not False:
            raise SystemExit('JANUS_SELF_MEMORY_TRAINING_FIREWALL_FAIL')
    suffix=obj.get('native_prompt_suffix')
    if not isinstance(suffix,str) or not suffix:
        raise SystemExit('JANUS_ORGAN_CONTEXT_SUFFIX_MISSING')
    return f"{prompt}\n{suffix}\nJANUS:"

def main():
    ap=argparse.ArgumentParser(prog='janus')
    sub=ap.add_subparsers(dest='cmd',required=True)
    run=sub.add_parser('run')
    run.add_argument('--checkpoint',default='janus_model/checkpoints/promoted.pt')
    run.add_argument('--prompt',required=True)
    run.add_argument('--organ-context')
    run.add_argument('--max-new-tokens',type=int,default=160)
    run.add_argument('--temperature',type=float,default=.75)
    ins=sub.add_parser('inspect')
    ins.add_argument('--checkpoint',default='janus_model/checkpoints/promoted.pt')
    a=ap.parse_args(); path=Path(a.checkpoint)
    if not path.exists(): raise SystemExit('JANUS_CHECKPOINT_MISSING')
    model,obj=load_checkpoint(path)
    if a.cmd=='inspect':
        print(json.dumps({'checkpoint_sha256':sha256_file(path),'config':obj['config'],'meta':obj.get('meta',{}),'external_llm':False},ensure_ascii=False,indent=2,sort_keys=True)); return
    prompt=_augment_prompt(a.prompt,a.organ_context)
    ids=ByteTokenizer.encode(prompt,bos=True)
    x=torch.tensor([ids],dtype=torch.long)
    torch.manual_seed(20260901)
    out=model.generate(x,max_new_tokens=a.max_new_tokens,temperature=a.temperature,top_k=40)[0].tolist()
    print(ByteTokenizer.decode(out))
if __name__=='__main__': main()
