"""Bounded feature graph -> OCCT BREP. Data only; never executes proposal code."""
from __future__ import annotations
import ast,copy,hashlib,json,math,re
from pathlib import Path
from build123d import (Axis,Box,Circle,Compound,Cylinder,GeomType,Plane,Polygon,Pos,Rectangle,Rot,
                       SlotOverall,export_step,extrude,fillet,chamfer,import_step)
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'design-output'
PARAM=re.compile(r'[A-Za-z][A-Za-z0-9_]{0,31}')


def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def sha(v):return hashlib.sha256(canonical(v).encode()).hexdigest()
def finite(v,name,lo=-500,hi=500):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError(f'{name}: finite number in [{lo}, {hi}] required')
    return float(v)
def text(v,name,limit=200):
    if not isinstance(v,str) or not v.strip() or len(v)>limit:raise ValueError(name+': invalid text')
    return v.strip()
def exact(obj,fields,name):
    if not isinstance(obj,dict) or set(obj)!=set(fields):raise ValueError(name+': fields must be '+', '.join(fields))


def expression(value,params):
    if isinstance(value,(int,float)) and not isinstance(value,bool):return finite(value,'expression',-2000,2000)
    if not isinstance(value,str) or len(value)>100:raise ValueError('Expressions must be numbers or <=100-character arithmetic')
    try:node=ast.parse(value,mode='eval')
    except SyntaxError:raise ValueError('Invalid arithmetic expression')
    if len(list(ast.walk(node)))>40:raise ValueError('Expression too complex')
    def read(n):
        if isinstance(n,ast.Expression):return read(n.body)
        if isinstance(n,ast.Constant):return finite(n.value,'constant',-2000,2000)
        if isinstance(n,ast.Name) and n.id in params:return params[n.id]
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return read(n.operand)*(1 if isinstance(n.op,ast.UAdd) else -1)
        if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Add,ast.Sub,ast.Mult,ast.Div)):
            a,b=read(n.left),read(n.right)
            if isinstance(n.op,ast.Div) and abs(b)<1e-9:raise ValueError('Division by zero')
            result=a+b if isinstance(n.op,ast.Add) else a-b if isinstance(n.op,ast.Sub) else a*b if isinstance(n.op,ast.Mult) else a/b
            return finite(result,'arithmetic result',-2000,2000)
        raise ValueError('Only parameter names, + - * / and parentheses are supported')
    return read(node)


def vector(v,p):
    if not isinstance(v,list) or len(v)!=3:raise ValueError('Expected vector of three expressions')
    return [expression(x,p) for x in v]


def default_interface():
    return dict(mount_holes=[dict(x_mm=x,y_mm=y,diameter_mm=4.2) for x in (-20,20) for y in (-10,10)],
                mount_plane_z_mm=0.,source_note='Synthetic fixture dimensions, not a vendor sensor or Q4 mounting interface.')


def validate_interface(raw):
    exact(raw,['mount_holes','mount_plane_z_mm','source_note'],'interface')
    if not isinstance(raw['mount_holes'],list) or not 1<=len(raw['mount_holes'])<=12:raise ValueError('Use 1–12 sensor holes')
    holes=[];positions=set()
    for h in raw['mount_holes']:
        exact(h,['x_mm','y_mm','diameter_mm'],'mount hole')
        v=dict(x_mm=finite(h['x_mm'],'hole x',-100,100),y_mm=finite(h['y_mm'],'hole y',-100,100),diameter_mm=finite(h['diameter_mm'],'hole diameter',1,12))
        key=(v['x_mm'],v['y_mm'])
        if key in positions:raise ValueError('Duplicate mounting hole')
        positions.add(key);holes.append(v)
    return dict(mount_holes=holes,mount_plane_z_mm=finite(raw['mount_plane_z_mm'],'mount plane',-.001,.001),source_note=text(raw['source_note'],'source',500))


def overlap(a,b):
    common=a&b
    return common.volume if common is not None else 0.


def mesh(shape):
    # OCCT triangulation can affect bounding boxes and downstream selectors.
    # Never attach display triangulation to the authoritative BREP.
    shape=copy.deepcopy(shape)
    vertices,triangles=shape.tessellate(.03,.15)
    if len(vertices)>40000 or len(triangles)>80000:raise ValueError('Mesh exceeds workbench complexity limit')
    return dict(positions=[round(c,5) for v in vertices for c in (v.X,v.Z,-v.Y)],indices=[int(i) for tri in triangles for i in tri])


def inspect_reference(path,interface):
    interface=validate_interface(interface);sensor=import_step(path)
    box=sensor.bounding_box()
    if len(sensor.faces())>400 or len(sensor.edges())>1000:raise ValueError('Reference STEP exceeds topology complexity limit')
    if not sensor.is_valid or len(sensor.solids())!=1:raise ValueError('Reference STEP must contain one valid solid')
    if abs(box.min.Z)> .001:raise ValueError('Reference STEP mounting face must lie at Z=0; align it in CAD before import')
    if max(box.size.X,box.size.Y,box.size.Z)>150 or min(box.size.X,box.size.Y,box.size.Z)<1:raise ValueError('Reference envelope must be 1–150 mm on each axis')
    for h in interface['mount_holes']:
        probe=Pos(h['x_mm'],h['y_mm'],box.size.Z/2)*Cylinder(h['diameter_mm']/2-.01,box.size.Z+2)
        if overlap(sensor,probe)>.001:raise ValueError('Declared sensor hole is not a through clearance in imported BREP')
        if not (box.min.X<h['x_mm']<box.max.X and box.min.Y<h['y_mm']<box.max.Y):raise ValueError('Sensor hole outside reference envelope')
    return sensor,dict(bbox_min_mm=list(box.min),bbox_max_mm=list(box.max),volume_mm3=sensor.volume,
                       geometry_valid=True,interface_voids_verified=True,source_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),mesh=mesh(sensor))


def ensure_reference():
    folder=OUTPUT/'.references'/'fixture-sensor-v1';folder.mkdir(parents=True,exist_ok=True)
    file=folder/'sensor.step'
    if not file.exists():
        s=Pos(0,0,11)*Box(50,30,22)
        for h in default_interface()['mount_holes']:s=s-Pos(h['x_mm'],h['y_mm'],11)*Cylinder(h['diameter_mm']/2,30)
        s.label='SYNTHETIC SENSOR / NOT HARDWARE';export_step(s,file)
        meta=dict(id='fixture-sensor-v1',name='Sensor fixture 50 × 30 × 22',provenance='synthetic_fixture',interface=default_interface())
        (folder/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
    return folder


def brief(reference='fixture-sensor-v1'):
    if reference=='fixture-sensor-v1':folder=ensure_reference()
    elif isinstance(reference,str) and re.fullmatch('[a-f0-9]{32}',reference):folder=OUTPUT/'.references'/reference
    else:raise ValueError('Invalid reference ID')
    if not (folder/'metadata.json').is_file():raise ValueError('Reference unavailable')
    meta=json.loads((folder/'metadata.json').read_text());_,geometry=inspect_reference(folder/'sensor.step',meta['interface'])
    result=dict(format='forge-design-brief-v1',name='Gá cảm biến / mounting fixture',units='mm',reference_id=reference,
                sensor=dict(name=meta['name'],provenance=meta['provenance'],interface=meta['interface'],geometry={k:v for k,v in geometry.items() if k!='mesh'}),
                carrier=dict(name='Synthetic receiving plate',mount_holes=[dict(x_mm=x,y_mm=y,diameter_mm=5.2) for x in (-35,35) for y in (-25,25)],width_mm=120,length_mm=90,thickness_mm=8),
                requirements=dict(max_envelope_mm=[100,80,45],max_mass_kg=.18,min_hole_web_mm=2.,plate_thickness_mm=4.,max_sensor_shift_mm=20.,hole_diameter_tolerance_mm=.1),
                density_kg_m3=2700.,density_basis='Representative aluminium assumption; not a material certificate',
                missing=['Structural load/FEA/fatigue','Fits, GD&T, threads and screw selection','Optical FOV and cable bend verification','Supplier data and hardware trial'],
                scope='Single connected machined bracket with fixed receiving interface. Synthetic carrier is not the Q4 cover.')
    return {**result,'brief_sha256':sha(result)},folder/'sensor.step',geometry['mesh']


def example(b):
    holes=b['sensor']['interface']['mount_holes'];carrier=b['carrier']['mount_holes']
    p=dict(width=90.,length=70.,thickness=4.,sensor_shift_x=0.,sensor_shift_y=0.,sensor_hole_diameter=holes[0]['diameter_mm'],rib_height=12.,rib_width=3.,rib_length=32.)
    f=[dict(id='plate_profile',op='sketch',plane='XY',origin=[0,0,0],profile=dict(kind='rectangle',width='width',height='length')),
       dict(id='plate',op='extrude',sketch='plate_profile',amount='thickness'),
       dict(id='sensor_bore',op='sketch',plane='XY',origin=[0,0,-1],profile=dict(kind='circle',diameter='sensor_hole_diameter')),
       dict(id='sensor_tool',op='extrude',sketch='sensor_bore',amount='thickness+2'),
       dict(id='sensor_pattern',op='pattern',source='sensor_tool',translations=[[f"sensor_shift_x+({h['x_mm']})",f"sensor_shift_y+({h['y_mm']})",0] for h in holes]),
       dict(id='sensor_mount',op='boolean',base='plate',tool='sensor_pattern',mode='cut'),
       dict(id='carrier_bore',op='sketch',plane='XY',origin=[0,0,-1],profile=dict(kind='circle',diameter=5.2)),
       dict(id='carrier_tool',op='extrude',sketch='carrier_bore',amount='thickness+2'),
       dict(id='carrier_pattern',op='pattern',source='carrier_tool',translations=[[h['x_mm'],h['y_mm'],0] for h in carrier]),
       dict(id='mounting_plate',op='boolean',base='sensor_mount',tool='carrier_pattern',mode='cut'),
       dict(id='edge_finish',op='fillet',source='mounting_plate',edges=dict(type='LINE',parallel_axis='Z',at=None),radius=3)]
    # Imported references may have different hole sizes; use independent tools for those holes.
    if len({h['diameter_mm'] for h in holes})>1:
        groups={}
        for hole in holes:groups.setdefault(hole['diameter_mm'],[]).append(hole)
        group_nodes=[];base='plate'
        for index,(diameter,members) in enumerate(groups.items()):
            prefix='sensor_'+str(index+1)
            group_nodes.extend([
                dict(id=prefix+'_bore',op='sketch',plane='XY',origin=[0,0,-1],profile=dict(kind='circle',diameter=diameter)),
                dict(id=prefix+'_tool',op='extrude',sketch=prefix+'_bore',amount='thickness+2'),
                dict(id=prefix+'_pattern',op='pattern',source=prefix+'_tool',translations=[[f"sensor_shift_x+({h['x_mm']})",f"sensor_shift_y+({h['y_mm']})",0] for h in members]),
                dict(id=prefix+'_mount',op='boolean',base=base,tool=prefix+'_pattern',mode='cut')])
            base=prefix+'_mount'
        f=f[:2]+group_nodes+f[6:]
        next(node for node in f if node['id']=='mounting_plate')['base']=base
    f.extend([
        dict(id='rib_profile',op='sketch',plane='XY',origin=[0,0,'thickness'],profile=dict(kind='rectangle',width='rib_width',height='rib_length')),
        dict(id='rib',op='extrude',sketch='rib_profile',amount='rib_height'),
        dict(id='rib_finish',op='chamfer',source='rib',edges=dict(type='LINE',parallel_axis=None,at=dict(axis='Z',value='thickness+rib_height')),length=.5),
        dict(id='side_ribs',op='pattern',source='rib_finish',translations=[['-width/2+3.5',0,0],['width/2-3.5',0,0]]),
        dict(id='cradle',op='boolean',base='edge_finish',tool='side_ribs',mode='add')])
    return dict(format='forge-feature-design-v1',name='Sensor cradle / engineer-authored example',units='mm',brief_sha256=b['brief_sha256'],parameters=p,features=f,result='cradle')


OPS={
 'sketch':['id','op','plane','origin','profile'], 'extrude':['id','op','sketch','amount'],
 'boolean':['id','op','base','tool','mode'],'pattern':['id','op','source','translations'],
 'transform':['id','op','source','translation','rotation_deg'],
 'fillet':['id','op','source','edges','radius'],'chamfer':['id','op','source','edges','length']}


def validate(raw,b):
    exact(raw,['format','name','units','brief_sha256','parameters','features','result'],'program')
    if raw['format']!='forge-feature-design-v1' or raw['units']!='mm' or raw['brief_sha256']!=b['brief_sha256']:raise ValueError('Program format/units/brief hash mismatch; export current context')
    p=copy.deepcopy(raw);p['name']=text(p['name'],'name',120)
    if not isinstance(p['parameters'],dict) or not 1<=len(p['parameters'])<=24:raise ValueError('Use 1–24 named numeric parameters')
    for k,v in p['parameters'].items():
        if not PARAM.fullmatch(k):raise ValueError('Invalid parameter name')
        p['parameters'][k]=finite(v,k)
    if not isinstance(p['features'],list) or not 1<=len(p['features'])<=60:raise ValueError('Use 1–60 feature nodes')
    known={};params=p['parameters']
    for node in p['features']:
        op=node.get('op') if isinstance(node,dict) else None
        if op not in OPS:raise ValueError('Unsupported feature operation')
        exact(node,OPS[op],op)
        id=node['id']
        if not isinstance(id,str) or not PARAM.fullmatch(id) or id in known:raise ValueError('Duplicate/invalid feature ID')
        for key in ['source','sketch','base','tool']:
            if key in node:
                ref=node[key]
                if not isinstance(ref,str) or ref not in known:raise ValueError(id+': references must point to an earlier feature')
                if (key=='sketch') != (known[ref]=='sketch'):raise ValueError('Sketch/solid reference type mismatch')
        if op=='sketch':
            if node['plane'] not in ('XY','XZ','YZ'):raise ValueError('Plane must be XY, XZ or YZ')
            vector(node['origin'],params);s=node['profile'];kind=s.get('kind') if isinstance(s,dict) else None
            fields={'rectangle':['kind','width','height'],'circle':['kind','diameter'],'slot':['kind','length','width'],'polygon':['kind','points']}
            if kind not in fields:raise ValueError('Unknown sketch profile')
            exact(s,fields[kind],kind)
            if kind=='polygon':
                if not isinstance(s['points'],list) or not 3<=len(s['points'])<=20:raise ValueError('Polygon needs 3–20 points')
                for point in s['points']:
                    if not isinstance(point,list) or len(point)!=2:raise ValueError('Polygon point must have two expressions')
                    for value in point:expression(value,params)
            else:
                values={k:finite(expression(v,params),k,.2,200) for k,v in s.items() if k!='kind'}
                if kind=='slot' and values['length']<=values['width']:raise ValueError('Slot length must exceed width')
        elif op=='extrude':
            if abs(expression(node['amount'],params))<.2 or abs(expression(node['amount'],params))>150:raise ValueError('Extrusion must be 0.2–150 mm')
        elif op=='boolean':
            if node['mode'] not in ('add','cut','intersect'):raise ValueError('Invalid boolean mode')
        elif op=='pattern':
            if not isinstance(node['translations'],list) or not 1<=len(node['translations'])<=16:raise ValueError('Pattern needs 1–16 transforms')
            for v in node['translations']:vector(v,params)
        elif op=='transform':vector(node['translation'],params);vector(node['rotation_deg'],params)
        else:
            e=node['edges'];exact(e,['type','parallel_axis','at'],'edge selector')
            if e['type'] not in ('LINE','CIRCLE') or e['parallel_axis'] not in (None,'X','Y','Z'):raise ValueError('Unsupported semantic edge selector')
            if e['at'] is not None:
                exact(e['at'],['axis','value'],'edge coordinate')
                if e['at']['axis'] not in ('X','Y','Z'):raise ValueError('Invalid selector axis')
                expression(e['at']['value'],params)
            finite(expression(node.get('radius',node.get('length')),params),'edge finish',.1,10)
        known[id]=op
    if p['result'] not in known or known[p['result']]=='sketch':raise ValueError('Result must reference a solid feature')
    # The selected solid must depend on every node; unused graph branches are rejected.
    needed=set()
    def visit(id):
        if id in needed:return
        needed.add(id);n=next(n for n in p['features'] if n['id']==id)
        for k in ['source','sketch','base','tool']:
            if k in n:visit(n[k])
    visit(p['result'])
    if needed!=set(known):raise ValueError('Every feature must contribute to the result')
    return p


def evaluate_graph(p,previews=True):
    nodes={};log=[];params=p['parameters'];triangles=0
    for f in p['features']:
        id,op=f['id'],f['op'];selected=None
        try:
            if op=='sketch':
                s=f['profile'];v=lambda k:expression(s[k],params)
                shape=Rectangle(v('width'),v('height')) if s['kind']=='rectangle' else Circle(v('diameter')/2) if s['kind']=='circle' else SlotOverall(v('length'),v('width')) if s['kind']=='slot' else Polygon(*[tuple(expression(x,params) for x in pt) for pt in s['points']],align=None)
                shape=Pos(*vector(f['origin'],params))*(getattr(Plane,f['plane'])*shape)
            elif op=='extrude':
                sketch_node=next(n for n in p['features'] if n['id']==f['sketch'])
                shape=extrude(nodes[f['sketch']],amount=expression(f['amount'],params),dir=getattr(Plane,sketch_node['plane']).z_dir)
            elif op=='boolean':
                a,b=nodes[f['base']],nodes[f['tool']];shape=a+b if f['mode']=='add' else a-b if f['mode']=='cut' else a&b
            elif op=='pattern':shape=Compound(children=[Pos(*vector(v,params))*copy.deepcopy(nodes[f['source']]) for v in f['translations']])
            elif op=='transform':shape=Pos(*vector(f['translation'],params))*Rot(*vector(f['rotation_deg'],params))*copy.deepcopy(nodes[f['source']])
            else:
                shape=nodes[f['source']];e=f['edges'];edges=shape.edges().filter_by(getattr(GeomType,e['type']))
                if e['parallel_axis']:edges=edges.filter_by(getattr(Axis,e['parallel_axis']))
                if e['type']=='LINE':
                    # Straight seams on cylindrical faces are not physical sharp edges.
                    planar=shape.faces().filter_by(GeomType.PLANE)
                    edges=[edge for edge in edges if sum(any(edge.wrapped.IsSame(other.wrapped) for other in face.edges()) for face in planar)>=2]
                if e['at'] is not None:
                    axis=e['at']['axis'];value=expression(e['at']['value'],params)
                    edges=[edge for edge in edges if abs(getattr(edge.bounding_box().min,axis)-value)<.001 and abs(getattr(edge.bounding_box().max,axis)-value)<.001]
                selected=len(edges)
                if not selected:raise ValueError('Semantic selector matched no edges')
                shape=fillet(edges,expression(f['radius'],params)) if op=='fillet' else chamfer(edges,expression(f['length'],params))
            if len(shape.faces())>1200:raise ValueError('Feature exceeds topology complexity limit')
            if not shape.is_valid:raise ValueError('Invalid OCCT shape')
            nodes[id]=shape;box=shape.bounding_box();entry=dict(id=id,op=op,selected_edges=selected,bbox_mm=list(box.size),solid_count=len(shape.solids()),volume_mm3=shape.volume if op!='sketch' else None)
            if previews:
                data=mesh(shape);triangles+=len(data['indices'])//3
                if triangles<=150000:entry['mesh']=data
            log.append(entry)
        except Exception as e:raise ValueError(f'Feature {id} ({op}): {type(e).__name__}: {e}') from e
    return nodes[p['result']],log


def checks(shape,p,b,reference_path):
    params=p['parameters'];sx=params.get('sensor_shift_x',0.);sy=params.get('sensor_shift_y',0.);t=b['requirements']['plate_thickness_mm'];box=shape.bounding_box();sensor=Pos(sx,sy,t)*import_step(reference_path)
    gates=[];add=lambda id,passed,actual,requirement:gates.append(dict(id=id,passed=bool(passed),actual=actual,requirement=requirement))
    add('valid_single_solid',shape.is_valid and len(shape.solids())==1,len(shape.solids()),'One valid connected solid')
    add('envelope',all(v<=lim+.001 for v,lim in zip(box.size,b['requirements']['max_envelope_mm'])),list(box.size),'Envelope <= 100 × 80 × 45 mm')
    add('mass',shape.volume*b['density_kg_m3']/1e9<=b['requirements']['max_mass_kg'],shape.volume*b['density_kg_m3']/1e9,'Mass <= 0.18 kg under declared density')
    add('mount_plane',abs(box.min.Z)<.001,box.min.Z,'Part lower datum at Z=0')
    add('sensor_shift',abs(sx)<=20 and abs(sy)<=20,[sx,sy],'Sensor translation <=20 mm on each axis')
    add('sensor_collision',overlap(shape,sensor)<.001,overlap(shape,sensor),'No BREP volume overlap with reference sensor')
    hole_results=[];web=b['requirements']['min_hole_web_mm']
    for group,holes in [('carrier',b['carrier']['mount_holes']),('sensor',b['sensor']['interface']['mount_holes'])]:
        for i,h in enumerate(holes):
            x=h['x_mm']+(sx if group=='sensor' else 0);y=h['y_mm']+(sy if group=='sensor' else 0);r=h['diameter_mm']/2
            probe=Pos(x,y,t/2)*Cylinder(r-.01,t+.02);void=overlap(shape,probe)
            ring=Pos(x,y,t/2)*Cylinder(r+web,t)-Pos(x,y,t/2)*Cylinder(r+.15,t)
            retained=overlap(shape,ring)/ring.volume
            circles=[e for e in shape.edges() if e.geom_type==GeomType.CIRCLE and abs(e.radius-r)<=.05 and abs(e.bounding_box().center().X-x)<.01 and abs(e.bounding_box().center().Y-y)<.01 and abs(e.bounding_box().min.Z-t)<.01 and abs(e.bounding_box().max.Z-t)<.01]
            bore=void<.001 and bool(circles)
            add(f'{group}_hole_{i+1}',bore,dict(void_overlap_mm3=void,circular_edges=len(circles)),f'Through Ø{2*r:g} at ({x:g},{y:g}), upper datum Z=4')
            add(f'{group}_web_{i+1}',retained>=.98,retained,'>=98% material retained in declared 2 mm bearing ring; geometry only')
            hole_results.append(dict(group=group,x_mm=x,y_mm=y,diameter_mm=r*2,verified=bore,web_fraction=retained,actual_diameter_mm=circles[0].radius*2 if circles else None))
    # Clearance for a vertical tool over receiving fasteners; not full toolpath/access qualification.
    access=max(overlap(shape,Pos(h['x_mm'],h['y_mm'],t+10)*Cylinder(5,19.8)) for h in b['carrier']['mount_holes'])
    add('receiving_tool_clearance',access<.001,access,'No bracket material in Ø10 ×19.8 vertical tool cylinders above receiving fasteners')
    return gates,hole_results,sensor


def diff(before,after):
    old={f['id']:f for f in before['features']};new={f['id']:f for f in after['features']}
    return dict(parameters={k:dict(before=before['parameters'].get(k),after=after['parameters'].get(k)) for k in sorted(set(before['parameters'])|set(after['parameters'])) if before['parameters'].get(k)!=after['parameters'].get(k)},
                added=[k for k in new if k not in old],removed=[k for k in old if k not in new],changed=[k for k in new if k in old and new[k]!=old[k]])
