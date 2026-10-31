"""Independent Git remote tests for immutable queue rollover and restoration."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile
import unittest

from daddy_keymaster.git_cas_queue import (
    BRANCH, STATE_PATH, GitCAS, empty, enqueue, claim,
    checkpoint, complete,
)
from daddy_keymaster.queue_rotation import (
    HEAD_PATH, ARCHIVE_DIR, MARKER_DIR, _plan, _read_at,
    _archive_context, rotate_once, rotate_if_ready, status,
)

A = hashlib.sha256(b"commit-a").hexdigest()
B = hashlib.sha256(b"commit-b").hexdigest()
NOW = "2026-10-31T12:00:00Z"
LATER = "2026-10-31T12:06:00Z"


def git(*args):
    return subprocess.run(["git", *map(str,args)], check=True,
                          text=True, capture_output=True, timeout=30).stdout.strip()


def try_rotate(repo, source):
    try:
        return rotate_once(GitCAS(repo, branch=BRANCH), source)["status"]
    except Exception as exc:
        # Expose error classification instead of suppressing an unknown failure.
        return "ERROR:" + type(exc).__name__ + ":" + str(exc)[:100]


class RotationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        bare = self.folder / "bare.git"
        seed = self.folder / "seed"
        git("init", "--bare", bare)
        git("init", seed)
        git("-C", seed, "config", "user.name", "JANUS")
        git("-C", seed, "config", "user.email", "janus@localhost")
        p = seed / STATE_PATH
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(empty(), sort_keys=True)+"\n")
        git("-C", seed, "add", STATE_PATH)
        git("-C", seed, "commit", "-m", "initial queue")
        git("-C", seed, "remote", "add", "origin", bare)
        git("-C", seed, "push", "origin", "HEAD:refs/heads/"+BRANCH)
        self.a = self.clone(bare, "a")
        self.b = self.clone(bare, "b")

    def clone(self, bare, name):
        path = self.folder / name
        git("clone", "--branch", BRANCH, bare, path)
        return GitCAS(path, branch=BRANCH)

    def update(self, store, f):
        head, state = store.read()
        new = f(state)
        store.compare_and_swap(head, state, new)
        return new

    def enqueue_one(self):
        self.update(self.a, lambda s: enqueue(s, "test-a", "contract_test", A))

    def complete_one(self):
        self.enqueue_one()
        token = None
        head, state = self.a.read()
        state, token = claim(state, "worker-a", ["contract_test"], 1, now=NOW)
        self.a.compare_and_swap(head, self.a.read()[1], state)
        self.update(self.b, lambda s: checkpoint(s, token, A, now=NOW))
        self.update(self.a, lambda s: complete(s, token, B, now=NOW))

    def test_atomic_archive_and_new_queue_with_marker(self):
        self.complete_one()
        old_head, previous = self.b.read()
        self.assertEqual(previous["epoch"], 4)
        result = rotate_once(self.a, B)
        self.assertEqual(result["status"], "ARCHIVED_ATOMIC_AND_RESET")
        self.assertEqual(result["segment"], 1)
        head, current = self.b.read()
        self.assertEqual(current, empty())
        self.assertNotEqual(head, old_head)
        serial, digest, _ = _archive_context(self.b, head)
        self.assertEqual(serial, 1)
        archive = _read_at(self.b.repo, head, ARCHIVE_DIR+"/00000001.json")
        self.assertEqual(archive["queue"], previous)
        self.assertEqual(archive["receipt_sha256"], digest)
        self.assertEqual(status(self.b, A)["current_already_archived"], True)
        self.assertEqual(status(self.b, B)["current_already_archived"], False)
        self.assertEqual(rotate_once(self.b, B)["status"], "EMPTY")
        self.update(self.b, lambda s: enqueue(s, "test-b", "contract_test", B))
        self.assertEqual(self.a.read()[1]["epoch"], 1)

    def test_unresolved_lease_never_rotates(self):
        self.enqueue_one()
        head, state = self.a.read()
        new, token = claim(state, "worker-a", ["contract_test"], 1, now=NOW)
        self.a.compare_and_swap(head, state, new)
        before = self.a.read()[0]
        self.assertEqual(rotate_once(self.b, B)["status"], "UNRESOLVED_LEASE")
        self.assertEqual(self.a.read()[0], before)

    def test_stale_parallel_archive_only_one_commit(self):
        self.complete_one()
        with ProcessPoolExecutor(max_workers=2) as pool:
            f = [pool.submit(try_rotate, store.repo, B)
                 for store in (self.a, self.b)]
            statuses = [v.result(timeout=45) for v in f]
        self.assertEqual(statuses.count("ARCHIVED_ATOMIC_AND_RESET"), 1, statuses)
        # Other contender either observed EMPTY or failed CAS.
        self.assertEqual(_archive_context(self.a, self.a.read()[0])[0], 1)
        self.assertEqual(self.a.read()[1], empty())

    def test_second_segment_links_to_prior_digest(self):
        self.complete_one()
        first = rotate_if_ready(self.a, B)
        self.assertEqual(first["segment"], 1)
        self.update(self.a, lambda s: enqueue(s, "test-b", "contract_test", B))
        h, s = self.a.read()
        next_state, tok = claim(s, "worker-b", ["contract_test"], 1, now=NOW)
        self.a.compare_and_swap(h, s, next_state)
        self.update(self.a, lambda s: checkpoint(s, tok, B, now=NOW))
        self.update(self.a, lambda s: complete(s, tok, A, now=NOW))
        result = rotate_if_ready(self.b, hashlib.sha256(b"commit-c").hexdigest())
        self.assertEqual(result["segment"], 2)
        head, state = self.a.read()
        serial, digest, _ = _archive_context(self.a, head)
        self.assertEqual(serial, 2)
        seg2 = _read_at(self.a.repo, head, f"{ARCHIVE_DIR}/00000002.json")
        self.assertEqual(seg2["previous_segment_digest_sha256"], first["archive_sha256"])
        self.assertEqual(seg2["receipt_sha256"], digest)
        self.assertEqual(state, empty())

    def test_archive_requires_terminal_state(self):
        self.enqueue_one()
        self.assertEqual(rotate_once(self.a, B)["status"], "NONTERMINAL_TASK")
        self.assertEqual(rotate_once(self.a, A)["status"], "CURRENT_SOURCE_IN_ACTIVE")


if __name__ == "__main__":
    unittest.main()
