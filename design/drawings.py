"""A3 dossier with HLR and section computed from the accepted candidate BREP."""
from pathlib import Path
from build123d import Plane,section
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from technical import Sheet,view,sampled


def generate(shape,program,brief,holes,revision,dest,passed):
    candidates=[Path('/System/Library/Fonts/Supplemental/Arial.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    regular=next((p for p in candidates if p.exists()),None)
    if regular is None:raise RuntimeError('Unicode drawing font unavailable')
    bold=regular.with_name('Arial Bold.ttf' if regular.name=='Arial.ttf' else 'DejaVuSans-Bold.ttf')
    if 'Forge' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('Forge',str(regular)));pdfmetrics.registerFont(TTFont('ForgeBold',str(bold)))
    views={};file_names={}
    for id,label,eye,up in [('top','XY / từ trên',(0,0,1000),(0,1,0)),('front','XZ / chính diện',(0,-1000,0),(0,0,1)),('right','YZ / bên phải',(1000,0,0),(0,0,1)),('iso','Trục đo',(1000,-1000,1000),(0,0,1))]:
        file_names[id]=f'bracket-{id}.dxf';views[id]=view(shape,eye,up,dest/file_names[id])
    cut=Plane.XZ;cut_shape=section(shape,section_by=cut);local=cut.to_local_coords(cut_shape);box=local.bounding_box();faces=[]
    for face in local.faces():
        loops=[]
        for wire in [face.outer_wire(),*face.inner_wires()]:
            count=min(500,max(24,int(wire.length/.5)));loops.append([[p.X,p.Y] for p in [wire.position_at(i/count) for i in range(count+1)]])
        faces.append(loops)
    views['section']=dict(visible=[],hidden=[],faces=faces,bbox=[box.min.X,box.min.Y,box.max.X,box.max.Y])
    sheet=Sheet(program['name'],'AI-CAD / 001',revision,1,1,'Hồ sơ tham chiếu | '+('đạt kiểm hình học khai báo' if passed else 'CANDIDATE CÓ KIỂM CHƯA ĐẠT'))
    next(item for item in sheet.items if item.get('type')=='text' and item.get('text')=='FORGE Q4')['text']='FORGE / AI CAD'
    sheet.drawing(views['top'],18,48,118,109,'Từ trên XY / 1:1',True,1)
    sheet.drawing(views['iso'],154,48,115,113,'Trục đo / minh họa',False)
    sheet.drawing(views['front'],18,190,118,55,'Chính diện XZ / 1:1',True,1)
    sheet.drawing(views['right'],154,190,112,55,'Bên phải YZ / 1:1',True,1)
    # Compact physical section; no screenshot-based slicing.
    sheet.drawing(views['section'],154,144,112,34,'Mặt cắt tại Y=0',False,1)
    sheet.line(284,44,284,251,'#bbbbbb',.15)
    sheet.text(292,48,'Yêu cầu độc lập với đề xuất',3.6,True)
    for i,line in enumerate(['Gá một solid; datum dưới Z=0','Tấm nhận gá: 4 lỗ Ø5.2','Giữ giao diện khi dời cảm biến','Mật độ nhôm đại diện: 2700 kg/m³','Chưa có tải, FEA, dung sai hoặc vít']):sheet.text(292,58+i*7,line,2.8)
    sheet.text(292,102,'Bảng vị trí lỗ / mm / datum XY',3.3,True)
    sheet.text(292,112,'Nhóm        X          Y         Ø       BREP',2.7,True)
    for i,h in enumerate(holes):
        sheet.text(292,120+i*6,f"{h['group'][:7]:8} {h['x_mm']:7.2f} {h['y_mm']:7.2f} {(h['actual_diameter_mm'] if h['actual_diameter_mm'] is not None else h['diameter_mm']):5.2f}   {'OK' if h['verified'] else 'FAIL'}",2.6)
    y=min(212,126+len(holes)*6)
    sheet.text(292,y,'Recipe có thể dựng lại',3.3,True)
    for i,line in enumerate(['JSON → sketch → extrude → boolean',f"{len(program['features'])} feature / result: {program['result'][:20]}",'STEP giữ BREP; JSON giữ cây thao tác','Gói kèm brief, source và manifest']):sheet.text(292,y+10+i*7,line,2.7)
    pdf=dest/'bracket-A3.pdf';c=canvas.Canvas(str(pdf),pagesize=(420*mm,297*mm));c.setTitle(program['name']);sheet.pdf(c);c.save()
    svg=dest/'bracket-A3.svg';svg.write_text(sheet.svg())
    return dict(pdf='bracket-A3.pdf',svg='bracket-A3.svg',dxf=file_names,views=views)
