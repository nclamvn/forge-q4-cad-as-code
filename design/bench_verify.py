"""Standalone evidence verifier, copied as verify.py into evaluation archives."""
import hashlib
import importlib.util
import json
import re
import tempfile
import zipfile
from pathlib import Path
from build123d import import_step


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def main(root):
    manifest = json.loads((root/'MANIFEST.json').read_text())
    for name, digest in manifest['files'].items():
        path = (root/name).resolve()
        if not path.is_relative_to(root.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Evidence file mismatch: '+name)
    trial = json.loads((root/'trial.json').read_text())
    task = json.loads((root/'task.json').read_text())
    candidates = [a for a in trial['attempts'] if a.get('revision')]
    if not candidates:
        raise ValueError('Trial has no CAD candidate to verify')
    number = trial['accepted_attempt'] or candidates[-1]['number']
    archive_path = root/'attempts'/f'{number:04d}'/'FORGE-AI-CAD.zip'
    with tempfile.TemporaryDirectory() as temp:
        dest = Path(temp)
        with zipfile.ZipFile(archive_path) as archive:
            cad_manifest = json.loads(archive.read('MANIFEST.json'))
            for name, digest in cad_manifest['files'].items():
                if not re.fullmatch('[A-Za-z0-9_.-]+', name):
                    raise ValueError('Unexpected CAD archive path')
                content = archive.read(name)
                if hashlib.sha256(content).hexdigest() != digest:
                    raise ValueError('CAD archive mismatch: '+name)
                (dest/name).write_bytes(content)
        compiler = module('recorded_compiler', dest/'feature_compiler.py')
        for name, digest in task['source_sha256'].items():
            if hashlib.sha256((root/'evaluator'/name).read_bytes()).hexdigest() != digest:
                raise ValueError('Recorded evaluator source mismatch')
        if hashlib.sha256((dest/'feature_compiler.py').read_bytes()).hexdigest() != task['source_sha256']['design/compiler.py']:
            raise ValueError('CAD and evaluator compiler differ')
        if compiler.sha({k:v for k,v in task.items() if k != 'task_sha256'}) != task['task_sha256']:
            raise ValueError('Task hash mismatch')
        rules = module('recorded_rules', root/'evaluator/design/bench_rules.py')
        p = compiler.validate(json.loads((dest/'program.json').read_text()), task['brief'])
        shape, _ = compiler.evaluate_graph(p, False)
        cad = import_step(dest/'bracket.step')
        if abs(cad.volume-shape.volume)/shape.volume > 1e-8:
            raise ValueError('Rebuilt BREP/STEP volume mismatch')
        gates, _, _ = compiler.checks(shape, p, task['brief'], dest/'sensor-original.step')
        gates += rules.task_gates(shape, p, task)
        family = rules.family_gates(p, task, dest/'sensor-original.step', compiler)
        passed = all(g['passed'] for g in gates) and all(v['passed'] for v in family)
        result = dict(trial=trial['id'], attempt=number, independently_recomputed_pass=passed,
                      gates=gates, family=family, hardware_verified=False, llm_runtime=False)
        (root/'verification.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(dict(trial=trial['id'], attempt=number, passed=passed, family_count=len(family))))
        return passed


if __name__ == '__main__':
    raise SystemExit(0 if main(Path(__file__).resolve().parent) else 1)
