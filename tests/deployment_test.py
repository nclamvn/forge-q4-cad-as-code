"""Independent budget oracle, adversarial evidence, supervisor and real HTTP tests."""
import copy,csv,hashlib,io,json,math,sys,tempfile,threading,urllib.error,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from http.server import ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from robotics import deployment as d
from robotics.supervisor import Supervisor
checks=[]
def rejects(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('Expected rejection')
def meta(p,source='simulation'):
    return dict(provenance=source,hardware_id='TEST-NO-HARDWARE',firmware_revision='fixture-v1',operator='test',
                collected_at=datetime.now(timezone.utc).isoformat(),sensor_calibration_id='NO-SENSOR',mission_sha256=d.digest(p),cad_revision=p['cad_revision'])
def fixture(p):
    rows=[];t=0;x=y=0
    def add(id='',capture=0):
        rows.append(dict(t_s=t,x_m=x,y_m=y,soc=.9,voltage_v=24,current_a=2,motor_c=25,estop=0,command_enabled=1,
            target_id=id,capture_ok=capture,rgb_ref=id+'/rgb.jpg' if capture else '',thermal_ref=id+'/thermal.tiff' if capture else ''))
    add()
    for target in p['targets']+[dict(id='',x_m=0,y_m=0)]:
        ax,ay=x,y;bx,by=target['x_m'],target['y_m'];steps=max(1,math.ceil(math.dist((ax,ay),(bx,by))/p['speed_m_s']))
        for i in range(1,steps+1):
            x=ax+(bx-ax)*i/steps;y=ay+(by-ay)*i/steps;t+=1;add(target['id'])
        if target['id']:
            for i in range(math.ceil(p['dwell_s'])):
                t+=1;add(target['id'],int(i==math.ceil(p['dwell_s'])-1))
    return rows
def encode(rows):
    f=io.StringIO();w=csv.DictWriter(f,fieldnames=d.FIELDS,lineterminator='\n');w.writeheader();w.writerows(rows);return f.getvalue()

p=d.validate_mission(d.example());q=copy.deepcopy(p);q['targets']=[dict(id='ONLY',x_m=3.,y_m=4.,asset='Fixture',max_surface_c=70.)]
b=d.plan(q)
assert abs(b['route_length_m']-10)<1e-12
assert abs(b['nominal_duration_s']-65)<1e-12
assert abs(b['estimated_energy_wh']-65*115/3600)<1e-12
assert abs(b['reserve_available_wh']-62.4)<1e-12
c=d.context();assert abs(c['hardware_gap']['candidate_loaded_mass_kg']-9.302491562844638)<1e-9
assert c['hardware_gap']['full_bom_cost_usd'] is None and all(v['status']=='missing' for v in c['readiness'])
for changed in [dict(speed_m_s=float('nan')),dict(supervised=False),dict(supervised=1),dict(python='print(1)'),dict(cad_revision='stale'),dict(initial_soc=.3,reserve_soc=.4),dict(targets=[p['targets'][0]]*2)]:
    rejects(lambda:d.validate_mission({**p,**changed}))
checks.append(dict(check='Independent 3-4-5 route / Wh / reserve oracle, 12-actuator mass replacement and finite bounded mission schema',passed=True))

rows=fixture(p);data=encode(rows);r=d.assess(p,meta(p),data)
assert r['declared_log_checks_pass'] and not r['deployment_authorized'] and not r['provenance_verified']
assert abs(r['metrics']['electrical_energy_wh']-(rows[-1]['t_s']-rows[0]['t_s'])*48/3600)<1e-10
field=d.assess(p,meta(p,'field'),data)
assert not field['hardware_verified'] and not field['deployment_authorized'] and all(not v['media_bytes_verified'] for v in field['captures'])
for edits,key in [({'motor_c':72},'motor_temperature'),({'soc':.1},'battery_reserve'),({'estop':1,'command_enabled':1},'estop_interlock')]:
    bad=copy.deepcopy(rows);bad[3].update(edits);rr=d.assess(p,meta(p),encode(bad));assert not next(g['passed'] for g in rr['gates'] if g['id']==key)
assert not d.assess(p,meta(p),encode(rows[:2]))['declared_log_checks_pass']
bad=copy.deepcopy(rows);bad[1]['t_s']=bad[0]['t_s'];rejects(lambda:d.assess(p,meta(p),encode(bad)))
bad=copy.deepcopy(rows);bad[1]['t_s']=1e-323;rejects(lambda:d.assess(p,meta(p),encode(bad)))
bad=copy.deepcopy(rows)
for row in bad:
    if row['target_id']=='P01' and row['t_s']%3==0:row['target_id']=''
assert not next(g['passed'] for g in d.assess(p,meta(p),encode(bad))['gates'] if g['id']=='dwell')
bad=copy.deepcopy(rows);bad[-1]['current_a']='nan';rejects(lambda:d.assess(p,meta(p),encode(bad)))
bad=copy.deepcopy(rows);cap=next(v for v in bad if v['capture_ok']);cap['rgb_ref']='../../secret.jpg';rejects(lambda:d.assess(p,meta(p),encode(bad)))
bad=copy.deepcopy(rows);cap=next(v for v in bad if v['capture_ok']);cap['thermal_ref']='';assert not d.assess(p,meta(p),encode(bad))['declared_log_checks_pass']
rejects(lambda:d.assess(p,{**meta(p),'mission_sha256':'0'*64},data))
rejects(lambda:d.assess(p,{**meta(p),'provenance':'verified_field'},data))
rejects(lambda:d.assess(p,{**meta(p),'collected_at':'2027-01-01T00:00:00Z'},data))
checks.append(dict(check='Complete declared mission logs, independent V×I integration, false-field cannot authorize, hot/low-SOC/E-stop failures, stale hash, nonfinite CSV and media traversal rejection',passed=True))

s=Supervisor();rejects(lambda:s.command('arm'));s.update(0,heartbeat=True);s.command('arm');assert not s.snapshot()['command_permitted'];s.command('start');assert s.snapshot()['command_permitted']
s.update(.251);assert s.state=='HOLD' and not s.snapshot()['command_permitted'];s.update(.3,heartbeat=True);assert s.state=='HOLD';rejects(lambda:s.command('start'))
s.command('reset');s.command('arm');s.command('start');s.update(.4,heartbeat=True,estop=True);assert s.state=='ESTOP';s.update(.5,heartbeat=True);assert s.state=='ESTOP' and not s.snapshot()['command_permitted'];rejects(lambda:s.command('arm'))
s.update(float('nan'));assert s.state=='ESTOP';s.update(.6,heartbeat=True);s.command('reset');assert s.state=='DISARMED'
s.command('arm');s.command('start');s.update(.7,heartbeat=True,motor_c=70);assert s.state=='FAULT';s.update(.8,heartbeat=True);assert s.state=='FAULT';rejects(lambda:s.command('start'))
s.command('reset');s.command('arm');s.command('start');s.update(.9,heartbeat=True,soc=.24);assert s.state=='HOLD';s.update(.5,heartbeat=True);assert s.state=='FAULT'
for telemetry in [dict(t=-.5),dict(t=0,motor_c=-100),dict(t=0,heartbeat='yes')]:
    invalid=Supervisor();invalid.update(**telemetry);assert invalid.state=='FAULT' and not invalid.snapshot()['command_permitted']
invalid=Supervisor();invalid.update(float('nan'),estop=True);assert invalid.state=='ESTOP'
checks.append(dict(check='Deterministic supervisor inhibits on watchdog, reserve, thermal, invalid telemetry and clock regression; E-stop latches; explicit reset and arm before restarting',passed=True))

with tempfile.TemporaryDirectory() as folder:
    old=d.OUTPUT;d.OUTPUT=Path(folder)
    saved=d.save_report(r,data);assert d.load_report(saved['id'])['current_source_match']
    reportpath=d.OUTPUT/saved['id']/'report.json';reportpath.write_text(reportpath.read_text().replace('"deployment_authorized": false','"deployment_authorized": true'))
    rejects(lambda:d.load_report(saved['id']))
    rejects(lambda:d.load_report('../../secret'))
    from server import Handler,CACHE
    m=d.baseline();CACHE[json.dumps(m['spec'],sort_keys=True)]=m
    class Quiet(Handler):
        def log_message(self,*a):pass
    http=ThreadingHTTPServer(('127.0.0.1',0),Quiet);url='http://127.0.0.1:'+str(http.server_port)
    threading.Thread(target=http.serve_forever,daemon=True).start()
    def request(path,raw=None,origin=None):
        headers={'Content-Type':'application/json'}
        if origin is not None:headers['Origin']=origin
        req=urllib.request.Request(url+path,data=None if raw is None else json.dumps(raw).encode(),headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=15) as result:return result.status,json.load(result)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    try:
        assert request('/api/deployment/context')[0]==200
        assert request('/api/deployment/plan',{'mission':p})[0]==200
        assert request('/api/deployment/llm-context',{'mission':p})[1]['llm_runtime'] is False
        for origin in ['null','http://evil.example','http://127.0.0.1:1']:assert request('/api/deployment/plan',{'mission':p},origin)[0]==403
        assert request('/api/deployment/plan',{'mission':p},url)[0]==200
        assert request('/api/deployment/plan',{'mission':p,'code':'x'})[0]==422
        code,res=request('/api/deployment/assess',dict(mission=p,metadata=meta(p),csv=data));assert code==200 and res['declared_log_checks_pass']
        assert request('/api/deployment/report?id='+res['id'])[1]['current_source_match']
        assert request('/api/deployment/report?id=../secret')[0]==422
        with urllib.request.urlopen(url+'/deployment.html') as page:assert page.status==200 and b'deployment.js' in page.read()
    finally:http.shutdown();http.server_close();d.OUTPUT=old
checks.append(dict(check='Atomic local report/raw-log manifest detects mutation; actual HTTP schema, origin, JSON-only LLM context and static workspace',passed=True))
out=dict(status='passed',hardware_tested=False,checks=checks,source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['robotics/deployment.py','robotics/supervisor.py','robotics/commercial-components.json','server.py','tests/deployment_test.py']})
(ROOT/'reports/robotics/deployment-tests.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
