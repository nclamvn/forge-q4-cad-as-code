"""Independent engineering checks; no visual or performance claims."""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from kernel import DEFAULT, build, validate, SpecError, capsule_link

class KernelTests(unittest.TestCase):
    def test_capsule_formula_across_dimensions(self):
        for length,width,thickness,bore in [(110,26,4,6),(140,32,7,10),(190,48,12,16)]:
            with self.subTest(length=length):
                shape=capsule_link(length,width,thickness,bore)
                oracle=((length*width)+(math.pi*width*width/4)-(math.pi*bore*bore/2))*thickness
                self.assertTrue(shape.is_valid)
                self.assertAlmostEqual(shape.volume,oracle,places=5)

    def test_bad_specs_fail_before_geometry(self):
        for override in [dict(link_width=18),dict(units='cm'),dict(body_width=float('nan')),
                         dict(material='unobtainium'),dict(body_length=True),dict(unknown=123),
                         dict(link_width=24,bore_diameter=10)]:
            with self.subTest(override=override):
                self.assertRaises(SpecError,validate,{**DEFAULT,**override})

    def test_variants_step_and_mass(self):
        variants=[{},dict(body_length=284,body_width=168,upper_length=126,lower_length=140,material='pa12',payload_kg=.5),
                  dict(body_length=360,body_width=208,upper_length=174,lower_length=194),dict(material='steel')]
        report=[]
        with tempfile.TemporaryDirectory() as folder:
            for override in variants:
                model=build({**DEFAULT,**override},Path(folder),include_documentation=False)
                self.assertTrue(all(c['passed'] for c in model['proof']['checks'] if c['id']!='mass'))
                self.assertEqual(model['proof']['roundtrip']['solid_count'],42)
                self.assertLess(model['proof']['roundtrip']['relative_error'],1e-6)
                self.assertEqual(model['metrics']['part_count'],42)
                self.assertTrue(all(p['indices'] and p['positions'] for p in model['parts'].values()))
                self.assertTrue(all(abs(sample['distance_mm']-3)<1e-5 for sample in model['proof']['clearance_samples']))
                report.append(dict(revision=model['revision'],spec=model['spec'],metrics=model['metrics'],proof=model['proof']))
        self.assertLess(report[1]['metrics']['mass_kg'],report[0]['metrics']['mass_kg'])
        self.assertGreater(report[2]['metrics']['height_mm'],report[0]['metrics']['height_mm'])
        self.assertFalse(next(c['passed'] for c in report[3]['proof']['checks'] if c['id']=='mass'))
        (Path(__file__).resolve().parents[1]/'reports/kernel-tests.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=='__main__':unittest.main(verbosity=2)
