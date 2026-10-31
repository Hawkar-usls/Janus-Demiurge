"""Real Git ref CAS arbitration through independent local Git clones."""
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from daddy_keymaster.git_cas_queue import (
    BRANCH, STATE_PATH, GitCAS, Conflict, empty, enqueue, claim,
    checkpoint, complete,
)
PIN = hashlib.sha256(b"demo-canonical-pin").hexdigest()
NOW = "2026-10-31T12:00:00Z"

def git(*args):
    return subprocess.run(["git", *map(str,args)],check=True,
                          capture_output=True,text=True,timeout=30).stdout.strip()

def competing(client, head, state, next_state):
    try:
        GitCAS(client).compare_and_swap(head,state,next_state)
        return "WON"
    except Conflict:
        return "CONFLICT"

class GitCASRemoteTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        remote = self.dir / "remote.git"
        seed = self.dir / "seed"
        git("init", "--bare", remote)
        git("init", seed)
        git("-C", seed, "config", "user.name", "JANUS Lab")
        git("-C", seed, "config", "user.email", "janus-lab@localhost")
        target = seed / STATE_PATH
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(empty(), sort_keys=True)+"\n")
        git("-C", seed, "add", STATE_PATH)
        git("-C", seed, "commit", "-m", "initial synthetic queue")
        git("-C", seed, "remote", "add", "origin",remote)
        git("-C", seed, "push", "origin", "HEAD:refs/heads/"+BRANCH)
        self.a = self._clone(remote,"a")
        self.b = self._clone(remote,"b")

    def _clone(self,remote,name):
        folder = self.dir/name
        git("clone","--branch",BRANCH,remote,folder)
        return GitCAS(folder)

    def test_stale_head_rejected_by_live_remote(self):
        ha,sa=self.a.read()
        hb,sb=self.b.read()
        self.assertEqual(ha,hb)
        self.a.compare_and_swap(ha,sa,enqueue(sa,"task-a","contract_test",PIN))
        with self.assertRaises(Conflict):
            self.b.compare_and_swap(hb,sb,enqueue(sb,"task-a","contract_test",PIN))
        new_head,new_state=self.b.read()
        self.assertNotEqual(new_head,hb)
        self.b.compare_and_swap(new_head,new_state,
            enqueue(new_state,"task-b","contract_test",PIN))
        _,final=self.a.read()
        self.assertEqual(set(final["tasks"]),{"task-a","task-b"})

    def test_two_independent_clones_race_for_one_lease(self):
        h,s=self.a.read()
        self.a.compare_and_swap(h,s,enqueue(s,"task-a","contract_test",PIN))
        ha,sa=self.a.read()
        hb,sb=self.b.read()
        next_a,token_a=claim(sa,"worker-a",["contract_test"],1,now=NOW)
        next_b,token_b=claim(sb,"worker-b",["contract_test"],1,now=NOW)
        self.assertEqual(token_a["task_id"],token_b["task_id"])
        with ProcessPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(competing,self.a.repo,ha,sa,next_a),
                  pool.submit(competing,self.b.repo,hb,sb,next_b)]
            outcomes=[j.result(timeout=45) for j in jobs]
        self.assertEqual(sorted(outcomes),["CONFLICT","WON"])
        _,live=self.a.read()
        self.assertEqual(live["epoch"],2)
        self.assertEqual(live["tasks"]["task-a"]["state"],"LEASED")

    def test_handoff_across_independent_clones(self):
        h,s=self.a.read()
        self.a.compare_and_swap(h,s,enqueue(s,"task-a","contract_test",PIN))
        h,s=self.a.read()
        leased,token=claim(s,"worker-a",["contract_test"],1,now=NOW)
        self.a.compare_and_swap(h,s,leased)
        h,s=self.b.read()
        self.b.compare_and_swap(h,s,checkpoint(s,token,PIN,now=NOW))
        h,s=self.a.read()
        self.a.compare_and_swap(h,s,complete(s,token,PIN,now=NOW))
        _,final=self.b.read()
        self.assertEqual(final["epoch"],4)
        self.assertEqual(final["tasks"]["task-a"]["state"],"COMPLETE")

if __name__ == "__main__":
    unittest.main()
