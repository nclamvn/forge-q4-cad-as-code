"""Revision-linked engineering drawings from OCCT solids, not from display meshes."""
from __future__ import annotations
import copy, hashlib, html, json, math, zipfile
from pathlib import Path
from build123d import Compound, Plane, Location, section, ExportDXF, LineType, GeomType
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm

PART_INFO={
 'frame':('Q4-101','Kết cấu',['body_length','body_width','body_height'],['Loft 3 tiết diện bo góc','Trừ khoang rỗng, thành 3 mm','Khoét lỗ vai Ø12 và hốc visor'],['Vỏ đúc/gia công là phương án tham khảo','Chưa có draft angle, dung sai hoặc tính bền']),
 'cover':('Q4-102','Kết cấu',['body_length','body_width'],['Loft nắp 3 mm','4 lỗ Ø4.2 tại x ±0.4L, y ±0.34W','6 khe 3 × 0.22W xuyên nắp'],['Cần xác nhận khoảng lắp nắp với khung','Finish graphite chỉ là hiển thị']),
 'upper':('Q4-201','Cơ cấu chân',['upper_length','link_width','link_thickness','bore_diameter'],['Sketch capsule: hai cung và hai cạnh','Trừ 2 biên dạng lỗ đồng tâm','Extrude theo độ dày; lắp 4 bản'],['Vành nhỏ nhất kiểm theo tay dưới','Chưa định nghĩa fit lỗ hoặc tải khớp']),
 'lower':('Q4-202','Cơ cấu chân',['lower_length','link_width','link_thickness','bore_diameter'],['Capsule rộng 0.85 × link_width','Trừ 2 lỗ xuyên tại hai tâm','Extrude; lệch mặt tay trên 3 mm'],['Khe 3 mm kiểm tại 5 góc mẫu','Chưa quét va chạm toàn bộ vỏ']),
 'upper_fairing':('Q4-203','Vỏ chân',['upper_length','link_width','link_thickness'],['Loft 3 ellipse với độ lệch -7 mm','Trừ thể tích tay chịu lực','Khoét hai vùng khớp Ø12'],['Mật độ polymer 1010 kg/m³ là giả định','Chưa thiết kế gân, chốt hoặc khuôn']),
 'lower_fairing':('Q4-204','Vỏ chân',['lower_length','link_width','link_thickness'],['Loft 3 ellipse; lệch +7 mm','Trừ tay dưới; scale vỏ 0.92','Khoét hai vùng khớp Ø12'],['Chưa kiểm độ dày vỏ tại mọi điểm','Chưa có phân khuôn và dung sai']),
 'shoulder':('Q4-205','Vỏ chân',[],['Loft ellipse tại z -33/-13/+7 mm','Trừ lòng trụ Ø49 xuyên 80 mm','Đặt 4 bản tại vị trí vai'],['Vỏ polymer theo mật độ giả định','Chưa có giao diện vít giữ vỏ']),
 'motor':('Q4-301','Thiết bị đại diện',[],['Trụ Ø48 × 16, chamfer 0.7','Bích Ø42 × 2, trục Ø14 × 2','6 lỗ Ø3.4 trên PCD Ø34'],['Actuator đại diện, chưa chọn sản phẩm','Không mô hình rotor, stator, ổ bi hoặc gearbox']),
 'foot':('Q4-401','Tiếp xúc',[],['Box 26 × 24 × 24 mm','Fillet toàn bộ cạnh R6','Lắp 4 đệm bàn chân'],['Mật độ cao su 1100 kg/m³ giả định','Chưa thử ma sát, lão hóa hoặc tải']),
 'sensor':('Q4-501','Thiết bị đại diện',['body_width'],['Box 14 × 0.66W × 25 mm','Bo cạnh dọc X với R7','2 lỗ Ø12 tại y ±0.20W'],['Giá cảm biến CAD, camera là đại diện','Chưa có PCB, đầu nối hoặc optical stack']),
 'lens':('Q4-502','Thiết bị đại diện',[],['Trụ Ø11 × 6 mm','Đặt 2 bản trong giá cảm biến','Khối lượng gán 12 g / bản'],['Không là thiết kế quang học','Chưa có focal length, FOV hoặc datasheet']),
 'battery':('Q4-601','Thiết bị đại diện',['body_length','body_width'],['Box 0.50L × 0.66W × 36 mm','Fillet R3','Đặt trong khoang thân'],['Khối lượng pin gán, chưa có datasheet','Chưa mô hình cell, BMS, dây và tản nhiệt'])}
KEY_LABELS={'body_length':'Chiều dài thân','body_width':'Bề rộng thân','body_height':'Chiều cao thân','upper_length':'Tâm tay trên','lower_length':'Tâm tay dưới','link_width':'Bề rộng tay','link_thickness':'Độ dày tay','bore_diameter':'Đường kính lỗ'}
VIEWS=[('front','Chính diện / XZ',(0,-1000,0),(0,0,1)),('top','Từ trên / XY',(0,0,1000),(0,1,0)),('right','Bên phải / YZ',(1000,0,0),(0,0,1)),('iso','Trục đo',(1000,-1000,1000),(0,0,1))]

def sampled(edge):
    count=1 if edge.geom_type==GeomType.LINE else max(12,min(320,math.ceil(edge.length/.6)))
    return [[round(p.X,5),round(p.Y,5)] for p in [edge.position_at(i/count) for i in range(count+1)]]

def view(shape,eye,up,dxf_path=None):
    visible,hidden=shape.project_to_viewport(eye,viewport_up=up,look_at=(0,0,0))
    all_edges=visible+hidden
    box=Compound(children=all_edges).bounding_box()
    if dxf_path:
        dxf=ExportDXF();dxf.add_layer('VISIBLE',line_weight=.25);dxf.add_layer('HIDDEN',line_weight=.13,line_type=LineType.ISO_DASH)
        dxf.add_shape(visible,layer='VISIBLE');dxf.add_shape(hidden,layer='HIDDEN');dxf.write(dxf_path)
    return {'visible':[sampled(e) for e in visible],'hidden':[sampled(e) for e in hidden],
            'bbox':[box.min.X,box.min.Y,box.max.X,box.max.Y], 'edge_count':[len(visible),len(hidden)]}

class Sheet:
    def __init__(self,title,code,rev,page,total,scope):
        self.items=[];self.title=title;self.code=code;self.rev=rev
        self.rect(8,8,404,281);self.line(8,34,412,34);self.line(8,264,412,264)
        self.text(16,20,'FORGE Q4',6.5,True);self.text(16,28,title,3.5)
        self.text(310,19,code,5,True);self.text(310,28,f'Revision {rev}',3)
        self.text(16,273,scope,3);self.text(16,282,'Đơn vị mm | kích thước theo CAD | chưa phát hành chế tạo',2.7)
        self.line(298,264,298,289);self.text(306,273,'A3 / 420 × 297 mm',3,True);self.text(306,282,f'Tờ {page:02d} / {total:02d} | OCCT / BREP',2.7)
    def line(self,x1,y1,x2,y2,color='#555555',width=.18,dash=None):self.items.append(dict(type='line',points=[[x1,y1],[x2,y2]],color=color,width=width,dash=dash))
    def rect(self,x,y,w,h):self.items.append(dict(type='rect',x=x,y=y,w=w,h=h))
    def text(self,x,y,text,size=3,bold=False):self.items.append(dict(type='text',x=x,y=y,text=str(text),size=size,bold=bold))
    def poly(self,points,hidden=False):self.items.append(dict(type='line',points=points,color='#969696' if hidden else '#111111',width=.14 if hidden else .22,dash=[1.5,1] if hidden else None))
    def dimension(self,a,b,label,vertical=False):
        self.line(*a,*b,'#555555',.16)
        for x,y in [a,b]:self.line(x-1,y-1,x+1,y+1,'#555555',.16)
        self.text((a[0]+b[0])/2+2 if vertical else (a[0]+b[0])/2-4,(a[1]+b[1])/2 if vertical else a[1]-2,label,2.9)
    def drawing(self,data,x,y,w,h,title,dimensions=True,fixed_scale=None):
        self.text(x,y-3,title,3.2,True)
        x0,y0,x1,y1=data['bbox'];bw=max(x1-x0,.01);bh=max(y1-y0,.01)
        scale=fixed_scale if fixed_scale is not None else min((w-18)/bw,(h-18)/bh)
        ox=x+w/2-(x0+x1)/2*scale;oy=y+h/2+(y0+y1)/2*scale
        trans=lambda p:[ox+p[0]*scale,oy-p[1]*scale]
        for pts in data.get('hidden',[]):self.poly([trans(p) for p in pts],True)
        for pts in data.get('visible',[]):self.poly([trans(p) for p in pts])
        if 'faces' in data:
            for face in data['faces']:
                self.items.append(dict(type='section',loops=[[trans(p) for p in loop] for loop in face]))
        if dimensions:
            bx0,by0=trans([x0,y1]);bx1,by1=trans([x1,y0])
            for xx in [bx0,bx1]:self.line(xx,by1+1,xx,by1+9,'#aaaaaa',.12)
            self.dimension([bx0,by1+7],[bx1,by1+7],f'{bw:.2f}')
            for yy in [by0,by1]:self.line(bx1+1,yy,bx1+10,yy,'#aaaaaa',.12)
            self.dimension([bx1+8,by0],[bx1+8,by1],f'{bh:.2f}',True)
        return trans
    def svg(self):
        parts=['<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="297mm" viewBox="0 0 420 297" role="img" aria-label="'+html.escape(self.title)+'">', '<defs><pattern id="hatch" width="2" height="2" patternUnits="userSpaceOnUse"><path d="M-1 1L1 -1M0 2L2 0M1 3L3 1" stroke="#666" stroke-width=".12"/></pattern></defs><rect width="420" height="297" fill="white"/>']
        for i in self.items:
            if i['type']=='text':parts.append(f'<text x="{i["x"]}" y="{i["y"]}" fill="#111" font-family="Arial,Helvetica,sans-serif" font-size="{i["size"]}" font-weight="{600 if i["bold"] else 400}">{html.escape(i["text"])}</text>')
            elif i['type']=='rect':parts.append(f'<rect x="{i["x"]}" y="{i["y"]}" width="{i["w"]}" height="{i["h"]}" fill="none" stroke="#555" stroke-width=".2"/>')
            elif i['type']=='line':
                pts=' '.join(f'{p[0]:.4f},{p[1]:.4f}' for p in i['points']);dash=f' stroke-dasharray="{" ".join(map(str,i["dash"]))}"' if i['dash'] else ''
                parts.append(f'<polyline points="{pts}" fill="none" stroke="{i["color"]}" stroke-width="{i["width"]}"{dash}/>')
            elif i['type']=='section':
                path=' '.join('M'+' L'.join(f'{p[0]:.4f} {p[1]:.4f}' for p in loop)+'Z' for loop in i['loops'])
                parts.append(f'<path d="{path}" fill="url(#hatch)" fill-rule="evenodd" stroke="#111" stroke-width=".22"/>')
        return ''.join(parts)+'</svg>'
    def pdf(self,c):
        for i in self.items:
            if i['type']=='text':c.setFillColor('#111111');c.setFont('ForgeBold' if i['bold'] else 'Forge',i['size']*mm);c.drawString(i['x']*mm,(297-i['y'])*mm,i['text'])
            elif i['type']=='rect':c.setStrokeColor('#555555');c.setLineWidth(.2*mm);c.setDash();c.rect(i['x']*mm,(297-i['y']-i['h'])*mm,i['w']*mm,i['h']*mm,fill=0,stroke=1)
            elif i['type']=='line':
                c.setStrokeColor(i['color']);c.setLineWidth(i['width']*mm);c.setDash([d*mm for d in i['dash']] if i['dash'] else [])
                p=c.beginPath();p.moveTo(i['points'][0][0]*mm,(297-i['points'][0][1])*mm)
                for x,y in i['points'][1:]:p.lineTo(x*mm,(297-y)*mm)
                c.drawPath(p)
            elif i['type']=='section':
                c.saveState();p=c.beginPath()
                for loop in i['loops']:
                    p.moveTo(loop[0][0]*mm,(297-loop[0][1])*mm)
                    for x,y in loop[1:]:p.lineTo(x*mm,(297-y)*mm)
                    p.close()
                c.setDash();c.setStrokeColor('#111111');c.setLineWidth(.22*mm);c.drawPath(p,fill=0,stroke=1)
                c.clipPath(p,stroke=0,fill=0,fillMode=0);c.setStrokeColor('#666666');c.setLineWidth(.12*mm)
                for z in range(-297,421,2):c.line(z*mm,0,(z+297)*mm,297*mm)
                c.restoreState()
        c.showPage()

def dimensions(key,s):
    L,W,H=s['body_length'],s['body_width'],s['body_height'];u,d,w,t,b=s['upper_length'],s['lower_length'],s['link_width'],s['link_thickness'],s['bore_diameter']
    return {'frame':[('Thành danh nghĩa',3),('Lỗ vai Ø',12),('Vị trí vai X ±',L*.34)],'cover':[('Độ dày',3),('Lỗ lắp 4 × Ø',4.2),('Rộng khe',3)],'upper':[('Tâm–tâm',u),('Bề rộng',w),('2 lỗ Ø',b),('Độ dày',t)],'lower':[('Tâm–tâm',d),('Bề rộng = 0.85w',w*.85),('2 lỗ Ø',b),('Độ dày',t)],'motor':[('Thân Ø / dày',48),('Dày thân',16),('Trục Ø',14),('Bích Ø',42),('6 lỗ Ø / PCD34',3.4),('Chamfer',.7)],'foot':[('X × Y × Z','26 × 24 × 24'),('Bo cạnh R',6)],'sensor':[('X × Y × Z',f'14 × {W*.66:.2f} × 25'),('2 hốc Ø',12),('Vị trí tâm Y ±',W*.20)],'lens':[('Trụ Ø',11),('Chiều dài',6)],'battery':[('L × W × H',f'{L*.5:.1f} × {W*.66:.1f} × 36'),('Fillet R',3)],'upper_fairing':[('Chiều dài tâm',u),('Lệch tiết diện X',-7),('Lỗ vùng khớp Ø',12)],'lower_fairing':[('Chiều dài tâm',d),('Lệch tiết diện X',7),('Scale vỏ',.92),('Lỗ vùng khớp Ø',12)],'shoulder':[('Lòng Ø',49),('Z ba tiết diện','-33 / -13 / 7')]}.get(key,[])

def generate(model,definitions,assembly,dest):
    started=__import__('time').perf_counter();rev=model['revision'];root=dest/'drawings';root.mkdir(exist_ok=True)
    # System fonts are embedded in PDF; fall back to the first installed Unicode font.
    candidates=[Path('/System/Library/Fonts/Supplemental/Arial.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    regular=next((p for p in candidates if p.exists()),None)
    if regular is None:raise RuntimeError('Cần Arial hoặc DejaVu Sans để xuất PDF tiếng Việt.')
    bold=regular.with_name('Arial Bold.ttf' if regular.name=='Arial.ttf' else 'DejaVuSans-Bold.ttf')
    if 'Forge' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('Forge',str(regular)));pdfmetrics.registerFont(TTFont('ForgeBold',str(bold)))
    sheets=[];docs={};s=model['spec'];total=14
    for index,(key,(shape,name,role,count)) in enumerate(definitions.items(),3):
        code,group,keys,recipe,notes=PART_INFO[key];part=model['parts'][key];box=shape.bounding_box();size=box.size
        part.update(part_number=code,group=group,bbox_mm=[size.X,size.Y,size.Z],surface_mm2=shape.area,faces=len(shape.faces()),edges=len(shape.edges()),vertices=len(shape.vertices()),parameter_keys=keys,recipe=recipe,notes=notes,dimensions=dimensions(key,s))
        # Local part STEP exports, distinct from the positioned assembly.
        from build123d import export_step
        local=copy.deepcopy(shape);local.label=code;step=root/f'{code}.step';export_step(local,step);part['step_url']=f'/artifacts/{rev}/drawings/{step.name}'
        views={}
        for vid,title,eye,up in VIEWS:
            views[vid]=view(shape,eye,up,root/f'{code}-{vid}.dxf')
        cut=Plane.XZ.offset(-shape.bounding_box().center().Y);cutshape=section(shape,section_by=cut);localcut=cut.to_local_coords(cutshape)
        cb=localcut.bounding_box();faces=[]
        for face in localcut.faces():
            loops=[]
            for wire in [face.outer_wire(),*face.inner_wires()]:
                sample_count=min(1200,max(32,math.ceil(wire.length/.4)));loops.append([[p.X,p.Y] for p in [wire.position_at(j/sample_count) for j in range(sample_count+1)]])
            faces.append(loops)
        views['section']={'visible':[],'hidden':[],'faces':faces,'bbox':[cb.min.X,cb.min.Y,cb.max.X,cb.max.Y],'area_mm2':cutshape.area,'cut_y_mm':shape.bounding_box().center().Y}
        sheet=Sheet(name,code,rev,index,total,'Bố trí góc chiếu 3 | cùng tỷ lệ hình chiếu | trục đo minh họa | mặt cắt gạch vật liệu')
        fit=min(min(94/max(d['bbox'][2]-d['bbox'][0],.01),73/max(d['bbox'][3]-d['bbox'][1],.01)) for k,d in views.items() if k!='iso')
        sc=max(v for v in (.05,.1,.2,.25,.5,1,2,4,8) if v<=fit)
        scale_label=f'1:{1/sc:g}' if sc<1 else f'{sc:g}:1'
        transforms={}
        for vid,title,x,y in [('front','Chính diện XZ',18,158),('top','Từ trên XY',18,49),('right','Bên phải YZ',152,158),('iso','Trục đo / minh họa',152,49),('section','Mặt cắt A–A / XZ',286,49)]:
            transforms[vid]=sheet.drawing(views[vid],x,y,112,91,title+(' / '+scale_label if vid!='iso' else ''),vid!='iso',sc if vid!='iso' else None)
        # Identify the actual mid-Y cutting plane on the corresponding XY view.
        topbox=views['top']['bbox'];cut_y=views['section']['cut_y_mm']
        left=transforms['top']([topbox[0],cut_y]);right=transforms['top']([topbox[2],cut_y])
        sheet.line(left[0]-6,left[1],right[0]+6,right[1],'#555555',.22,[4,1,.5,1])
        for x,y in [(left[0]-6,left[1]),(right[0]+6,right[1])]:
            sheet.line(x,y-7,x,y,'#333333',.3)
            sheet.line(x-1,y-2,x,y,'#333333',.3);sheet.line(x+1,y-2,x,y,'#333333',.3)
            sheet.text(x-1,y-9,'A',2.8,True)

        if key in ('upper','lower'):
            length=s['upper_length' if key=='upper' else 'lower_length'];w0=s['link_width']*(.85 if key=='lower' else 1)
            data=views['front'];x0,y0,x1,y1=data['bbox'];ox=18+56-(x0+x1)/2*sc;oy=158+45.5+(y0+y1)/2*sc
            tx=ox-(w0/2+7)*sc;ya=oy;yb=oy+length*sc
            sheet.dimension([tx,ya],[tx,yb],'',True);sheet.text(tx-18,(ya+yb)/2,f'C-C {length:g}',2.9)
            for cy in (ya,yb):
                sheet.line(ox-4,cy,ox+4,cy,'#777777',.12,[2,.6,.3,.6]);sheet.line(ox,cy-4,ox,cy+4,'#777777',.12,[2,.6,.3,.6])
            sheet.line(ox,ya,ox+18,ya-9);sheet.text(ox+19,ya-9,f'2 × Ø{s["bore_diameter"]:g}',2.9)
        sheet.text(286,151,'Thông số chương trình (mm)',3.2,True)
        for j,(label,value) in enumerate(part['dimensions'][:6]):sheet.text(286,159+j*6,f'{label}: {value:g}' if isinstance(value,(int,float)) else f'{label}: {value}',2.8)
        sheet.text(286,201,f'V = {part["volume_mm3"]:,.1f} mm³',3.1,True)
        sheet.text(286,208,f'm = {part["mass_kg"]*1000:.1f} g / SL {count}',3)
        sheet.text(286,215,f'{part["faces"]} mặt / {part["edges"]} cạnh / 1 solid',2.8)
        sheet.text(286,226,'Ghi chú kỹ thuật',3,True)
        for j,note in enumerate(notes):
            # Short notes are authored to fit 112 mm.
            sheet.text(286,233+j*6,note,2.55)
        sheet.text(286,254,f'Section area: {cutshape.area:.1f} mm²',2.8)
        svg=sheet.svg();(root/f'{code}.svg').write_text(svg)
        docs[key]={'sheet':svg,'view_metrics':{v:{k:d[k] for k in ('bbox','edge_count','area_mm2','cut_y_mm') if k in d} for v,d in views.items()},'svg_url':f'/artifacts/{rev}/drawings/{code}.svg','dxf_url':f'/artifacts/{rev}/drawings/{code}-front.dxf','section_area_mm2':cutshape.area,'scale':sc}
        sheets.append(sheet)
    # Whole assembly: real hidden-line removal, separate normal and exploded views.
    av=view(assembly,(1000,-1000,1000),(0,0,1))
    overview=Sheet('Tổng thể lắp ráp','Q4-000',rev,1,total,'Lắp ráp 42 vị trí | 12 hình học duy nhất | thiết bị đại diện được ghi rõ trong BOM')
    overview.drawing(av,17,51,256,198,'Trục đo lắp ráp',False)
    overview.text(285,51,'Danh mục cấu phần',4,True)
    for j,(key,p) in enumerate(model['parts'].items()):
        overview.text(285,63+j*12,p['part_number']+'  '+p['name'],3,True);overview.text(285,68+j*12,f'SL {p["count"]} | {p["mass_kg"]*1000:.1f} g / bản',2.7)
    overview.text(285,221,f'Khối lượng tính: {model["metrics"]["mass_kg"]:.3f} kg',3,True)
    overview.text(285,231,'Actuator, pin, điện tử: khối lượng giả định',2.6)
    overview.text(285,239,'Chưa có dung sai lắp và thử chịu lực',2.6)
    exploded=[]
    for obj,inst in zip(assembly.children,model['instances']):exploded.append(obj.moved(Location(inst['explode_mm'])))
    ev=view(Compound(children=exploded),(1000,-1000,1000),(0,0,1))
    exp=Sheet('Phân rã lắp ráp và quan hệ','Q4-001',rev,2,total,'Các vị trí tách chỉ để đọc cấu trúc; không là vị trí vận hành hoặc kích thước lắp')
    exp.drawing(ev,17,51,260,198,'Trục đo phân rã',False)
    exp.text(286,51,'Quan hệ lắp / giao diện',4,True)
    rows=['Khung → 4 vỏ vai / 4 roll actuator','Mỗi chân: hip → tay trên → knee','Tay dưới lệch mặt tay trên 3 mm','Vỏ chân trừ hình học tay chịu lực','Nắp: 4 lỗ Ø4.2 và 6 khe thoáng','Giá cảm biến: 2 hốc Ø12','Ống kính: 2 trụ Ø11 đại diện','Pin: khối bo R3 trong khoang thân']
    for j,row in enumerate(rows):exp.text(286,66+j*10,row,2.8)
    exp.text(286,159,'Các phần chưa mô hình',3.4,True)
    for j,row in enumerate(['Vít, bearing, dây điện và PCB','Rotor, stator, gearbox và encoder','Cell pin, BMS và giải pháp tản nhiệt','Dung sai, GD&T, độ nhám và test tải']):exp.text(286,170+j*8,row,2.8)
    exp.text(286,221,'BOM 42 vị trí có trong hồ sơ JSON.',2.8)
    exp.text(286,232,'Khối được định danh riêng trong STEP.',2.8)
    sheets=[overview,exp]+sheets
    for page in sheets:(root/f'{page.code}.svg').write_text(page.svg())
    pdf=root/'FORGE-Q4-CAD-A3.pdf';c=canvas.Canvas(str(pdf),pagesize=(420*mm,297*mm));c.setTitle('FORGE Q4 - 14 technical CAD sheets');c.setAuthor('FORGE Q4 / deterministic CAD compiler')
    for page in sheets:page.pdf(c)
    c.save()
    data={'revision':rev,'generator_hash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12],'parts':docs,'assembly':{'sheet':overview.svg(),'exploded_sheet':exp.svg()},'sheet_count':14,'pdf_url':f'/artifacts/{rev}/drawings/{pdf.name}','scope':'Engineering concept. Not a manufacturing release.','projection':'OCCT hidden-line removal; curves sampled at <=0.6 mm for SVG/PDF display; DXF retains CAD edges.','generated_ms':round((__import__('time').perf_counter()-started)*1000)}
    (root/'documentation.json').write_text(json.dumps(data,separators=(',',':'),ensure_ascii=False))
    (root/'BOM-42.json').write_text(json.dumps({'revision':rev,'parts':{k:{kk:vv for kk,vv in p.items() if kk not in ('positions','indices')} for k,p in model['parts'].items()},'instances':model['instances']},ensure_ascii=False,indent=2))
    archive=root/'FORGE-Q4-CAD-dossier.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for f in root.iterdir():
            if f!=archive and f.is_file():z.write(f,f.name)
    data['zip_url']=f'/artifacts/{rev}/drawings/{archive.name}'
    (root/'documentation.json').write_text(json.dumps(data,separators=(',',':'),ensure_ascii=False))
    return data
