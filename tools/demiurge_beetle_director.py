#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, json, pathlib, re
from typing import Any


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')


def load(path: str) -> Any:
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))


def load_optional(path: str | None) -> dict[str, Any]:
    if not path or not pathlib.Path(path).exists(): return {}
    obj=load(path)
    return obj if isinstance(obj,dict) else {}


def clamp(x: float, lo: float=0, hi: float=100) -> float:
    return max(lo, min(hi, x))


def extract_model(path: str | None) -> dict[str, Any]:
    if not path or not pathlib.Path(path).exists():
        return {}
    text = pathlib.Path(path).read_text(encoding='utf-8', errors='replace')
    for candidate in [text] + re.findall(r'\{.*\}', text, flags=re.S):
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                if isinstance(obj.get('result'), str):
                    try:
                        inner=json.loads(obj['result'])
                        if isinstance(inner, dict): return inner
                    except Exception: pass
                return obj
        except Exception:
            pass
    return {}


def clean_focus(rows: Any, allowed_dirs: set[str], source: str, max_items: int=5) -> list[dict[str,Any]]:
    out=[]
    if not isinstance(rows,list): return out
    for row in rows:
        if not isinstance(row,dict): continue
        did=str(row.get('direction_id',''))
        if did not in allowed_dirs: continue
        delta=clamp(float(row.get('priority_delta',0)),-25,25)
        out.append({'direction_id':did,'priority_delta':delta,'reason':str(row.get('reason',''))[:240],'source':source})
        if len(out)>=max_items: break
    return out


def clean_adhoc(rows: Any, allow_repos: set[str], source: str, max_items: int=2) -> list[dict[str,Any]]:
    out=[]
    if not isinstance(rows,list): return out
    for row in rows:
        if not isinstance(row,dict): continue
        rid=re.sub(r'[^a-z0-9_-]+','-',str(row.get('id','')).lower()).strip('-')[:48]
        kws=[str(x)[:120] for x in row.get('keywords',[]) if str(x).strip()][:12]
        targets=[r for r in row.get('target_repositories',[]) if r in allow_repos][:6]
        if not rid or not kws or not targets: continue
        out.append({'id':'demiurge_'+rid,'title':str(row.get('title',rid))[:160], 'keywords':kws, 'target_repositories':targets, 'priority':clamp(float(row.get('priority',65))), 'source':source})
        if len(out)>=max_items: break
    return out


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--directives', required=True)
    ap.add_argument('--status', required=True)
    ap.add_argument('--desires')
    ap.add_argument('--model-output')
    ap.add_argument('--out', required=True)
    args=ap.parse_args()
    d=load(args.directives); status=load(args.status); desires=load_optional(args.desires); model=extract_model(args.model_output)
    base={str(k): float(v) for k,v in d.get('base_priorities',{}).items()}
    boosts={k:0.0 for k in base}; reasons={k:[] for k in base}
    asc=status.get('agent_ascent_status',{}); amap=d.get('agent_to_direction_boosts',{})
    for agent, state in asc.items():
        if state == 'ASCENDED_NEW_EVIDENCE':
            for direction in amap.get(agent,[]):
                if direction in boosts:
                    boosts[direction]+=12.0; reasons[direction].append(f'{agent}:ASCENDED_NEW_EVIDENCE')
    allowed_dirs=set(base); allow_repos=set(d.get('allowed_target_repositories',[]))

    desire_focus=clean_focus(desires.get('focus',[]),allowed_dirs,'JANUS_DESIRES')
    for row in desire_focus:
        boosts[row['direction_id']]+=row['priority_delta']; reasons[row['direction_id']].append('JANUS_DESIRE:'+row['reason'])
    desire_holds=[]
    for row in desires.get('hold',[]) if isinstance(desires.get('hold',[]),list) else []:
        if not isinstance(row,dict): continue
        did=str(row.get('direction_id',''))
        if did not in allowed_dirs: continue
        delta=-min(25.0,abs(float(row.get('priority_delta',25))))
        boosts[did]+=delta; reason=str(row.get('reason',''))[:240]
        reasons[did].append('JANUS_HOLD:'+reason); desire_holds.append({'direction_id':did,'priority_delta':delta,'reason':reason})
        if len(desire_holds)>=5: break
    desire_adhoc=clean_adhoc(desires.get('ad_hoc',[]),allow_repos,'JANUS_DESIRES')

    model_focus=clean_focus(model.get('focus',[]),allowed_dirs,'JANUS_MODEL')
    for row in model_focus:
        boosts[row['direction_id']]+=row['priority_delta']; reasons[row['direction_id']].append('JANUS_MODEL:'+row['reason'])
    model_adhoc=clean_adhoc(model.get('ad_hoc',[]),allow_repos,'JANUS_MODEL')

    # Desires are first-class; model additions fill only remaining bounded ad-hoc slots.
    adhoc=(desire_adhoc+model_adhoc)[:2]
    priorities={k:round(clamp(base[k]+boosts[k]),3) for k in base}
    out={
      'schema':'janus.demiurge.beetle.live_priorities.v1',
      'generated_at':now(),
      'source_scout_run_id':status.get('run_id'),
      'source_scout_updated_at':status.get('updated_at_utc'),
      'desire_control_plane_loaded':bool(desires),
      'desire_control_used':bool(desire_focus or desire_adhoc or desire_holds),
      'desire_status':desires.get('status'),
      'model_synthesis_used':bool(model_focus or model_adhoc),
      'direction_priorities':priorities,
      'reasons':{k:v for k,v in reasons.items() if v},
      'desire_focus_accepted':desire_focus,
      'desire_holds_accepted':desire_holds,
      'model_focus_accepted':model_focus,
      'ad_hoc_directions':adhoc,
      'claim_ceiling':'SEARCH_STEERING_ONLY__ZERO_EVIDENCE_AUTHORITY',
      'firewall':['PRIORITY_NE_TRUTH','JANUS_DESIRE_NE_EVIDENCE','MODEL_DESIRE_NE_EVIDENCE','AD_HOC_QUERY_NE_GRAZER_APPROVAL','COUNTEREVIDENCE_AND_CONTROL_MAY_NOT_BE_DISABLED_GLOBALLY']
    }
    p=pathlib.Path(args.out); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False))
    return 0

if __name__=='__main__': raise SystemExit(main())
