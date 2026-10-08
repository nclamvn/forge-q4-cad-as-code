"""Integration gates, independent mass sum, SI inertia, actual solver, tamper rejection."""
import json,sys,hashlib,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from build123d import import_step
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from design.integration import build,load,sources
from design.service import result
from robotics.model import compile_robot,verified_package
revision=sys.argv[1] if len(sys.argv)>1 else 'ad4b6af35e412c2d'
r=build(revision);r,m=load(r['revision']);base=json.loads((ROOT/'web/default-model.json').read_text())
assert r['geometry_passed'] and not r['engineering_release_eligible']
assert all(g['passed'] for g in r['gates'] if g['id']!='mass_budget')
assert len(m['instances'])==49 and len(import_step(ROOT/m['step_url'].lstrip('/')).solids())==49
old=sum(p['mass_kg']*p['count'] for p in base['parts'].values())
new=sum(p['mass_kg']*p['count'] for p in m['parts'].values())
assert abs((new-old)-r['mass_delta_kg'])<1e-10
assert r['mass_budget_passed']==(r['mass_after_kg']<=base['spec']['target_mass_kg'])
assert abs(r['payload_budget_kg']-(base['spec']['target_mass_kg']-new-base['spec']['electronics_mass_kg']))<1e-10
desc=compile_robot(m);meta=verified_package(desc['directory'])
assert abs(meta['mass_kg']-r['mass_after_kg'])<1e-10
assert len(meta['links']['base_link']['instances'])==len([i for i in m['instances'] if not any(i['id'].startswith(s) for s in ['front_','rear_'])])
urdf=ET.parse(desc['package']/'forge_q4.urdf').getroot()
base_link=urdf.find("link[@name='base_link']")
assert len([v for v in base_link.findall('visual') if v.get('name','').startswith('ai_')])==7
for link in meta['links'].values():assert np.linalg.eigvalsh(link['inertia_kg_m2']).min()>0
for s in r['simulation_summary']:
 assert abs(s['elapsed_simulation_s']-3)<1e-9 and len(s['summary']['joints'])==12
 assert all(np.isfinite(j['torque_nm']) for j in s['summary']['joints'])
file=ROOT/'artifacts'/r['revision']/'parts/ai_bracket.step';original=file.read_bytes()
try:
 file.write_bytes(original+b'\nTAMPER')
 try:load(r['revision']);raise AssertionError('Tampered CAD accepted')
 except ValueError as e:assert 'mismatch' in str(e)
finally:file.write_bytes(original)
try:build('0'*16);raise AssertionError('Unknown design accepted')
except ValueError:pass
report=dict(status='passed',cad_revision=base['revision'],integration_revision=r['revision'],design_revision=revision,
 checks=[dict(check=c,passed=True) for c in ['Actual cover bores, bearing rings, assembled BREP overlap and 49-solid STEP reread',
 'Independent per-part mass sum and honest original 7 kg mass-budget gate',
 'URDF includes seven attached instances; SI inertia positive and robot package verified',
 'Actual MuJoCo stand/trot 3 s each: finite joint telemetry; endurance not certified',
 'Mutated STEP and unknown revision rejected']],
 source_sha256={**sources(),**{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['robotics/service.py','server.py','tests/integration_test.py']}},
 hardware_verified=False,ros2_launch_tested=False)
(ROOT/'reports/robotics/integration-tests.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
