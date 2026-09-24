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
 {'name': 'ka_experiment_run',
  'description': 'Validate a file specification and protected inputs, then start one managed run. '
                 'Matching keys reuse the recorded request.',
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
                                                     'maxLength': 80}},
                  'required': ['project', 'spec_path', 'idempotency_key'],
                  'additionalProperties': False},
  'annotations': {'readOnlyHint': False,
                  'destructiveHint': True,
                  'idempotentHint': False,
                  'openWorldHint': True}},
 {'name': 'ka_experiment_stop',
  'description': 'Stop one managed run, preserving actual terminal state and evidence.',
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
                  'required': ['project', 'run_id'],
                  'additionalProperties': False},
  'annotations': {'readOnlyHint': False,
                  'destructiveHint': True,
                  'idempotentHint': True,
                  'openWorldHint': False}},
 {'name': 'ka_evidence_check',
  'description': 'Check environment, run or claim evidence from a specification. Save a report and '
                 'return bounded findings.',
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
                                               'maxLength': 1024}},
                  'required': ['project', 'spec_path'],
                  'additionalProperties': False},
  'annotations': {'readOnlyHint': False,
                  'destructiveHint': False,
                  'idempotentHint': False,
                  'openWorldHint': False}},
 {'name': 'ka_evidence_import',
  'description': 'Validate and record external evidence, preserving source and unverified origin.',
  'inputSchema': {'type': 'object',
                  'properties': {'project': {'type': 'string',
                                             'description': 'Absolute research project directory.',
                                             'minLength': 1,
                                             'maxLength': 1024},
                                 'manifest_path': {'type': 'string',
                                                   'description': 'Path to a versioned JSON '
                                                                  'specification; validated before '
                                                                  'any operation.',
                                                   'minLength': 1,
                                                   'maxLength': 1024}},
                  'required': ['project', 'manifest_path'],
                  'additionalProperties': False},
  'annotations': {'readOnlyHint': False,
                  'destructiveHint': False,
                  'idempotentHint': False,
                  'openWorldHint': False}}]
PUBLIC_NAMES = frozenset(item["name"] for item in DEFINITIONS)


def definition(name):
    return deepcopy(next(item for item in DEFINITIONS if item["name"] == name))


def call_public_tool(name, args):
    from .tool_registry import call_tool
    return call_tool(name, args)
