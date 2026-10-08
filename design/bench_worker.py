"""Trusted bounded evaluation worker. Proposal is always data, never executable code."""
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from build123d import import_step
from . import compiler
from .benchmark import OUTPUT, environment, read_state, seal, unseal
from .bench_rules import family_gates, task_gates
from .worker import build


def evaluate(dest):
    started = time.perf_counter()
    trial = dest.parent.parent
    task = unseal(trial/'task.json')
    state = read_state(trial)
    number = int(dest.name)
    raw_text = (dest/'proposal.txt').read_text()
    if not environment(task):
        return dict(category='stale_environment', eligible=False, error='Evaluator source/version changed', compute_seconds=0.)
    try:
        p = json.loads(raw_text, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON: '+value)))
    except (ValueError, TypeError) as e:
        return dict(category='invalid_json', eligible=False, error=str(e), compute_seconds=time.perf_counter()-started)
    if isinstance(p, dict) and isinstance(p.get('features'), list):
        unsupported = [f.get('op') for f in p['features'] if isinstance(f, dict) and f.get('op') not in compiler.OPS]
        if unsupported:
            return dict(category='outside_catalog', eligible=False, error='Operation outside catalog: '+str(unsupported), compute_seconds=time.perf_counter()-started)
    try:
        p = compiler.validate(p, task['brief'])
    except (ValueError, KeyError, TypeError) as e:
        return dict(category='input_schema', eligible=False, error=str(e), compute_seconds=time.perf_counter()-started)
    current, refpath, _ = compiler.brief(task['brief']['reference_id'])
    if current['brief_sha256'] != task['brief']['brief_sha256']:
        return dict(category='stale_reference', eligible=False, error='Reference/brief changed', compute_seconds=time.perf_counter()-started)
    stage = dest/'cad'
    stage.mkdir()
    actor = state['actor']
    provenance = dict(source='external_llm' if actor['kind'] == 'external_llm' else 'engineer', model=actor['label'],
                      note=f"Trial {state['id']}; attempt {number}; task {task['task_sha256']}; actor {actor['kind']} (user declared)")
    try:
        result = build(p, task['brief']['reference_id'], provenance, stage)
    except Exception as e:
        return dict(category='kernel_execution', eligible=False, error=str(e), compute_seconds=time.perf_counter()-started,
                    diagnosis='Construction failed; this category alone does not establish an LLM or compiler bug.')
    shape = import_step(stage/'bracket.step')
    gates = task_gates(shape, p, task)
    family = family_gates(p, task, refpath, compiler)
    passed = result['eligible'] and all(g['passed'] for g in gates) and all(v['passed'] for v in family)
    out = compiler.OUTPUT/result['revision']
    if out.exists():
        from .service import result as verify
        verify(result['revision'])
    else:
        os.replace(stage, out)
    return dict(format='forge-cad-evaluation-outcome-v1', category='passed' if passed else 'requirements_rejected',
                eligible=passed, revision=result['revision'], task_sha256=task['task_sha256'],
                core_gates=result['gates'], task_gates=gates, family=family, metrics=result['metrics'],
                compute_seconds=time.perf_counter()-started, llm_runtime=False, hardware_verified=False,
                manufacturing_authorized=False)


if __name__ == '__main__':
    dest = Path(sys.argv[1]).resolve()
    if (dest.parent.name != 'attempts' or dest.parent.parent.parent != OUTPUT.resolve()
        or not re.fullmatch('[a-f0-9]{32}', dest.parent.parent.name) or not re.fullmatch('[0-9]{4}', dest.name)):
        raise SystemExit('Invalid internal evaluation directory')
    try:
        seal(dest/'worker-outcome.json', evaluate(dest))
    except Exception as e:
        traceback.print_exc()
        seal(dest/'worker-outcome.json', dict(category='infrastructure', eligible=False, error=str(e), compute_seconds=None))
