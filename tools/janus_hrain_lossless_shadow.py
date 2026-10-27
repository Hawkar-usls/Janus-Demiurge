#!/usr/bin/env python3
"""JANUS HRAiN · lossless PRIVATE shadow of the legacy graph.

Never imports/executes the old autonomy engine and NEVER replaces the source.
The "compact view" is only a derived navigation projection. Original JSON
bytes remain compressed inside the PRIVATE shadow for exact verified recovery.
This is NOT production compression, scientific interpretation, or a license to
activate HrainGraphEngine.compress_clusters().
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import zlib
from janus_hrain_compression_preflight import assess, _score, MAX_BYTES

SCHEMA="janus.hrain.private_lossless_shadow_compaction.v1"
MAX_SHADOW_BYTES=40_000_000

def _hash(body):
    return hashlib.sha256(body).hexdigest()

def _group_members(nodes,threshold=0.7):
    ids=list(nodes)
    seen=set()
    groups=[]
    for nid in ids:
        if nid in seen:continue
        group=[nid];seen.add(nid)
        for peer in ids:
            if peer not in seen and _score(nodes[nid],nodes[peer])>threshold:
                seen.add(peer);group.append(peer)
        if len(group)>1:groups.append(group)
    return groups

def make_shadow(source:bytes):
    if not isinstance(source,bytes) or not 1<=len(source)<=MAX_BYTES:
        raise ValueError("PRIVATE_INPUT_BYTE_BOUND_HOLD")
    record=json.loads(source)
    if not isinstance(record,dict):
        raise ValueError("GRAPH_ROOT_SCHEMA_HOLD")
    nodes,edges=record.get("nodes"),record.get("edges")
    risk=assess(nodes,edges)
    if risk["alreadyDanglingEdges"]:
        raise ValueError("DANGLING_SOURCE_EDGES_HOLD")
    groups=_group_members(nodes)
    member_map={}
    summaries={}
    reserved=set(nodes)
    for i,group in enumerate(groups):
        meta=f"shadow_cluster_{i:04d}"
        while meta in reserved:
            meta="_"+meta
        reserved.add(meta)
        summaries[meta]={"kind":"SHADOW_GROUP_ONLY","memberCount":len(group)}
        for nid in group:member_map[nid]=meta
    condensed={}
    for nid in nodes:
        if nid not in member_map:
            condensed[nid]={"kind":"UNCHANGED_SOURCE_REFERENCE"}
    condensed.update(summaries)
    projected={}
    for key in edges:
        src,dst=key.split("->")
        new_src,new_dst=member_map.get(src,src),member_map.get(dst,dst)
        relation=(new_src,new_dst)
        projected[relation]=projected.get(relation,0)+1
    # JSON-safe array avoids ambiguous "src->dst" concatenation.
    relations=[{"source":a,"target":b,"originalEdgeMultiplicity":count}
               for (a,b),count in sorted(projected.items())]
    compressed=zlib.compress(source,level=9)
    encoded=base64.b64encode(compressed).decode("ascii")
    if len(encoded)>MAX_SHADOW_BYTES:
        raise ValueError("SHADOW_ARCHIVE_LENGTH_HOLD")
    return {
        "schema":SCHEMA,"status":"OWNER_PRIVATE_REVERSIBLE_SHADOW_NOT_PRODUCTION",
        "sourceSha256":_hash(source),"sourceBytes":len(source),
        "archive":{"codec":"zlib+base64","payload":encoded},
        "compactView":{
            "nodes":condensed,"relations":relations,
            "originalEdgeCount":len(edges),
            "projectedRelationCount":len(relations),
            "groupsDetected":len(groups),
            "originalNodesRepresented":len(nodes),
            "scientificVerdict":"NOT_TOPA_ADJUDICATED",
            "sourceGraphMutationAllowed":False,
        },
        "losslessness":{
            "rawSourceBytesRetained":True,
            "recoveryRequiresThisPrivateShadow":True,
            "originalInputNeverOverwritten":True,
            "archiveCryptographicallyVerified":True,
        }
    }

def expanded_bytes(shadow):
    if not isinstance(shadow,dict) or shadow.get("schema")!=SCHEMA:
        raise ValueError("SHADOW_SCHEMA_HOLD")
    archive=shadow.get("archive",{})
    if archive.get("codec")!="zlib+base64":
        raise ValueError("SHADOW_ARCHIVE_CODEC_HOLD")
    payload=archive.get("payload")
    if not isinstance(payload,str) or len(payload)>MAX_SHADOW_BYTES:
        raise ValueError("SHADOW_ARCHIVE_LENGTH_HOLD")
    try:
        zipped=base64.b64decode(payload,validate=True)
        inflater=zlib.decompressobj()
        source=inflater.decompress(zipped,MAX_BYTES+1)
        if len(source)>MAX_BYTES or inflater.unconsumed_tail or inflater.unused_data or not inflater.eof:
            raise ValueError("SHADOW_DECOMPRESSION_INTEGRITY_HOLD")
    except (ValueError,zlib.error) as e:
        raise ValueError("SHADOW_ARCHIVE_INVALID_HOLD") from e
    if len(source)!=shadow.get("sourceBytes") or _hash(source)!=shadow.get("sourceSha256"):
        raise ValueError("SHADOW_SHA256_MISMATCH_HOLD")
    regenerated=make_shadow(source)
    if regenerated["compactView"]!=shadow.get("compactView"):
        raise ValueError("SHADOW_PROJECTED_GRAPH_TAMPERED_HOLD")
    return source

def _approved_parent(snapshot):
    if snapshot.is_symlink() or snapshot.name!="hrain_graph_state.json" or snapshot.parent.name!="raw_logs":
        raise ValueError("ONLY_OWNER_LOCAL_HRAIN_STATE_ALLOWED")
    parent=snapshot.parent.parent.resolve(strict=True)
    if (parent/"raw_logs").is_symlink():
        raise ValueError("RAW_LOGS_SYMLINK_HOLD")
    return parent

def _output_path(root,target):
    base=root/"artifacts"/"audits"
    if not base.exists() or base.is_symlink():
        raise ValueError("APPROVED_LOCAL_AUDIT_FOLDER_REQUIRED")
    base=base.resolve(strict=True)
    resolved=target.resolve(strict=False)
    if resolved.parent!=base or resolved.suffix!=".json" or target.is_symlink():
        raise ValueError("ONLY_OWNER_PRIVATE_AUDIT_OUTPUT_ALLOWED")
    if target.exists():
        raise FileExistsError("NEVER_OVERWRITE_PRIVATE_SHADOW_OR_SOURCE")
    return resolved

def _exclusive(path,body):
    fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",type=Path,required=True)
    p.add_argument("--shadow",type=Path,required=True)
    p.add_argument("--verify-only",action="store_true")
    args=p.parse_args()
    root=_approved_parent(args.snapshot)
    if args.verify_only:
        shadow=json.loads(args.shadow.read_bytes())
        restored=expanded_bytes(shadow)
        if not args.snapshot.is_file() or args.snapshot.stat().st_size>MAX_BYTES:
            raise ValueError("SOURCE_BYTES_OR_FILE_HOLD")
        if args.snapshot.read_bytes()!=restored:
            raise ValueError("SHADOW_SOURCE_MISMATCH_HOLD")
        print(json.dumps({"status":"VERIFIED_NO_MUTATIONS",
                          "sha256":_hash(restored),"bytes":len(restored)}))
        return
    if not args.snapshot.is_file() or args.snapshot.stat().st_size>MAX_BYTES:
        raise ValueError("SOURCE_BYTES_OR_FILE_HOLD")
    target=_output_path(root,args.shadow)
    original=args.snapshot.read_bytes()
    packed=make_shadow(original)
    recovered=expanded_bytes(packed)
    if recovered!=original:
        raise ValueError("SHADOW_BYTE_ROUNDTRIP_HOLD")
    _exclusive(target,(json.dumps(packed,ensure_ascii=False,separators=(",",":"))+"\n").encode("utf8"))
    print(json.dumps({"status":"PRIVATE_LOSSLESS_SHADOW_CREATED",
                      "sourceSha256":_hash(original),
                      "originalNodes":packed["compactView"]["originalNodesRepresented"],
                      "originalEdges":packed["compactView"]["originalEdgeCount"],
                      "projectedRelations":packed["compactView"]["projectedRelationCount"],
                      "groups":packed["compactView"]["groupsDetected"],
                      "sourceModified":False,"scientificVerdict":"NOT_TOPA_ADJUDICATED"}))

if __name__=="__main__":
    main()
