"""Floating-base MuJoCo plant with a bounded PD reference controller.

The browser receives solved body transforms and actual contact forces. No
prescribed body motion, position teleportation or fabricated sensor telemetry.
"""
from __future__ import annotations
import hashlib
import json
import math
import shutil
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation
from .model import ROOT, C, LEGS, mjcf, quaternion

MOTIONS = ('stand','walk','trot','pace','bound','reverse','sidestep','turn','crouch','sit','bow','wave','balance','dance','jump')


def finite_number(value, lo, hi, name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError(f'{name} must be between {lo} and {hi}')
    return float(value)


def reference(spec, motion='stand', amplitude=1., speed=1.):
    if motion not in MOTIONS: raise ValueError('Unknown motion')
    amplitude=finite_number(amplitude,.25,1.35,'amplitude');speed=finite_number(speed,.25,2.,'speed')
    node=shutil.which('node')
    if not node: raise RuntimeError('Node.js 18+ is required to compile the shared motion reference')
    result=subprocess.run([node,str(ROOT/'tools/motion-reference.mjs')],input=json.dumps(dict(spec=spec,motion=motion,amplitude=amplitude,speed=speed)),text=True,capture_output=True,timeout=20,check=True)
    data=json.loads(result.stdout)
    t=np.array([s['seconds'] for s in data['samples']]);q=np.array([s['commands'] for s in data['samples']])
    return dict(motion=motion,duration=data['duration'],times=t,positions=q,amplitude=amplitude,speed=speed)


class Simulator:
    def __init__(self, desc, motion='stand', amplitude=1., speed=1., terrain='flat', friction=.8, operations=None):
        if terrain not in ('flat','ramp','steps'): raise ValueError('Unknown terrain')
        friction=finite_number(friction,.1,1.5,'friction')
        self.desc=desc;self.config=desc['config'];self.terrain=terrain;self.friction=friction
        xml=ET.fromstring(mjcf(desc,terrain,friction));xml.find('compiler').set('meshdir',str(desc['package']/'meshes'))
        self.model=mujoco.MjModel.from_xml_string(ET.tostring(xml,encoding='unicode'))
        self.data=mujoco.MjData(self.model)
        if terrain=='ramp':
            # Place the initial CAD home pose along the ramp normal, avoiding
            # a pre-penetrated rear pad. Subsequent pose is entirely dynamic.
            ramp=Rotation.from_euler('y',math.radians(5)).as_matrix()
            self.data.qpos[:3]=ramp@self.data.qpos[:3]
            self.data.qpos[3:7]=quaternion(ramp)
        mujoco.mj_forward(self.model,self.data)
        self.ref=reference(desc['model']['spec'],motion,amplitude,speed)
        self.joint_names=[l['joint'] for l in desc['links'].values() if l['joint']]
        self.joint_ids=[mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_JOINT,n) for n in self.joint_names]
        self.qadr=self.model.jnt_qposadr[self.joint_ids];self.vadr=self.model.jnt_dofadr[self.joint_ids]
        self.body_ids={name:mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_BODY,name) for name in desc['links']}
        from .operations import OperatingModel
        self.operations=OperatingModel(operations,self.config['torque_limit_nm'])
        self.foot_sites=[mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_SITE,leg+'_foot_site') for leg,_,_ in LEGS]
        self.lock=threading.RLock();self.status='paused';self.estopped=False;self.pending_push=None
        self.last_access=time.monotonic();self.record=[];self.command=np.zeros(12)
        self.peak_torque=0.;self.peak_speed=0.;self.max_tilt=0.;self.max_penetration=0.;self.energy=0.;self.fall_time=None
        self.start_xy=self.data.qpos[:2].copy();self.fingerprint=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    def control(self, action):
        with self.lock:
            if action=='resume':
                if self.estopped:raise ValueError('Reset is required after motor cutoff')
                self.status='running'
            elif action=='pause':self.status='paused'
            elif action=='estop':
                self.estopped=True;self.status='estopped';self.data.ctrl[:]=0;self.pending_push=None
                self.model.opt.disableflags|=int(mujoco.mjtDisableBit.mjDSBL_ACTUATION)
                mujoco.mj_forward(self.model,self.data)
            elif action=='push':self.pending_push=[35.,.12]
            else:raise ValueError('Unknown control action')
            return self.snapshot()

    def step(self, seconds=.04):
        seconds=finite_number(seconds,0,.1,'seconds')
        with self.lock:
            self.last_access=time.monotonic()
            if self.status not in ('running','estopped'):return self.snapshot()
            steps=round(seconds/self.config['timestep_s'])
            for _ in range(steps):self._tick()
            return self.snapshot()

    def _tick(self):
        d=self.data;m=self.model;dt=m.opt.timestep
        self.operations.before_step(m,d.qvel[self.vadr],d.time)
        if not self.estopped:
            elapsed=max(0.,d.time-1.)
            phase=elapsed%self.ref['duration'];target=np.array([np.interp(phase,self.ref['times'],self.ref['positions'][:,j]) for j in range(12)])
            fade=min(1.,elapsed/.8);fade=fade*fade*(3-2*fade);target*=fade
            limit=self.config['velocity_limit_rad_s']*dt
            self.command+=np.clip(target-self.command,-limit,limit)
            # MuJoCo's position servo applies the PD law and force clamp inside
            # the implicit integrator; ctrl is radians, actuator_force is Nm.
            d.ctrl[:]=self.command
        else:d.ctrl[:]=0
        d.xfrc_applied[:]=0
        if self.pending_push:
            d.xfrc_applied[self.body_ids['base_link'],1]=self.pending_push[0]
            self.pending_push[1]-=dt
            if self.pending_push[1]<=0:self.pending_push=None
        mujoco.mj_step(m,d)
        self.operations.after_step(d.actuator_force,d.qvel[self.vadr],dt)
        if not np.all(np.isfinite(d.qpos)) or not np.all(np.isfinite(d.qvel)):
            self.status='fault';d.ctrl[:]=0;raise RuntimeError('Physics state is non-finite; reset the run')
        self.peak_torque=max(self.peak_torque,float(np.max(np.abs(d.actuator_force))))
        self.peak_speed=max(self.peak_speed,float(np.max(np.abs(d.qvel[self.vadr]))))
        self.energy+=float(np.sum(np.abs(d.actuator_force*d.qvel[self.vadr])))*dt
        tilt=math.degrees(math.acos(np.clip(d.xmat[self.body_ids['base_link']].reshape(3,3)[2,2],-1,1)))
        self.max_tilt=max(self.max_tilt,tilt)
        if self.fall_time is None and (tilt>45 or d.qpos[2]<.09):self.fall_time=float(d.time)
        for c in d.contact:self.max_penetration=max(self.max_penetration,max(0.,-float(c.dist))*1000)
        if round(d.time/dt)%10==0:
            frame=self.snapshot(include_instances=False)
            self.record.append(frame)
            if len(self.record)>15000:self.record=self.record[-15000:]

    def snapshot(self, include_instances=True):
        d=self.data;m=self.model
        # mj_step integrates qpos after evaluating kinematics. Re-evaluate at
        # that qpos so angles, mesh transforms and contacts share one timestamp.
        mujoco.mj_forward(m,d)
        forces={leg:np.zeros(3) for leg,_,_ in LEGS};normal={leg:0. for leg,_,_ in LEGS};collisions=[]
        for i,c in enumerate(d.contact):
            names=[mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_GEOM,int(g)) for g in [c.geom1,c.geom2]]
            force=np.zeros(6);mujoco.mj_contactForce(m,d,i,force)
            f=c.frame.reshape(3,3).T@force[:3]
            foot=next((leg for leg,_,_ in LEGS if leg+'_foot' in names),None)
            environment=any(n=='floor' or (n and n.startswith('step_')) for n in names)
            if foot and environment:
                sign=1 if names[1]==foot+'_foot' else -1;forces[foot]+=f*sign;normal[foot]+=max(0.,float(force[0]))
            elif c.dist<-.0002 and not environment:collisions.append(dict(parts=names,penetration_mm=-float(c.dist)*1000))
        base=self.body_ids['base_link'];R=d.xmat[base].reshape(3,3);euler=Rotation.from_matrix(R).as_euler('xyz')
        foot_data=[]
        for (leg,_,_),site in zip(LEGS,self.foot_sites):
            v=np.zeros(6);mujoco.mj_objectVelocity(m,d,mujoco.mjtObj.mjOBJ_SITE,site,v,0)
            foot_data.append(dict(id=leg,position_m=d.site_xpos[site].tolist(),force_n=forces[leg].tolist(),normal_force_n=normal[leg],contact=normal[leg]>.5,slip_m_s=float(np.linalg.norm(v[3:5]))))
        frame=dict(time_s=round(float(d.time),6),status=self.status,estopped=self.estopped,
            model_revision=self.desc['revision'],cad_revision=self.desc['model']['revision'],motion=self.ref['motion'],phase=max(0.,d.time-1.)%self.ref['duration']/self.ref['duration'],
            base_position_m=d.xpos[base].tolist(),base_quaternion_wxyz=d.xquat[base].tolist(),body_angles_rad=euler.tolist(),com_m=d.subtree_com[base].tolist(),
            joints=[dict(name=n,position_rad=float(d.qpos[self.qadr[i]]),velocity_rad_s=float(d.qvel[self.vadr[i]]),command_rad=float(self.command[i]),torque_nm=float(d.actuator_force[i]),
                lower_limit_rad=float(m.jnt_range[self.joint_ids[i],0]),upper_limit_rad=float(m.jnt_range[self.joint_ids[i],1])) for i,n in enumerate(self.joint_names)],
            feet=foot_data,contact_count=sum(f['contact'] for f in foot_data),self_contacts=collisions,
            imu_gyro_rad_s=d.sensor('imu_gyro').data.tolist(),imu_accel_m_s2=d.sensor('imu_accel').data.tolist(),
            peak_torque_nm=self.peak_torque,peak_joint_speed_rad_s=self.peak_speed,max_tilt_deg=self.max_tilt,max_penetration_mm=self.max_penetration,
            mechanical_abs_work_j=self.energy,fall_detected=self.fall_time is not None,fall_time_s=self.fall_time,hardware_verified=False)
        from .operations import support_margin
        frame['operations']=self.operations.snapshot()
        frame['tracking_rms_rad']=float(np.sqrt(np.mean((d.qpos[self.qadr]-self.command)**2)))
        frame['support_margin_m']=support_margin([f['position_m'] for f in foot_data if f['contact']],frame['com_m'])
        frame['loaded_foot_slip_m_s']=max([f['slip_m_s'] for f in foot_data if f['contact']]+[0.])
        if include_instances:
            frame['instances']=[]
            for inst,placement in self.desc['placements'].items():
                body=self.body_ids[placement['link']];local=np.array(placement['local']);R=d.xmat[body].reshape(3,3)
                world_R=R@local[:3,:3];world_p=d.xpos[body]+R@local[:3,3]
                frame['instances'].append(dict(id=inst,position_m=(C@world_p).tolist(),quaternion_xyzw=Rotation.from_matrix(C@world_R@C.T).as_quat().tolist()))
        return frame

    def report(self):
        with self.lock:
            return dict(format='forge-physics-run-v1',engine='MuJoCo',engine_version=mujoco.__version__,model_revision=self.desc['revision'],cad_revision=self.desc['model']['revision'],
                simulation_source_sha256=self.fingerprint,profile=self.config,terrain=self.terrain,friction=self.friction,
                reference_source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'tools/motion-reference.mjs',ROOT/'web/motion-engine.js']},
                reference=dict(motion=self.ref['motion'],amplitude=self.ref['amplitude'],speed=self.ref['speed']),
                integration_timestep_s=self.model.opt.timestep,record_sample_rate_hz=50,
                operating_model_source_sha256=hashlib.sha256((ROOT/'robotics/operations.py').read_bytes()).hexdigest(),
                operating_profile=self.operations.profile,
                elapsed_simulation_s=float(self.data.time),summary=self.snapshot(include_instances=False),samples=self.record,
                scope='Rigid-body simulation with convex CAD collision hulls and assumed motor/material parameters. Optional equivalent-drive electrical/thermal estimates are uncalibrated. No hardware validation or full-body locomotion controller.')
