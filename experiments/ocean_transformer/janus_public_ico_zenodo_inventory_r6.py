#!/usr/bin/env python3
"""JANUS R6 external Zenodo photonic indefinite-causal-order archive inventory.

Publication Valibouse et al. 2026, https://doi.org/10.5281/zenodo.21916346
Archive: experimental_ico_qkd.zip. Examine *names and metadata only* and
minimal safe text headers; never execute untrusted Python scripts from zip.
This does not assert detector hardware timestamps exist or reproduce a
causal inequality from raw trials. No physical retrocausal signal claim.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

SOURCE="https://zenodo.org/records/21916346/files/experimental_ico_qkd.zip?download=1"
DOI="10.5281/zenodo.21916346"
MAX_ZIP_BYTES=3_000_000
MAX_UNCOMPRESSED=30_000_000
MAX_FILES=200
DATA_EXTS={".csv",".txt",".tsv",".dat",".json",".npy",".npz",".xlsx",".h5",".mat",".pkl"}
CODE_EXTS={".py",".ipynb",".m"}


def require(value,message):
    if not value:
        raise ValueError(message)


def inspect(path):
    raw=Path(path).read_bytes()
    require(len(raw)<=MAX_ZIP_BYTES and zipfile.is_zipfile(io.BytesIO(raw)),
            "NOT_A_SAFE_ZENODO_ZIP")
    extensions=Counter()
    files=[]
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        entries=[entry for entry in z.infolist() if not entry.is_dir()]
        require(0<len(entries)<=MAX_FILES and
                sum(e.file_size for e in entries)<=MAX_UNCOMPRESSED,
                "ZIP_BOMB_OR_INVALID_FILE_COUNT")
        for entry in entries:
            name=entry.filename
            segments=Path(name).parts
            require(not name.startswith("/") and
                    ".." not in segments and "\x00" not in name and
                    not name.startswith("\\"),
                    "UNSAFE_ZIP_PATH")
            ext=Path(name).suffix.lower()
            extensions[ext]+=1
            # Archive member is never executed or extracted to disk.
            item={"path":name,"bytes":entry.file_size,
                  "extension":ext}
            if ext==".txt" and entry.file_size<=10_000:
                payload=z.read(entry)
                header=payload.decode("utf-8",errors="replace").splitlines()[:3]
                item["first_three_lines_safe_preview"]=[x[:180] for x in header]
                item["text_line_count"]=len(payload.splitlines())
            files.append(item)
    files.sort(key=lambda f:f["path"])
    number_data=sum(extensions[e] for e in DATA_EXTS)
    number_code=sum(extensions[e] for e in CODE_EXTS)
    return {
        "schema":"janus.open_photon_ico_zenodo_inventory.r6",
        "dataset_doi":DOI,
        "source_download":SOURCE,
        "original_archive_sha256":hashlib.sha256(raw).hexdigest(),
        "archive_bytes":len(raw),
        "file_count":len(files),
        "data_candidate_files_by_extension":number_data,
        "code_files_by_extension":number_code,
        "extensions":dict(extensions),
        "complete_members":files,
        "external_code_executed":False,
        "licensed_research_code_not_modified_or_redistributed":True,
        "original_individual_shot_time_tags_independently_verified":False,
        "original_no_click_trials_independently_verified":False,
        "actual_later_free_choice_independently_verified":False,
        "physical_future_to_past_message_demonstrated":False,
        "promote_to_production":False,
        "scope":"ONLY_SAFE_ARCHIVE_INVENTORY_NO_PHYSICAL_PROOF"
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--zip",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():
        raise RuntimeError("REFUSE_OVERWRITE")
    v=inspect(args.zip)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(v,indent=2,sort_keys=True)+"\n",
                        encoding="utf-8")
    print(json.dumps({k:v[k] for k in ("file_count","archive_bytes",
        "data_candidate_files_by_extension","code_files_by_extension",
        "physical_future_to_past_message_demonstrated")}))
    print("DATA_ARCHIVE_MEMBER_MANIFEST="+json.dumps(v["complete_members"],sort_keys=True))
    print("DATA_TEXT_PREVIEW="+json.dumps([x for x in v["complete_members"] if x["extension"]==".txt"],sort_keys=True))


if __name__=="__main__":
    main()
