"""Check exported drawing assets and their linkage to the default CAD revision."""
import json, math, sys, zipfile, xml.etree.ElementTree as ET
from pathlib import Path
import ezdxf
from pypdf import PdfReader
from build123d import import_step
ROOT=Path(__file__).resolve().parents[1]
m=json.loads((ROOT/'web/default-model.json').read_text());d=m['documentation'];assert d['revision']==m['revision']
assembly=import_step(ROOT/m['step_url'].lstrip('/'))
assert len(assembly.solids())==42
assert {s.label for s in assembly.children}=={i['id'] for i in m['instances']}
assert len({i['id'] for i in m['instances']})==42
checks=[]
for key,p in m['parts'].items():
    shape=import_step(ROOT/p['step_url'].lstrip('/'));assert shape.is_valid and len(shape.solids())==1
    error=abs(shape.volume-p['volume_mm3'])/p['volume_mm3'];assert error<2e-6  # Individual NURBS volume integration after STEP: 0.0002% bound.
    doc=d['parts'][key];svg=ET.fromstring(doc['sheet']);assert svg.attrib['width']=='420mm' and svg.attrib['height']=='297mm'
    text=' '.join(svg.itertext());assert f'SL {p["count"]}' in text
    assert doc['section_area_mm2']>0
    metrics=doc['view_metrics'];assert all(sum(metrics[v]['edge_count'])>0 for v in ('front','top','right','iso'))
    assert doc['scale'] in (.05,.1,.2,.25,.5,1,2,4,8)
    entity_counts={}
    for v in ('front','top','right','iso'):
        dx=ezdxf.readfile(ROOT/doc['dxf_url'].replace('-front.dxf',f'-{v}.dxf').lstrip('/'))
        assert dx.units==4 and len(dx.modelspace())>0
        assert 'VISIBLE' in dx.layers and 'HIDDEN' in dx.layers
        entity_counts[v]=len(dx.modelspace())
    if key in ('upper','lower'):
        assert abs(doc['section_area_mm2']*m['spec']['link_thickness']-p['volume_mm3'])/p['volume_mm3']<1e-6
    checks.append({'part':key,'step_volume_error':error,'section_area_mm2':doc['section_area_mm2'],'scale':doc['scale'],'dxf_entities':entity_counts})
pdf=PdfReader(ROOT/d['pdf_url'].lstrip('/'));assert len(pdf.pages)==14
assert all(abs(float(p.mediabox.width)-420*72/25.4)<.1 and abs(float(p.mediabox.height)-297*72/25.4)<.1 for p in pdf.pages)
for index,key in enumerate(m['parts'],2):
    text=pdf.pages[index].extract_text();assert m['parts'][key]['part_number'] in text
    assert f'SL {m["parts"][key]["count"]}' in text
    assert m['revision'] in text
with zipfile.ZipFile(ROOT/d['zip_url'].lstrip('/')) as z:
    assert z.testzip() is None
    assert 'FORGE-Q4-CAD-A3.pdf' in z.namelist() and len([n for n in z.namelist() if n.endswith('.step')])==12
out={'status':'passed','revision':m['revision'],'unique_step_names':42,'a3_pdf_pages':14,'parts':checks}
(ROOT/'reports/monochrome/dossier-tests.json').write_text(json.dumps(out,indent=2,ensure_ascii=False))
print(json.dumps(out,indent=2))
