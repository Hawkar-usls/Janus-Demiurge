from __future__ import annotations

import json
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR = ROOT / '.janus' / 'JANUS_MODULE.json'
INDEX = ROOT / 'janus_model' / 'extensions' / 'INDEX.json'


def fail(code: str) -> None:
    raise SystemExit(code)


def main() -> None:
    descriptor = json.loads(DESCRIPTOR.read_text(encoding='utf-8'))
    index = json.loads(INDEX.read_text(encoding='utf-8'))

    if descriptor.get('repository') != 'Hawkar-usls/Janus-Demiurge':
        fail('SELF_EXTENSION_DESCRIPTOR_REPOSITORY_MISMATCH')
    actuator = descriptor.get('actuator') or {}
    if actuator.get('enabled') is not True:
        fail('SELF_EXTENSION_ACTUATOR_DISABLED')
    if actuator.get('direct_main_write') is not False or actuator.get('autonomous_merge') is not False:
        fail('SELF_EXTENSION_AUTHORITY_CEILING_VIOLATION')
    if actuator.get('create_new_module_files') is not True:
        fail('SELF_EXTENSION_CREATE_MODULE_DISABLED')

    required_forbidden = {
        '.github/workflows/', '.janus/JANUS_MODULE.json',
        'janus_model/model.py', 'janus_model/train_registry.py', 'janus_model/decision.py',
        'janus_model/state/', 'janus_model/checkpoints/', 'janus_model/receipts/', 'janus_model/outbox/',
        'secrets/', 'credentials/'
    }
    forbidden = set(descriptor.get('forbidden_paths') or [])
    if not required_forbidden.issubset(forbidden):
        fail('SELF_EXTENSION_FORBIDDEN_PATH_SET_INCOMPLETE')

    allowed = set(descriptor.get('ordinary_self_extension_paths') or [])
    required_allowed = {'janus_model/extensions/', 'tools/extensions/', 'tests/extensions/', 'protocol/extensions/'}
    if allowed != required_allowed:
        fail('SELF_EXTENSION_ALLOWLIST_DRIFT')

    if index.get('schema') != 'janus.native_extensions.index.v1':
        fail('SELF_EXTENSION_INDEX_SCHEMA_MISMATCH')
    if index.get('extension_count') != len(index.get('extensions') or []):
        fail('SELF_EXTENSION_INDEX_COUNT_MISMATCH')
    auth = index.get('authority') or {}
    for key in ('direct_main_write', 'autonomous_merge', 'core_model_rewrite', 'checkpoint_rewrite', 'workflow_rewrite', 'governance_descriptor_rewrite'):
        if auth.get(key) is not False:
            fail(f'SELF_EXTENSION_INDEX_AUTHORITY_VIOLATION:{key}')

    for base in ('janus_model/extensions', 'tools/extensions', 'tests/extensions', 'protocol/extensions'):
        root = ROOT / base
        if not root.exists():
            continue
        for path in root.rglob('*'):
            if not path.is_file():
                continue
            if path.suffix == '.py':
                py_compile.compile(str(path), doraise=True)
            elif path.suffix == '.json':
                json.loads(path.read_text(encoding='utf-8'))

    print(json.dumps({
        'status': 'PASS',
        'module_id': descriptor.get('module_id'),
        'self_extension_surface': sorted(allowed),
        'extension_count': index.get('extension_count'),
        'direct_main_write': False,
        'autonomous_merge': False,
    }, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
