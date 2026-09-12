# Generated deterministically by JANUS Rex v1. Do not hand-edit.
MODULE_META = {'schema': 'janus.rex.generated_module.v1', 'module_id': 'rex_lifecycle_heartbeat', 'version': '1.0.0', 'purpose': 'Remain alive as a bounded scheduled Rex-created organ and prove that Nexus lifecycle admission can repeatedly execute an exact-SHA module without giving Rex execution authority.', 'template': 'heartbeat', 'authority': 'NONE__NEXUS_ADMISSION_REQUIRED'}

async def run(context):
    if not isinstance(context, dict):
        raise TypeError('context must be dict')
    return {
        'status': 'ALIVE',
        'message': 'REX LIFECYCLE HEARTBEAT',
        'module_id': MODULE_META['module_id'],
        'authority_delta': 0,
    }
