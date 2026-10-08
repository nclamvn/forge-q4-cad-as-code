"""Bounded, same-origin localhost API for reproducible engineering runs."""
import importlib.util
import json
import re
import threading
import time
import uuid
from urllib.parse import urlsplit, parse_qs

from .model import ROOT, compile_robot, profile, input_fingerprint

SESSIONS={};MODELS={};LOCK=threading.RLock()


def public_model(desc):
    prefix='/robotics-output/'+desc['revision']+'/'
    return {**desc['metadata'],'downloads':{'package':prefix+'FORGE-Q4-Robotics.zip','urdf':prefix+'forge_q4_description/forge_q4.urdf',
            'mjcf':prefix+'forge_q4_description/forge_q4.xml','model':prefix+'forge_q4_description/robot-model.json','manifest':prefix+'forge_q4_description/MANIFEST.json'}}


def capabilities():
    return dict(available=bool(importlib.util.find_spec('mujoco')),engine='MuJoCo',hardware_verified=False,
        requirement='pip install -r requirements-simulation.txt',max_sessions=8,coordinate_system='ROS REP-103 / SI')


def get_model(revision, cache, overrides):
    from .simulation import finite_number
    snapshot=json.loads((ROOT/'web/default-model.json').read_text())
    model=next((m for m in cache.values() if m['revision']==revision),None)
    if snapshot['revision']==revision:model=snapshot
    if model is None and isinstance(revision,str) and re.fullmatch('[a-f0-9]{12}',revision):
        if (ROOT/'artifacts'/revision/'integration-manifest.json').is_file():
            from design.integration import load
            _,model=load(revision)
    if model is None:raise ValueError('CAD revision is unavailable; build CAD first')
    config=profile()
    if set(overrides)-{'torque_limit_nm','kp_nm_rad','kd_nm_s_rad'}:raise ValueError('Unknown actuator profile field')
    ranges={'torque_limit_nm':(.1,30),'kp_nm_rad':(1,180),'kd_nm_s_rad':(.05,6)}
    for key,value in overrides.items():config[key]=finite_number(value,*ranges[key],key)
    key=json.dumps([revision,input_fingerprint(model),config],sort_keys=True)
    with LOCK:
        if key not in MODELS:
            while len(MODELS)>=8:MODELS.pop(next(iter(MODELS)))
            MODELS[key]=compile_robot(model,config)
        return MODELS[key]


def session(raw):
    token=raw.get('session')
    if not isinstance(token,str) or not re.fullmatch(r'[a-f0-9]{32}',token):raise ValueError('Invalid simulation session')
    with LOCK:
        s=SESSIONS.get(token)
        if s is None:raise ValueError('Simulation session expired; create a new run')
        s.last_access=time.monotonic()
        return s


def handle_get(handler):
    path=urlsplit(handler.path)
    if path.path=='/api/robotics/capabilities':handler.json(capabilities());return True
    if path.path=='/api/physics/report':
        try:handler.json(session({'session':parse_qs(path.query).get('session',[''])[0]}).report())
        except ValueError as e:handler.json({'error':str(e)},422)
        return True
    return False


def handle_post(handler,cache):
    path=urlsplit(handler.path).path
    if path not in ['/api/robotics/compile','/api/physics/create','/api/physics/step','/api/physics/control','/api/physics/close']:return False
    try:
        origin_header=handler.headers.get('Origin','')
        origin=urlsplit(origin_header);host=urlsplit('http://'+handler.headers.get('Host',''))
        if origin_header and (origin.scheme!='http' or origin.hostname not in ('localhost','127.0.0.1','::1') or origin.hostname!=host.hostname or origin.port!=handler.server.server_port):
            handler.json({'error':'Physics API accepts only same-origin localhost requests'},403);return True
        size=int(handler.headers.get('Content-Length','0'))
        if not 0<size<=8192:raise ValueError('Request body must be 1–8192 bytes')
        raw=json.loads(handler.rfile.read(size))
        if not isinstance(raw,dict):raise ValueError('Expected a JSON object')
        fields={'/api/robotics/compile':{'cad_revision','profile'},'/api/physics/create':{'cad_revision','profile','motion','amplitude','speed','terrain','friction','operations'},
                '/api/physics/step':{'session','seconds'},'/api/physics/control':{'session','action'},'/api/physics/close':{'session'}}[path]
        if set(raw)-fields:raise ValueError('Unknown request fields')
        if not capabilities()['available']:
            handler.json({'error':'Install requirements-simulation.txt to use the physics service'},503);return True
        if path in ('/api/robotics/compile','/api/physics/create'):
            overrides=raw.get('profile',{})
            if not isinstance(overrides,dict):raise ValueError('profile must be an object')
            desc=get_model(raw.get('cad_revision'),cache,overrides)
            if path=='/api/robotics/compile':handler.json(public_model(desc));return True
            from .simulation import Simulator
            sim=Simulator(desc,raw.get('motion','stand'),raw.get('amplitude',1),raw.get('speed',1),raw.get('terrain','flat'),raw.get('friction',.8),raw.get('operations'))
            token=uuid.uuid4().hex
            with LOCK:
                for key,s in list(SESSIONS.items()):
                    if time.monotonic()-s.last_access>1800:del SESSIONS[key]
                if len(SESSIONS)>=8:
                    disposable=next((key for key,s in SESSIONS.items() if s.status in ('paused','fault') or time.monotonic()-s.last_access>60),None)
                    if disposable:del SESSIONS[disposable]
                    else:handler.json({'error':'Eight simulation sessions are active; close a run first'},409);return True
                SESSIONS[token]=sim
            handler.json({'session':token,'model':public_model(desc),'frame':sim.snapshot()});return True
        sim=session(raw)
        if path=='/api/physics/step':result=sim.step(raw.get('seconds',.04))
        elif path=='/api/physics/control':result=sim.control(raw.get('action'))
        else:
            with LOCK:SESSIONS.pop(raw['session'],None)
            result={'closed':True}
        handler.json(result)
    except (ValueError,TypeError,KeyError) as e:handler.json({'error':str(e),'gate':'PHYSICS_INPUT'},422)
    except Exception as e:
        import traceback;traceback.print_exc()
        handler.json({'error':str(e),'gate':'PHYSICS_ENGINE'},500)
    return True
