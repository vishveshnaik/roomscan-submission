import unittest,tempfile
from pathlib import Path
import numpy as np
import cv2
from roomscan.structure import horizontal_plane
from roomscan.compare import transform_xz,icp2d,polygon_iou
from roomscan.damage import anomaly_masks,project_region
from roomscan.geometry import measurement
from roomscan.pipeline import validate

class ExtendedTests(unittest.TestCase):
 def test_robust_local_plane_rejects_furniture(self):
  rng=np.random.default_rng(4);xz=rng.uniform(0,4,(2000,2));y=.02*xz[:,0]-.015*xz[:,1]+2.5+rng.normal(0,.005,2000)
  points=np.c_[xz[:,0],y,xz[:,1]];plane=horizontal_plane(points,2.5)
  np.testing.assert_allclose(plane['coefficients'],[.02,-.015,2.5],atol=.008)
 def test_absent_ceiling_stays_absent(self):
  rng=np.random.default_rng(4);p=rng.uniform([0,-1.5,0],[4,-1.4,3],(2000,3))
  self.assertIsNone(horizontal_plane(p,2.5))
 def test_rigid_alignment_does_not_fit_scale(self):
  rng=np.random.default_rng(6);source=rng.uniform([-2,-1],[2,1],(1000,2));target=transform_xz(source,.1,[.15,-.05])
  aligned,yaw,t=icp2d(source,target,.09,[.14,-.04])
  np.testing.assert_allclose(aligned,target,atol=.001);self.assertAlmostEqual(yaw,.1,places=3)
 def test_polygon_overlap_changes_with_placement(self):
  p=[[0,0],[2,0],[2,2],[0,2]]
  self.assertGreater(polygon_iou(p,p),.99);self.assertEqual(polygon_iou(p,transform_xz(p,0,[5,0])),0)
 def test_plain_surface_and_straight_fixture_are_not_damage(self):
  image=np.full((576,768,3),200,np.uint8);self.assertEqual(anomaly_masks(image),[])
  cv2.line(image,(50,200),(700,200),(40,40,40),3)
  self.assertEqual([r for r in anomaly_masks(image) if r['class']=='crack_candidate'],[])
 def test_depth_area_requires_confident_support(self):
  mask=np.ones((8,8),np.uint8);depth=np.ones((8,8));confidence=np.zeros((8,8),np.uint8)
  row={'qx':0,'qy':0,'qz':0,'qw':1,'x':0,'y':0,'z':0}
  self.assertIsNone(project_region(mask,depth,confidence,row,np.eye(3),(8,8,3)))
 def test_metric_area_on_frontal_plane(self):
  mask=np.ones((8,8),np.uint8);depth=np.ones((8,8));confidence=np.full((8,8),2,np.uint8)
  row={'qx':0,'qy':0,'qz':0,'qw':1,'x':0,'y':0,'z':0,'fx':100,'fy':100,'cx':4,'cy':4}
  region=project_region(mask,depth,confidence,row,np.eye(3),(8,8,3))
  self.assertAlmostEqual(region['area_m2'],64/10000,places=6)

if __name__=='__main__':unittest.main()
