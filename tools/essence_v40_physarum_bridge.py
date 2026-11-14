#!/usr/bin/env python3
"""ESSENCE v4.0: source-pinned JANUS Physarum search + real CODEX sibling trials.

Adapts the user's original physarum_engine(20261112-211012).py:
Tero-Nakagaki flux/conductivity; Jeff Jones sensing/pheromone; historical
fitness map. Reimplements as audited bounded stdlib code; does not execute
the legacy source or evaluate any G3 external exam data.
Source: Library original SHA256 e0e7a7d6f62acbae18a68141c4708f9d0006679d5e58bb95f36bc74c398dcf13.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import random

from tools import essence_v37_codex_gpt as core
from tools import essence_v38_inheritance as prior
from tools import essence_v39_g3 as g3
from tools import essence_v36_juxtapose_exact as jux

SCHEMA = "janus.essence.physarum_neural_candidate_trial/4.0"
PHYSARUM_ORIGIN = {
    "name": "physarum_engine(20261112-211012).py",
    "sha256": "e0e7a7d6f62acbae18a68141c4708f9d0006679d5e58bb95f36bc74c398dcf13",
    "size_bytes": 13493,
    "library_file_id": "file_000000003fec82109c31e8170633ed6b",
    "adapted": ["Tero-Nakagaki conductance flow",
                "Jeff Jones sensory swarm and pheromone",
                "PhysarumOptimizer historical fitness proposal"],
    "original_code_executed": False,
}
LR = (0.0001, 0.00025, 0.0005, 0.00075, 0.001)
CLIP = (0.5, 1.0, 2.0)
GRID_SIZE = len(LR) * len(CLIP)
PROBE_INDICES = (5, 7, 9)
PROBE_STEPS = 2
SIBLING_STEPS = 8
BASELINE_INDEX = 7
RNG_SEED = 4001
G3_MANIFEST_SHA256 = "ed63cc6f143a71e00a3867d1b465be8a6c5f4aa061f20dbd37f85a007e8cd3e7"
G3_WEIGHTS_SHA256 = "7ae346fff869dc14eec9e32ffa0e00419d98faa2150f79a763e927e0fc2cd299"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def finite(number):
    return type(number) in (float, int) and math.isfinite(number)


def config(index):
    require(type(index) is int and 0 <= index < GRID_SIZE,
            "INVALID_PARAMETER_GRID_INDEX")
    return {"grid_index": index, "lr": LR[index % len(LR)],
            "clip": CLIP[index // len(LR)]}


def solve_linear(mat, b):
    """Small SPD Laplacian with grounded sink; no NumPy dependency."""
    n = len(b)
    require(n > 0 and n <= 15 and len(mat) == n, "INVALID_LAPLACIAN_SIZE")
    a = [list(map(float, mat[i])) + [float(b[i])] for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda j: abs(a[j][i]))
        require(abs(a[p][i]) > 1e-12, "PHYSARUM_DISCONNECTED_GRAPH")
        a[i], a[p] = a[p], a[i]
        div = a[i][i]
        for k in range(i, n + 1):
            a[i][k] /= div
        for j in range(i + 1, n):
            fact = a[j][i]
            for k in range(i, n + 1):
                a[j][k] -= fact * a[i][k]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = a[i][n] - sum(a[i][j] * x[j]
                             for j in range(i + 1, n))
    require(all(math.isfinite(k) for k in x), "NONFINITE_NETWORK_PRESSURES")
    return x


class TeroNetwork:
    """Discrete Poiseuille Q=D*(pi-pj)/L; dD/dt = |Q|-decay*D."""
    def __init__(self):
        self.n = GRID_SIZE
        self.d = [[0.0] * self.n for _ in range(self.n)]
        self.length = [[1.0] * self.n for _ in range(self.n)]
        for i in range(self.n):
            for j in range(i + 1, self.n):
                xi, yi = i % 5, i // 5
                xj, yj = j % 5, j // 5
                if abs(xi-xj) + abs(yi-yj) == 1:
                    self.d[i][j] = self.d[j][i] = 0.02
        self.last = [[0.0]*self.n for _ in range(self.n)]

    def step(self, source, sink, dt=0.08):
        require(source != sink and type(source) is int and
                type(sink) is int and 0 <= source < self.n and
                0 <= sink < self.n, "INVALID_PHYSARUM_TERMINALS")
        require(finite(dt) and 0 < dt <= 0.1, "INVALID_PHYSARUM_TIMESTEP")
        lap = [[0.0]*self.n for _ in range(self.n)]
        rhs = [0.0] * self.n
        rhs[source], rhs[sink] = 1.0, -1.0
        for i in range(self.n):
            for j in range(i+1, self.n):
                if self.d[i][j] == 0:
                    continue
                g = self.d[i][j] / self.length[i][j]
                lap[i][i] += g; lap[j][j] += g
                lap[i][j] -= g; lap[j][i] -= g
        free = [i for i in range(self.n) if i != sink]
        grounded = solve_linear([[lap[i][j] for j in free] for i in free],
                                [rhs[i] for i in free])
        pressure = [0.0] * self.n
        for i, v in zip(free, grounded):
            pressure[i] = v
        q = [[0.0]*self.n for _ in range(self.n)]
        for i in range(self.n):
            for j in range(i + 1, self.n):
                if self.d[i][j] == 0:
                    continue
                flow = self.d[i][j]*(pressure[i]-pressure[j])/self.length[i][j]
                q[i][j], q[j][i] = flow, -flow
                value = max(1e-6, self.d[i][j] + dt*(
                    abs(flow) - 0.1*self.d[i][j]))
                self.d[i][j] = self.d[j][i] = value
        require(all(abs(sum(q[i]) - rhs[i]) < 1e-7
                    for i in range(self.n)), "PHYSARUM_FLOW_NOT_CONSERVED")
        self.last = q
        return q


class JonesSwarm:
    """Bounded 5x3 particles, left/front/right sensing, evaporation/trails."""
    def __init__(self, count=28):
        require(type(count) is int and 1 <= count <= 64,
                "UNBOUNDED_PHYSARUM_PARTICLES")
        rng = random.Random(RNG_SEED)
        self.particles = [[rng.randrange(5), rng.randrange(3),
                           rng.randrange(8)] for _ in range(count)]
        self.trail = [[0.0]*5 for _ in range(3)]

    def step(self, attractant):
        require(len(attractant) == 3 and all(len(row) == 5
                for row in attractant), "INVALID_ATTRACTANT_GRID")
        self.trail = [[v*0.86 for v in row] for row in self.trail]
        directions = ((1,0),(1,1),(0,1),(-1,1),
                      (-1,0),(-1,-1),(0,-1),(1,-1))
        for p in self.particles:
            x, y, direction = p
            readings = []
            for turn in (-1,0,1):
                dx,dy=directions[(direction+turn)%8]
                nx=min(4,max(0,x+dx))
                ny=min(2,max(0,y+dy))
                readings.append((attractant[ny][nx]+
                                 0.075*self.trail[ny][nx],-abs(turn),-turn,
                                 (direction+turn)%8,nx,ny))
            _,_,_,nd,nx,ny=max(readings)
            p[:] = [nx,ny,nd]
            self.trail[ny][nx] += 0.04
        require(all(math.isfinite(v) and v>=0 for row in self.trail
                    for v in row), "NONFINITE_PHEROMONE")
        return self.trail


def choose_physarum(observed):
    """Only registered *development* probe losses are visible to Physarum."""
    require(isinstance(observed, dict) and set(observed) ==
            set(PROBE_INDICES), "INVALID_DEVELOPMENT_PROBE_SET")
    require(all(type(k) is int and type(v) is float and
                0 < v < 100 and math.isfinite(v)
                for k,v in observed.items()), "INVALID_PROBE_LOSS")
    worst = max(observed, key=lambda k:(observed[k],k))
    best = min(observed, key=lambda k:(observed[k],k))
    require(worst != best, "PROBE_NO_FITNESS_INFORMATION")
    net = TeroNetwork()
    for _ in range(12):
        net.step(worst,best)
    swarm = JonesSwarm()
    bestx, besty = best%5,best//5
    attractant = [
        [1.0/(1.0+abs(x-bestx)+abs(y-besty))
         for x in range(5)]
        for y in range(3)
    ]
    for _ in range(12):
        swarm.step(attractant)
    candidates=[]
    for i in range(GRID_SIZE):
        if i in observed:
            continue
        x,y=i%5,i//5
        total_flow=sum(abs(net.last[i][j]) for j in range(GRID_SIZE))
        conductance=sum(net.d[i])
        pheromone=swarm.trail[y][x]
        # Physarum geometry, not the hidden evaluation target.
        priority=total_flow+0.1*conductance+0.02*pheromone
        candidates.append((priority,-i,i))
    chosen=max(candidates)[2]
    return {"selected":config(chosen),
            "baseline":config(BASELINE_INDEX),
            "source":PHYSARUM_ORIGIN,
            "observed_development_losses":{str(k):observed[k] for k in sorted(observed)},
            "search_candidates_unobserved":len(candidates),
            "network_steps":12,
            "swarm_steps":12,
            "swarm_particles":len(swarm.particles),
            "algorithm":"TERO_CONDUCTIVITY_PLUS_JONES_SWARM",
            "source_code_executed":False,
            "future_external_exam_used":False}


def load_g3(directory, freeze_path, torch):
    freeze=prior.check_freeze(prior.read_json(freeze_path))
    require(freeze["receipt_sha256"] == g3.G2_FREEZE_SHA256,
            "ORIGINAL_G2_FREEZE_MISMATCH")
    model,manifest=prior.load_checkpoint(directory,torch,freeze)
    require(manifest["generation"] == "g3" and
            manifest["manifest_sha256"] == G3_MANIFEST_SHA256 and
            manifest["weights_sha256"] == G3_WEIGHTS_SHA256 and
            manifest["parent_manifest_sha256"] == g3.G2_MANIFEST_SHA256 and
            manifest["inherited_initial_weights_sha256"] == g3.G2_WEIGHT_SHA256,
            "UNVERIFIED_REAL_G3_ORIGIN")
    return freeze,model,manifest


def train_steps(torch, model, train, *, lr, clip, steps, seed):
    require(finite(lr) and 0 < lr <= 0.001 and
            finite(clip) and 0 < clip <= 2.0 and
            type(steps) is int and 1 <= steps <= SIBLING_STEPS,
            "UNSAFE_PHYSARUM_HYPERPARAMETERS")
    torch.manual_seed(seed)
    opt=torch.optim.AdamW(model.parameters(),lr=lr,weight_decay=0.01)
    rejected=0
    for _ in range(steps):
        model.train()
        starts=torch.randint(len(train)-core.BLOCK-1,(4,))
        x=torch.stack([train[i:i+core.BLOCK] for i in starts])
        y=torch.stack([train[i+1:i+core.BLOCK+1] for i in starts])
        opt.zero_grad(set_to_none=True)
        logits=model(x)
        loss=torch.nn.functional.cross_entropy(
            logits.reshape(-1,256),y.reshape(-1))
        if not bool(torch.isfinite(loss)):
            rejected+=1;continue
        loss.backward()
        grads=[p.grad for p in model.parameters() if p.grad is not None]
        if not grads or not all(bool(torch.isfinite(g).all()) for g in grads):
            rejected+=1; opt.zero_grad(set_to_none=True);continue
        norm=torch.nn.utils.clip_grad_norm_(model.parameters(),clip)
        if not math.isfinite(float(norm)):
            rejected+=1;opt.zero_grad(set_to_none=True);continue
        opt.step()
    require(steps>rejected,"NO_VALID_NEURAL_WEIGHT_UPDATE")
    return rejected


def run(root, g3_dir, g2_freeze, output_root):
    import torch
    torch.set_num_threads(1)
    freeze, g3model, g3manifest=load_g3(g3_dir,g2_freeze,torch)
    train, val=prior.train_bytes(root,freeze)
    starting,_=prior.weight_bytes(torch,g3model)
    require(hashlib.sha256(starting).hexdigest() == G3_WEIGHTS_SHA256,
            "G3_INITIAL_WEIGHTS_INVALID")
    # Independent probe restarts from the same sealed G3; no probe weights
    # migrate into sibling models, only development metrics inform proposals.
    observed={}
    for idx in PROBE_INDICES:
        cfg=config(idx)
        probe=core.new_model(torch)
        probe.load_state_dict(g3model.state_dict(),strict=True)
        train_steps(torch,probe,train,lr=cfg["lr"],clip=cfg["clip"],
                    steps=PROBE_STEPS,seed=RNG_SEED)
        observed[idx]=float(core.val_loss(torch,probe,val))
    decision=choose_physarum(observed)
    results={}
    target=Path(output_root)
    require(not target.exists() and not target.is_symlink(),
            "IMMUTABLE_PHYSARUM_OUTPUT_REQUIRED")
    for label,cfg in (("control",decision["baseline"]),
                      ("physarum",decision["selected"])):
        model=core.new_model(torch)
        model.load_state_dict(g3model.state_dict(),strict=True)
        rejected=train_steps(torch,model,train,lr=cfg["lr"],
                             clip=cfg["clip"],steps=SIBLING_STEPS,seed=RNG_SEED+1)
        development_loss=float(core.val_loss(torch,model,val))
        manifest=prior.save_checkpoint(
            target/label,torch,model,generation="g4_"+label,
            freeze=freeze,initial_weights_sha256=G3_WEIGHTS_SHA256,
            parent_manifest_sha256=G3_MANIFEST_SHA256,
            trained_steps=SIBLING_STEPS,rejected=rejected)
        results[label]={"config":cfg,
                        "development_validation_loss":development_loss,
                        "checkpoint_manifest_sha256":manifest["manifest_sha256"],
                        "weights_sha256":manifest["weights_sha256"],
                        "actual_neural_update":manifest["weights_sha256"] !=
                        G3_WEIGHTS_SHA256}
    proof=jux.field_search([[1,2],[-1,3],[2,-3]],80)
    require(proof["exact_verifier_has_veto"] is True and
            proof["production_authority"] is False and
            proof["coverage_ratio"] == 1.0,
            "JUXTAPOSE_VERIFIER_AUTHORITY_LOST")
    receipt={
        "schema":SCHEMA,
        "source":PHYSARUM_ORIGIN,
        "g3_parent_manifest_sha256":G3_MANIFEST_SHA256,
        "g3_parent_weight_sha256":G3_WEIGHTS_SHA256,
        "decision":decision,
        "sibling_results":results,
        "measured_train_steps_including_probes":
            len(PROBE_INDICES)*PROBE_STEPS+2*SIBLING_STEPS,
        "development_only":True,
        "g3_external_cohort_consumed":False,
        "future_blind_generalization_proven":False,
        "physarum_outperforms_baseline_proven":False,
        "juxtapose_exact_receipt_sha256":proof["receipt_sha256"],
        "external_independent_replicator":False,
        "automatic_promotion":False,
        "production_authority":False
    }
    return prior.sealed(receipt)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo-root",default=".")
    p.add_argument("--g3-dir",required=True)
    p.add_argument("--freeze",required=True)
    p.add_argument("--out-dir",required=True)
    a=p.parse_args()
    path=Path(a.out_dir)
    receipt=run(a.repo_root,a.g3_dir,a.freeze,path)
    prior.immutable_json(path/"physarum-development-trial.json",receipt)
    print(json.dumps({
        "status":"PHYSARUM_AND_CONTROL_RESEARCH_EXECUTED",
        "selected":receipt["decision"]["selected"],
        "control_development_loss":receipt["sibling_results"]["control"][
            "development_validation_loss"],
        "physarum_development_loss":receipt["sibling_results"]["physarum"][
            "development_validation_loss"],
        "total_neural_steps_including_probes":
            receipt["measured_train_steps_including_probes"],
        "receipt_sha256":receipt["receipt_sha256"],
        "production_authority":False
    },sort_keys=True))


if __name__=="__main__":
    main()
