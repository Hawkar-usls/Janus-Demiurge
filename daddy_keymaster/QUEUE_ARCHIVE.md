# JANUS DADDY_KEYMASTER · R3 atomic archive and second physical copy

## Atomic rollover
The version-bound Git-CAS CI queue has fixed limits (32 tasks, 256 events).
Before admitting a new main commit, queue_rotation.py archives a prior
fully-terminal segment. No pending QUEUED, LEASED or HOLD tasks are discarded.
Old unclaimed tasks receive an explicit SKIPPED event first.

One ordinary non-forced Git push advances all four objects in one commit:
- state/archive_segments/00000001.json, carrying exact previous queue,
  previous archive digest, source ref and immutable SHA-256 receipt.
- state/relay_archive_head.json, identifying the latest verified segment.
- state/processed_sources/<source-SHA256>.json, immutable dedup markers.
- state/relay_queue.json, now an empty v1 queue.

The previous and new state share one remote Git ref; two conflicting sibling
pushes cannot both succeed. A conflict forces a bounded refetch; no forced
push, no replay of external side effects. The old segment's exact tasks and
event hash chain can be verified by queue_rotation._archive_context and
git_cas_queue.verify. Archived source SHA reverted on main remains IDLE.

## Tested guarantees and limitations
PR CI uses two independent Git clones and a bare remote. Adversarial tests
cover simultaneous rollover, exact snapshots, repeated source versions,
two linked segments and refusing live/uncertain leases. Production main is
not modified by PR validation. The archive journal is a chain of Git hashes,
not a cryptographically signed record from an independent authority.

A separate, owner-connected Windows device successfully created a read-only
ZIP snapshot of the state branch with a SHA-256 receipt. An unprivileged
Windows Scheduled Task was installed and verified with LastTaskResult=0.
It attempts updates twice daily; duplicate SHA snapshots are idempotently
verified. This local copy is outside GitHub artifact retention, but the
host, disk, account logon, power and internet availability are not guaranteed.
The local host name and private paths are intentionally not published here.

The archive and physical copy do not license general compute on GitHub.
The queue still has explicit per-segment ceilings, finite disk storage,
and no signed third-party storage quorum. It is not an infinitely scaled
service. Always-on owner-operated workers, provider registration, R2 model
blind evaluation (#385), secure checkpoint loader (#301), consumer ACK and
safe rollback are separate gates.

## Recovery rule
A restored archived source is *evidence*, not new execution authority.
Never re-run previously completed work automatically. Restore from an exact
verified archive only after comparing current CAS head, independent worker
receipts and source digest. A HOLD or LEASED task remains blocked until
separate reconciliation.

## Validation
python -m unittest discover -s tests -p test_daddy_keymaster_queue_rotation.py -v

No private model checkpoints, secrets, API credentials, paid Rowan jobs,
arbitrary shell dispatch or unauthorized external devices are included.
