from __future__ import annotations
import argparse,json
from pathlib import Path
import torch
from janus_model.model import ByteTokenizer
from janus_model.train_registry import load_checkpoint,sha256_file
def main():
    ap=argparse.ArgumentParser(prog='janus'); sub=ap.add_subparsers(dest='cmd',required=True); run=sub.add_parser('run'); run.add_argument('--checkpoint',default='janus_model/checkpoints/promoted.pt'); run.add_argument('--prompt',required=True); run.add_argument('--max-new-tokens',type=int,default=160); run.add_argument('--temperature',type=float,default=.75); ins=sub.add_parser('inspect'); ins.add_argument('--checkpoint',default='janus_model/checkpoints/promoted.pt'); a=ap.parse_args(); path=Path(a.checkpoint)
    if not path.exists(): raise SystemExit('JANUS_CHECKPOINT_MISSING')
    model,obj=load_checkpoint(path)
    if a.cmd=='inspect': print(json.dumps({'checkpoint_sha256':sha256_file(path),'config':obj['config'],'meta':obj.get('meta',{}),'external_llm':False},ensure_ascii=False,indent=2,sort_keys=True)); return
    ids=ByteTokenizer.encode(a.prompt,bos=True); x=torch.tensor([ids],dtype=torch.long); torch.manual_seed(20260901); out=model.generate(x,max_new_tokens=a.max_new_tokens,temperature=a.temperature,top_k=40)[0].tolist(); print(ByteTokenizer.decode(out))
if __name__=='__main__': main()
