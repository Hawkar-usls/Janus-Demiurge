# Generated deterministically by JANUS Rex v1. Do not hand-edit.
MODULE_META = {'schema': 'janus.rex.generated_module.v1', 'module_id': 'rex_lifecycle_heartbeat_ledger_summary', 'version': '1.0.0', 'purpose': 'Summarize a bounded snapshot of the repeatedly accumulating ledger family rex_lifecycle_heartbeat; Rex detected 4 persisted receipts under rex/lifecycle_runs/rex_lifecycle_heartbeat.', 'template': 'ledger_summary', 'authority': 'NONE__NEXUS_ADMISSION_REQUIRED'}

async def run(context):
    if not isinstance(context, dict):
        raise TypeError('context must be dict')
    rows = context.get('rows', [])
    if not isinstance(rows, list):
        raise TypeError('context.rows must be list')
    dict_rows = [row for row in rows if isinstance(row, dict)]
    keys = sorted({key for row in dict_rows for key in row.keys() if isinstance(key, str)})
    return {'status': 'OK', 'row_count': len(rows), 'dict_row_count': len(dict_rows), 'keys': keys, 'authority_delta': 0}
