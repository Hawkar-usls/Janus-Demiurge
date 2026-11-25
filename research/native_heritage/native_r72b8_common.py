from native_r72b7_common import *
def registry_rows(spec,root):
    rows=[]
    for src in spec["sources"]:
        raw=(Path(root)/src["path"]).read_bytes()
        req(git_blob(raw)==src["blob"],"SOURCE_PIN")
        doc=json.loads(raw)
        for entry in src["entries"]:
            value=doc
            for k in entry["path"]:value=value[int(k)] if isinstance(value,list) else value[k]
            req(isinstance(value,str),"TEXT")
            v=value[entry["start"]:entry["end"]];req(v==entry["exact_text"],"EXCERPT_PIN")
            rows.append({"source":src["path"],"path":entry["path"],"type":"string","value":json.dumps(v),"event":entry["event"],"outcome":entry["outcome"],"cohort":entry["cohort"]})
    req(len({r["value"] for r in rows})==len(rows),"DUPLICATE_TEXT")
    return rows
def labels(rows):
    return torch.tensor([r["event"] for r in rows]),torch.tensor([r["outcome"] for r in rows])
def balanced(rows):
    cats=sorted(set(r["cohort"] for r in rows));ix=torch.tensor([cats.index(r["cohort"]) for r in rows]);w=torch.bincount(ix).float().reciprocal()[ix];return w/w.sum()
def score(rows,e,o):
    ge,go=labels(rows);y=compose(ge,go);p=compose(e,o);known=ge>=0
    d={"n":int(known.sum()),"factor_exact":int(((e==ge)&(o==go)&known).sum()),"group":selective_stats(y[known],p[known]),"cohorts":{}}
    for c in sorted(set(r["cohort"] for r in rows)):
        ix=torch.tensor([r["cohort"]==c for r in rows])&known
        if ix.any():d["cohorts"][c]={"n":int(ix.sum()),"factor_exact":int(((e==ge)&(o==go)&ix).sum()),"group":selective_stats(y[ix],p[ix])}
    return d
