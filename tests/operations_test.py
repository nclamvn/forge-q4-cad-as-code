"""Independent energy/thermal oracles and causal effects on the physical plant."""
import hashlib,json,math,sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from robotics.operations import OperatingModel,validate,support_margin
from robotics.model import compile_robot
from robotics.simulation import Simulator
RESULTS=[]

class OperationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.desc=compile_robot(json.loads((ROOT/'web/default-model.json').read_text()))

    def test_energy_and_thermal_oracles(self):
        op=OperatingModel({'enabled':True},8);p=op.profile;tau=np.full(12,2.);velocity=np.full(12,1.)
        dt=.002;heat=(2/.8)**2*.15
        op.after_step(tau,velocity,dt)
        np.testing.assert_allclose(op.temperature,25+heat*dt/80,atol=1e-12)
        expected_power=12+24/.78+12*heat
        self.assertAlmostEqual(op.power_w,expected_power,places=12)
        self.assertAlmostEqual(op.energy_j,expected_power*dt,places=12)
        self.assertAlmostEqual(op.soc,.9-expected_power*dt/(120*3600),places=12)
        op.after_step(np.zeros(12),np.zeros(12),dt)
        self.assertLess(op.temperature[0],25+heat*dt/80)
        RESULTS.append(dict(check='Independent I²R, thermal RC, positive mechanical power and battery energy integrals',passed=True,expected_power_w=expected_power))

    def test_speed_thermal_health_and_cutoff(self):
        class Plant:actuator_forcerange=np.zeros((12,2))
        m=Plant();o=OperatingModel({'enabled':True,'initial_motor_c':80,'failed_joint':2,'joint_health':.35},8)
        o.before_step(m,np.full(12,8.),0)
        self.assertAlmostEqual(o.limits[0],8*.5*.75);self.assertAlmostEqual(o.limits[2],8*.5*.75*.35)
        o.temperature[0]=90;o.before_step(m,np.zeros(12),1)
        self.assertTrue(o.cutoff);self.assertEqual(o.events[0]['reason'],'motor_temperature');self.assertLess(max(m.actuator_forcerange[:,1]),2e-9)
        o.temperature[:]=25;o.before_step(m,np.zeros(12),2);self.assertTrue(o.cutoff)
        low=OperatingModel({'enabled':True,'initial_soc':.1},8);low.before_step(m,np.zeros(12),0)
        self.assertTrue(low.cutoff);self.assertEqual(low.events[0]['reason'],'battery_reserve')
        RESULTS.append(dict(check='Speed envelope, thermal derating, single-joint health, latched thermal/battery cutoff',passed=True))

    def test_support_polygon_and_input_validation(self):
        square=[[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0]]
        self.assertAlmostEqual(support_margin(square,[0,0,2]),1)
        self.assertAlmostEqual(support_margin(square,[2,0,2]),-1)
        self.assertIsNone(support_margin(square[:2],[0,0,0]))
        self.assertIsNone(support_margin([[0,0],[1,0],[2,0]],[0,0]))
        for raw in [{'enabled':'true'},{'failed_joint':.5},{'efficiency':float('nan')},{'initial_soc':.05,'minimum_soc':.1},{'cutoff_c':65},{'python':'exec(...)'}]:
            with self.assertRaises(ValueError):validate(raw)
        RESULTS.append(dict(check='Signed support projection independent square oracle; degenerate cases; strict finite inputs',passed=True))

    def test_actual_plant_cutoff_and_disabled_equivalence(self):
        a=Simulator(self.desc);b=Simulator(self.desc,operations={'enabled':False})
        for s in (a,b):
            s.control('resume')
            for _ in range(10):s.step(.1)
        np.testing.assert_allclose(a.data.qpos,b.data.qpos,atol=1e-13)
        normal=Simulator(self.desc,operations={'enabled':True});hot=Simulator(self.desc,operations={'enabled':True,'initial_motor_c':95})
        for s in (normal,hot):
            s.control('resume')
            for _ in range(30):s.step(.1)
        f=hot.snapshot(False);n=normal.snapshot(False)
        self.assertTrue(f['operations']['cutoff']);self.assertLess(max(abs(j['torque_nm']) for j in f['joints']),2e-9)
        self.assertGreater(n['base_position_m'][2]-f['base_position_m'][2],.08)
        self.assertGreater(n['operations']['electrical_energy_wh'],0);self.assertLess(n['operations']['battery_soc'],.9)
        normal.control('pause');before=normal.snapshot(False);after=normal.step(.1)
        self.assertEqual(before['operations'],after['operations'])
        RESULTS.append(dict(check='Actual MuJoCo force cutoff drops body; estimates integrate solved actuation; pause freezes; disabled plant unchanged',passed=True,normal_height_m=n['base_position_m'][2],hot_height_m=f['base_position_m'][2],hot_max_torque_nm=max(abs(j['torque_nm']) for j in f['joints'])))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(OperationsTests);result=unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        files=['robotics/operations.py','robotics/simulation.py','tests/operations_test.py']
        out=dict(status='passed',cad_revision=OperationsTests.desc['model']['revision'],model_revision=OperationsTests.desc['revision'],checks=RESULTS,
            source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},calibrated=False,hardware_verified=False)
        (ROOT/'reports/robotics/operations-tests.json').write_text(json.dumps(out,indent=2)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)
