"""Small fixed model-facing surface; file contracts are loaded only on use."""
from __future__ import annotations

from copy import deepcopy

DEFINITIONS = [{'name': 'ka_research_status',
  'description': 'Read bounded project or run status and evidence paths without filesystem writes.',
  'inputSchema': {'type': 'object',
                  'properties': {'project': {'type': 'string',
                                             'description': 'Absolute research project directory.',
                                             'minLength': 1,
                                             'maxLength': 1024},
                                 'run_id': {'type': 'string',
                                            'description': 'Recorded run identifier.',
                                            'minLength': 1,
                                            'maxLength': 80,
                                            'pattern': '^[A-Za-z0-9_-]{1,80}$'}},
                  'required': ['project'],
                  'additionalProperties': False},
  'annotations': {'readOnlyHint': True,
                  'destructiveHint': False,
                  'idempotentHint': True,
                  'openWorldHint': False}},
 {'name': 'ka_experiment',
  'description': 'Run: validate a file specification and start a managed run; require spec_path '
                 'and idempotency_key. Matching run keys reuse recorded requests. Stop: require '
                 'run_id. Omit unused fields.',
  'inputSchema': {'type': 'object',
                  'properties': {'project': {'type': 'string',
                                             'description': 'Absolute research project directory.',
                                             'minLength': 1,
                                             'maxLength': 1024},
                                 'spec_path': {'type': 'string',
                                               'description': 'Path to a versioned JSON '
                                                              'specification; validated before any '
                                                              'operation.',
                                               'minLength': 1,
                                               'maxLength': 1024},
                                 'idempotency_key': {'type': 'string',
                                                     'minLength': 1,
                                                     'maxLength': 80},
                                 'action': {'type': 'string', 'enum': ['run', 'stop']},
                                 'run_id': {'type': 'string',
                                            'description': 'Recorded run identifier.',
                                            'minLength': 1,
                                            'maxLength': 80,
                                            'pattern': '^[A-Za-z0-9_-]{1,80}$'}},
                  'required': ['project', 'action'],
                  'additionalProperties': False},
  'annotations': {'readOnlyHint': False,
                  'destructiveHint': True,
                  'idempotentHint': False,
                  'openWorldHint': True}},
 {'name': 'ka_evidence',
  'description': 'Check: inspect evidence and save a report. Import: preserve external artifacts '
                 'and unverified origin. spec_path selects the action-specific JSON file.',
  'inputSchema': {'type': 'object',
                  'properties': {'project': {'type': 'string',
                                             'description': 'Absolute research project directory.',
                                             'minLength': 1,
                                             'maxLength': 1024},
                                 'spec_path': {'type': 'string',
                                               'description': 'Path to a versioned JSON '
                                                              'specification; validated before any '
                                                              'operation.',
                                               'minLength': 1,
                                               'maxLength': 1024},
                                 'action': {'type': 'string', 'enum': ['check', 'import']}},
                  'required': ['project', 'action', 'spec_path'],
                  'additionalProperties': False},
  'annotations': {'readOnlyHint': False,
                  'destructiveHint': False,
                  'idempotentHint': False,
                  'openWorldHint': False}}]
DEFINITIONS.append({
    'name': 'ka_delphi',
    'description': 'Manage native-agent research: idea_spark modes or ponder_forge high/max. Open/prepare/verify require request_id. Return instructions, input templates and complete-file receipts; host owns agents, parent owns decisions.',
    'inputSchema': {
        'type': 'object',
        'properties': {
            'project': deepcopy(DEFINITIONS[0]['inputSchema']['properties']['project']),
            'workflow': {'type': 'string', 'enum': ['idea_spark', 'ponder_forge']},
            'action': {'type': 'string', 'enum': ['open', 'status', 'plan', 'prepare', 'record', 'collect', 'update', 'verify', 'finish']},
            'mode': {'type': 'string', 'maxLength': 80, 'description': 'Workflow mode; open returns supported names/default.'},
            'effort': {'type': 'string', 'enum': ['high', 'max']},
            **{key: {'type': 'string', 'minLength': 1, 'maxLength': 80, 'pattern': '^[A-Za-z0-9_-]+$'}
               for key in ('room_id', 'run_id', 'task_id', 'request_id')},
            'goal': {'type': 'string', 'minLength': 1, 'maxLength': 50000},
            **{key: {'type': 'string', 'minLength': 1, 'maxLength': 1024}
               for key in ('input_path', 'file_path', 'host_agent_id', 'agent_id', 'role')},
            'receipt_paths': {'type': 'array', 'minItems': 1, 'maxItems': 50,
                              'items': {'type': 'string', 'minLength': 1, 'maxLength': 1024}},
            'status': {'type': 'string', 'maxLength': 40},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
        'required': ['project', 'workflow', 'action'],
        'additionalProperties': False,
    },
    'annotations': {'readOnlyHint': False, 'destructiveHint': False,
                    'idempotentHint': False, 'openWorldHint': False},
})
PUBLIC_NAMES = frozenset(item["name"] for item in DEFINITIONS)


def definition(name):
    return deepcopy(next(item for item in DEFINITIONS if item["name"] == name))


def call_public_tool(name, args):
    from .tool_registry import call_tool
    return call_tool(name, args)
