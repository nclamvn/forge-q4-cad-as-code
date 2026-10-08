"""Geometry oracles + actual HTTP/worker + durable evidence and replay boundaries."""
import copy
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import Handler, CACHE
from design import benchmark as bench, compiler, service
from design.bench_rules import family_gates, fixture_program, task_gates
from build123d import Box, Pos

model = json.loads((ROOT/'web/default-model.json').read_text())
CACHE[json.dumps(model['spec'], sort_keys=True)] = model


class Quiet(Handler):
    def log_message(self, *args):
        pass


http = ThreadingHTTPServer(('127.0.0.1', 0), Quiet)
url = 'http://127.0.0.1:'+str(http.server_port)
threading.Thread(target=http.serve_forever, daemon=True).start()
checks = []


def request(path, data=None, origin=None, content_type='application/json'):
    headers = {'Content-Type': content_type}
    if origin is not None:
        headers['Origin'] = origin
    req = urllib.request.Request(url+path, data=None if data is None else json.dumps(data).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def create(case, kind='software_fixture', seed=20261008):
    raw = dict(case_id=case, reference='fixture-sensor-v1', seed=seed,
               actor=dict(kind=kind, label='Automated regression fixture'))
    code, v = request('/api/benchmark/create', raw)
    assert code == 200, v
    return v


def attempt(v, p):
    code, j = request('/api/benchmark/submit', dict(trial=v['id'], proposal_text=p if isinstance(p, str) else json.dumps(p)))
    assert code == 200, j
    assert request('/api/benchmark/submit', dict(trial=v['id'], proposal_text='{}'))[0] == 422
    assert request('/api/design/start', dict(reference='fixture-sensor-v1', program=compiler.example(compiler.brief()[0]),
                   provenance=dict(source='engineer', model='manual', note='Concurrency boundary probe')))[0] == 422
    deadline = time.monotonic()+95
    while time.monotonic() < deadline:
        code, trial = request('/api/benchmark/trial?trial='+v['id'])
        assert code == 200, trial
        if trial['pending'] is None:
            return trial
        time.sleep(.25)
    raise AssertionError('Evaluation worker timed out')


try:
    # Independent numerical corridor oracle: solid material inside requested slot must fail.
    b, ref, _ = compiler.brief()
    task = dict(brief=b, rules=[dict(id='void', kind='clear_circle', xy_mm=[0,0], diameter_mm=10)])
    gates = task_gates(Pos(0,0,2)*Box(30,30,4), {'parameters':{}}, task)
    assert not gates[0]['passed'] and abs(gates[0]['actual']['overlap_mm3']-100*3.141592653589793)<1e-6
    timer = dict(timer_started_at=100., elapsed_seconds=7.)
    assert bench.elapsed(timer, 112.) == 19.
    try:
        bench.elapsed(timer, 99.)
        raise AssertionError('Clock regression accepted')
    except ValueError:
        pass
    checks.append(dict(check='Independent cylindrical void-volume and accumulated timer oracle; clock regression rejected', passed=True))
    human = dict(task_sha256='same', status='closed', accepted_attempt=1, current_environment=True,
                 accepted_artifacts_valid=True, actor=dict(kind='engineer'), elapsed_seconds=100)
    model = {**human, 'actor':dict(kind='external_llm'), 'elapsed_seconds':50}
    assert bench.pair_trials([human, model])[0]['elapsed_ratio'] == .5
    for field, value in [('task_sha256','different'), ('status','open'), ('accepted_attempt',None),
                         ('current_environment',False), ('accepted_artifacts_valid',False), ('actor',dict(kind='software_fixture'))]:
        assert bench.pair_trials([human, {**model, field:value}]) == []
    checks.append(dict(check='Synthetic in-memory pairing oracle: equal task, closed pass, current source and intact artifacts required; software fixtures excluded',passed=True))

    v = create('cable')
    same = create('cable', 'engineer')
    assert same['task_sha256'] == v['task_sha256']
    assert request('/api/benchmark/create', dict(case_id='cable', reference='fixture-sensor-v1', seed=True, actor=dict(kind='engineer',label='x')))[0] == 422
    assert request('/api/benchmark/submit',dict(trial=v['id'],proposal_text='{}'))[0] == 422
    assert request('/api/benchmark/timer',dict(trial=v['id'],action='start'),origin='http://evil.test')[0] == 403
    assert request('/api/benchmark/timer',dict(trial=v['id'],action='start'),content_type='text/plain')[0] == 422
    assert request('/api/benchmark/trial?trial=../secret')[0] == 422
    code,c = request('/api/benchmark/context?trial='+v['id'])
    assert code == 200 and 'example' not in c and not c['llm_runtime']
    assert request('/api/benchmark/fixture',dict(trial=same['id']))[0] == 422
    assert request('/api/benchmark/timer',dict(trial=v['id'],action='start'))[0] == 200
    v = attempt(v, '{invalid')
    assert v['attempts'][-1]['outcome']['category'] == 'invalid_json'
    bad = copy.deepcopy(v['task']['baseline_program'])
    bad['features'][0]['op'] = 'loft'
    v = attempt(v,bad)
    assert v['attempts'][-1]['outcome']['category'] == 'outside_catalog'
    v = attempt(v,v['task']['baseline_program'])
    assert v['attempts'][-1]['outcome']['category'] == 'requirements_rejected'
    assert all(g['passed'] for g in v['attempts'][-1]['outcome']['core_gates'])
    assert request('/api/benchmark/close',dict(trial=v['id'],accepted_attempt=3))[0] == 422
    v = attempt(v,fixture_program(v['task'],compiler))
    assert v['attempts'][-1]['eligible']
    assert request('/api/benchmark/context?trial='+v['id'])[1]['feedback']['attempt'] == 4
    code,v = request('/api/benchmark/close',dict(trial=v['id'],accepted_attempt=4))
    assert code == 200 and v['status'] == 'closed'
    assert request('/api/benchmark/submit',dict(trial=v['id'],proposal_text='{}'))[0] == 422
    assert request('/api/benchmark/index')[1]['pairs'] == []
    checks.append(dict(check='Actual HTTP, bounded workers, invalid JSON/catalog classification; generic CAD passing cannot bypass independent task; failed candidate cannot be accepted; fixtures excluded from comparisons',passed=True,trial=v['id'],attempts=4))

    for case in ['lightweight','family']:
        trial = create(case)
        request('/api/benchmark/timer',dict(trial=trial['id'],action='start'))
        p = fixture_program(trial['task'],compiler)
        if case == 'family':
            fake = copy.deepcopy(p)
            fake['features'][0]['profile']['width'] = 90
            outcomes = family_gates(fake,trial['task'],ref,compiler)
            assert not all(o['passed'] for o in outcomes)
        trial = attempt(trial,p)
        assert trial['attempts'][-1]['eligible'],trial['attempts'][-1]['outcome']
        if case == 'family':
            assert [o['actual_width_mm'] for o in trial['attempts'][-1]['outcome']['family']] == [88,94,98]
        code,trial = request('/api/benchmark/close',dict(trial=trial['id'],accepted_attempt=1))
        assert code == 200
        with urllib.request.urlopen(url+'/api/benchmark/export?trial='+trial['id']) as response:
            data=response.read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            manifest=json.loads(z.read('MANIFEST.json'))
            for name,h in manifest['files'].items():
                assert hashlib.sha256(z.read(name)).hexdigest()==h
            with tempfile.TemporaryDirectory() as temp:
                z.extractall(temp)
                r=subprocess.run([sys.executable,str(Path(temp)/'verify.py')],capture_output=True,text=True,timeout=40)
                assert r.returncode==0,(r.stdout,r.stderr)
        checks.append(dict(check=case+' actual BREP task and standalone evidence replay; no ignored width parameter passes family checks',passed=True,trial=trial['id'],evidence_bytes=len(data)))

    # Digest corruption is fail-loud; original state restored after this adversarial probe.
    path=bench.folder(v['id'])/'session.json'
    original=path.read_bytes()
    try:
        envelope=json.loads(original);envelope['payload']['actor']['kind']='external_llm';path.write_text(json.dumps(envelope))
        assert request('/api/benchmark/trial?trial='+v['id'])[0]==422
    finally:
        path.write_bytes(original)
    original_sources=bench.sources
    try:
        bench.sources=lambda:{'modified':'source'}
        assert not request('/api/benchmark/trial?trial='+v['id'])[1]['current_environment']
    finally:
        bench.sources=original_sources
    persisted=bench.read_state(bench.folder(v['id']))
    assert persisted['accepted_attempt']==4 and len(persisted['attempts'])==4
    checks.append(dict(check='Durable trial/events/proposal/outcome fingerprints, corruption rejection and changed evaluator detection; all data remains user-declared, not authenticated',passed=True))
    names=['server.py','design/benchmark.py','design/bench_rules.py','design/bench_worker.py','design/bench_verify.py','tests/benchmark_test.py']
    report=dict(status='passed',checks=checks,llm_quality_benchmarked=False,hardware_verified=False,
                source_sha256={**bench.sources(),**{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}})
    (ROOT/'reports/robotics/benchmark-tests.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
finally:
    http.shutdown()
    http.server_close()
