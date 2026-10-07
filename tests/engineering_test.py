"""Untrusted proposal gates, a real 10-trial experiment and digest-bound adoption."""
import copy,hashlib,json,shutil,sys,tempfile,time,unittest,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from robotics import engineering as e
from robotics.model import compile_robot,profile

RESULTS=[]
class EngineeringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cad=json.loads((ROOT/'web/default-model.json').read_text())
        cls.proposal=e.example(cls.cad)
        jobs=[e.read_job(p.parent.name) for p in e.OUTPUT.glob('*/report.json')]
        cls.job=next((j for j in reversed(jobs) if j['status']=='completed' and j['source_sha256']==e.sources() and j['proposal']['changes']=={'link_thickness':6}),None)
        if cls.job is None:
            cache={json.dumps(cls.cad['spec'],sort_keys=True):cls.cad}
            started=e.start({'base_revision':cls.cad['revision'],'proposal':cls.proposal},cache,threading.Lock())
            deadline=time.monotonic()+300
            while time.monotonic()<deadline:
                cls.job=e.read_job(started['id'])
                if cls.job['status'] not in ('queued','running','cancelling'):break
                time.sleep(.2)
            if cls.job['status']!='completed':raise RuntimeError(cls.job['message'])

    def test_untrusted_proposal_validation(self):
        p,s=e.validate_proposal(self.proposal,self.cad);self.assertEqual(s['link_thickness'],6)
        cases=[]
        for patch in [{'base_revision':'stale'},{'changes':{'link_width':18}},{'changes':{'python':'exec(1)'}},
            {'actuator_profile':{'torque_limit_nm':float('nan')}},{'operations':{'enabled':False}},
            {'operations':{'enabled':True,'failed_joint':.2}},{'goals':{}},{'assumptions':[]},{'changes':{}},{'surprise':1}]:
            raw={**self.proposal,**patch}
            with self.assertRaises((ValueError,TypeError)):e.validate_proposal(raw,self.cad)
            cases.append(list(patch))
        c=e.context(self.cad,'Tối ưu khối lượng',None)
        self.assertFalse(c['llm_runtime']);self.assertIn(self.cad['revision'],c['prompt'])
        self.assertEqual(hashlib.sha256(c['prompt'].encode()).hexdigest(),c['context_sha256'])
        RESULTS.append(dict(check='Stale revision, unknown code, thin ligament, NaN, malformed profiles/goals and empty proposals rejected; provenance prompt digest',passed=True,rejected=cases))

    def test_real_experiment_and_independent_energy_trace(self):
        j=self.job
        self.assertTrue(j['eligible']);self.assertEqual(j['progress'],10)
        self.assertEqual(len(j['trials']['baseline']),5);self.assertEqual(len(j['trials']['candidate']),5)
        self.assertNotEqual(j['candidate_revision'],j['base_revision'])
        self.assertLess(j['models']['candidate']['loaded_mass_kg'],j['models']['baseline']['loaded_mass_kg'])
        for name,trials in j['trials'].items():
            for trial,case in zip(trials,e.SUITE):
                self.assertEqual(trial['case'],case);self.assertEqual(trial['final_frame']['time_s'],case['seconds'])
                self.assertGreater(trial['metrics']['electrical_energy_wh'],0)
                self.assertEqual(trial['passed'],all(g['passed'] for g in trial['gates']))
                self.assertTrue(all(trial['trace'][i]['time_s']<trial['trace'][i+1]['time_s'] for i in range(len(trial['trace'])-1)))
                self.assertFalse(trial['final_frame']['operations']['calibrated'])
        RESULTS.append(dict(check='Two different CAD revisions, same five scenarios, real timestamped traces, explicit estimates, all acceptance gates evaluated',passed=True,experiment_id=j['id'],baseline_mass_kg=j['models']['baseline']['loaded_mass_kg'],candidate_mass_kg=j['models']['candidate']['loaded_mass_kg']))

    def test_adoption_integrity_and_refusal(self):
        real_output=e.OUTPUT
        with tempfile.TemporaryDirectory() as folder:
            e.OUTPUT=Path(folder);j=copy.deepcopy(self.job);j['id']='f'*32
            target=e.OUTPUT/j['id'];shutil.copytree(real_output/self.job['id'],target)
            def sign():
                e.write_json(target/'report.json',j);e.write_json(target/'EVIDENCE.json',{'report_sha256':e.sha(target/'report.json'),'candidate_sha256':e.sha(target/'candidate.json')})
            try:
                sign();cache={'baseline':self.cad};raw=dict(id=j['id'],base_revision=self.cad['revision'])
                result=e.adopt(raw,cache);self.assertEqual(result['model']['revision'],j['candidate_revision'])
                with self.assertRaises(ValueError):e.adopt({**raw,'base_revision':'old'},cache)
                j['eligible']=False;sign()
                with self.assertRaises(ValueError):e.adopt(raw,cache)
                j['eligible']=True;sign();(target/'candidate.json').write_text((target/'candidate.json').read_text()+' ')
                with self.assertRaises(ValueError):e.adopt(raw,cache)
                shutil.copyfile(real_output/self.job['id']/'candidate.json',target/'candidate.json');sign()
                j['source_sha256']['robotics/operations.py']='wrong';sign()
                with self.assertRaises(ValueError):e.adopt(raw,cache)
            finally:e.OUTPUT=real_output
        RESULTS.append(dict(check='Apply actual passed CAD; reject stale baseline, failed gate, changed candidate bytes and changed solver source',passed=True))

    def test_failed_physical_design_retained(self):
        cfg={**profile(),'torque_limit_nm':.25};desc=compile_robot(self.cad,cfg)
        trial=e.run_trial(desc,e.SUITE[0],{'enabled':True},e.GOALS)
        self.assertFalse(trial['passed']);self.assertLess(trial['metrics']['minimum_height_ratio'],e.GOALS['minimum_height_ratio'])
        RESULTS.append(dict(check='Weak motor fails actual pose-height gate; failure evidence retained',passed=True,metrics=trial['metrics'],failed_gates=[g['id'] for g in trial['gates'] if not g['passed']]))

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(EngineeringTests))
    if result.wasSuccessful():
        out=dict(status='passed',cad_revision=EngineeringTests.cad['revision'],experiment_id=EngineeringTests.job['id'],checks=RESULTS,source_sha256={**e.sources(),'tests/engineering_test.py':e.sha(Path(__file__))},llm_runtime=False,hardware_verified=False)
        (ROOT/'reports/robotics/engineering-tests.json').write_text(json.dumps(out,indent=2)+'\n')
        shutil.copyfile(e.OUTPUT/EngineeringTests.job['id']/'report.json',ROOT/'reports/robotics/engineering-example.json')
    sys.exit(0 if result.wasSuccessful() else 1)
