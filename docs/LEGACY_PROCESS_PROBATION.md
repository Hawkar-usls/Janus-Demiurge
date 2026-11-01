# JANUS Demiurge: owner-approved process-separated module probation

## What is restored from the E-drive
Early JANUS Nexus discovered code by filename and called `run(core)`; Conductor started modules by priority. Old direct `exec()`, dynamic Python imports, unbounded tasks and auto-quarantine are NOT restored.

Modern modules: `restored/legacy_process_probation.py` and a separate one-shot `restored/legacy_probation_worker.py`. The only admitted entrypoint is a reviewed repository-local graph-query organ, not arbitrary historical Python.

## Admission chain
1. Caller explicitly opts in using `run_approved_process_probation(graph,start,end,operator_approved=True)`; default denies.
2. The repo policy pins SHA-256 of four modern source files and the canonical SHA-256 of the historical registry graph.
3. Parent refuses mismatched file, authority, target or graph; no executable source or import path from user data.
4. One child Python process runs with `-I -S -B`, empty environment, temporary working directory, bounded JSON stdin/stdout and wall timeout.
5. Child verifies all SHA pins again, recreates reviewed Nexus plan and calls only `run_legacy_graph_query` on a detached read-only graph port.
6. Parent validates the typed receipt and holds on unexpected authority, missing evidence, invalid graph or child failure.

Archive input: Hawkar-usls/janus-meta-registry/data/JANUS-LEGACY-CORE-MODULE-RELATIONSHIP-GRAPH-2026-11-01-v1.0.json

## Security ceiling
Process separation is NOT an OS security sandbox. Python -I -S and an empty environment do not block filesystem or network access by arbitrary Python code. This is restricted to approved modern code; untrusted legacy *.py still requires an actual OS-enforced no-network, read-only sandbox, separate identity, quotas, proof of deterministic behavior and canary rollback.
Neither model promotion, live HRAiN mutation, NAS read, privileged worker dispatch nor automated code installation is granted. No permanent service or new schedule is started.

## Example
From a trusted developer process, after independently fetching the pinned archive as graph:
    from restored.legacy_process_probation import run_approved_process_probation
    result = run_approved_process_probation(graph, 'janus_cortex', 'genesis_engine', operator_approved=True)

The user must approve each direct invocation. This function does not fetch remote files or modify input.

## Evidence limits
Passing tests confirms the bounded subprocess and registered modern organ, not full security isolation, runtime recovery of all historical modules, autonomous installation, superior model quality or proof of P=NP.
