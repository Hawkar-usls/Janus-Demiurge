# Generated deterministically by JANUS Rex v1. Do not hand-edit.
MODULE_META = {'schema': 'janus.rex.generated_module.v1', 'module_id': 'rex_birth_notice', 'version': '1.0.0', 'purpose': 'Emit a bounded proof-of-birth notice showing that Rex can create a new organ and Nexus, not Rex, controls execution admission.', 'template': 'echo', 'authority': 'NONE__NEXUS_ADMISSION_REQUIRED'}

async def run(context):
    if not isinstance(context, dict):
        raise TypeError('context must be dict')
    return {
        'status': 'OK',
        'message': 'REX CREATED THIS ORGAN; NEXUS CROWNED ITS EXACT SHA',
        'input': context,
        'authority_delta': 0,
    }
