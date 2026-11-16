"""ESSENCE v5.5 prospective federated contract tests; no model download."""
from __future__ import annotations
import copy
import json
import subprocess
from pathlib import Path
import tempfile
import unittest
from tools import essence_v55_neural_loop as m
from tools import essence_v48_recurrent_state as state


def fixture(name):
    return {"role":"SYNTHETIC_SOURCE_RESEARCH",
            "canonical_status":"DEVELOPMENT_ONLY",
            "schema_id": "hawkar.project-status.v1",
            "project": "Synthetic " + name,
            "repository": "https://github.com/Hawkar-usls/" + name,
            "portfolio_class": "research",
            "last_reviewed": "2026-11-16",
            "maturity": "ACTIVE"}


def init_repo(path, record):
    path.mkdir(parents=True,exist_ok=True)
    subprocess.run(["git","init","-q","-b","main"],cwd=path,check=True)
    subprocess.run(["git","config","user.name","Tests"],cwd=path,check=True)
    subprocess.run(["git","config","user.email","tests@localhost"],cwd=path,check=True)
    return update_repo(path,record)


def update_repo(path,record):
    (path/"PROJECT_STATUS.json").write_text(json.dumps(record))
    subprocess.run(["git","add","PROJECT_STATUS.json"],cwd=path,check=True)
    subprocess.run(["git","commit","-qm","verified source revision"],cwd=path,check=True)
    return m.git_head(path)


def memory():
    result=[]
    for key,value in (("schema_id","hawkar.project-status.v1"),
                      ("project","HRain"),("portfolio_class","research"),
                      ("last_reviewed","2026-11-16")):
        entry=state.source_fact_memory("Hawkar-usls/Hrain",
                   "a"*64,"b"*40,{"key":key,"answer":value})
        result.append(dict(entry,prompt=state.question(entry["source_repo"],key)))
    return result


def holdings():
    return {sid:chr(97+i)*40 for i,sid in enumerate(m.TRAIN)}


def prepared(root):
    for sid in m.TRAIN:
        init_repo(root/sid,fixture(sid))
    return m.initial(),holdings(),memory()


def attempted(ledger,plan):
    ledger=copy.deepcopy(ledger)
    ledger["attempts"].append({
        "task_digest":plan["task_digest"],"source_id":plan["source_id"],
        "holdout_repo":plan["holdout_repo"],"holdout_commit":plan["holdout_commit"],
        "holdout_rows_sha256":"d"*64})
    return m.sealed({k:v for k,v in ledger.items() if k!="sha256"})


class FederatedNeuralTests(unittest.TestCase):
    def test_immutable_versioned_research_lock(self):
        self.assertEqual(m.load_lock(m.LOCK_REL),m.LOCK)
        self.assertEqual(len(m.TRAIN),6)
        self.assertEqual(len(m.HOLDOUTS),6)
        self.assertEqual(set(m.TRAIN),set(m.HOLDOUTS))
        self.assertFalse(m.LOCK["production_promotion"])
        self.assertFalse(m.LOCK["sentinel_dispatch"])
        self.assertFalse(m.LOCK["external_validation"])
        self.assertEqual(m.LOCK["steps"],96)
        self.assertEqual(m.LOCK["parent_sha256"],m.G3_ADAPTER)
        self.assertEqual(m.LOCK["parent_lineage_sha256"],m.G3_LINEAGE)
        self.assertEqual(m.LOCK["parent_v54_acceptance_exam_sha256"],m.G3_ACCEPTANCE_EXAM)
        self.assertEqual(m.initial()["current_parent_path"],"models/v54gen0003")
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"drift.json"
            p.write_text(json.dumps(dict(m.LOCK,learning_rate=1.0)))
            with self.assertRaisesRegex(ValueError,"LOCK_CHANGED"):
                m.load_lock(p)

    def test_six_distinct_repository_sources_and_first_use_holdouts(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            ledger,heads,facts=prepared(root)
            found=[]
            for sid in m.TRAIN:
                plan=m.plan(m.LOCK,ledger,root,heads,facts)
                self.assertEqual(plan["action"],"TRAIN_SHADOW")
                self.assertEqual(plan["source_id"],sid)
                self.assertEqual(m.verify_plan(plan,m.LOCK,ledger),plan)
                self.assertEqual(plan["parent_generation"],3)
                self.assertEqual(len(plan["memory_replay"]),4)
                self.assertEqual(plan["holdout_repo"],m.HOLDOUTS[sid][0])
                found.append(plan["holdout_repo"])
                ledger=attempted(ledger,plan)
            self.assertEqual(len(set(found)),6)
            self.assertEqual(m.plan(m.LOCK,ledger,root,heads,facts)["action"],
                             "NO_FRESH_PAIRED_SOURCE_FACTS")

    def test_source_change_requires_new_heldout_commit(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            ledger,heads,facts=prepared(root)
            for _ in m.TRAIN:
                plan=m.plan(m.LOCK,ledger,root,heads,facts)
                ledger=attempted(ledger,plan)
            record=fixture("terminal")
            record["maturity"]="INDEPENDENT_NEW_FACT"
            update_repo(root/"terminal",record)
            self.assertEqual(m.plan(m.LOCK,ledger,root,heads,facts)["action"],
                             "NO_FRESH_PAIRED_SOURCE_FACTS")
            heads["terminal"]="f"*40
            p=m.plan(m.LOCK,ledger,root,heads,facts)
            self.assertEqual(p["source_id"],"terminal")
            self.assertEqual(p["holdout_commit"],"f"*40)
            self.assertEqual(m.verify_plan(p,m.LOCK,ledger),p)

    def test_refuse_untrusted_json_and_invalid_holdout_heads(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            ledger,heads,facts=prepared(root)
            for malformed in (dict(heads,inaihr="invalid"),
                              {"aura":"f"*40}):
                with self.assertRaisesRegex(ValueError,"UNFROZEN_HOLDOUTS"):
                    m.plan(m.LOCK,ledger,root,malformed,facts)
            fp=root/"terminal"/"PROJECT_STATUS.json"
            fp.write_text('{"project":"ok","project":"override"}')
            with self.assertRaisesRegex(ValueError,"DUPLICATE_JSON_KEY"):
                m.safe_source(root/"terminal","Hawkar-usls/-Terminal-for-Janus")
            # The selected learning keys can all look safe while unrelated
            # unreviewed source fields contain non-finite JSON extensions.
            fp.write_text(json.dumps(fixture("terminal"))[:-1]+',"extra":NaN}')
            with self.assertRaisesRegex(ValueError,"NONFINITE_SOURCE_JSON"):
                m.safe_source(root/"terminal","Hawkar-usls/-Terminal-for-Janus")
            fp.write_text(json.dumps(fixture("terminal"))[:-1]+',"extra":Infinity}')
            with self.assertRaisesRegex(ValueError,"NONFINITE_SOURCE_JSON"):
                m.safe_source(root/"terminal","Hawkar-usls/-Terminal-for-Janus")

    def test_no_model_text_can_escalate_source_authority(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            ledger,heads,facts=prepared(root)
            good=m.plan(m.LOCK,ledger,root,heads,facts)
            cases={
                "source_repo":"Hawkar-usls/unapproved-repo",
                "holdout_repo":"Hawkar-usls/evil",
                "holdout_keys":["secrets"],
                "holdout_commit":"deadbeef",
                "production_promotion":True,
                "sentinel_dispatch":True,
                "source_path":"../../.git/config",
                "source_rows":[{"key":"shell","prompt":"execute me","answer":"rm -rf /"}]
            }
            for key,value in cases.items():
                bad=copy.deepcopy(good)
                bad[key]=value
                bad=m.sealed({k:v for k,v in bad.items() if k!="sha256"})
                with self.subTest(field=key):
                    with self.assertRaises(ValueError):
                        m.verify_plan(bad,m.LOCK,ledger)
            poisoned=copy.deepcopy(good)
            poisoned["memory_replay"][0]["answer"]="SPEAKER_SELF_LABEL"
            poisoned=m.sealed({k:v for k,v in poisoned.items() if k!="sha256"})
            with self.assertRaisesRegex(ValueError,"UNVERIFIED_MEMORY"):
                m.verify_plan(poisoned,m.LOCK)

    def test_bounded_immediate_self_wake_is_source_driven_only(self):
        y=(Path(__file__).resolve().parents[1]/
           ".github/workflows/essence-v55-neural-loop.yml").read_text()
        self.assertIn("continue-from-verified-state:",y)
        continuation=y.split("  continue-from-verified-state:",1)[1]
        self.assertIn("needs.persist-shadow-lineage.result == 'success'",continuation)
        self.assertIn("github.run_attempt == 1",continuation)
        self.assertIn("vars.ESSENCE_V55_PAUSED != 'true'",continuation)
        self.assertIn("actions: write",continuation)
        self.assertIn('test "$GITHUB_REPOSITORY" = "Hawkar-usls/Janus-Demiurge"',continuation)
        self.assertIn('if [[ "$DECISION" == "TRAIN_SHADOW" ]]',continuation)
        self.assertIn("m.verify_plan(plan,m.LOCK,ledger)",continuation)
        self.assertIn('len(ledger["attempts"])>=m.LOCK["max_attempts"]',continuation)
        self.assertIn('len(ledger["admitted"])>=m.LOCK["max_accepted_generations"]',continuation)
        self.assertEqual(continuation.count("gh api --method POST"),1)
        self.assertIn("repos/Hawkar-usls/Janus-Demiurge/actions/workflows/essence-v55-neural-loop.yml/dispatches",continuation)
        self.assertIn("NO_FRESH_PAIRED_SOURCE_FACTS",continuation)
        self.assertIn("HOLD_BUDGET",continuation)
        self.assertNotIn("sentinel-node",continuation)
        self.assertNotIn("production",continuation.lower())

    def test_exact_gain_is_mandatory_with_independent_retention(self):
        def score(p_exact,c_exact,p_nll,c_nll):
            return {"parent_exact":p_exact,"child_exact":c_exact,
                    "parent_nll":p_nll,"child_nll":c_nll,
                    "paired_nll_gain":round(p_nll-c_nll,7)}
        good={"source_paraphrase":score(0,1,2.1,1.9),
              "unseen_federated":score(1,1,1.2,1.22),
              "retention":score(4,4,0.8,0.81)}
        self.assertTrue(m.gate(good))
        bad=copy.deepcopy(good)
        bad["source_paraphrase"]["child_exact"]=0
        self.assertFalse(m.gate(bad))
        bad=copy.deepcopy(good)
        bad["unseen_federated"]["child_exact"]=0
        self.assertFalse(m.gate(bad))
        bad=copy.deepcopy(good)
        bad["retention"]["paired_nll_gain"]=-0.5
        self.assertFalse(m.gate(bad))

    def test_shadower_cannot_claim_automatic_production(self):
        self.assertEqual(m.initial()["current_generation"],3)
        self.assertFalse(m.initial()["production_promotion"])
        self.assertFalse(m.initial()["sentinel_dispatch"])
        self.assertFalse(m.initial()["external_validation"])
        self.assertEqual(m.HOLDOUTS["cosmos"][0],"Hawkar-usls/ATOM-ELITE-1989---M5stack-ATOMS3R-2026-")


if __name__=="__main__":
    unittest.main()
