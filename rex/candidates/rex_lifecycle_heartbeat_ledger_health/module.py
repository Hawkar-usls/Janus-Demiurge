# Generated deterministically by JANUS Rex v1. Do not hand-edit.
MODULE_META = {'schema': 'janus.rex.generated_module.v1', 'module_id': 'rex_lifecycle_heartbeat_ledger_health', 'version': '1.0.0', 'purpose': 'Report status counts and detect regression in ledger family rex_lifecycle_heartbeat after 327 persisted receipts; independently compare with original summary.', 'template': 'ledger_health', 'authority': 'NONE__NEXUS_ADMISSION_REQUIRED'}

async def run(context):
    if not isinstance(context, dict):
        raise TypeError('context must be dict')
    rows = context.get('rows', [])
    if not isinstance(rows, list):
        raise TypeError('context.rows must be list')
    dict_rows = [row for row in rows if isinstance(row, dict)]
    keys = sorted({key for row in dict_rows for key in row.keys() if isinstance(key, str)})
    states = {}
    for row in dict_rows:
        state = row.get('result_status', row.get('status', row.get('state', 'UNKNOWN')))
        if not isinstance(state, str):
            state = 'UNKNOWN'
        state = state[:64]
        states[state] = states.get(state, 0) + 1
    return {'status': 'OK', 'row_count': len(rows), 'dict_row_count': len(dict_rows), 'keys': keys, 'status_counts': states, 'authority_delta': 0}
