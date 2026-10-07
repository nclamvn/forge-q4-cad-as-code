"""Compile CAD instance placements into one articulated SI/ROS robot model.

Inertia comes from OCCT volume integrals, scaled by each CAD part's assigned
mass. Hardware mass, electronics distribution and motor settings remain
explicit assumptions. Collision meshes use convex hulls in MuJoCo.
"""
from __future__ import annotations
import hashlib
import json
import math
import errno
import os
import struct
import tempfile
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import yaml
from build123d import import_step, Location
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'robotics-output'
C = np.array([[1., 0, 0], [0, 0, 1.], [0, -1., 0]])  # ROS/CAD -> Three
LEGS = [('front_left', 1, 1), ('front_right', 1, -1),
        ('rear_left', -1, 1), ('rear_right', -1, -1)]


def vec(v):
    return ' '.join(f'{float(x):.12g}' for x in np.asarray(v).flat)


def tf(position, matrix=None):
    t = np.eye(4); t[:3, 3] = position
    if matrix is not None: t[:3, :3] = matrix
    return t


def quaternion(matrix):
    x, y, z, w = Rotation.from_matrix(matrix).as_quat()
    return [float(w), float(x), float(y), float(z)]


def origin(parent, t):
    r=t[:3,:3];pitch=math.asin(float(np.clip(-r[2,0],-1,1)))
    if abs(math.cos(pitch))>1e-8:roll=math.atan2(r[2,1],r[2,2]);yaw=math.atan2(r[1,0],r[0,0])
    else:roll=math.atan2(-r[1,2],r[1,1]);yaw=0.
    return ET.SubElement(parent, 'origin', xyz=vec(t[:3, 3]),
                         rpy=vec([roll,pitch,yaw]))


def profile():
    return yaml.safe_load((ROOT / 'robotics/profile.yaml').read_text())


def part_properties(model):
    result = {}
    for key, p in model['parts'].items():
        path = (ROOT / p['step_url'].lstrip('/')).resolve()
        if not path.is_relative_to(ROOT / 'artifacts'): raise ValueError('Invalid CAD source')
        shape = import_step(path)
        g = GProp_GProps(); BRepGProp.VolumeProperties_s(shape.wrapped, g)
        relative_error = abs(g.Mass() - p['volume_mm3']) / p['volume_mm3']
        # STEP spline surfaces can introduce ppm-scale volume differences.
        # Record the measured discrepancy and enforce the dossier's 2 ppm gate.
        if relative_error > 2e-6:
            raise ValueError('STEP volume differs from snapshot: ' + key)
        inertia = np.array([[g.MatrixOfInertia().Value(i, j) for j in range(1, 4)] for i in range(1, 4)])
        result[key] = dict(mass=p['mass_kg'], com=np.array(g.CentreOfMass().Coord()) * .001,
                           inertia=inertia * p['mass_kg'] / g.Mass() * 1e-6,
                           basis=p['mass_basis'], step_volume_relative_error=relative_error,
                           step_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return result


def build_description(model, config):
    s = model['spec']; L, W, ul, ll = [s[k] * .001 for k in ['body_length', 'body_width', 'upper_length', 'lower_length']]
    h = (ul + ll) * math.cos(.62) + .025
    gap = (s['link_thickness'] + 3) * .001
    props = part_properties(model)
    links = {'base_link': dict(parent=None, world=tf([0, 0, h]), joint=None, parts=[])}
    for name, sx, sy in LEGS:
        a = [sx * L * .34, sy * (W / 2 + .002), h - .008]
        u = np.array(a) + [0, sy * .026, 0]
        r = Rotation.from_euler('y', sx * .62).as_matrix()
        k = u + r @ np.array([0, sy * gap, -ul])
        links[name + '_abduction'] = dict(parent='base_link', world=tf(a), joint=name + '_roll', axis=[1, 0, 0], parts=[])
        links[name + '_upper'] = dict(parent=name + '_abduction', world=tf(u, r), joint=name + '_hip', axis=[0, -1, 0], parts=[])
        links[name + '_lower'] = dict(parent=name + '_upper', world=tf(k, Rotation.from_euler('y', -sx * .62).as_matrix()), joint=name + '_knee', axis=[0, -1, 0], parts=[])
    placements = {}
    for inst in model['instances']:
        leg = next((name for name, _, _ in LEGS if inst['id'].startswith(name + '_')), None)
        suffix = inst['id'][len(leg) + 1:] if leg else ''
        group = 'base_link' if not leg else leg + ('_abduction' if suffix in ['roll', 'shoulder'] else '_upper' if suffix in ['hip', 'upper', 'upper_fairing'] else '_lower')
        loc = Location(inst['position_mm'], inst['rotation_deg']).wrapped.Transformation()
        matrix = np.array([[loc.Value(i, j) for j in range(1, 4)] for i in range(1, 4)])
        world = tf(np.array(inst['position_mm']) * .001, matrix)
        local = np.linalg.inv(links[group]['world']) @ world
        part = dict(id=inst['id'], part=inst['part'], local=local)
        links[group]['parts'].append(part); placements[inst['id']] = dict(link=group, local=local.tolist())
    extra = s['electronics_mass_kg'] + s['payload_kg']
    for name, link in links.items():
        weighted = []
        for part in link['parts']:
            p = props[part['part']]; t = part['local']; R = t[:3, :3]
            weighted.append((p['mass'], t[:3, 3] + R @ p['com'], R @ p['inertia'] @ R.T))
        if name == 'base_link' and extra:
            # Electronics and payload have no geometry: explicit central box assumption.
            size = np.array([L * .45, W * .50, .036])
            I = extra / 12 * np.diag([size[1]**2 + size[2]**2, size[0]**2 + size[2]**2, size[0]**2 + size[1]**2])
            weighted.append((extra, np.array([0., 0., .005]), I))
        mass = sum(p[0] for p in weighted)
        com = sum(p[0] * p[1] for p in weighted) / mass
        I = sum(p[2] + p[0] * ((np.dot(p[1] - com, p[1] - com) * np.eye(3)) - np.outer(p[1] - com, p[1] - com)) for p in weighted)
        if np.min(np.linalg.eigvalsh(I)) <= 0: raise ValueError('Non-positive inertia: ' + name)
        link.update(mass=mass, com=com, inertia=I, origin=np.eye(4) if not link['parent'] else np.linalg.inv(links[link['parent']]['world']) @ link['world'])
    mass = sum(l['mass'] for l in links.values())
    if abs(mass - model['metrics']['loaded_mass_kg']) > 1e-9: raise ValueError('Robot mass mismatch')
    return dict(model=model, config=config, links=links, placements=placements, properties=props, height=h, mass=mass)


def meshes(model, folder):
    folder.mkdir(parents=True, exist_ok=True)
    for key, p in model['parts'].items():
        vertices = np.array(p['positions']).reshape(-1, 3) @ C
        faces = np.array(p['indices']).reshape(-1, 3)
        lines = [f'v {vec(v)}' for v in vertices] + ['f ' + ' '.join(str(int(i) + 1) for i in face) for face in faces]
        (folder / (key + '.obj')).write_text('\n'.join(lines) + '\n')
        with (folder / (key + '.stl')).open('wb') as out:
            out.write(b'FORGE CAD SI mesh'.ljust(80, b'\0')); out.write(struct.pack('<I', len(faces)))
            for face in faces:
                tri = vertices[face]; normal = np.cross(tri[1] - tri[0], tri[2] - tri[0]); length = np.linalg.norm(normal)
                normal = normal / length if length > 0 else normal
                out.write(struct.pack('<12fH', *normal, *tri.flat, 0))


def urdf(desc, directory):
    robot = ET.Element('robot', name='forge_q4')
    ET.SubElement(robot, 'material', name='porcelain').append(ET.Element('color', rgba='.85 .85 .85 1'))
    for name, link in desc['links'].items():
        el = ET.SubElement(robot, 'link', name=name)
        inertial = ET.SubElement(el, 'inertial'); origin(inertial, tf(link['com']))
        ET.SubElement(inertial, 'mass', value=vec([link['mass']]))
        I = link['inertia']; ET.SubElement(inertial, 'inertia', **{k:vec([I[i,j]]) for k,i,j in [('ixx',0,0),('iyy',1,1),('izz',2,2),('ixy',0,1),('ixz',0,2),('iyz',1,2)]})
        for part in link['parts']:
            for tag in ['visual', 'collision']:
                geom = ET.SubElement(el, tag, name=part['id']); origin(geom, part['local'])
                ET.SubElement(ET.SubElement(geom, 'geometry'), 'mesh', filename='package://forge_q4_description/meshes/' + part['part'] + '.stl')
                if tag == 'visual': ET.SubElement(geom, 'material', name='porcelain')
        if link['joint']:
            joint = ET.SubElement(robot, 'joint', name=link['joint'], type='revolute')
            origin(joint, link['origin']); ET.SubElement(joint, 'parent', link=link['parent']); ET.SubElement(joint, 'child', link=name)
            ET.SubElement(joint, 'axis', xyz=vec(link['axis']))
            limit = desc['model']['spec']['joint_limit_deg'] * math.pi / 180
            if name.endswith('_abduction'): limit = min(.5, limit)
            ET.SubElement(joint, 'limit', lower=str(-limit), upper=str(limit), effort=str(desc['config']['torque_limit_nm']), velocity=str(desc['config']['velocity_limit_rad_s']))
            ET.SubElement(joint, 'dynamics', damping=str(desc['config']['joint_damping_nm_s_rad']), friction='0')
    ET.indent(robot)
    (directory / 'forge_q4.urdf').write_text('<?xml version="1.0"?>\n' + ET.tostring(robot, encoding='unicode') + '\n')


def mjcf(desc, terrain='flat', friction=None, payload_scale=1):
    cfg = desc['config']; xml = ET.Element('mujoco', model='FORGE-Q4')
    ET.SubElement(xml, 'compiler', angle='radian', inertiafromgeom='false', meshdir='meshes', autolimits='true', fusestatic='false')
    ET.SubElement(xml, 'option', timestep=str(cfg['timestep_s']), gravity=f"0 0 -{cfg['gravity_m_s2']}", integrator='implicitfast', cone='elliptic', iterations='60', tolerance='1e-10')
    default = ET.SubElement(xml, 'default')
    ET.SubElement(default, 'joint', armature=str(cfg['armature_kg_m2']), damping=str(cfg['joint_damping_nm_s_rad']))
    ET.SubElement(default, 'geom', friction=f"{cfg['friction'] if friction is None else friction} .005 .0001", condim='3', solref='.008 1', solimp='.95 .99 .001')
    asset = ET.SubElement(xml, 'asset')
    for key in desc['model']['parts']: ET.SubElement(asset, 'mesh', name=key, file=key+'.obj', inertia='convex')
    world = ET.SubElement(xml, 'worldbody')
    ET.SubElement(world, 'geom', name='floor', type='plane', size='4 4 .1', quat=vec(quaternion(Rotation.from_euler('y', math.radians(5) if terrain == 'ramp' else 0).as_matrix())), rgba='.2 .2 .2 1')
    if terrain == 'steps':
        for i in range(3): ET.SubElement(world, 'geom', name=f'step_{i}', type='box', pos=vec([.30 + i*.17, 0, .015*(i+1)]), size=vec([.085, .3, .015*(i+1)]), rgba='.3 .3 .3 1')
    elements = {}; actuator = ET.SubElement(xml, 'actuator')
    for name, link in desc['links'].items():
        t = link['world'] if not link['parent'] else link['origin']
        el = ET.SubElement(world if not link['parent'] else elements[link['parent']], 'body', name=name, pos=vec(t[:3,3]), quat=vec(quaternion(t[:3,:3])))
        elements[name] = el
        I = link['inertia']; ET.SubElement(el, 'inertial', mass=str(link['mass']), pos=vec(link['com']), fullinertia=vec([I[0,0],I[1,1],I[2,2],I[0,1],I[0,2],I[1,2]]))
        if link['parent']:
            limit = desc['model']['spec']['joint_limit_deg']*math.pi/180
            if name.endswith('_abduction'): limit = min(.5, limit)
            ET.SubElement(el, 'joint', name=link['joint'], axis=vec(link['axis']), range=vec([-limit,limit]))
            ET.SubElement(actuator, 'position', name=link['joint']+'_motor', joint=link['joint'], gear='1', kp=str(cfg['kp_nm_rad']), kv=str(cfg['kd_nm_s_rad']),
                          ctrllimited='true',ctrlrange=vec([-limit,limit]),forcelimited='true',forcerange=vec([-cfg['torque_limit_nm'],cfg['torque_limit_nm']]))
        else: ET.SubElement(el, 'freejoint', name='floating_base')
        for part in link['parts']:
            local=part['local']; ET.SubElement(el, 'geom', name=part['id'], type='mesh', mesh=part['part'], pos=vec(local[:3,3]), quat=vec(quaternion(local[:3,:3])), rgba='.85 .85 .85 1')
        if name.endswith('_lower'): ET.SubElement(el,'site',name=name.replace('_lower','_foot_site'),pos=vec([0,0,-desc['model']['spec']['lower_length']*.001]),size='.002')
    ET.SubElement(elements['base_link'], 'site', name='imu', size='.002')
    sensors = ET.SubElement(xml, 'sensor')
    ET.SubElement(sensors,'gyro',name='imu_gyro',site='imu'); ET.SubElement(sensors,'accelerometer',name='imu_accel',site='imu')
    ET.SubElement(sensors,'framequat',name='imu_quat',objtype='site',objname='imu')
    ET.indent(xml); return ET.tostring(xml,encoding='unicode')


def input_fingerprint(model):
    """Hash every geometry/mass input consumed by the robot compiler."""
    parts={}
    for name,part in model['parts'].items():
        path=(ROOT/part['step_url'].lstrip('/')).resolve()
        if not path.is_relative_to(ROOT/'artifacts'):raise ValueError('Invalid CAD source')
        parts[name]={k:part[k] for k in ('mass_kg','mass_basis','volume_mm3','positions','indices')}
        parts[name]['step_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    data=dict(spec=model['spec'],instances=model['instances'],parts=parts)
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _compile_into(model, config, digest, dest, inputs_sha):
    pkg = dest / 'forge_q4_description'; pkg.mkdir(parents=True,exist_ok=True)
    desc = build_description(model, config)
    meshes(model,pkg/'meshes'); urdf(desc,pkg)
    (pkg/'forge_q4.xml').write_text(mjcf(desc)+'\n')
    (pkg/'profile.yaml').write_text(yaml.safe_dump(config,allow_unicode=True))
    meta = {'format':'forge-robot-model-v1','model_revision':digest,'cad_revision':model['revision'],'cad_input_sha256':inputs_sha,'coordinates':'ROS REP-103: x forward, y left, z up; SI metres, kg, radians, kg m^2',
            'mass_kg':desc['mass'],'link_count':len(desc['links']),'actuated_joint_count':12,'cad_instance_count':len(model['instances']),
            'hardware_verified':False,'profile':config,'collision_model':'CAD meshes; MuJoCo convex hulls, adjacent bodies excluded by simulator defaults. Not an exact BREP clearance certificate.',
            'assumptions':['Assigned actuator/battery masses are retained. Their inertias assume uniform density over representative CAD solids.', 'Electronics and payload are central box masses, not measured distributions.', 'Motor casing allocation to rigid links is conceptual; rotor/stator and shaft inertias need a real actuator model.'],
            'step_volume_relative_error_limit':2e-6,
            'parts':{k:dict(mass_kg=p['mass'],com_m=p['com'].tolist(),inertia_kg_m2=p['inertia'].tolist(),basis=p['basis'],step_volume_relative_error=p['step_volume_relative_error'],step_sha256=p['step_sha256']) for k,p in desc['properties'].items()},
            'links':{k:dict(parent=l['parent'],joint=l['joint'],axis=l.get('axis'),origin=l['origin'].tolist(),home_world=l['world'].tolist(),mass_kg=l['mass'],com_m=l['com'].tolist(),inertia_kg_m2=l['inertia'].tolist(),instances=[p['id'] for p in l['parts']]) for k,l in desc['links'].items()},
            'instance_placements':desc['placements']}
    (pkg/'robot-model.json').write_text(json.dumps(meta,indent=2)+'\n')
    (pkg/'package.xml').write_text('''<?xml version="1.0"?><package format="3"><name>forge_q4_description</name><version>0.2.0</version><description>CAD-derived Q4 engineering reference, hardware unverified.</description><maintainer email="noreply@localhost">FORGE Q4</maintainer><license>MIT</license><buildtool_depend>ament_cmake</buildtool_depend><exec_depend>robot_state_publisher</exec_depend><exec_depend>joint_state_publisher_gui</exec_depend><exec_depend>rviz2</exec_depend><exec_depend>launch_ros</exec_depend><exec_depend>ament_index_python</exec_depend><export><build_type>ament_cmake</build_type></export></package>\n''')
    (pkg/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.8)\nproject(forge_q4_description)\nfind_package(ament_cmake REQUIRED)\ninstall(DIRECTORY meshes launch DESTINATION share/${PROJECT_NAME})\ninstall(FILES forge_q4.urdf forge_q4.xml robot-model.json profile.yaml README.md DESTINATION share/${PROJECT_NAME})\nament_package()\n')
    (pkg/'launch').mkdir(exist_ok=True)
    (pkg/'launch/display.launch.py').write_text('''from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
def generate_launch_description():
    folder=Path(get_package_share_directory('forge_q4_description'))
    description=(folder/'forge_q4.urdf').read_text()
    return LaunchDescription([
        Node(package='robot_state_publisher',executable='robot_state_publisher',parameters=[{'robot_description':description}]),
        Node(package='joint_state_publisher_gui',executable='joint_state_publisher_gui'),
        Node(package='rviz2',executable='rviz2')])
''')
    (pkg/'README.md').write_text('''# FORGE Q4 robot description

CAD-derived 13 rigid links / 12 revolute joints / 42 visual instances, SI / ROS coordinates. Joint position zero is the CAD assembly home pose. The URDF base is fixed when viewed alone; MuJoCo XML has a floating base, gravity, floor contacts and bounded motor torque.

ROS 2: put this directory in `your_ws/src`, run `colcon build --packages-select forge_q4_description`, source the workspace, then `ros2 launch forge_q4_description display.launch.py`. In RViz select `base_link` as Fixed Frame and add RobotModel. Launch code is supplied; ROS runtime must be verified on a ROS-equipped machine.

MuJoCo: `python -m mujoco.viewer --mjcf=forge_q4.xml`. Motors require a controller; this file alone does not command a gait. Run the FORGE server for the torque-limited reference controller.

Read `robot-model.json` and `profile.yaml` before engineering use. Hardware parameters, material densities, electronics/payload distributions and collision hulls remain assumptions. This package contains no hardware driver or hardware deployment approval.
''')
    manifest={str(p.relative_to(pkg)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(pkg.rglob('*')) if p.is_file() and p.name!='MANIFEST.json'}
    (pkg/'MANIFEST.json').write_text(json.dumps({'cad_revision':model['revision'],'model_revision':digest,'files':manifest},indent=2)+'\n')
    archive=dest/'FORGE-Q4-Robotics.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as out:
        for file in sorted(pkg.rglob('*')):
            if file.is_file():out.write(file,'forge_q4_description/'+str(file.relative_to(pkg)))
    desc.update(directory=dest,package=pkg,metadata=meta,revision=digest)
    return desc


def verified_package(dest):
    """Check immutable published files and their ZIP against one manifest."""
    pkg=dest/'forge_q4_description'
    manifest=json.loads((pkg/'MANIFEST.json').read_text())
    with zipfile.ZipFile(dest/'FORGE-Q4-Robotics.zip') as archive:
        if archive.testzip() is not None:raise ValueError('Invalid robotics ZIP')
        if json.loads(archive.read('forge_q4_description/MANIFEST.json'))!=manifest:
            raise ValueError('Robotics ZIP manifest mismatch')
        for name,sha in manifest['files'].items():
            path=(pkg/name).resolve()
            if not path.is_relative_to(pkg.resolve()):raise ValueError('Invalid package path')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=sha or hashlib.sha256(archive.read('forge_q4_description/'+name)).hexdigest()!=sha:
                raise ValueError('Robotics package hash mismatch: '+name)
    return json.loads((pkg/'robot-model.json').read_text())


def compile_robot(model, config=None):
    config=config or profile()
    inputs_sha=input_fingerprint(model)
    digest=hashlib.sha256((model['revision']+inputs_sha+hashlib.sha256(Path(__file__).read_bytes()).hexdigest()+json.dumps(config,sort_keys=True)).encode()).hexdigest()[:16]
    OUTPUT.mkdir(parents=True,exist_ok=True);dest=OUTPUT/digest
    if dest.exists():
        meta=verified_package(dest);desc=build_description(model,config)
    else:
        # Publish one complete directory atomically. Independent CLI/server
        # compilers may race; the loser verifies and reuses the winner's files.
        with tempfile.TemporaryDirectory(prefix='.build-',dir=OUTPUT) as folder:
            stage=Path(folder);desc=_compile_into(model,config,digest,stage,inputs_sha)
            verified_package(stage)
            try:os.rename(stage,dest)
            except OSError as error:
                if error.errno not in (errno.EEXIST,errno.ENOTEMPTY):raise
            meta=verified_package(dest)
    if meta['cad_revision']!=model['revision'] or meta['model_revision']!=digest or meta['cad_input_sha256']!=inputs_sha:
        raise ValueError('Robotics package revision mismatch')
    desc.update(directory=dest,package=dest/'forge_q4_description',metadata=meta,revision=digest)
    return desc


if __name__ == '__main__':
    model=json.loads((ROOT/'web/default-model.json').read_text())
    result=compile_robot(model)
    print(json.dumps({k:result['metadata'][k] for k in ['cad_revision','model_revision','mass_kg','link_count','actuated_joint_count']},indent=2))
    print(result['directory'])
