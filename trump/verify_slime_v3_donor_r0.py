#!/usr/bin/env python3
"""Verify and execute the pinned Slime v3 amortized donor in isolation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "TRUMP_SLIME_V3_AMORTIZED_DONOR_R0.json"


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def main() -> int:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if m.get("status") != "PINNED_SOURCE_ONLY_BOOST_DONOR__NOT_YET_EXACT_COMPILER_LINKED":
        raise SystemExit("DONOR_STATUS_INVALID")
    if m.get("contract", {}).get("P_VS_NP") != "OPEN":
        raise SystemExit("DONOR_BOUNDARY_INVALID")
    repo = m["repository"]
    owner, name = repo.split("/", 1)
    commit = m["pinned_commit"]
    fetched = []
    with tempfile.TemporaryDirectory(prefix="janus-slime-v3-donor-") as td:
        root = Path(td)
        for item in m["files"]:
            path = item["path"]
            url = f"https://raw.githubusercontent.com/{owner}/{name}/{commit}/{path}"
            req = urllib.request.Request(url, headers={"User-Agent": "JANUS-TRUMP-SLIME-DONOR-R0/1"})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()
            actual = git_blob_sha(data)
            if actual != item["git_blob_sha"]:
                raise SystemExit(f"DONOR_BLOB_MISMATCH:{path}:{actual}")
            target = root / Path(path).name
            target.write_bytes(data)
            fetched.append({"path": path, "git_blob_sha": actual, "bytes": len(data)})

        proc = subprocess.run(
            [sys.executable, str(root / "slime_semantic_candidate_swarm_v3_amortized.py")],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        if proc.returncode != 0:
            raise SystemExit("DONOR_SELFTEST_FAILED\n" + proc.stdout + "\n" + proc.stderr)
        try:
            report = json.loads(proc.stdout)
        except Exception as exc:
            raise SystemExit("DONOR_SELFTEST_OUTPUT_NOT_JSON\n" + proc.stdout) from exc
        if report.get("status") != "PASS":
            raise SystemExit("DONOR_SELFTEST_NOT_PASS")
        if report.get("candidate_count") != 16 or report.get("v2_candidate_orders_preserved") is not True:
            raise SystemExit("DONOR_ORDER_EQUIVALENCE_NOT_CONFIRMED")
        ratios = report.get("example_new_over_old_cost_ratios") or []
        if not ratios or not all(float(r) < 1.0 for r in ratios):
            raise SystemExit("DONOR_COST_REDUCTION_NOT_CONFIRMED")
        if report.get("p_vs_np") != "OPEN":
            raise SystemExit("DONOR_P_VS_NP_BOUNDARY_DRIFT")

    out = {
        "schema": "janus.trump.slime_v3_donor_verification.r0",
        "status": "PASS",
        "pinned_commit": commit,
        "files": fetched,
        "selftest": report,
        "exact_compiler_linked": False,
        "end_to_end_solver_speedup_claimed": False,
        "P_VS_NP": "OPEN",
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
