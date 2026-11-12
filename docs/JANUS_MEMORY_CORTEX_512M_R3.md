# JANUS Memory Cortex 512M — R3.0/R3.1 source-audit and indexed readout

**Scope: engineering canary / not a new neural context window / not model promotion.**

Master roadmap: [#535](https://github.com/Hawkar-usls/Janus-Demiurge/issues/535).
Original v1 remains at 128 **bytes**; R2 256/512-byte shadow models remain untrained.

## Input provenance
The existing Meta Registry full-memory manifest
\`assets/hrain-full-memory/manifest.json\` catalogues 8,542 files, 43 metadata
shards and 293,091,756 bytes of **mixed** tracked file sizes, pinned to
source SHA \`c8e47bb54e954ab122e111c97198131f048bd5fd\`.
Do **not** count this metadata number as 512 MiB of useful, unique, read-only
memory. It includes binary images, code, infrastructure, generated self-reflection
and other sources that must not be fed directly into the native model.

The R3 audit:
1. Pins full manifest at Meta Registry Git SHA
   \`6c9259c43d89569b11351bf8579a3775025fa2f0\`.
2. Verifies all **43 shard file SHA-256 values**, shard source revision, ordering,
   object counts, path uniqueness, read-only/non-authority controls and total
   cataloged byte sum. Any violation fails the whole check.
3. Classifies \`.json/.jsonl/.txt/.md\` within explicit public research
   namespaces as *candidate memory*, excluding known sensitive/secret, blind,
   sealed/holdout, large (over 1 MiB each), model self-reflection and other
   prohibited paths. It does not automatically establish consent to training.
4. Reads every candidate from exact Git source commit, checks *raw byte SHA
   and byte size*, decodes UTF-8 and parses JSON/JSONL when applicable. Invalid
   JSON, non-UTF8 and duplicate content do not increase eligible unique bytes.
5. Publishes a **metadata-only receipt** with catalog total, verified candidate
   count/bytes, unique-source bytes, exclusion counts, gap to 512 MiB and SHA
   of audit receipt. Its eligibility count is technical/structural: a
   further privacy/rights/fitness audit may reduce the admissible total.
6. Creates an ephemeral SQLite FTS5 index of at most **16 MiB** of verified
   sources filtered to **Rowan paths**, with 4096-byte UTF-8-safe chunks. The
   index is stored in the runner temporary directory, not written to GitHub
   or to the immutable source checkout. It returns only source paths, SHAs
   and source commits; no raw JSON is uploaded in CI artifacts.
7. Exposes a two-hop readout: search an actual verified content chunk, then
   traverse **explicit JSON reference paths** into separately indexed verified
   documents. Missing first/second-hop evidence results in explicit refusal,
   never fabricated cross-document knowledge.

## Local isolated test

\`\`\`bash
python -m unittest discover -s tests -p 'test_janus_memory_512_audit_index_r3.py' -v
\`\`\`

GitHub Actions entrypoint: \`.github/workflows/janus-memory-cortex-512m-r3.yml\`.
GitHub-hosted runner checks out both pinned snapshots, audits full source tree,
builds the 16-MiB cap SQLite index, tests direct/multihop search, verifies source
checkout is unchanged and uploads ONLY the summary receipt.

## 512 MiB acceptance boundary

For final 512 MiB status we need **536,870,912 UNIQUE bytes** of read-only,
hash-verified, genuinely retrievable and permitted source contents, not merely
their metadata or duplicate chunk overlaps. Index overhead and mixed/binary
catalog bytes are never counted toward the target. A real readout must
demonstrate correct source selection/citations, abstention and multi-document
answer grounding on independently held-out tasks.

Today's R3 index proves **mechanics**, not an actual 512 MiB corpus, improved
model reasoning, or expanded native Transformer context. No updates to model
weights, no automatic training, no unrestricted agent commands. No access to
TACHYON R3.9 or other frozen external blind datasets.

**If any verification fails, preserve the failure.** Do not bypass a source
commit, SHA, excluded path or original checkpoint gate to manufacture PASS.
