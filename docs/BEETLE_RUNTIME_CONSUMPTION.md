# Beetle runtime consumption pilot

The durable Beetle inbox previously ended at `INBOX_DURABLE_UNVERIFIED__NOT_RUNTIME_CONSUMPTION`.
This pilot adds deterministic research triage and makes its output available to the next
research search. It also fixes `wikipedia_trunk.derive_topics`: the function previously
ignored `hypothesis_routes`, including existing Meta Registry inspiration supplied by iNaiHR.

## Flow

1. The existing receiver stages addressed, hash-checked packages and the delivery ACK.
2. The receiver workflow captures the current sender manifest from an exact `beetle-state`
   commit after staging. The offline consumer validates its ordered prefix against the ACK.
3. `tools/beetle_runtime_consumer.py` validates an entire bounded window before producing
   any result. It triages every item and selects up to eight distinct source URLs, preferring
   direction diversity. Deferred items remain in their immutable input packages and result.
4. Each package gets an immutable result and a processing receipt binding input SHA-256,
   processor bytes, consumer source commit, sender manifest commit and result bytes.
   `PROCESSING_ACK.json` advances only after both exist. This cursor is separate from the
   transport ACK. One workflow commit publishes inbox and processing artifacts together.
5. `CONTEXT.json` is a derived bounded projection. Research Spine mounts it from the
   `beetle-memory` branch, interleaves Beetle routes with registry-inspired iNaiHR routes,
   and preserves both sources' provenance. The next Wikipedia search reserves attention
   for the first two routes before applying its existing topic budget.

The Meta Registry already supplies the native training corpus and the source records for
iNaiHR semantic synthesis. This change reuses that inspiration path; it does not execute
registry source, treat archival labels as findings, or change native promotion thresholds.

## Meaning of processing

`TRIAGED_TO_RESEARCH_CONTEXT_NOT_VERIFIED` means that the named processor read the exact
package, recorded all item dispositions and produced bounded research questions. It does
not mean the model learned those items, selected an engineering task, verified a discovery,
improved a capability, or applied a patch. Search strings remain untrusted context.

The processor does not fetch source URLs, execute item text, modify the transport ACK or
grant code admission. The workflow remains a single writer through its existing concurrency
group; callers of the offline command must also serialize writes to the same output directory.

## Replay and interruption

Results and receipts are immutable and content-bound. Replaying a completed window does
not rewrite them. If interrupted after saving a result or receipt, the next run validates and
reuses it before advancing the cursor. If interrupted after cursor advancement, it rebuilds
the derived context from validated results. Missing or corrupted history fails closed.
The complete selected window is validated before new artifacts are written.

A changed processor SHA requires an explicit migration or a separate output directory.
Do not delete or rewind the old cursor to hide a processor change. A second processing
contract must preserve the earlier receipts and declare how replay is handled.

The sender manifest may extend beyond the receiver ACK. The consumer processes only the
delivered prefix. A manifest captured behind the ACK fails rather than guessing.

## Offline use

```powershell
python tools/beetle_runtime_consumer.py --delivery-manifest delivery.json --inbox-dir inbox --out-dir runtime-triage --source-commit <sender-commit> --consumer-commit <consumer-commit> --max-batches 16
python -m unittest discover -s tests -p test_beetle_runtime_consumer.py -v
python -m unittest discover -s tests -p test_janus_wikipedia_trunk.py -v
```

The CLI accepts at most 96 packages per invocation, 4 MB per input package, 32 MB per
sender manifest and 1,024 items per package. It is scoped to Janus-Demiurge in this pilot.
Receiver artifacts live under `data/beetle-runtime/{results,receipts}` with separate
`PROCESSING_ACK.json` and `CONTEXT.json` files.

The read-only PR workflow runs the failure, replay and source-to-search contract checks.
Production integration happens only when these changes enter the repository's active ref.
A recovery drill for the complete JANUS system and an autonomous engineering cycle remain
separate milestones; the interruption tests here cover only this consumer's persistence.
