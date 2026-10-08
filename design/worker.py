"""Fixed trusted CAD worker. CLI input is an internal job ID, never source code."""
import copy,hashlib,json,os,sys,time,traceback,zipfile
import importlib.metadata
import OCP
from pathlib import Path
from build123d import Box,Compound,Cylinder,Pos,export_step,import_step
from .compiler import ROOT,OUTPUT,brief,validate,evaluate_graph,checks,mesh,sha,canonical,overlap
from .drawings import generate


def engine_versions():
    return dict(build123d=importlib.metadata.version('build123d'),occt=getattr(OCP,'__version__','unknown'))


def source_hashes():
    return {n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['design/compiler.py','design/drawings.py','design/worker.py','technical.py']}


def build(raw,reference,provenance,dest):
    started=time.perf_counter();b,refpath,sensor_mesh=brief(reference);p=validate(raw,b);sources=source_hashes()
    revision=sha(dict(program=p,brief=b,source_sha256=sources,provenance=provenance,engine_versions=engine_versions()))[:16]
    shape,features=evaluate_graph(p)
    if not shape.solids() or shape.volume<.001:raise ValueError('Selected result has no volumetric solid')
    gates,holes,sensor=checks(shape,p,b,refpath)
    shape.label=p['name'];export_step(shape,dest/'bracket.step');again=import_step(dest/'bracket.step')
    roundtrip=abs(again.volume-shape.volume)/shape.volume
    gates.append(dict(id='step_roundtrip',passed=again.is_valid and len(again.solids())==len(shape.solids()) and roundtrip<1e-8,actual=roundtrip,requirement='STEP reread volume delta <1e-8; same solid count'))
    carrier=Pos(0,0,-4)*Box(120,90,8)
    for h in b['carrier']['mount_holes']:carrier=carrier-Pos(h['x_mm'],h['y_mm'],-4)*Cylinder(h['diameter_mm']/2,10)
    sensor.label='REFERENCE SENSOR / '+b['sensor']['provenance'];carrier.label='SYNTHETIC RECEIVING PLATE'
    export_step(carrier,dest/'carrier.step');(dest/'sensor-original.step').write_bytes(refpath.read_bytes())
    assembly=Compound(children=[copy.deepcopy(shape),copy.deepcopy(sensor),copy.deepcopy(carrier)]);export_step(assembly,dest/'assembly.step')
    eligible=all(g['passed'] for g in gates)
    docs=generate(shape,p,b,holes,revision,dest,eligible)
    box=shape.bounding_box()
    result=dict(format='forge-feature-result-v1',revision=revision,brief_sha256=b['brief_sha256'],program=p,brief=b,
                proposal_provenance=provenance,source_sha256=sources,engine_versions=engine_versions(),eligible=eligible,manufacturing_authorized=False,hardware_verified=False,llm_runtime=False,
                metrics=dict(volume_mm3=shape.volume,mass_kg=shape.volume*b['density_kg_m3']/1e9,bbox_min_mm=list(box.min),bbox_max_mm=list(box.max),
                             bbox_mm=list(box.size),faces=len(shape.faces()),edges=len(shape.edges()),solids=len(shape.solids()),build_seconds=time.perf_counter()-started),
                features=features,gates=gates,holes=holes,mesh=mesh(shape),reference_mesh=mesh(sensor),carrier_mesh=mesh(carrier),documentation=docs,
                limitations=b['missing']+['Geometry rules and sampled tool cylinders do not prove strength or complete machining accessibility.',
                                        'STEP import and roundtrip use OCCT; external CAD interoperability has not been tested.',
                                        'Reference provenance is user declared; synthetic fixture does not validate fit to the Q4 cover.'])
    (dest/'program.json').write_text(json.dumps(p,indent=2,ensure_ascii=False,allow_nan=False))
    (dest/'brief.json').write_text(json.dumps(b,indent=2,ensure_ascii=False,allow_nan=False))
    (dest/'result.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False))
    (dest/'feature_compiler.py').write_bytes((ROOT/'design/compiler.py').read_bytes())
    (dest/'reproduce.py').write_text("from pathlib import Path\nimport json\nfrom build123d import export_step\nfrom feature_compiler import validate, evaluate_graph, sha\nroot=Path(__file__).resolve().parent\nb=json.loads((root/'brief.json').read_text())\nassert sha({k:v for k,v in b.items() if k!='brief_sha256'})==b['brief_sha256']\np=validate(json.loads((root/'program.json').read_text()),b)\nshape,_=evaluate_graph(p,False)\nexport_step(shape,root/'reproduced.step')\nprint('BREP volume mm3:',shape.volume)\n")
    (dest/'README.txt').write_text('FORGE AI CAD Workbench\nInstall build123d==0.13.0 in Python 3.11-3.14. Run python reproduce.py.\nJSON contains the feature history; STEP contains BREP geometry. Source and brief hashes are in result.json.\nAll dimensions in mm; density is an assumption. No FEA, GD&T, hardware trial, or manufacturing release.\nSensor source is '+b['sensor']['provenance']+'. Carrier is a synthetic fixture, not the Q4 cover.\nThis archive contains no live LLM call; proposal source is user declared.\n')
    names=['bracket.step','assembly.step','carrier.step','sensor-original.step','bracket-A3.pdf','bracket-A3.svg','program.json','brief.json','result.json','feature_compiler.py','reproduce.py','README.txt',*docs['dxf'].values()]
    files={name:hashlib.sha256((dest/name).read_bytes()).hexdigest() for name in sorted(names)}
    (dest/'MANIFEST.json').write_text(json.dumps(dict(revision=revision,files=files),indent=2))
    with zipfile.ZipFile(dest/'FORGE-AI-CAD.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in [*sorted(files),'MANIFEST.json']:z.write(dest/name,name)
    return result


if __name__=='__main__':
    job=Path(sys.argv[1]).resolve();jobs=(ROOT/'design-jobs').resolve()
    if job.parent!=jobs or len(job.name)!=32:raise SystemExit('Invalid internal job folder')
    request=json.loads((job/'request.json').read_text());stage=job/'stage';stage.mkdir()
    try:
        if request['action']=='reference':
            from .compiler import inspect_reference,text,validate_interface
            file=job/'upload.step';_,geometry=inspect_reference(file,request['interface'])
            refid=job.name;meta=dict(id=refid,name=text(request['name'],'reference name',120),provenance='user_uploaded_step',interface=validate_interface(request['interface']))
            (stage/'sensor.step').write_bytes(file.read_bytes());(stage/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False))
            out=OUTPUT/'.references'/refid;out.parent.mkdir(parents=True,exist_ok=True);os.replace(stage,out)
            answer=dict(reference_id=refid,geometry={k:v for k,v in geometry.items() if k!='mesh'})
        else:
            result=build(request['program'],request['reference'],request['provenance'],stage)
            out=OUTPUT/result['revision'];out.parent.mkdir(exist_ok=True)
            if out.exists():
                # Existing immutable output must match its own manifest before reusing it.
                manifest=json.loads((out/'MANIFEST.json').read_text())
                if any(hashlib.sha256((out/n).read_bytes()).hexdigest()!=h for n,h in manifest['files'].items()):raise ValueError('Existing design output manifest mismatch')
            else:os.replace(stage,out)
            answer=dict(revision=result['revision'],eligible=result['eligible'])
        (job/'answer.json').write_text(json.dumps(answer));print(json.dumps(answer),flush=True)
    except Exception as e:
        (job/'error.json').write_text(json.dumps(dict(error=str(e))));traceback.print_exc();raise SystemExit(1)
