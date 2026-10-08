"""Package only public source and the verified default CAD snapshot."""
import base64
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    '.gitignore', '.gitattributes', 'README.md', 'DESIGN.md', 'Start.command', 'kernel.py',
    'technical.py', 'server.py', 'launch.py', 'spec.yaml', 'requirements.txt',
    'requirements-test.txt', 'requirements-simulation.txt', 'requirements-lock.txt', 'package.json', 'package-lock.json',
)
REPORT_FILES = (
    'reports/kernel-tests.json', 'reports/api-tests.json',
    'reports/monochrome/dossier-tests.json',
    'reports/monochrome/dossier-browser.json',
    'reports/motion/kinematics.json', 'reports/motion/browser-review.json',
    'reports/robotics/model-tests.json', 'reports/robotics/qualification.json',
    'reports/robotics/api-tests.json', 'reports/robotics/browser-review.json',
    'reports/robotics/operations-tests.json', 'reports/robotics/engineering-tests.json',
    'reports/robotics/engineering-api-tests.json', 'reports/robotics/engineering-example.json',
    'reports/robotics/engineering-browser.json',
    'reports/robotics/deployment-tests.json', 'reports/robotics/deployment-browser.json',
    'reports/robotics/feature-tests.json', 'reports/robotics/feature-api-tests.json',
    'reports/robotics/feature-browser.json',
    'reports/robotics/benchmark-tests.json', 'reports/robotics/benchmark-browser.json',
    'reports/robotics/integration-tests.json', 'reports/robotics/customer-browser.json',
    'reports/robotics/customer-api.json',
)


def package():
    model = json.loads((ROOT / 'web/default-model.json').read_text())
    revision = model['revision']
    if not re.fullmatch(r'[a-f0-9]{12}', revision):
        raise ValueError('Invalid CAD revision')
    if model['compiler_hash'] != hashlib.sha256((ROOT / 'kernel.py').read_bytes()).hexdigest()[:12]:
        raise ValueError('Snapshot does not match the CAD compiler')
    if model['documentation']['generator_hash'] != hashlib.sha256((ROOT / 'technical.py').read_bytes()).hexdigest()[:12]:
        raise ValueError('Snapshot does not match the drawing generator')

    downloads = {
        'FORGE-Q4.step': model['step_url'],
        'FORGE-Q4-CAD-A3.pdf': model['documentation']['pdf_url'],
        'FORGE-Q4-CAD-dossier.zip': model['documentation']['zip_url'],
    }
    for name, url in downloads.items():
        source = (ROOT / url.lstrip('/')).resolve()
        if not source.is_relative_to(ROOT / 'artifacts' / revision):
            raise ValueError('Download outside the default revision')
        shutil.copyfile(source, ROOT / name)

    html = (ROOT / 'FORGE-Q4.html').read_text()
    embedded = re.search(r"window.__FORGE_STEP__='data:application/step;base64,([^']+)'", html)
    if not embedded or base64.b64decode(embedded[1]) != (ROOT / 'FORGE-Q4.step').read_bytes():
        raise ValueError('Rebuild the standalone HTML before packaging')
    if '<script type="module" src=' in html or '<link rel="stylesheet"' in html:
        raise ValueError('Standalone HTML has external entry points')

    api = json.loads((ROOT / 'reports/api-tests.json').read_text())
    dossier = json.loads((ROOT / 'reports/monochrome/dossier-tests.json').read_text())
    if api.get('status') != 'passed' or api['variants'][0]['revision'] != revision:
        raise ValueError('Run API tests for this snapshot before release')
    if dossier.get('status') != 'passed' or dossier['revision'] != revision:
        raise ValueError('Run dossier tests for this snapshot before release')
    motion = json.loads((ROOT / 'reports/motion/kinematics.json').read_text())
    if motion.get('status') != 'passed' or motion.get('cad_revision') != revision:
        raise ValueError('Run motion tests for this snapshot before release')
    for name, sha in motion['source_sha256'].items():
        if hashlib.sha256((ROOT / 'web' / name).read_bytes()).hexdigest() != sha:
            raise ValueError('Motion source changed; rerun npm run test:motion')
    robotics=json.loads((ROOT/'reports/robotics/model-tests.json').read_text())
    physics_api=json.loads((ROOT/'reports/robotics/api-tests.json').read_text())
    qualification=json.loads((ROOT/'reports/robotics/qualification.json').read_text())
    for report in (robotics,physics_api):
        if report.get('status')!='passed' or report.get('cad_revision')!=revision:
            raise ValueError('Run robotics and physics API tests for this snapshot')
        for name,sha in report['source_sha256'].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:
                raise ValueError('Robotics source changed: '+name)
    for name in ['operations-tests','engineering-tests','engineering-api-tests']:
        report=json.loads((ROOT/f'reports/robotics/{name}.json').read_text())
        if report.get('status')!='passed' or report.get('cad_revision')!=revision:
            raise ValueError('Run engineering / operations checks for the current snapshot')
        for path,sha in report['source_sha256'].items():
            if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:
                raise ValueError('Engineering / operating source changed: '+path)
    if qualification['model_revision']!=robotics['model_revision']:
        raise ValueError('Qualification model does not match the tested model')
    # Historical browser reports remain historical. The customer review exercises
    # all workspaces against one frozen source set and supersedes their UI gates.
    for name in ('deployment-tests', 'feature-tests', 'feature-api-tests', 'benchmark-tests', 'integration-tests', 'customer-api', 'customer-browser'):
        report=json.loads((ROOT/f'reports/robotics/{name}.json').read_text())
        if report.get('status')!='passed':
            raise ValueError('Run current workbench checks before release: '+name)
        for path,sha in report['source_sha256'].items():
            if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:
                raise ValueError('Workbench source changed: '+path)
    if physics_api['model_revision']!=robotics['model_revision']:
        raise ValueError('Physics API and numerical tests use different models')
    robot_zip=ROOT/'FORGE-Q4-Robotics.zip'
    with zipfile.ZipFile(robot_zip) as archive:
        robot_manifest=json.loads(archive.read('forge_q4_description/MANIFEST.json'))
        if robot_manifest['model_revision']!=robotics['model_revision']:
            raise ValueError('Rebuild the default robotics download')
        for name,sha in robot_manifest['files'].items():
            if hashlib.sha256(archive.read('forge_q4_description/'+name)).hexdigest()!=sha:
                raise ValueError('Robotics download hash mismatch: '+name)

    paths = {ROOT / name for name in (*SOURCE_FILES, *REPORT_FILES, *downloads, 'FORGE-Q4.html', 'FORGE-Q4-Robotics.zip')}
    for folder in ('web', 'tools', 'tests', 'docs', 'robotics', 'design', f'artifacts/{revision}'):
        paths.update((ROOT / folder).rglob('*'))
    files = sorted(p for p in paths if p.is_file() and not p.is_symlink()
                   and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.pyo')
                   and p.name != '.DS_Store')
    missing = [name for name in (*SOURCE_FILES, *REPORT_FILES) if not (ROOT / name).is_file()]
    if missing:
        raise ValueError(f'Missing public source files: {missing}')
    manifest = {
        'edition': 'public-cad-as-code',
        'cad_revision': revision,
        'robot_model_revision':robotics['model_revision'],
        'drawing_generator': model['documentation']['generator_hash'],
        'files': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
    }
    manifest_file = ROOT / 'MANIFEST.json'
    manifest_file.write_text(json.dumps(manifest, indent=2) + '\n')
    files.append(manifest_file)
    out = ROOT / 'FORGE-Q4-PoC.zip'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, 'FORGE-Q4-PoC/' + str(path.relative_to(ROOT)))
    with zipfile.ZipFile(out) as archive:
        if archive.testzip() is not None:
            raise ValueError('Invalid ZIP')
        for path, sha in manifest['files'].items():
            if hashlib.sha256(archive.read('FORGE-Q4-PoC/' + path)).hexdigest() != sha:
                raise ValueError(f'ZIP hash mismatch: {path}')
    print(f'{out.name}: {out.stat().st_size/1048576:.2f} MiB, {len(files)} files; '
          f'revision {revision}; embedded STEP and ZIP hashes verified.')


if __name__ == '__main__':
    package()
