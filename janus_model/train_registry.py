from __future__ import annotations
import argparse, hashlib, json, math, random
from pathlib import Path
from typing import Optional
import torch
from janus_model.model import ByteTokenizer,JanusModelConfig,JanusTinyTransformer,parameter_count

def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def seed_everything(seed): random.seed(seed); torch.manual_seed(seed)
def tokens(path): return torch.tensor(ByteTokenizer.encode(Path(path).read_text(encoding='utf-8',errors='replace'),bos=True,eos=True),dtype=torch.long)
def batch_from(stream,batch_size,context,g):
    if stream.numel()<=context+2: raise RuntimeError('TOKEN_STREAM_TOO_SMALL')
    starts=torch.randint(0,stream.numel()-context-1,(batch_size,),generator=g)
    x=torch.stack([stream[int(s):int(s)+context] for s in starts]); y=torch.stack([stream[int(s)+1:int(s)+context+1] for s in starts]); return x,y
@torch.no_grad()
def eval_loss(model,stream,batches,batch_size,seed):
    model.eval(); g=torch.Generator().manual_seed(seed); vals=[]
    for _ in range(batches):
        x,y=batch_from(stream,batch_size,model.config.context_length,g); _,loss=model(x,y); vals.append(float(loss.item()))
    return sum(vals)/len(vals)
def load_checkpoint(path):
    obj=torch.load(path,map_location='cpu',weights_only=False); cfg=JanusModelConfig.from_dict(obj['config']); model=JanusTinyTransformer(cfg); model.load_state_dict(obj['model_state']); return model,obj
def save_checkpoint(path,model,meta): Path(path).parent.mkdir(parents=True,exist_ok=True); torch.save({'config':model.config.to_dict(),'model_state':model.state_dict(),'meta':meta},path)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--train',required=True); ap.add_argument('--holdout',required=True); ap.add_argument('--corpus-manifest',required=True); ap.add_argument('--incumbent'); ap.add_argument('--out',required=True); ap.add_argument('--receipt',required=True); ap.add_argument('--steps',type=int,default=240); ap.add_argument('--batch-size',type=int,default=12); ap.add_argument('--lr',type=float,default=3e-4); ap.add_argument('--seed',type=int,default=1337); a=ap.parse_args()
    seed_everything(a.seed); train_stream=tokens(a.train); holdout_stream=tokens(a.holdout); corpus=json.loads(Path(a.corpus_manifest).read_text())
    incumbent_path=Path(a.incumbent) if a.incumbent else None; incumbent_loss=None; parent_sha=None
    if incumbent_path and incumbent_path.exists():
        incumbent_model,_=load_checkpoint(incumbent_path); incumbent_loss=eval_loss(incumbent_model,holdout_stream,16,8,a.seed+11); candidate=JanusTinyTransformer(incumbent_model.config); candidate.load_state_dict(incumbent_model.state_dict()); parent_sha=sha256_file(incumbent_path); mode='CONTINUE_PROMOTED_WEIGHTS'
    else: candidate=JanusTinyTransformer(JanusModelConfig()); mode='BOOTSTRAP_FROM_SCRATCH'
    candidate.train(); opt=torch.optim.AdamW(candidate.parameters(),lr=a.lr,weight_decay=.01); g=torch.Generator().manual_seed(a.seed+1); losses=[]
    for _ in range(a.steps):
        x,y=batch_from(train_stream,a.batch_size,candidate.config.context_length,g); _,loss=candidate(x,y); opt.zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(candidate.parameters(),1.0); opt.step(); losses.append(float(loss.item()))
    candidate_loss=eval_loss(candidate,holdout_stream,24,8,a.seed+11)
    if incumbent_loss is None: promote=math.isfinite(candidate_loss) and candidate_loss<8.0; reason='BOOTSTRAP_FINITE_LOSS_GATE'
    else: promote=math.isfinite(candidate_loss) and candidate_loss<=incumbent_loss*1.002; reason='CANDIDATE_NOT_WORSE_THAN_INCUMBENT_WITH_0_2_PERCENT_TOLERANCE'
    out=Path(a.out); checkpoint_sha=None
    if promote:
        meta={'source_repository':corpus['source_repository'],'source_commit':corpus['source_commit'],'source_digest':corpus['source_digest'],'parent_checkpoint_sha256':parent_sha,'training_mode':mode,'seed':a.seed,'steps':a.steps,'candidate_eval_loss':candidate_loss,'incumbent_eval_loss':incumbent_loss,'parameter_count':parameter_count(candidate)}; save_checkpoint(out,candidate,meta); checkpoint_sha=sha256_file(out)
    prompt='JANUS remembers the registry. '; context=torch.tensor([ByteTokenizer.encode(prompt,bos=True)],dtype=torch.long); torch.manual_seed(a.seed+99); sample_ids=candidate.generate(context,max_new_tokens=96,temperature=.75,top_k=32)[0].tolist(); sample=ByteTokenizer.decode(sample_ids)
    receipt={'schema':'janus.model.training_receipt.v1','status':'PROMOTED' if promote else 'REJECTED','promotion_reason':reason,'training_mode':mode,'source_commit':corpus['source_commit'],'source_digest':corpus['source_digest'],'parent_checkpoint_sha256':parent_sha,'candidate_checkpoint_sha256':checkpoint_sha,'incumbent_eval_loss':incumbent_loss,'candidate_eval_loss':candidate_loss,'final_train_loss':losses[-1],'mean_last_20_train_loss':sum(losses[-20:])/min(20,len(losses)),'parameter_count':parameter_count(candidate),'config':candidate.config.to_dict(),'steps':a.steps,'seed':a.seed,'sample':sample[-500:],'claim_ceiling':{'own_weights_trained':True,'external_llm_used_for_training_or_inference':False,'registry_text_is_automatic_truth':False,'general_intelligence_proven':False,'self_development':'BOUNDED_WEIGHT_UPDATE_WITH_HOLDOUT_PROMOTION_GATE'}}
    Path(a.receipt).parent.mkdir(parents=True,exist_ok=True); Path(a.receipt).write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps({k:receipt[k] for k in ('status','training_mode','incumbent_eval_loss','candidate_eval_loss','candidate_checkpoint_sha256')},indent=2)); raise SystemExit(0 if promote else 2)
if __name__=='__main__': main()
