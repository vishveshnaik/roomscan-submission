import unittest
import tempfile
import zipfile
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from roomscan.ingest import unproject,extract_zip
from roomscan.drift import register
from roomscan.geometry import rooms_from_cloud,measurement
from roomscan.evaluate import evaluate
from roomscan.pipeline import validate


class CoreTests(unittest.TestCase):
    def test_mm_and_per_frame_intrinsics(self):
        d=np.full((2,2),1000,np.uint16); c=np.full((2,2),2,np.uint8)
        row={'qx':0,'qy':0,'qz':0,'qw':1,'x':1,'y':2,'z':3,'fx':4,'fy':4,'cx':0,'cy':0}
        cloud=unproject(d,c,row,np.eye(3),(4,4),1)
        np.testing.assert_allclose(cloud,[[1,2,4],[1.5,2,4],[1,2.5,4],[1.5,2.5,4]])

    def test_confidence_and_range(self):
        row={'qx':0,'qy':0,'qz':0,'qw':1,'x':0,'y':0,'z':0}
        a=unproject(np.array([[0,1000],[7000,1000]],np.uint16),np.array([[2,1],[2,2]],np.uint8),row,np.eye(3),(2,2),1)
        self.assertEqual(len(a),1)

    def test_zip_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bad.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('../escape.txt','bad')
            with self.assertRaises(ValueError): extract_zip(p,Path(td)/'out')
            self.assertFalse((Path(td)/'escape.txt').exists())

    def test_icp_reduces_known_shift(self):
        rng=np.random.default_rng(42)
        target=rng.uniform(-1,1,(1500,3)); source=target+[.035,-.022,.018]
        fixed,stats=register(source,target,30)
        self.assertTrue(stats['accepted'])
        self.assertLess(np.sqrt(((fixed-target)**2).mean()),.003)
        self.assertLess(stats['after_residual_m'],stats['before_residual_m'])

    def test_floor_survives_unobserved_ceiling(self):
        x,z=np.meshgrid(np.arange(0,4,.025),np.arange(0,3,.025))
        floor=np.c_[x.ravel(),np.full(x.size,-1.5),z.ravel()]
        rng=np.random.default_rng(7)
        # Furniture at varied heights, no ceiling.
        furniture=np.c_[rng.uniform(0,4,5000),rng.uniform(-1.4,0,5000),rng.uniform(0,3,5000)]
        rooms,_,diag=rooms_from_cloud(np.concatenate([floor,furniture]),'test')
        self.assertTrue(rooms)
        self.assertIsNone(rooms[0]['ceiling_height']['value'])
        self.assertAlmostEqual(sum(r['floor_area']['value'] for r in rooms),12,delta=1)

    def test_empty_plane_evidence(self):
        rng=np.random.default_rng(1)
        points=rng.uniform([0,-.1,0],[.5,.1,.5],(2000,3))
        rooms,_,_=rooms_from_cloud(points,'test')
        self.assertEqual(rooms,[])

    def fixture(self):
        r={'id':'a','ceiling_height':measurement(2.5,.1),'floor_area':measurement(12,1,'m2'),
           'walls':[{'id':'w','length':measurement(4,.2)}], 'openings':[]}
        return {'tier':'photos','rooms':[r],'footprint_area':measurement(12,1,'m2'),
                'adjacency':[],'diagnostics':[],'timing_seconds':1}

    def test_missing_ground_truth_never_passes(self):
        report=evaluate(self.fixture(),{'independent_measurements':False,'measurements':{}})
        self.assertEqual(report['status'],'not_evaluated')

    def test_missed_opening_counts_as_failure(self):
        report=evaluate(self.fixture(),{'independent_measurements':True,'measurements':{'a/opening/door':.8}})
        self.assertEqual(report['gates']['opening_width']['status'],'fail')
        self.assertEqual(report['gates']['opening_width']['scored_openings'],1)

    def test_phantom_opening_counts_as_miss(self):
        f=self.fixture(); f['rooms'][0]['openings']=[{'id':'door','width':measurement(.8,.1)},{'id':'ghost','width':measurement(.8,.1)}]
        report=evaluate(f,{'independent_measurements':True,'measurements':{'a/opening/door':.8}})
        self.assertEqual(report['gates']['opening_width']['correct'],1)
        self.assertEqual(report['gates']['opening_width']['scored_openings'],2)
        self.assertEqual(report['gates']['opening_width']['status'],'fail')

    def test_repeatable_but_biased(self):
        f=self.fixture()
        report=evaluate(f,{'independent_measurements':True,'measurements':{'a/ceiling_height':2.6,'a/wall/w':4}},f)
        self.assertEqual(report['bias_diagnosis'],'repeatable_but_biased')
        self.assertEqual(report['gates']['repeatability']['status'],'pass')
        self.assertEqual(report['gates']['ceiling_height']['status'],'fail')

    def test_unknown_scale_has_no_interval(self):
        m=measurement()
        self.assertIsNone(m['value']); self.assertIsNone(m['lower']); self.assertIsNone(m['confidence_level'])

    def test_false_precision_never_calibrated(self):
        report=evaluate(self.fixture(),{'independent_measurements':True,'measurements':{'a/wall/w':4}})
        self.assertEqual(report['gates']['interval_calibration']['status'],'not_evaluated')
        self.assertNotEqual(report['status'],'pass')

if __name__=='__main__':unittest.main()
