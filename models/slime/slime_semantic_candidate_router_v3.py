# -*- coding: utf-8 -*-
"""JANUS Slime semantic candidate router v3: projected relation-forest cap.

Candidate generator only.  v3 keeps every v1/v2 candidate and adds one new
assignment-independent candidate driven by a proof-carrying polynomial upper
bound on PS-signature diversity.

For distinct nonempty projected clauses A,B with satisfaction bits s_A,s_B:
  A subseteq B          => pair (1,0) impossible
  B subseteq A          => pair (0,1) impossible
  A union B tautology   => pair (0,0) impossible
  complementary units   => pair (1,1) impossible

A deterministic strongest-first acyclic subset of these sound relations is
selected.  The number of satisfying bit patterns of that relation forest is
counted exactly by tree DP.  Since unselected constraints are ignored, this is
an upper bound on actual projected signature count.  We also intersect it with
the assignment bound 2^r.

No SAT solver, truth table, exact PS-width scorer, branch assignment, or
post-probe feedback is used by this module.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys


def _load_v2():
    path=Path(__file__).with_name("slime_semantic_candidate_router_v2.py")
    name="janus_slime_semantic_candidate_router_v2_embedded"
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen Slime v2")
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module
    try: spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name,None); raise
    return module

v2=_load_v2(); v1=v2.v1


def _distinct_projected(cnf, clause_indices, visible_variables):
    values=set()
    for index in sorted(clause_indices):
        projected=frozenset(lit for lit in cnf[index] if abs(lit) in visible_variables)
        if projected: values.add(projected)
    return sorted(values,key=lambda c:(len(c),tuple(sorted(c))))


def _allowed_pairs(a,b):
    allowed={(0,0),(0,1),(1,0),(1,1)}; reasons=[]
    if a<=b:
        allowed.discard((1,0)); reasons.append("A_SUBSET_B_FORBIDS_10")
    if b<=a:
        allowed.discard((0,1)); reasons.append("B_SUBSET_A_FORBIDS_01")
    union=set(a)|set(b)
    if any(-lit in union for lit in union):
        allowed.discard((0,0)); reasons.append("A_OR_B_TAUTOLOGY_FORBIDS_00")
    if len(a)==1 and len(b)==1 and next(iter(a))==-next(iter(b)):
        allowed.discard((1,1)); reasons.append("COMPLEMENTARY_UNITS_FORBID_11")
    return tuple(sorted(allowed)),reasons


class _DSU:
    def __init__(self,n): self.p=list(range(n))
    def find(self,x):
        while self.p[x]!=x:
            self.p[x]=self.p[self.p[x]]; x=self.p[x]
        return x
    def union(self,a,b):
        a=self.find(a); b=self.find(b)
        if a==b:return False
        if a>b:a,b=b,a
        self.p[b]=a; return True


def _relation_forest(clauses):
    edges=[]
    for i in range(len(clauses)):
        for j in range(i+1,len(clauses)):
            allowed,reasons=_allowed_pairs(clauses[i],clauses[j])
            if len(allowed)<4: edges.append((len(allowed),i,j,allowed,reasons))
    edges.sort(key=lambda r:(r[0],r[1],r[2])); dsu=_DSU(len(clauses)); selected=[]
    for strength,i,j,allowed,reasons in edges:
        if dsu.union(i,j):
            selected.append((i,j,allowed,tuple(reasons)))
    return selected


def _count_forest_patterns(n,edges):
    if n==0:return 1
    adj=[[] for _ in range(n)]
    for i,j,allowed,_ in edges:
        aset=set(allowed); adj[i].append((j,aset,False)); adj[j].append((i,aset,True))
    seen=set(); total=1
    for root in range(n):
        if root in seen:continue
        parent={root:-1}; pedge={}; order=[root]; seen.add(root)
        for node in order:
            for nxt,allowed,rev in adj[node]:
                if nxt in parent:continue
                parent[nxt]=node; pedge[nxt]=(allowed,rev); order.append(nxt); seen.add(nxt)
        dp={}
        for node in reversed(order):
            counts=[1,1]
            for child,par in parent.items():
                if par!=node:continue
                allowed,rev=pedge[child]; out=[]
                for pv in (0,1):
                    subtotal=0
                    for cv in (0,1):
                        pair=(cv,pv) if rev else (pv,cv)
                        if pair in allowed: subtotal+=dp[child][cv]
                    out.append(counts[pv]*subtotal)
                counts=out
            dp[node]=counts
        total*=dp[root][0]+dp[root][1]
    return total


def _side_cap(cnf, clause_indices, visible_variables):
    clauses=_distinct_projected(cnf,clause_indices,visible_variables)
    forest=_relation_forest(clauses)
    relation_bound=_count_forest_patterns(len(clauses),forest)
    assignment_bound=1<<len(visible_variables)
    cap=min(assignment_bound,relation_bound)
    return {
        "distinct_projected_clause_count":len(clauses),
        "relation_edge_count":len(forest),
        "relation_pattern_bound":relation_bound,
        "assignment_bound":assignment_bound,
        "certified_signature_cap":cap,
    }


def relation_forest_signature_cap(cnf,selected_leaves):
    all_clause_indices=set(range(len(cnf))); all_vars=set(v1.variables_of(cnf))
    selected_vars={int(x.split(':',1)[1]) for x in selected_leaves if x.startswith('v:')}
    selected_clauses={int(x.split(':',1)[1]) for x in selected_leaves if x.startswith('c:')}
    right_vars=all_vars-selected_vars
    left=_side_cap(cnf,all_clause_indices-selected_clauses,selected_vars)
    right=_side_cap(cnf,selected_clauses,right_vars)
    return {"left":left,"right":right,"combined_cap":max(left["certified_signature_cap"],right["certified_signature_cap"])}


class SlimeRelationForestCandidateRouter:
    def __init__(self,trace_ema:float=0.85):
        self.base=v2.SlimeSignatureCapCandidateRouter(trace_ema=trace_ema)
        self.trace_ema=float(trace_ema)

    def _relation_order(self,cnf,clause_to_group,profiles):
        adjacency=v1.incidence(cnf); remaining=set(adjacency); selected=set(); order=[]; trace={x:0.5 for x in adjacency}; ops=0
        unique_profiles=sorted(set(profiles.values())); profile_ids={p:i for i,p in enumerate(unique_profiles)}
        leaf_group={f"v:{var}":f"VP:{profile_ids[p]}" for var,p in profiles.items()}
        leaf_group.update({f"c:{idx}":f"CG:{gid}" for idx,gid in clause_to_group.items()})
        literal_volume=sum(len(c) for c in cnf)
        while remaining:
            local=[]
            for leaf in sorted(remaining):
                trial=selected|{leaf}
                rel=relation_forest_signature_cap(cnf,trial)
                old=v2.signature_cap_exponent(cnf,trial)
                frontier=v1.SlimeSemanticCandidateRouter._semantic_frontier(adjacency,trial,leaf_group)
                crossing=v1.SlimeSemanticCandidateRouter._crossing(adjacency,trial)
                # Conservative polynomial scan/accounting proxy for pair relations,
                # projected clauses, forest construction, and graph metrics.
                q=len(cnf); ops += 8*(q*q + literal_volume + 1 + sum(len(adjacency[n]) for n in trial))
                error=(4.0*math.log2(max(1,rel["combined_cap"])) + 1.0*old["cap_log2"] + 0.5*frontier + 0.25*crossing)/max(1.0,float(len(adjacency)))
                bond=math.exp(-min(20.0,error)); trace[leaf]=self.trace_ema*trace[leaf]+(1-self.trace_ema)*bond
                local.append((leaf,rel["combined_cap"],old["cap_log2"],frontier,crossing,trace[leaf]))
            chosen=min(local,key=lambda r:(r[1],r[2],r[3],r[4],-r[5],r[0]))[0]
            order.append(chosen); selected.add(chosen); remaining.remove(chosen)
        return order,ops

    def generate_manifest(self,clauses):
        manifest=self.base.generate_manifest(clauses)
        cnf=v1.canonical_cnf(clauses); groups,clause_to_group=v1.clause_group_map(cnf); profiles=v1.variable_profiles(cnf,clause_to_group)
        order,ops=self._relation_order(cnf,clause_to_group,profiles)
        expected=sorted(v1.all_leaves(cnf))
        if sorted(order)!=expected or len(order)!=len(expected): raise AssertionError("relation-forest candidate is not a leaf permutation")
        manifest.candidates.append(v1.Candidate("SLIME_RELATION_FOREST_PRESSURE",order,"certified projected-clause relation-forest signature cap, then v2/v1 pressure",ops))
        manifest.feature_certificate["feature_classes"].append("PROJECTED_CLAUSE_RELATION_FOREST_CAP")
        manifest.feature_certificate["relation_forest_theorem"]={
            "subset_implication":True,
            "tautological_pair_exhaustiveness":True,
            "complementary_unit_exclusion":True,
            "forest_count_exact_by_tree_dp":True,
            "unselected_sound_relations_ignored_only_loosen_bound":True,
            "assignment_independent":True,
            "truth_table_free":True,
            "authority":"UPPER_BOUND_ONLY_NOT_EXACT_PSWIDTH",
        }
        manifest.total_generation_ops+=ops; manifest.artifact_id="JANUS-SLIME-SEMANTIC-CANDIDATE-MANIFEST-V3"; manifest.exact_ps_width_computed_inside_generator=False; manifest.sat_oracle_used=False
        return manifest.seal()

SlimeSemanticCandidateRouterV3=SlimeRelationForestCandidateRouter


def selftest():
    formula=((1,2,-3),(2,3,4),(-3,-4,-5),(5,3,1),(-5,-4,1),(-5,3,1),(2,-5,4))
    router=SlimeRelationForestCandidateRouter(); m=router.generate_manifest(formula)
    assert m.artifact_id=="JANUS-SLIME-SEMANTIC-CANDIDATE-MANIFEST-V3" and len(m.candidates)==6
    assert m.candidates[-1].name=="SLIME_RELATION_FOREST_PRESSURE"
    assert not m.exact_ps_width_computed_inside_generator and not m.sat_oracle_used
    cap=relation_forest_signature_cap(v1.canonical_cnf(formula),{"c:0","v:2","c:1","v:4"})
    assert cap["combined_cap"]==3
    return {"status":"PASS","candidate_count":6,"new_candidate":m.candidates[-1].name,"diagnostic_cap":cap["combined_cap"],"manifest_sha256":m.manifest_sha256,"generator_truth_table_free":True,"generator_sat_oracle_free":True}

if __name__=="__main__":
    import json; print(json.dumps(selftest(),indent=2,sort_keys=True))
