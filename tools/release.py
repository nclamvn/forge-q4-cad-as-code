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
    'requirements-test.txt', 'package.json', 'package-lock.json',
)
REPORT_FILES = (
    'reports/kernel-tests.json', 'reports/api-tests.json',
    'reports/monochrome/dossier-tests.json',
    'reports/monochrome/dossier-browser.json',
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

    paths = {ROOT / name for name in (*SOURCE_FILES, *REPORT_FILES, *downloads, 'FORGE-Q4.html')}
    for folder in ('web', 'tools', 'tests', 'docs', f'artifacts/{revision}'):
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
