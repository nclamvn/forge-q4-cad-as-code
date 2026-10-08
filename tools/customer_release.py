"""Freeze a reproducible customer bundle with only selected, declared trial evidence."""
import hashlib,json,shutil,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from design import benchmark,integration
from robotics.model import compile_robot
from tools.release import package

LLM='1015243d1fe54232890fc3d92283ba95'
ENGINEER='30cd3cb38db541c1b82355e305809990'
DESIGN='ea345ca303a25fdc'
INTEGRATION='88b2de0745b9'


def create():
    v=benchmark.view(LLM)
    if not v['accepted_attempt'] or not v['current_environment'] or not v['accepted_artifacts_valid']:raise ValueError('LLM trial not current and accepted')
    report,model=integration.load(INTEGRATION)
    default=json.loads((ROOT/'web/default-model.json').read_text())
    desc=compile_robot(default)
    shutil.copyfile(desc['directory']/'FORGE-Q4-Robotics.zip',ROOT/'FORGE-Q4-Robotics.zip')
    subprocess.run(['node','tools/package.cjs'],cwd=ROOT,check=True)
    package()
    dest=ROOT/'customer-release';dest.mkdir(exist_ok=True)
    (dest/'llm-evidence.zip').write_bytes(benchmark.export_zip(LLM))
    shutil.copyfile(ROOT/'artifacts'/INTEGRATION/'FORGE-Q4-Integrated.zip',dest/'integration.zip')
    curated=[ROOT/'design-output'/DESIGN,ROOT/'design-output/.references/fixture-sensor-v1',
             ROOT/'benchmark-output'/LLM,ROOT/'benchmark-output'/ENGINEER,
             ROOT/'artifacts'/INTEGRATION,desc['directory'],ROOT/'robotics-output'/report['robot']['model_revision']]
    engineering=json.loads((ROOT/'reports/robotics/engineering-tests.json').read_text())['experiment_id']
    experiment=json.loads((ROOT/'engineering-output'/engineering/'report.json').read_text())
    curated.extend([ROOT/'engineering-output'/engineering,ROOT/'artifacts'/experiment['candidate_revision']])
    curated.extend(ROOT/'robotics-output'/m['model_revision'] for m in experiment['models'].values())
    files={}
    with zipfile.ZipFile(ROOT/'FORGE-Q4-PoC.zip') as z:
        for name in z.namelist():
            path=name.removeprefix('FORGE-Q4-PoC/')
            if path!='MANIFEST.json':files[path]=z.read(name)
    for folder in curated:
        for file in sorted(folder.rglob('*')):
            if file.is_file() and file.name!='worker.log':files[str(file.relative_to(ROOT))]=file.read_bytes()
    sources={k:hashlib.sha256(b).hexdigest() for k,b in files.items() if k.startswith(('web/','design/','robotics/','tools/','tests/')) or k in ('server.py','kernel.py','technical.py')}
    release_id=hashlib.sha256(json.dumps({k:hashlib.sha256(b).hexdigest() for k,b in files.items()},sort_keys=True).encode()).hexdigest()[:16]
    status=dict(format='forge-customer-release-v1',release_id=release_id,cad_revision=default['revision'],design_revision=DESIGN,integration_revision=INTEGRATION,
                package_verified=True,clean_install_verified=False,human_comparison_complete=bool(benchmark.summary()['pairs']),
                llm_trial=LLM,human_trial=ENGINEER,source_sha256=sources,
                routes={'cad':'feature-cad.html?design='+DESIGN,'evaluation':'benchmark.html?trial='+LLM,
                        'integration':'integration.html?revision='+INTEGRATION,'physics':'/?integrated='+INTEGRATION+'&workspace=physics&motion=trot&backend=webgl',
                        'engineering':'/?workspace=ai&backend=webgl&experiment='+engineering},
                downloads={'Source & dữ liệu tái lập':'/customer-release/FORGE-Q4-Customer.zip','Bằng chứng lượt LLM':'/customer-release/llm-evidence.zip',
                           'CAD & robot tích hợp':'/customer-release/integration.zip','STEP Q4':default['step_url'],
                           'PDF 14 trang A3':default['documentation']['pdf_url'],'Hồ sơ DXF & STEP':default['documentation']['zip_url']},
                limitations=['One assisted LLM-authored public exercise; no completed human comparison or provider-authenticated receipt.',
                             'Integrated robot exceeds original loaded mass budget; software exposes failure.',
                             'No FEA/GD&T/manufacturing/hardware verification; ROS 2 launch not tested.'])
    # A release is immutable once identified. Clean-install evidence is an external
    # receipt; the delivered source snapshot always states it was pending at freeze.
    (dest/'status.json').write_text(json.dumps(status,indent=2,ensure_ascii=False))
    files['customer-release/status.json']=(dest/'status.json').read_bytes()
    files['customer-release/llm-evidence.zip']=(dest/'llm-evidence.zip').read_bytes()
    files['customer-release/integration.zip']=(dest/'integration.zip').read_bytes()
    manifest=dict(release_id=release_id,files={k:hashlib.sha256(b).hexdigest() for k,b in sorted(files.items())})
    (dest/'MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
    files['MANIFEST.json']=(dest/'MANIFEST.json').read_bytes()
    with zipfile.ZipFile(dest/'FORGE-Q4-Customer.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(files.items()):z.writestr('FORGE-Q4-Customer/'+name,data)
    with zipfile.ZipFile(dest/'FORGE-Q4-Customer.zip') as z:
        assert z.testzip() is None
        for name,digest in manifest['files'].items():
            if hashlib.sha256(z.read('FORGE-Q4-Customer/'+name)).hexdigest()!=digest:raise ValueError('Release ZIP mismatch: '+name)
    print(json.dumps(dict(release_id=release_id,files=len(files),bytes=(dest/'FORGE-Q4-Customer.zip').stat().st_size)))

if __name__=='__main__':create()
