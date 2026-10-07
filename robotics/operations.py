"""Explicit, uncalibrated drive/battery model coupled to solved torque and speed.

These estimates are deliberately distinct from MuJoCo's mechanical telemetry.
The output torque constant and resistance describe an equivalent joint drive,
not an identified motor. No claimed endurance or component certification.
"""
import math
import numpy as np

DEFAULT = dict(enabled=False, ambient_c=25., initial_motor_c=25.,
    thermal_capacity_j_k=80., thermal_resistance_k_w=3., derate_c=70., cutoff_c=90.,
    output_torque_constant_nm_a=.8, equivalent_resistance_ohm=.15,
    no_load_speed_rad_s=32., efficiency=.78, auxiliary_power_w=12.,
    battery_wh=120., initial_soc=.9, battery_voltage_v=24., battery_resistance_ohm=.12,
    minimum_soc=.1, failed_joint=-1, joint_health=1.)
RANGES = dict(ambient_c=(-10,50),initial_motor_c=(-10,95),thermal_capacity_j_k=(5,1000),
    thermal_resistance_k_w=(.1,20),derate_c=(40,85),cutoff_c=(60,110),
    output_torque_constant_nm_a=(.1,4),equivalent_resistance_ohm=(.01,2),
    no_load_speed_rad_s=(4,100),efficiency=(.1,1),auxiliary_power_w=(0,100),
    battery_wh=(1,1000),initial_soc=(.05,1),battery_voltage_v=(12,60),
    battery_resistance_ohm=(0,1),minimum_soc=(.01,.3),failed_joint=(-1,11),joint_health=(0,1))


def validate(raw=None):
    from .simulation import finite_number
    raw={} if raw is None else raw
    if not isinstance(raw,dict) or set(raw)-set(DEFAULT):raise ValueError('Unknown operating profile fields')
    p={**DEFAULT,**raw}
    if type(p['enabled']) is not bool:raise ValueError('operations.enabled must be boolean')
    for name,(lo,hi) in RANGES.items():p[name]=finite_number(p[name],lo,hi,name)
    if not p['failed_joint'].is_integer():raise ValueError('failed_joint must be an integer')
    p['failed_joint']=int(p['failed_joint'])
    if p['cutoff_c']<=p['derate_c']:raise ValueError('cutoff_c must exceed derate_c')
    if p['initial_soc']<p['minimum_soc']:raise ValueError('initial_soc must be at least minimum_soc')
    return p


def support_margin(points,com):
    """Signed XY distance to the convex support polygon; null for <3 contacts.

    This is a static geometric indicator, never a dynamic stability proof.
    """
    pts=sorted(set(tuple(map(float,p[:2])) for p in points))
    if len(pts)<3:return None
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    lower=[];upper=[]
    for seq,out in [(pts,lower),(reversed(pts),upper)]:
        for p in seq:
            while len(out)>1 and cross(out[-2],out[-1],p)<=0:out.pop()
            out.append(p)
    hull=lower[:-1]+upper[:-1]
    if len(hull)<3:return None
    c=np.asarray(com[:2]);inside=True;distances=[]
    for i,a in enumerate(hull):
        a=np.array(a);b=np.array(hull[(i+1)%len(hull)]);edge=b-a
        delta=c-a
        inside &= bool(edge[0]*delta[1]-edge[1]*delta[0]>=-1e-12)
        u=np.clip(np.dot(c-a,edge)/np.dot(edge,edge),0,1)
        distances.append(float(np.linalg.norm(c-(a+u*edge))))
    return min(distances)*(1 if inside else -1)


class OperatingModel:
    def __init__(self, raw, torque_limit):
        self.profile=validate(raw);p=self.profile;self.enabled=p['enabled']
        self.temperature=np.full(12,p['initial_motor_c']);self.limits=np.full(12,torque_limit)
        self.nominal=torque_limit;self.soc=p['initial_soc'];self.energy_j=0.;self.power_w=0.
        self.voltage=p['battery_voltage_v'];self.cutoff=False;self.events=[];self.factors=np.ones(12)

    def before_step(self, model, velocities, time_s):
        if not self.enabled:return
        p=self.profile
        thermal=np.clip((p['cutoff_c']-self.temperature)/(p['cutoff_c']-p['derate_c']),0,1)
        speed=np.clip(1-np.abs(velocities)/p['no_load_speed_rad_s'],0,1)
        health=np.ones(12)
        if p['failed_joint']>=0:health[p['failed_joint']]=p['joint_health']
        reason='motor_temperature' if np.max(self.temperature)>=p['cutoff_c'] else 'battery_reserve' if self.soc<=p['minimum_soc'] else None
        if reason and not self.cutoff:
            self.cutoff=True;self.events.append(dict(time_s=round(float(time_s),6),event='drive_cutoff',reason=reason))
        self.factors=thermal*speed*health*min(1,self.voltage/p['battery_voltage_v'])
        self.limits=self.nominal*self.factors*(0 if self.cutoff else 1)
        limits=np.maximum(self.limits,1e-9)
        model.actuator_forcerange[:,0]=-limits;model.actuator_forcerange[:,1]=limits

    def after_step(self, torque, velocity, dt):
        if not self.enabled:return
        p=self.profile
        copper=(torque/p['output_torque_constant_nm_a'])**2*p['equivalent_resistance_ohm']
        cooling=(self.temperature-p['ambient_c'])/p['thermal_resistance_k_w']
        self.temperature+=(copper-cooling)*dt/p['thermal_capacity_j_k']
        # Positive mechanical power only: braking is dissipated, no regeneration.
        self.power_w=p['auxiliary_power_w']+float(np.sum(np.maximum(0,torque*velocity)))/p['efficiency']+float(np.sum(copper))
        self.energy_j+=self.power_w*dt
        self.soc=max(0,p['initial_soc']-self.energy_j/(p['battery_wh']*3600))
        voc=p['battery_voltage_v']*(.9+.1*self.soc)
        self.voltage=max(0,voc-self.power_w/max(voc,1)*p['battery_resistance_ohm'])

    def snapshot(self):
        return dict(enabled=self.enabled,calibrated=False,basis='Assumed equivalent joint drive + lumped RC thermal model; estimated, not measured.',
            motor_temperature_c=self.temperature.tolist(),available_torque_nm=self.limits.tolist(),
            torque_factor=self.factors.tolist(),battery_soc=self.soc,battery_voltage_v=self.voltage,
            electrical_power_w=self.power_w,electrical_energy_wh=self.energy_j/3600,
            cutoff=self.cutoff,events=list(self.events),profile=self.profile)
