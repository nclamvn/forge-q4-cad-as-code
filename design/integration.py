"""Verified feature CAD -> a concrete Q4 mounting study -> SI robot exports.

This is a computer-validated mounting study, not a manufacturing release.
Only the fixed mounting recipe runs; no proposal code is executed.
"""
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from . import service
from .compiler import ROOT, overlap, sha, exact

JOBS = ROOT/'integration-jobs'
RUNNING = set()


def sources():
    return {n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
            ['design/integration.py','robotics/model.py','robotics/simulation.py',
             'robotics/operations.py','robotics/profile.yaml','kernel.py']}


def load(revision):
    if not isinstance(revision,str) or not re.fullmatch('[a-f0-9]{12}',revision):
        raise ValueError('Invalid integrated revision')
    dest=ROOT/'artifacts'/revision
    manifest=json.loads((dest/'integration-manifest.json').read_text())
    if manifest['revision']!=revision:raise ValueError('Integrated revision mismatch')
    for name,digest in manifest['files'].items():
        path=(dest/name).resolve()
        if not path.is_relative_to(dest.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Integrated artifact mismatch: '+name)
    r=json.loads((dest/'integration.json').read_text())
    candidate=service.result(r['design_revision'])
    if r['source_sha256']!=sources() or not candidate['current_sources_match']:
        raise ValueError('Integration source changed; rebuild the mounting study')
    r['downloads']={k:f'/artifacts/{revision}/{v}' for k,v in
                    [('step','forge-q4.step'),('package','FORGE-Q4-Integrated.zip'),
                     ('report','integration.json'),('simulation','simulation.json')]}
    return r, json.loads((dest/'model.json').read_text())


def build(design_revision):
    from build123d import Cylinder, Pos, Compound, Location, export_step, import_step
    from kernel import tessellation
    from robotics.model import compile_robot, verified_package
    from robotics.service import public_model
    from robotics.simulation import Simulator
    r=service.result(design_revision)
    if not r['eligible'] or not r['current_sources_match']:
        raise ValueError('Design must pass current geometry gates')
    base=json.loads((ROOT/'web/default-model.json').read_text())
    if base['compiler_hash']!=hashlib.sha256((ROOT/'kernel.py').read_bytes()).hexdigest()[:12]:
        raise ValueError('Default CAD source changed; rebuild it first')
    # Fingerprint every default geometry input, not just the spec/revision.
    from robotics.model import input_fingerprint
    base_hash=input_fingerprint(base)
    source=sources()
    revision=sha(dict(base=base_hash,design=design_revision,sources=source,recipe='top-deck-x55-6mm-v1'))[:12]
    dest=ROOT/'artifacts'/revision
    if dest.exists():return load(revision)[0]
    with tempfile.TemporaryDirectory(prefix='.integration-',dir=ROOT/'artifacts') as temp:
        stage=Path(temp);(stage/'parts').mkdir()
        model=copy.deepcopy(base);model['revision']=revision
        shapes={k:import_step(ROOT/p['step_url'].lstrip('/')) for k,p in base['parts'].items()}
        mount=next(i for i in model['instances'] if i['id']=='top_cover')
        holes=r['brief']['carrier']['mount_holes']
        cover=shapes['cover'];gates=[]
        def gate(name,passed,actual,requirement):
            gates.append(dict(id=name,name=name.replace('_',' '),method='OCCT / BREP',detail=requirement,passed=bool(passed),actual=actual,requirement=requirement))
        for i,h in enumerate(holes):
            x,y=55+h['x_mm'],h['y_mm']
            cover=cover-Pos(x,y,0)*Cylinder(h['diameter_mm']/2,8)
            ring=Pos(x,y,0)*Cylinder(h['diameter_mm']/2+2,3)-Pos(x,y,0)*Cylinder(h['diameter_mm']/2+.15,3)
            gate('cover_web_'+str(i+1),overlap(cover,ring)/ring.volume>=.98,
                 overlap(cover,ring)/ring.volume,'98% of 2 mm bearing ring retained in actual Q4 cover')
            gate('cover_bore_'+str(i+1),overlap(cover,Pos(x,y,0)*Cylinder(h['diameter_mm']/2-.01,8))<.001,
                 [x,y,h['diameter_mm']],'Actual Q4 cover through-bore aligned to carrier')
        shapes['cover']=cover
        folder=ROOT/'design-output'/design_revision
        shapes['ai_bracket']=import_step(folder/'bracket.step')
        shapes['ai_carrier']=import_step(folder/'carrier.step')
        shapes['ai_sensor']=import_step(folder/'sensor-original.step')
        shapes['ai_spacer']=Pos(0,0,3)*Cylinder(5,6)-Pos(0,0,3)*Cylinder(2.6,8)
        deck_top=mount['position_mm'][2]+1.5
        assembly_origin=[55.,0.,deck_top+14.]
        def instance(part,id,position):
            model['instances'].append(dict(part=part,id=id,position_mm=position,rotation_deg=[0,0,0],explode_mm=[0,0,160]))
        instance('ai_bracket','ai_bracket',assembly_origin)
        instance('ai_carrier','ai_carrier',assembly_origin)
        p=r['program']['parameters'];t=r['brief']['requirements']['plate_thickness_mm']
        instance('ai_sensor','ai_sensor',[55+p.get('sensor_shift_x',0),p.get('sensor_shift_y',0),assembly_origin[2]+t])
        for i,h in enumerate(holes):instance('ai_spacer','ai_spacer_'+str(i+1),[55+h['x_mm'],h['y_mm'],deck_top])
        for key,shape in shapes.items():
            old=model['parts'].get(key)
            count=sum(i['part']==key for i in model['instances'])
            rho=1010. if key=='ai_sensor' else 2700.
            mass=shape.volume*rho/1e9
            if old:
                mass=old['mass_kg']*shape.volume/old['volume_mm3'];part=copy.deepcopy(old)
            else:
                part=dict(name={'ai_bracket':'Gá AI','ai_carrier':'Tấm adapter','ai_sensor':'Sensor tham chiếu','ai_spacer':'Trụ đỡ 6 mm'}[key],
                          role='metal' if key!='ai_sensor' else 'dark',mass_basis=f'V × assumed density {rho:g} kg/m³',
                          part_number='Q4-'+key.upper(),part_revision=revision)
            # Tessellation modifies OCCT cache; preserve BREP used for mass/clearance.
            part.update(**tessellation(copy.deepcopy(shape)),count=count,mass_kg=mass,volume_mm3=shape.volume,
                        valid=bool(shape.is_valid),solids=len(shape.solids()),com_mm=list(shape.center()),
                        step_url=f'/artifacts/{revision}/parts/{key}.step')
            export_step(shape,stage/'parts'/f'{key}.step');model['parts'][key]=part
        placed={i['id']:shapes[i['part']].moved(Location(i['position_mm'],i['rotation_deg'])) for i in model['instances']}
        additions=[i['id'] for i in model['instances'] if i['part'].startswith('ai_')]
        max_collision=max((overlap(placed[a],placed[b]) for a in additions for b in placed if a!=b),default=0)
        gate('assembled_interference',max_collision<.01,max_collision,'No volumetric overlap in home pose; touching mating faces allowed')
        loaded=sum(v['mass_kg']*v['count'] for v in model['parts'].values())+model['spec']['electronics_mass_kg']+model['spec']['payload_kg']
        model['metrics'].update(loaded_mass_kg=loaded,mass_kg=loaded-model['spec']['payload_kg'],part_count=len(placed),unique_parts=len(shapes),
                                height_mm=max(s.bounding_box().max.Z for s in placed.values()))
        gate('mass_budget',loaded<=model['spec']['target_mass_kg'],loaded,'Integrated loaded mass <= original declared target; densities assumed')
        assembly_parts=[]
        for id,s in placed.items():
            obj=copy.deepcopy(s);obj.label=id;assembly_parts.append(obj)
        assembly=Compound(children=assembly_parts)
        export_step(assembly,stage/'forge-q4.step');again=import_step(stage/'forge-q4.step')
        gate('assembly_step',again.is_valid and len(again.solids())==len(placed) and abs(again.volume-assembly.volume)/assembly.volume<2e-6,
             len(again.solids()),'STEP reread: 49 solids and volume within 2 ppm')
        if not all(g['passed'] for g in gates if g['id']!='mass_budget'):raise ValueError('Mounting geometry failed: '+json.dumps([g for g in gates if not g['passed']]))
        model['step_url']=f'/artifacts/{revision}/forge-q4.step'
        # Main CAD dossier remains explicitly the base robot dossier. Integration
        # has separate exports so no old drawing is relabelled as newly checked.
        model['integration']=dict(design_revision=design_revision,base_revision=base['revision'])
        model['proof']={'checks':gates,'analytic':[],'clearance_samples':[],
                        'roundtrip':dict(valid=True,solid_count=len(placed),relative_error=abs(again.volume-assembly.volume)/assembly.volume)}
        model['limitations']+=['Top-deck mounting study: cover drilled, 6 mm spacers, 8 mm adapter. Fasteners, cover load capacity, cable routing and FEA not qualified.']
        (stage/'model.json').write_text(json.dumps(model,ensure_ascii=False))
        os.rename(stage,dest)
    # Geometry must be published for the existing SI compiler to read its STEP.
    try:
        robot=compile_robot(model);robot_base=compile_robot(base)
        verified_package(robot['directory'])
        sims=[]
        for motion in ('stand','trot'):
            sim=Simulator(robot,motion);sim.control('resume')
            for _ in range(30):sim.step(.1)
            report=sim.report();sims.append(report)
        (dest/'simulation.json').write_text(json.dumps(sims,ensure_ascii=False,allow_nan=False))
        before=robot_base['metadata']['links']['base_link'];after=robot['metadata']['links']['base_link']
        report=dict(format='forge-q4-integration-v1',revision=revision,design_revision=design_revision,
                    base_revision=base['revision'],base_input_sha256=base_hash,source_sha256=source,
                    mass_before_kg=robot_base['mass'],mass_after_kg=robot['mass'],mass_delta_kg=robot['mass']-robot_base['mass'],
                    mass_budget_passed=loaded<=model['spec']['target_mass_kg'],
                    payload_budget_kg=max(0,model['spec']['target_mass_kg']-model['metrics']['mass_kg']),
                    geometry_passed=True,engineering_release_eligible=False,
                    base_com_before_m=before['com_m'],base_com_after_m=after['com_m'],
                    base_inertia_before_kg_m2=before['inertia_kg_m2'],base_inertia_after_kg_m2=after['inertia_kg_m2'],
                    mounting=dict(origin_mm=assembly_origin,cover_holes_mm=[[55+h['x_mm'],h['y_mm'],h['diameter_mm']] for h in holes],spacer_height_mm=6),
                    gates=gates,robot=public_model(robot),simulation_summary=[dict(motion=m,summary=s['summary'],elapsed_simulation_s=s['elapsed_simulation_s']) for m,s in zip(('stand','trot'),sims)],
                    hardware_verified=False,manufacturing_authorized=False,
                    limitations=['Synthetic reference sensor; its mass adds assumed uniform polymer density, not measured electronics mass.',
                                 'New top-deck holes and stack are a specific mounting study. Screws/nuts omitted; strength and tolerances unqualified.',
                                 'Home-pose BREP clearance only; 3 s runs do not prove locomotion endurance. MuJoCo collision uses convex hulls.',
                                 'ROS 2 URDF/MJCF exported; ROS 2 launch/RViz not executed here.',
                                 'Base dossier still describes base robot. Integrated STEP and this report document the mounting changes.'])
        (dest/'integration.json').write_text(json.dumps(report,ensure_ascii=False,allow_nan=False))
        with zipfile.ZipFile(dest/'FORGE-Q4-Integrated.zip','w',zipfile.ZIP_DEFLATED) as z:
            for file in sorted(dest.rglob('*')):
                if file.is_file() and file.suffix!='.zip':z.write(file,str(file.relative_to(dest)))
            z.write(folder/'FORGE-AI-CAD.zip','feature-cad.zip')
            for file in robot['package'].rglob('*'):
                if file.is_file():z.write(file,'forge_q4_description/'+str(file.relative_to(robot['package'])))
        files={str(f.relative_to(dest)):hashlib.sha256(f.read_bytes()).hexdigest() for f in dest.rglob('*') if f.is_file()}
        (dest/'integration-manifest.json').write_text(json.dumps(dict(revision=revision,files=files),indent=2))
        return load(revision)[0]
    except Exception:
        # Unmanifested stage is never accepted by load(); preserve for diagnosis.
        raise


def job(token):
    if not isinstance(token,str) or not re.fullmatch('[a-f0-9]{32}',token):raise ValueError('Invalid integration job')
    result=json.loads((JOBS/token/'status.json').read_text())
    if result['status']=='running' and token not in RUNNING:result.update(status='interrupted',error='Server restarted; create another integration job')
    return result


def run(token):
    path=JOBS/token
    try:
        with (path/'worker.log').open('wb') as log:
            proc=subprocess.run([sys.executable,'-m','design.integration',str(path)],cwd=ROOT,stdout=log,stderr=log,timeout=180)
        if proc.returncode:raise ValueError((path/'error.txt').read_text() if (path/'error.txt').exists() else 'Integration worker failed')
        state=dict(id=token,status='completed',revision=json.loads((path/'answer.json').read_text())['revision'])
    except Exception as e:state=dict(id=token,status='failed',error=str(e))
    finally:
        (path/'status.json').write_text(json.dumps(state));RUNNING.discard(token)
        with service.LOCK:
            if service.ACTIVE=='integration/'+token:service.ACTIVE=None


def start(raw):
    exact(raw,['design_revision'],'integration request')
    r=service.result(raw['design_revision'])
    if not r['eligible'] or not r['current_sources_match']:raise ValueError('Rebuild and pass geometry before integration')
    with service.LOCK:
        if service.ACTIVE:raise ValueError('A CAD worker is active; wait')
        JOBS.mkdir(exist_ok=True)
        if len(list(JOBS.glob('*/status.json')))>=100:raise ValueError('Integration job store full')
        token=uuid.uuid4().hex;path=JOBS/token;path.mkdir()
        (path/'request.json').write_text(json.dumps(raw))
        state=dict(id=token,status='running');(path/'status.json').write_text(json.dumps(state))
        service.ACTIVE='integration/'+token;RUNNING.add(token)
        threading.Thread(target=run,args=(token,),daemon=True).start();return state


def handle(handler):
    u=urlsplit(handler.path)
    if u.path not in ('/api/integration/start','/api/integration/job','/api/integration/result','/api/integration/model'):return False
    if not service.local(handler):handler.json({'error':'Same-origin localhost only'},403);return True
    try:
        if handler.command=='POST' and u.path.endswith('/start'):
            if handler.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('Use application/json')
            size=int(handler.headers.get('Content-Length','0'))
            if not 0<size<1024:raise ValueError('Request too large')
            handler.json(start(json.loads(handler.rfile.read(size))))
        elif handler.command=='GET' and not u.path.endswith('/start'):
            q=parse_qs(u.query)
            if u.path.endswith('/job'):handler.json(job(q.get('id',[''])[0]))
            else:
                r,m=load(q.get('revision',[''])[0]);handler.json(m if u.path.endswith('/model') else r)
        else:raise ValueError('Wrong HTTP method')
    except (ValueError,KeyError,TypeError,OSError) as e:handler.json({'error':str(e),'gate':'Q4_INTEGRATION'},422)
    return True


if __name__=='__main__':
    path=Path(sys.argv[1]).resolve()
    if path.parent!=JOBS or not re.fullmatch('[a-f0-9]{32}',path.name):raise SystemExit('Invalid internal job')
    try:
        r=build(json.loads((path/'request.json').read_text())['design_revision'])
        (path/'answer.json').write_text(json.dumps(r))
    except Exception as e:
        (path/'error.txt').write_text(str(e));raise
