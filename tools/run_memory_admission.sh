#!/usr/bin/env bash
# JANUS Native Model memory lane: source-verified, bounded, baseline-preserving.
# Runs inside existing native-model job after EYE corpus and modular organ context.
set -euo pipefail
mkdir -p runtime/memory-v2
cp runtime/corpus/train.txt runtime/memory-v2/baseline-train.txt
cp runtime/corpus/corpus_manifest.json runtime/memory-v2/baseline-manifest.json

set +e
(
  set -euo pipefail
  git clone --quiet --depth 1 --filter=blob:none --sparse \
    https://github.com/Hawkar-usls/Demi_Head.git runtime/demihead-provider
  git -C runtime/demihead-provider sparse-checkout set tools

  ENGINE="runtime/meta-registry/experiments/unified-memory-v2/janus_unified_memory.py"
  python "$ENGINE" build --registry-root runtime/meta-registry \
    --db runtime/memory-v2/index.sqlite > runtime/memory-v2/build.json
  python "$ENGINE" verify --registry-root runtime/meta-registry \
    --db runtime/memory-v2/index.sqlite > runtime/memory-v2/verify.json

  TOPIC=$(python -c 'import os; from janus_model.memory_admission import choose_topic; print(choose_topic(os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_EVENT_NAME"]))')
  SOURCE_COMMIT=$(python -c 'import json; print(json.load(open("runtime/memory-v2/verify.json"))["source_commit"])')
  MANIFEST_SHA=$(python -c 'import json; print(json.load(open("runtime/memory-v2/verify.json"))["source_manifest_sha256"])')

  python runtime/demihead-provider/tools/unified_memory_v2_bridge.py \
    --index runtime/memory-v2/index.sqlite --query "$TOPIC" \
    --expected-source-commit "$SOURCE_COMMIT" --expected-manifest-sha256 "$MANIFEST_SHA" \
    --limit 8 --output runtime/memory-v2/demihead-packet.json
  python tools/demiurge_unified_memory_v2_consumer.py \
    --packet runtime/memory-v2/demihead-packet.json \
    --expect-source-commit "$SOURCE_COMMIT" --expect-manifest-sha256 "$MANIFEST_SHA" \
    --output runtime/memory-v2/demiurge-context.json
  python -m janus_model.memory_admission \
    --registry runtime/meta-registry \
    --verification runtime/memory-v2/verify.json \
    --packet runtime/memory-v2/demihead-packet.json \
    --context runtime/memory-v2/demiurge-context.json \
    --corpus-dir runtime/corpus \
    --run-id "$GITHUB_RUN_ID" --event "$GITHUB_EVENT_NAME" \
    --output runtime/memory-v2/admission.json
) > runtime/memory-v2/phase.log 2>&1
RC=$?
set -e

if [ "$RC" -ne 0 ]; then
  cp runtime/memory-v2/baseline-train.txt runtime/corpus/train.txt
  cp runtime/memory-v2/baseline-manifest.json runtime/corpus/corpus_manifest.json
  # A failed proof is not a pass; the existing brain may still run on baseline.
  rm -f runtime/memory-v2/admission.json
  python - <<'PY'
import json
from pathlib import Path
Path('runtime/memory-v2/hold.json').write_text(
    json.dumps({
        'schema':'janus.native.memory_v2_hold.v1',
        'status':'MEMORY_SOURCE_HELD_NATIVE_BASELINE_CONTINUES',
        'training_inputs_restored':True,
        'memory_source_admitted':False,
        'reason':'MEMORY_LANE_VALIDATION_OR_AVAILABILITY_ERROR',
        'source_authority_delta':0,
    },sort_keys=True)+'\n',encoding='utf-8'
)
PY
  echo 'status=HOLD' >> "$GITHUB_OUTPUT"
  echo "JANUS_MEMORY_V2=HOLD_NATIVE_BASELINE_CONTINUES (code $RC)"
else
  echo 'status=VERIFIED' >> "$GITHUB_OUTPUT"
  python -c 'import json; x=json.load(open("runtime/memory-v2/admission.json")); print("JANUS_MEMORY_V2="+x["status"]+" admitted="+str(x["admitted_count"]))'
fi
