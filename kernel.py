"""Deterministic CAD compiler. No user code execution and no hidden LLM calls."""
from __future__ import annotations
import copy
import hashlib
import json
import math
import time
from pathlib import Path
from build123d import (Box, Cylinder, Sphere, Rectangle, Circle, Plane, Pos,
                      Rot, Location, Compound, Align, extrude, fillet,
                      export_step, import_step, Axis, Polygon, Ellipse, loft, chamfer)

ROOT = Path(__file__).resolve().parent
DEFAULT = dict(name="FORGE Q4", units="mm", body_length=340, body_width=180,
               body_height=64, upper_length=110, lower_length=140,
               link_width=32, link_thickness=7, bore_diameter=10,
               material="aluminium", payload_kg=1.0, target_mass_kg=7.0,
               actuator_mass_kg=.18, electronics_mass_kg=.65,
               battery_mass_kg=.55, joint_limit_deg=65)
MATERIALS = {
    "aluminium": dict(label="Nhôm đại diện", density_kg_m3=2700, color="#ededeb"),
    "pa12": dict(label="PA12 đại diện", density_kg_m3=1010, color="#dcdcd8"),
    "steel": dict(label="Thép đại diện", density_kg_m3=7850, color="#b7b7b7"),
}
RANGES = dict(body_length=(260,400), body_width=(150,250), body_height=(58,90),
              upper_length=(110,190), lower_length=(110,210), link_width=(12,48),
              link_thickness=(4,12), bore_diameter=(6,16), payload_kg=(0,4),
              target_mass_kg=(2,20), actuator_mass_kg=(.05,.6),
              electronics_mass_kg=(0,3), battery_mass_kg=(0,3),joint_limit_deg=(30,90))

class SpecError(ValueError):
    pass

def validate(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise SpecError("Đặc tả phải là một object.")
    unknown = set(raw)-set(DEFAULT)
    if unknown:
        raise SpecError("Trường chưa được hỗ trợ: " + ", ".join(sorted(unknown)))
    s = {**DEFAULT, **raw}
    for key,(lo,hi) in RANGES.items():
        v=s[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not lo<=v<=hi:
            raise SpecError(f"{key} phải nằm trong [{lo}, {hi}].")
        s[key]=int(v) if v==int(v) else float(v)
    if s["material"] not in MATERIALS:
        raise SpecError("Vật liệu phải là aluminium, pa12 hoặc steel.")
    if s["units"] != "mm" or s["name"] != "FORGE Q4":
        raise SpecError("PoC này chỉ hỗ trợ FORGE Q4, đơn vị mm.")
    ligament=(s["link_width"]*.85-s["bore_diameter"])/2
    if ligament < 6:
        raise SpecError(f"Vành vật liệu quanh lỗ chỉ còn {ligament:g} mm; cần ít nhất 6 mm theo quy tắc PoC. Tăng bề rộng tay hoặc giảm đường kính lỗ.")
    return s

def capsule_link(length: float, width: float, thickness: float, bore: float):
    # The end-circle centres are separated by `length`. Independent analytic oracle.
    profile=(Circle(width/2) + Pos(0,-length)*Circle(width/2)
             + Pos(0,-length/2)*Rectangle(width,length))
    profile=profile-Circle(bore/2)-Pos(0,-length)*Circle(bore/2)
    return Pos(0,thickness/2,0)*extrude(Plane.XZ*profile,amount=thickness)

def analytic_link_volume(length,width,thickness,bore):
    return (width*length+math.pi*(width/2)**2-2*math.pi*(bore/2)**2)*thickness

def hull_profile(length,width,z):
    x,y=length/2,width/2
    outline=Polygon((-x,-y*.65),(-x*.76,-y),(x*.76,-y),(x,-y*.65),
                    (x,y*.65),(x*.76,y),(-x*.76,y),(-x,y*.65))
    return Pos(0,0,z)*fillet(outline.vertices(),min(6,width*.04))

def leg_fairing(length,width,link,lower=False):
    """Hollow lofted casing around a separate, analytically verified structural link."""
    scale=.92 if lower else 1.18
    sections=[Pos(0,0,18)*Ellipse(width*scale*.58,10),
              Pos(7 if lower else -7,0,-length*.40)*Ellipse(width*scale*.51,11),
              # The lower casing must stop above the fixed foot pad. Extending
              # it past the link endpoint made the casing hit the floor first.
              Pos(0,0,-length+6 if lower else -length-18)*Ellipse(width*scale*.43,7)]
    raw=loft(sections,ruled=False)
    casing=raw-link
    for z in (0,-length):casing=casing-Pos(0,0,z)*Rot(90,0,0)*Cylinder(6,40)
    return casing

def tessellation(shape):
    vertices,triangles=shape.tessellate(.65,.18)
    return {"positions":[round(c*.001,7) for v in vertices for c in (v.X,v.Z,-v.Y)],
            "indices":[int(i) for tri in triangles for i in tri]}

def build(raw:dict, output_dir:Path|None=None, verify_roundtrip=True, include_documentation=True):
    started=time.perf_counter();s=validate(raw)
    compiler_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    rev=hashlib.sha256((compiler_hash+json.dumps(s,sort_keys=True)).encode()).hexdigest()[:12]
    dest=(output_dir or ROOT/"artifacts")/rev;dest.mkdir(parents=True,exist_ok=True)
    L,W,H=s["body_length"],s["body_width"],s["body_height"]
    wall=3.0
    # Faceted monocoque with a narrower belly and inset shoulders.
    outer=loft([hull_profile(L*.84,W*.80,-H/2),hull_profile(L,W,-H*.08),
                hull_profile(L*.95,W*.92,H/2)],ruled=True)
    inner=loft([hull_profile(L*.84-6,W*.80-6,-H/2+wall),
                hull_profile(L-6,W-6,-H*.08),hull_profile(L*.95-6,W*.92-6,H/2+10)],ruled=True)
    frame=outer-inner
    for x in (-L*.34,L*.34):
        for y in (-W/2,W/2):
            frame=frame-Rot(90,0,0)*Pos(x,0,-y)*Cylinder(6,W+10)
    cover=loft([hull_profile(L*.95,W*.92,-1.5),hull_profile(L*.94,W*.90,1.5)],ruled=True)
    for x in (-L*.4,L*.4):
        for y in (-W*.34,W*.34):
            cover=cover-Pos(x,y,0)*Cylinder(2.1,8)
    for x in (-L*.27,-L*.24,-L*.21,-L*.18,-L*.15,-L*.12):
        cover=cover-Pos(x,0,0)*Box(3,W*.22,12)
    upper=capsule_link(s["upper_length"],s["link_width"],s["link_thickness"],s["bore_diameter"])
    lower=capsule_link(s["lower_length"],s["link_width"]*.85,s["link_thickness"],s["bore_diameter"])
    # Assemblies use schematic actuator geometry and explicitly prescribed mass.
    motor=chamfer(Cylinder(24,16).edges(),.7)+Pos(0,0,9)*Cylinder(21,2)+Pos(0,0,11)*Cylinder(7,2)
    for a in range(0,360,60):
        motor=motor-Pos(17*math.cos(math.radians(a)),17*math.sin(math.radians(a)),0)*Cylinder(1.7,40)
    # A 32 mm pad stands below the lower link's 27.2 mm end capsule, so ground
    # contact belongs to rubber rather than the structural metal link.
    foot=fillet(Box(26,24,32).edges(),6)
    sensor=fillet(Box(14,W*.66,25).edges().filter_by(Axis.X),7)
    visor_pocket=fillet(Box(55,W*.665,25.5).edges().filter_by(Axis.X),7)
    frame=frame-Pos(L*.47,0,2)*visor_pocket
    for y in (-W*.20,W*.20):
        sensor=sensor-Pos(0,y,0)*Rot(0,90,0)*Cylinder(6,20)
    lens=Cylinder(5.5,6)
    battery=fillet(Box(L*.50,W*.66,36).edges(),3)
    upper_fairing=leg_fairing(s['upper_length'],s['link_width'],upper)
    lower_fairing=leg_fairing(s['lower_length'],s['link_width']*.85,lower,True)
    shoulder=loft([Pos(0,0,-33)*Ellipse(24,28),Pos(0,0,-13)*Ellipse(32,36),
                   Pos(0,0,7)*Ellipse(30,32)])
    shoulder=shoulder-Cylinder(24.5,80)
    definitions={
       "frame":(frame,"Khung chịu lực","shell",1),
       "cover":(cover,"Nắp thân","carbon",1),
       "upper":(upper,"Tay chân trên","metal",4),
       "lower":(lower,"Tay chân dưới","metal",4),
       "motor":(motor,"Actuator đại diện","motor",12),
       "foot":(foot,"Đệm bàn chân","rubber",4),
       "sensor":(sensor,"Giá cảm biến","dark",1),
       "lens":(lens,"Ống kính đại diện","glass",2),
       "battery":(battery,"Pin đại diện","battery",1),
       "upper_fairing":(upper_fairing,"Vỏ chân trên","shell",4),
       "lower_fairing":(lower_fairing,"Vỏ chân dưới","carbon",4),
       "shoulder":(shoulder,"Vỏ vai","shell",4),
    }
    parts={};rho=MATERIALS[s["material"]]["density_kg_m3"]
    for key,(shape,label,role,count) in definitions.items():
        mass=shape.volume*rho/1e9
        basis="V × mật độ giả định"
        if key=="motor":mass=s["actuator_mass_kg"];basis="Khối lượng gán; chưa có datasheet"
        if key=="battery":mass=s["battery_mass_kg"];basis="Khối lượng gán; chưa có datasheet"
        if key=="foot":mass=shape.volume*1100/1e9;basis="V × mật độ cao su giả định"
        if key=="lens":mass=.012;basis="Khối lượng giả định"
        if key=="sensor":mass=shape.volume*1010/1e9;basis="V × mật độ polymer giả định"
        if key in ('upper_fairing','lower_fairing','shoulder'):
            mass=shape.volume*1010/1e9;basis="V × mật độ vỏ polymer giả định"
        center=shape.center()
        parts[key]={**tessellation(shape),"name":label,"role":role,"count":count,"com_mm":[center.X,center.Y,center.Z],
                    "volume_mm3":shape.volume,"mass_kg":mass,"mass_basis":basis,
                    "valid":bool(shape.is_valid),"solids":len(shape.solids())}
    ul,ll=s["upper_length"],s["lower_length"]
    angle=.62;body_z=(ul+ll)*math.cos(angle)+25
    instances=[];assembly_parts=[]
    def add(key,id,pos,rot=(0,0,0),explode=(0,0,0)):
        obj=copy.deepcopy(definitions[key][0]);obj.label=id
        obj=obj.moved(Location(pos,rot));assembly_parts.append(obj)
        instances.append(dict(part=key,id=id,position_mm=list(pos),rotation_deg=list(rot),explode_mm=list(explode)))
    add("frame","chassis",(0,0,body_z))
    add("cover","top_cover",(0,0,body_z+H/2+1.5),explode=(0,0,115))
    add("battery","battery",(-L*.08,0,body_z+3),explode=(-60,0,75))
    add("sensor","sensor_front",(L*.47,0,body_z+2),explode=(90,0,0))
    for n,y in enumerate((-W*.20,W*.20)):
        add("lens",f"camera_{n}",(L*.47+8,y,body_z+2),(0,90,0),(135,0,0))
    for ix,signx in enumerate((-1,1)):
      for iy,signy in enumerate((-1,1)):
        tag=f"{'rear' if signx<0 else 'front'}_{'right' if signy<0 else 'left'}"
        x,y=signx*L*.34,signy*(W/2+28)
        theta=-signx*angle;knee=signx*angle*2
        hipz=body_z-8
        kx=x+ul*math.sin(theta);kz=hipz-ul*math.cos(theta)
        fx=kx+ll*math.sin(theta+knee);fz=kz-ll*math.cos(theta+knee)
        add("motor",tag+"_roll",(x,signy*(W/2+2),hipz),(signy*90,0,0),(0,signy*75,0))
        add("shoulder",tag+"_shoulder",(x,signy*(W/2+2),hipz),(signy*90,0,0),(0,signy*85,15))
        add("motor",tag+"_hip",(x,y+signy*8,hipz),(signy*90,0,0),(signx*12,signy*110,0))
        add("upper",tag+"_upper",(x,y,hipz),(0,-math.degrees(theta),0),(0,signy*120,-25))
        add("upper_fairing",tag+"_upper_fairing",(x,y,hipz),(0,-math.degrees(theta),0),(0,signy*150,-10))
        add("motor",tag+"_knee",(kx,y+signy*8,kz),(signy*90,0,0),(signx*20,signy*160,-30))
        lower_y=y+signy*(s["link_thickness"]+3)
        add("lower",tag+"_lower",(kx,lower_y,kz),(0,-math.degrees(theta+knee),0),(signx*35,signy*175,-65))
        add("lower_fairing",tag+"_lower_fairing",(kx,lower_y,kz),(0,-math.degrees(theta+knee),0),(signx*35,signy*205,-45))
        add("foot",tag+"_foot",(fx,lower_y,fz),(0,0,0),(signx*45,signy*195,-70))
    assembly=Compound(label="FORGE_Q4",children=assembly_parts)
    step=dest/"forge-q4.step";export_step(assembly,step)
    total_volume=sum(obj.volume for obj in assembly_parts)
    roundtrip=None
    if verify_roundtrip:
        imported=import_step(step)
        restored=sum(obj.volume for obj in imported.solids())
        roundtrip={"volume_before_mm3":total_volume,"volume_after_mm3":restored,
                   "relative_error":abs(restored-total_volume)/total_volume,
                   "solid_count":len(imported.solids()),"valid":bool(imported.is_valid)}
    analytic=[]
    for key,length,width in (("upper",ul,s["link_width"]),("lower",ll,s["link_width"]*.85)):
        expected=analytic_link_volume(length,width,s["link_thickness"],s["bore_diameter"])
        measured=parts[key]["volume_mm3"]
        analytic.append(dict(part=key,formula_mm3=expected,cad_mm3=measured,relative_error=abs(expected-measured)/expected))
    clearance_samples=[]
    for joint_angle in (-65,-32.5,0,32.5,65):
        trial=lower.moved(Location((0,s["link_thickness"]+3,-ul),(0,joint_angle,0)))
        clearance_samples.append(dict(joint_deg=joint_angle,distance_mm=upper.distance_to(trial)))
    total_mass=sum(v["mass_kg"]*v["count"] for v in parts.values())+s["electronics_mass_kg"]
    ligament=(s["link_width"]*.85-s["bore_diameter"])/2
    checks=[dict(id="brep",name="Khối CAD hợp lệ",passed=all(v["valid"] and v["solids"]==1 for v in parts.values()),method="OCCT / BREP",detail=f"{len(parts)} hình học duy nhất, {len(instances)} chi tiết lắp ráp"),
            dict(id="analytic",name="Thể tích khớp công thức",passed=all(v["relative_error"]<1e-6 for v in analytic),method="Công thức độc lập",detail="Tay capsule: (wL + πr² − 2πr_lỗ²) × t"),
            dict(id="roundtrip",name="STEP đọc lại đúng",passed=bool(roundtrip and roundtrip["relative_error"]<1e-6 and roundtrip["valid"] and roundtrip["solid_count"]==len(instances)),method="Xuất → nhập lại",detail="So sánh tổng thể tích và số khối sau trao đổi CAD"),
            dict(id="wall",name="Vành lỗ đủ bề dày",passed=ligament>=6,method="Quy tắc PoC / 6 mm",detail=f"Vành nhỏ nhất {ligament:.2f} mm; không thay tính bền"),
            dict(id="clearance",name="Hai tay chịu lực có khe hở",passed=min(v["distance_mm"] for v in clearance_samples)>=2.99,method="Khoảng cách BREP / 5 góc",detail="Khe giữa hai tay chịu lực ≥ 3 mm; chưa quét vỏ và toàn bộ robot"),
            dict(id="mass",name="Trong ngân sách khối lượng",passed=total_mass+s["payload_kg"]<=s["target_mass_kg"],method="CAD + khối lượng gán",detail=f"{total_mass+s['payload_kg']:.2f} / {s['target_mass_kg']:.2f} kg, đã gồm tải")]
    # Keep mass distribution explicit for browser kinematic CoM calculation.
    result={"revision":rev,"compiler_hash":compiler_hash,"spec":s,"parts":parts,"instances":instances,
            "materials":MATERIALS,"metrics":{"mass_kg":total_mass,"loaded_mass_kg":total_mass+s["payload_kg"],"height_mm":body_z+H/2+3,"part_count":len(instances),"unique_parts":len(parts),"joint_count":12,"ligament_mm":ligament},
            "proof":{"checks":checks,"analytic":analytic,"roundtrip":roundtrip,"clearance_samples":clearance_samples},
            "coordinate_system":"CAD x forward, y left, z up; viewer x forward, y up, z right",
            "step_url":f"/artifacts/{rev}/forge-q4.step",
            "duration_ms":round((time.perf_counter()-started)*1000),
            "limitations":["Chuyển động động học minh họa, chưa mô phỏng động lực học.","Vật liệu và khối lượng linh kiện là giả định PoC; chưa có datasheet.","Không có FEA, kiểm tra mỏi, nhiệt, dung sai chế tạo hoặc thử tải.","Lệnh văn bản dùng bộ phân tích cục bộ, không gọi LLM."]}
    from technical import generate
    if include_documentation:result["documentation"]=generate(result,definitions,assembly,dest)
    result["duration_ms"]=round((time.perf_counter()-started)*1000)
    (dest/"model.json").write_text(json.dumps(result,separators=(",",":"),ensure_ascii=False))
    (dest/"spec.json").write_text(json.dumps(s,indent=2,ensure_ascii=False))
    (dest/"proof.json").write_text(json.dumps(result["proof"],indent=2,ensure_ascii=False))
    return result

if __name__=="__main__":
    import yaml
    result=build(yaml.safe_load((ROOT/"spec.yaml").read_text()))
    (ROOT/"web/default-model.json").write_text(json.dumps(result,separators=(",",":"),ensure_ascii=False))
    print(json.dumps({"revision":result["revision"],"metrics":result["metrics"],"checks":result["proof"]["checks"],"duration_ms":result["duration_ms"]},ensure_ascii=False,indent=2))
