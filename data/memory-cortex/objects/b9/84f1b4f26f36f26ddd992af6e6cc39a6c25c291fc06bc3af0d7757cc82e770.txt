# JANUS-R3 — Verified Knowledge Pipeline / Continuous Evaluation

Status: STAGED RESEARCH / NOT SCIENTIFICALLY ADMITTED / NOT SCHEDULED IN main.
This draft stacks on GitHub Meta Registry PR #510 and does not modify NAS or JANUS Ocean.

## GDELT 404 recovery from official published file lists

GDELT 2.0 publishes GKG batches about every 15 minutes. The newest ZIP in lastupdate.txt can return HTTP404 before it is propagated. R3 requests that latest HTTPS file once. ONLY on HTTP404 it fetches a bounded 196,608-byte HTTP Range suffix of the official masterfilelist.txt. The server must return HTTP206 and Content-Range: otherwise the fallback fails closed, never downloading the huge full master list.

From the published master tail, R3 chooses ONE previous GKG archive within 24 hours with its own manifest size and MD5. It downloads that one ZIP, verifies exact size and MD5, creates SHA256, and reads 1–3 rows in memory, requiring 27 tab-separated fields. There are NO invented archive URLs, no retried loops, no fallback on HTTP429 and no fallback after checksum corruption. If GDELT is down, record UNAVAILABLE, never falsely claim there are no news. Source: https://www.gdeltproject.org/data.html . GDELT attribution is required for downstream use.

## Two immutable JSONs per candidate

A daily intake produces (1) data/observations/public_source_quarantine/JANUS-PUBLIC-SOURCES-<id>.json, (2) data/observations/public_source_quality/JANUS-R3-QUALITY-<same-id>.json. The quality JSON references the original source record SHA and evaluates metadata provenance, URL/DOI validity, GKG ZIP/checksum structure, provider errors, and novelty relative to historical source identities (DOIs, URLs, GitHub runs and GKG ZIP SHA). It contains its own SHA256 receipt.

The publishing job checks both reports, recomputes the quality report on the checked-out base branch, compares bytes, and proposes ONLY the two JSON files as an append-only review PR. Missing one partner file or a different file scope fails closed. No auto-merge.

New source metadata still belongs to PUBLIC_UNTRUSTED_METADATA_QUARANTINE. No automatic scientific truth assertion, no TACHYON/Ocean training and no R2B/R2C scientific model admission. Metadata integrity and novelty are NOT independent science or journalism fact checks.

## Continuous evaluation vs model learning

The scheduled workflow runs at most once daily, at 06:27 UTC, after review and merge into the default branch. It performs offline security tests, bounded public-source acquisition, metadata quality and novelty evaluation, evidence artifact archive, and PR proposal. New DOIs are not automatically useful training examples. A later curator must independently assess source quality, content rights, leakage vs sealed holdouts and benchmark performance before a separate approved training PR may consume the corpus.

The current educational TACHYON generator still has 0/8 new PUBLIC numerical answers, while the routing model has 18/18 known development labels. Those facts do NOT show that more GitHub Actions runners would yield scientific generalization. GitHub resources remain bounded; the experiment never self-dispatches unlimited jobs.

## Security and activation gates

Provider calls are fixed URL allowlists and bounded sizes, no DOC API hammering, no private user questions. The Actions PR code has only contents:read. The separate on-main proposer has narrowly scoped write credentials. The EYE semantic indexer must continue excluding the public source quarantine; quality JSON is evidence metadata, not a training corpus.

Acceptance: PR safety/quality tests pass; the read-only network smoke reports honest provider status; then maintainers approve and merge #510 and this stacked R3 PR. A manual run on main must demonstrate source and quality PR creation, then two dated scheduled checks and independent audit of duplicate handling. Until those live gates pass, JANUS-R3 DAILY PIPELINE is NOT established.

Parent intake: https://github.com/Hawkar-usls/janus-meta-registry/pull/510
R3 staged PR: https://github.com/Hawkar-usls/janus-meta-registry/pull/511
Scientific source gateway: https://github.com/Hawkar-usls/Janus/pull/51
R2H training: https://github.com/Hawkar-usls/Demi_Head/pull/79
