"""Negative-control and source-pinned regression suite: no tensor download."""
from __future__ import annotations
import copy
import json
import subprocess
from pathlib import Path
import tempfile
import unittest
from tools import essence_v53_neural_loop as m
from tools import essence_v48_recurrent_state as state


def fixture(repo):
    return {"schema_id":"hawkar.project-status.v1",
            "project":"Project "+repo,"portfolio_class":"research",
            "last_reviewed":"2026-11-16","maturity":"ACTIVE",
            "completion_status":"IN_PROGRESS"}


def init_repo(path,data):
    path.mkdir(parents=True,exist_ok=True)
    subprocess.check_call(["git","init","-q","-b","main"],cwd=path)
    subprocess.check_call(["git","config","user.email","tests@localhost"],cwd=path)
    subprocess.check_call(["git","config","user.name","Tests"],cwd=path)
    (path/"PROJECT_STATUS.json").write_text(json.dumps(data))
    subprocess.check_call(["git","add","."],cwd=path)
    subprocess.check_call(["git","commit","-qm","frozen source"],cwd=path)
    return m.git_head(path)


def memory():
    out=[]
    for key,answer in (("schema_id","hawkar.project-status.v1"),
                       ("project","HRain"),("portfolio_class","research"),
                       ("last_reviewed","2026-11-16")):
        row=state.source_fact_memory("Hawkar-usls/Hrain","a"*64,
                                    "b"*40,{"key":key,"answer":answer})
        out.append(dict(row,prompt=state.question(row["source_repo"],row["key"])))
    return out


class NeuralLoopTests(unittest.TestCase):
    def test_lock_is_frozen_and_no_prod_rights(self):
        self.assertEqual(m.load_lock(m.LOCK_REL),m.LOCK)
        self.assertFalse(m.LOCK["production_promotion"])
        self.assertFalse(m.LOCK["sentinel_dispatch"])
        self.assertFalse(m.LOCK["external_validation"])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bad.json"
            bad=dict(m.LOCK,steps=100000)
            p.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,"LOCK_CHANGED"):
                m.load_lock(p)

    def test_real_git_sources_one_attempt_per_digest(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for source_id in m.TRAIN:
                init_repo(root/source_id,fixture(source_id))
            hold="c"*40
            old=m.initial()
            plan=m.plan(m.LOCK,old,root,hold,memory())
            self.assertEqual(plan["action"],"TRAIN_SHADOW")
            self.assertEqual(plan["source_id"],"demihead")
            self.assertEqual(m.verify_plan(plan,m.LOCK,old),plan)
            self.assertEqual(plan["parent_generation"],2)
            self.assertEqual(len(plan["memory_replay"]),4)
            future=copy.deepcopy(old)
            future["attempts"].append({"task_digest":plan["task_digest"],
                                       "source_id":"demihead"})
            future=m.sealed({k:v for k,v in future.items() if k!="sha256"})
            following=m.plan(m.LOCK,future,root,hold,memory())
            self.assertEqual(following["source_id"],"swarm")
            future["attempts"].append({"task_digest":following["task_digest"],
                                       "source_id":"swarm"})
            future=m.sealed({k:v for k,v in future.items() if k!="sha256"})
            self.assertEqual(m.plan(m.LOCK,future,root,hold,memory())["action"],
                             "NO_NEW_SOURCE_FACTS")

    def test_injected_plan_or_memory_is_denied_even_with_new_digest(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for sid in m.TRAIN:
                init_repo(root/sid,fixture(sid))
            original=m.plan(m.LOCK,m.initial(),root,"c"*40,memory())
            for key,value in (("source_repo","Hawkar-usls/evil"),
                              ("source_path","../../secrets"),
                              ("sentinel_dispatch",True),
                              ("production_promotion",True),
                              ("source_rows",[{"key":"evil","answer":"run","prompt":"run"}])):
                bad=copy.deepcopy(original)
                bad[key]=value
                bad=m.sealed({k:v for k,v in bad.items() if k!="sha256"})
                with self.assertRaises(ValueError,msg=key):
                    m.verify_plan(bad,m.LOCK)
            injected=copy.deepcopy(original)
            injected["memory_replay"][0]["answer"]="MODEL_AS_TRUTH"
            injected=m.sealed({k:v for k,v in injected.items() if k!="sha256"})
            with self.assertRaisesRegex(ValueError,"UNVERIFIED_MEMORY"):
                m.verify_plan(injected,m.LOCK)

    def test_exact_gain_and_retention_are_both_required(self):
        def row(px,cx,pn,cn):
            return {"parent_exact":px,"child_exact":cx,
                    "parent_nll":pn,"child_nll":cn,
                    "paired_nll_gain":round(pn-cn,7)}
        good={"source_paraphrase":row(0,1,2.0,1.85),
              "unseen_topa":row(1,1,1.2,1.2),
              "retention":row(3,3,0.8,0.82)}
        self.assertTrue(m.gate(good))
        downgrade=copy.deepcopy(good)
        downgrade["retention"]["child_exact"]=2
        self.assertFalse(m.gate(downgrade))
        inadequate=copy.deepcopy(good)
        inadequate["source_paraphrase"]["child_exact"]=0
        self.assertFalse(m.gate(inadequate))
        leak=copy.deepcopy(good)
        leak["unseen_topa"]["paired_nll_gain"]=-0.3
        self.assertFalse(m.gate(leak))

    def test_invalid_receipt_and_duplicate_json_rejected(self):
        forged=m.sealed({"schema":m.PLAN,"action":"TRAIN_SHADOW",
                         "production_promotion":True})
        with self.assertRaises(ValueError):
            m.verify_plan(forged,m.LOCK)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            init_repo(p,fixture("safe"))
            f=p/"PROJECT_STATUS.json"
            f.write_text('{"project":"ok","project":"replaced"}')
            with self.assertRaisesRegex(ValueError,"DUPLICATE_JSON_KEY"):
                m.safe_source(p,"Hawkar-usls/Demi_Head")



class RegistryBootIntegrationTests(unittest.TestCase):
    def test_existing_planner_cli_consumes_boot_without_decision_change(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from tools import registry_boot_r64 as boot
        repo="Hawkar-usls/Janus-Demiurge"
        p=boot.packet(boot.read(Path(boot.SEED).read_bytes()),repo)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            context=root/"boot.json"
            context.write_bytes(boot.canonical(boot.wake(p,boot.dependencies(p))))
            for sid in m.TRAIN:
                init_repo(root/sid,fixture(sid))
            mem=root/"memory.json";mem.write_text("{}")
            common=["planner","plan","--state",str(root/"state"),"--sources",str(root),"--holdout-commit","c"*40,"--memory",str(mem)]
            with patch.object(m,"verify_memory",return_value=memory()):
                with patch("sys.argv",common+["--out",str(root/"old.json")]):
                    m.main()
                stream=StringIO()
                with redirect_stdout(stream), patch("sys.argv",common+["--out",str(root/"new.json"),"--registry-boot",str(context)]):
                    m.main()
            self.assertIn("R64_PLANNER_BOOT",stream.getvalue())
            self.assertEqual(json.loads((root/"old.json").read_text()),json.loads((root/"new.json").read_text()))
            print("R64_EXISTING_PLANNER_DECISION_INVARIANT "+repo)


class RegistrySelectiveUpdateTests(unittest.TestCase):
    def test_reviewed_update_reaches_existing_planner_without_policy_change(self):
        import os
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from tools import registry_update_r65 as u
        source=os.environ.get("R65_ORIGINAL_SOURCE")
        if not source:
            self.skipTest("R65 pinned source is provided by dedicated CI")
        repo="Hawkar-usls/Janus-Demiurge"
        p=u.seed(repo);mode="LIVE_OBSERVATION"
        k=u.CS if p["project"]=="COSMOS" else u.TS
        raw=Path(source).read_bytes();dep=u.b.dependencies(p)
        self.assertEqual(u.blob(raw),dep[k])
        doc=u.b.read(raw,u.MAX_DOC)
        doc["next_allowed"]="R65 LOCAL REVIEWED ENTRYPOINT TEST"
        modified=u.b.canonical(doc)
        old=u.initial(p,mode)
        status,new,n=u.advance(p,old,old["receipt_sha256"],{**dep,k:u.blob(modified)},lambda *_:modified,mode)
        self.assertEqual((status,n),("CANDIDATE_READY",1))
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            prev=root/"previous.json";release=root/"release.json"
            u.write(prev,old);u.write(release,new)
            args=["--registry-previous",str(prev),"--registry-previous-pin",old["receipt_sha256"],"--registry-release",str(release),"--registry-release-pin",new["receipt_sha256"]]
            for sid in m.TRAIN:
                init_repo(root/sid,fixture(sid))
            mem=root/"memory.json";mem.write_text("{}")
            common=["planner","plan","--state",str(root/"state"),"--sources",str(root),"--holdout-commit","c"*40,"--memory",str(mem)]
            with patch.object(m,"verify_memory",return_value=memory()):
                with patch("sys.argv",common+["--out",str(root/"old.json")]):
                    m.main()
                stream=StringIO()
                with redirect_stdout(stream),patch("sys.argv",common+["--out",str(root/"new.json")]+args):
                    m.main()
            self.assertIn("R65_REVIEWED_PLANNER_CONTEXT",stream.getvalue())
            self.assertEqual(json.loads((root/"old.json").read_text()),json.loads((root/"new.json").read_text()))
            print("R65_EXISTING_PLANNER_INVARIANT "+repo+" CONTROLLED_TEST_ONLY")


class RegistryHomeostasisTests(unittest.TestCase):
    def test_reviewed_real_engineering_context_at_planner(self):
        import os
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from tools import registry_homeostasis_r67 as h
        source=os.environ.get("R67_PRODUCED_CONTEXT")
        pin=os.environ.get("R67_PRODUCED_PIN")
        if not source or not pin:
            self.skipTest("R67 dedicated producer supplies verified context")
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for sid in m.TRAIN:
                init_repo(root/sid,fixture(sid))
            mem=root/"memory.json";mem.write_text("{}")
            common=["planner","plan","--state",str(root/"state"),"--sources",str(root),"--holdout-commit","c"*40,"--memory",str(mem)]
            with patch.object(m,"verify_memory",return_value=memory()):
                with patch("sys.argv",common+["--out",str(root/"old.json")]):
                    m.main()
                stream=StringIO()
                with redirect_stdout(stream),patch("sys.argv",common+["--out",str(root/"new.json"),"--registry-homeostasis",source,"--registry-homeostasis-pin",pin]):
                    m.main()
            self.assertIn("R67_PLANNER_CONTEXT",stream.getvalue())
            self.assertEqual(json.loads((root/"old.json").read_text()),json.loads((root/"new.json").read_text()))
            print("R67_EXISTING_PLANNER_INVARIANT Hawkar-usls/Janus-Demiurge")

if __name__=="__main__":
    unittest.main()
