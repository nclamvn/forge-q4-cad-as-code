"""CAD linkage, independent URDF import, physical causality and qualification.

Passing software tests does not qualify every reference gait or real hardware.
The qualification matrix records failures instead of hiding them in animation.
"""
import hashlib
import json
import math
import shutil
import subprocess
import sys
import time
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import mujoco
import numpy as np
from build123d import Location

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from robotics.model import C, compile_robot
from robotics.simulation import MOTIONS, Simulator, finite_number

OUT=ROOT/'reports/robotics';OUT.mkdir(parents=True,exist_ok=True)

def run(sim,seconds):
    sim.control('resume')
    for _ in range(round(seconds/.1)):frame=sim.step(.1)
    return frame

class RoboticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cad=json.loads((ROOT/'web/default-model.json').read_text())
        cls.desc=compile_robot(cls.cad)
        cls.results=[]

    def test_cad_linkage_inertia_and_package(self):
        d=self.desc;cad=self.cad;s=Simulator(d);f=s.snapshot()
        self.assertEqual((len(d['links']),len(f['joints']),len(f['instances'])),(13,12,42))
        self.assertAlmostEqual(sum(s.model.body_mass),cad['metrics']['loaded_mass_kg'],places=9)
        direct=[];minima={};lookup={i['id']:i for i in f['instances']}
        for inst in cad['instances']:
            loc=Location(inst['position_mm'],inst['rotation_deg']).wrapped.Transformation()
            R=np.array([[loc.Value(i,j) for j in range(1,4)] for i in range(1,4)])
            p=np.array(inst['position_mm'])*.001;prop=d['properties'][inst['part']]
            direct.append((prop['mass'],p+R@prop['com']))
            np.testing.assert_allclose(lookup[inst['id']]['position_m'],C@p,atol=1e-10)
            vertices=np.array(cad['parts'][inst['part']]['positions']).reshape(-1,3)@C
            minima[inst['id']]=float(np.min((vertices@R.T+p)[:,2]))
        extra=cad['spec']['electronics_mass_kg']+cad['spec']['payload_kg']
        direct.append((extra,np.array([0,0,d['height']+.005])))
        oracle=sum(m*p for m,p in direct)/sum(m for m,p in direct)
        np.testing.assert_allclose(f['com_m'],oracle,atol=1e-10)
        self.assertGreater(min(minima.values()),.0008)
        self.assertLess(max(v for k,v in minima.items() if k.endswith('_foot')),min(v for k,v in minima.items() if k.endswith('_lower')))
        for l in d['links'].values():
            eig=np.linalg.eigvalsh(l['inertia'])
            self.assertGreater(min(eig),0);self.assertLessEqual(max(eig),sum(eig)-max(eig)+1e-10)
        manifest=json.loads((d['package']/'MANIFEST.json').read_text())
        with zipfile.ZipFile(d['directory']/'FORGE-Q4-Robotics.zip') as z:
            self.assertIsNone(z.testzip())
            for name,sha in manifest['files'].items():self.assertEqual(hashlib.sha256(z.read('forge_q4_description/'+name)).hexdigest(),sha)
        self.results.append(dict(check='CAD mass, COM, positive inertia, 42 home transforms, pad clearance and package hashes',passed=True,mass_kg=d['mass'],minimum_home_clearance_mm=min(minima.values())*1000))

    def test_urdf_independent_import_and_joint_kinematics(self):
        d=self.desc;root=ET.parse(d['package']/'forge_q4.urdf').getroot()
        self.assertEqual(len(root.findall('link')),13);self.assertEqual(len(root.findall('joint')),12)
        self.assertEqual(len(root.findall('.//visual')),42);self.assertEqual(len(root.findall('.//collision')),42)
        for mesh in root.findall('.//mesh'):
            mesh.set('filename',str(d['package']/'meshes'/Path(mesh.get('filename')).name))
        compiler=ET.SubElement(ET.SubElement(root,'mujoco'),'compiler',fusestatic='false',discardvisual='true')
        independent=mujoco.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'))
        data=mujoco.MjData(independent);s=Simulator(d)
        for i,name in enumerate(s.joint_names):
            q=.16*math.sin(i+1)
            jid=mujoco.mj_name2id(independent,mujoco.mjtObj.mjOBJ_JOINT,name)
            data.qpos[independent.jnt_qposadr[jid]]=q;s.data.qpos[s.qadr[i]]=q
        mujoco.mj_forward(independent,data);mujoco.mj_forward(s.model,s.data)
        maximum=0
        for name,bid in s.body_ids.items():
            other=mujoco.mj_name2id(independent,mujoco.mjtObj.mjOBJ_BODY,name)
            error=np.max(np.abs(data.xpos[other]-(s.data.xpos[bid]-[0,0,d['height']])))
            maximum=max(maximum,float(error));np.testing.assert_allclose(data.xpos[other],s.data.xpos[bid]-[0,0,d['height']],atol=2e-10)
            np.testing.assert_allclose(data.xmat[other],s.data.xmat[bid],atol=2e-10)
        self.results.append(dict(check='Independent MuJoCo URDF parser versus MJCF at nonzero joints',passed=True,max_link_position_error_m=maximum,ros_runtime_tested=False))

    def test_atomic_publish_race(self):
        kp=65+time.monotonic()%1
        code="import json; from robotics.model import compile_robot,profile; c=profile(); c['kp_nm_rad']="+repr(kp)+"; d=compile_robot(json.load(open('web/default-model.json')),c); print(d['revision'])"
        children=[subprocess.Popen([sys.executable,'-c',code],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
        revisions=[]
        for child in children:
            stdout,stderr=child.communicate(timeout=60)
            self.assertEqual(child.returncode,0,stderr);revisions.append(stdout.strip())
        self.assertEqual(revisions[0],revisions[1]);self.assertEqual(len(revisions[0]),16)
        self.results.append(dict(check='Two independent compilers race to publish a fresh complete package; both verify all hashes',passed=True,model_revision=revisions[0],kp_nm_rad=kp))

    def test_controls_causality_and_validation(self):
        s=Simulator(self.desc);self.assertEqual(s.step(.1)['time_s'],0)
        f=run(s,2);s.control('pause');self.assertEqual(s.step(.1)['time_s'],f['time_s'])
        s.control('estop');f=s.step(.1);self.assertTrue(f['estopped']);self.assertEqual(max(abs(j['torque_nm']) for j in f['joints']),0)
        self.assertRaises(ValueError,s.control,'resume')
        for _ in range(20):f=s.step(.1)
        self.assertLess(f['base_position_m'][2],self.desc['height']-.035)
        zero=Simulator(self.desc);zero.model.opt.gravity[:]=0;zero.control('estop')
        for _ in range(20):z=zero.step(.1)
        np.testing.assert_allclose(z['base_position_m'],[0,0,self.desc['height']],atol=1e-10)
        for value in (float('nan'),True,-1,2):self.assertRaises(ValueError,finite_number,value,0,1,'input')
        self.assertRaises(ValueError,Simulator,self.desc,motion='unknown')
        self.assertRaises(ValueError,Simulator,self.desc,friction=0)
        self.results.append(dict(check='Pause, gravity versus zero gravity, motor cutoff and fail-loud inputs',passed=True,cutoff_base_height_m=f['base_position_m'][2]))

    def test_standing_60_seconds_and_determinism(self):
        s=Simulator(self.desc);f=run(s,60)
        self.assertFalse(f['fall_detected']);self.assertEqual(f['contact_count'],4)
        self.assertFalse(f['self_contacts']);self.assertLess(f['max_tilt_deg'],1)
        self.assertLess(f['max_penetration_mm'],2)
        self.assertLessEqual(f['peak_torque_nm'],self.desc['config']['torque_limit_nm']+1e-8)
        self.assertAlmostEqual(sum(v['normal_force_n'] for v in f['feet']),self.desc['mass']*9.81,delta=.7)
        self.assertTrue(all(w.number==0 for w in s.data.warning))
        a=Simulator(self.desc,'trot',.6,.6);b=Simulator(self.desc,'trot',.6,.6)
        fa=run(a,5);fb=run(b,5);np.testing.assert_allclose(a.data.qpos,b.data.qpos,atol=1e-12)
        report=a.report();self.assertEqual(len(report['samples']),250)
        self.assertEqual(report['samples'][-1]['time_s'],5);json.dumps(report,allow_nan=False)
        self.results.append(dict(check='60 s stand, contact load, force bounds, warnings and deterministic replay',passed=True,summary={k:f[k] for k in ['time_s','contact_count','peak_torque_nm','max_tilt_deg','max_penetration_mm']},reaction_n=sum(v['normal_force_n'] for v in f['feet'])))

    @classmethod
    def tearDownClass(cls):
        if len(cls.results)==5:
            source={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'robotics/model.py',ROOT/'robotics/simulation.py',ROOT/'robotics/profile.yaml',ROOT/'web/motion-engine.js',ROOT/'tools/motion-reference.mjs',Path(__file__)]}
            (OUT/'model-tests.json').write_text(json.dumps(dict(status='passed',cad_revision=cls.cad['revision'],model_revision=cls.desc['revision'],engine_version=mujoco.__version__,source_sha256=source,checks=cls.results,ros_runtime_tested=False,hardware_verified=False),indent=2)+'\n')
            qualify(cls.desc)
            shutil.copyfile(cls.desc['directory']/'FORGE-Q4-Robotics.zip',ROOT/'FORGE-Q4-Robotics.zip')

def qualify(desc):
    scenarios=[dict(motion=m,amplitude=.6,speed=.6,terrain='flat',friction=.8) for m in MOTIONS]
    scenarios += [dict(motion='trot',amplitude=1,speed=1,terrain='flat',friction=.8),dict(motion='walk',amplitude=.6,speed=.6,terrain='ramp',friction=.8),dict(motion='walk',amplitude=.6,speed=.6,terrain='steps',friction=.8),dict(motion='walk',amplitude=.6,speed=.6,terrain='flat',friction=.15)]
    rows=[]
    for opts in scenarios:
        s=Simulator(desc,**opts);f=run(s,10)
        row={**opts,'seconds':10,'fall_detected':f['fall_detected'],'fall_time_s':f['fall_time_s'],'displacement_xy_m':float(np.linalg.norm(np.array(f['base_position_m'][:2])-s.start_xy)),
             'peak_torque_nm':f['peak_torque_nm'],'peak_joint_speed_rad_s':f['peak_joint_speed_rad_s'],'max_tilt_deg':f['max_tilt_deg'],'max_penetration_mm':f['max_penetration_mm'],
             'final_contacts':f['contact_count'],'no_loaded_feet_after_settle_s':sum(r['contact_count']==0 and r['time_s']>2 for r in s.record)*.02,
             'solver_warnings':sum(w.number for w in s.data.warning),'finite_state':bool(np.all(np.isfinite(s.data.qpos)))}
        rows.append(row);print(json.dumps(row),flush=True)
    push=Simulator(desc);run(push,2);before=push.data.qpos[:2].copy();push.control('push');f=run(push,2)
    rows.append(dict(motion='stand',experiment='35 N lateral force / 0.12 s',seconds=4,fall_detected=f['fall_detected'],displacement_xy_m=float(np.linalg.norm(push.data.qpos[:2]-before)),peak_torque_nm=f['peak_torque_nm'],max_tilt_deg=f['max_tilt_deg']))
    weak=compile_robot(desc['model'],{**desc['config'],'torque_limit_nm':.25})
    s=Simulator(weak);f=run(s,5)
    assert f['peak_torque_nm']<=.25+1e-8
    rows.append(dict(motion='stand',experiment='Undersized 0.25 Nm motors',model_revision=weak['revision'],seconds=5,fall_detected=f['fall_detected'],fall_time_s=f['fall_time_s'],peak_torque_nm=f['peak_torque_nm'],base_height_m=f['base_position_m'][2],base_height_loss_m=desc['height']-f['base_position_m'][2]))
    (OUT/'qualification.json').write_text(json.dumps(dict(cad_revision=desc['model']['revision'],model_revision=desc['revision'],engine='MuJoCo',engine_version=mujoco.__version__,hardware_verified=False,scope='Bounded 10-second reference-motion trials; no universal gait qualification. Falls are reported results, not test failures. No full-body balance controller.',scenarios=rows),indent=2)+'\n')

if __name__=='__main__':unittest.main(verbosity=2)
