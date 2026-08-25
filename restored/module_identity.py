from __future__ import annotations
from pathlib import PurePosixPath
from typing import Iterable, Any

SCHEMA="janus.module_identity.v1"

def canonical_module_key(value:str)->str:
    raw=str(value).strip().replace("\\","/")
    if not raw or raw.endswith("/"):
        raise ValueError("module identity must name a file or module")
    name=PurePosixPath(raw).name
    if name.lower().endswith(".py"):
        name=name[:-3]
    if not name or name in {".",".."}:
        raise ValueError("invalid module identity")
    return name.casefold()

def identity_receipt(value:str)->dict[str,Any]:
    return {"schema":SCHEMA,"observed":value,"canonical_key":canonical_module_key(value),
            "law":"PROTECTION_LOOKUP_MUST_USE_CANONICAL_MODULE_IDENTITY"}

def protected(value:str, protected_names:Iterable[str])->bool:
    key=canonical_module_key(value)
    keys={canonical_module_key(x) for x in protected_names}
    return key in keys

def collision_groups(values:Iterable[str])->dict[str,list[str]]:
    groups={}
    for value in values:
        key=canonical_module_key(value)
        groups.setdefault(key,[]).append(value)
    return {k:v for k,v in sorted(groups.items()) if len(v)>1}
