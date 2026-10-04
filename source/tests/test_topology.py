import unittest
import numpy as np
from roomscan.topology import clip_ray_to_walls,trajectory_crossings,boundary_support
from roomscan.openings import wall_gap_candidates
from roomscan.structure import extract_structure,surface_lines,local_ceiling_plane,region_rings
from roomscan.compare import polygon_iou
from roomscan.pipeline import validate_topology

class TopologyTests(unittest.TestCase):
    def fixture(self,head=True,filled=False):
        z,y=np.meshgrid(np.arange(0,3.01,.025),np.arange(.25,1.61,.05))
        keep=(z<=1)|(z>=2)|filled
        p=np.c_[np.zeros(keep.sum()),y[keep],z[keep]]
        if head:
            z,y=np.meshgrid(np.arange(1,2.01,.025),np.arange(2.05,2.51,.05));p=np.r_[p,np.c_[np.zeros(z.size),y.ravel(),z.ravel()]]
        lines=[{'id':'left','axis':0,'position':0.,'start':0.,'end':1.},
               {'id':'right','axis':0,'position':0.,'start':2.,'end':3.}]
        regions=np.ones((100,60),int);regions[:,20:]=2
        return p,lines,regions
    def openings(self,head=True,filled=False,cameras=()):
        p,lines,regions=self.fixture(head,filled);d={}
        result=wall_gap_candidates(lines,p,np.asarray(cameras).reshape(-1,3),0.,np.eye(3),regions,[-1.,-1.],.05,{1:'a',2:'b'},'synthetic',d)
        return result,d
    def test_rays_stop_at_structural_barriers(self):
        wall=np.zeros((20,20),np.uint8);wall[:,10]=1
        end,clipped=clip_ray_to_walls([2,10],[18,10],wall)
        self.assertTrue(clipped);self.assertLess(end[0],10)
    def test_diagonal_ray_cannot_skip_single_pixel_wall(self):
        wall=np.zeros((20,20),np.uint8);wall[10,10]=1
        end,clipped=clip_ray_to_walls([2,2],[18,18],wall)
        self.assertTrue(clipped);self.assertLess(end[0],10)
    def test_unblocked_ray_is_unchanged(self):
        end,clipped=clip_ray_to_walls([2,2],[18,18],np.zeros((20,20),np.uint8))
        np.testing.assert_array_equal(end,[18,18]);self.assertFalse(clipped)
    def test_camera_jump_is_not_door_crossing(self):
        self.assertEqual(trajectory_crossings([[-2,1,1.5],[2,1,1.5]],0,0,1,2),[])
        self.assertEqual(len(trajectory_crossings([[-.4,1,1.5],[.4,1,1.5]],0,0,1,2)),1)
    def test_supported_jambs_and_spanning_head_produce_opening(self):
        gaps,d=self.openings();self.assertEqual(len(gaps),1)
        self.assertAlmostEqual(gaps[0]['width']['value'],1.,delta=.10)
        self.assertTrue(gaps[0]['evidence']['vertically_supported_jambs'])
        self.assertFalse(gaps[0]['jambs_verified'])
        self.assertEqual({gaps[0]['room_a'],gaps[0]['room_b']},{'a','b'})
    def test_traversed_gap_can_survive_missing_head_views(self):
        gaps,d=self.openings(head=False,cameras=[[-.4,1,1.5],[.4,1,1.5]])
        self.assertEqual(len(gaps),1);self.assertIsNone(gaps[0]['height']['value'])
    def test_blind_gap_without_head_or_crossing_is_rejected(self):
        gaps,d=self.openings(head=False);self.assertEqual(gaps,[])
        self.assertEqual(d['rejected_gaps'][0]['reason'],'no_traversal_or_supported_two_sided_head')
    def test_painted_rectangle_is_not_an_opening(self):
        gaps,d=self.openings(filled=True);self.assertEqual(gaps,[])
        self.assertEqual(d['rejected_gaps'][0]['reason'],'wall_surface_present_inside_gap')
    def test_lintel_without_jambs_is_rejected(self):
        p,lines,regions=self.fixture();p=p[p[:,1]>2]
        gaps=wall_gap_candidates(lines,p,np.empty((0,3)),0,np.eye(3),regions,[-1,-1],.05,{1:'a',2:'b'},'test')
        self.assertEqual(gaps,[])
    def test_overlapping_plane_support_not_double_counted(self):
        lines=[{'id':'a','axis':0,'position':0,'start':0,'end':2},
               {'id':'b','axis':0,'position':0,'start':1,'end':3}]
        evidence=boundary_support([0,0],[0,3],lines)
        self.assertEqual(evidence['supported_fraction'],1.)
        self.assertEqual(evidence['kind'],'supported_wall_boundary')
    def test_unsupported_raster_edge_is_not_observed_wall(self):
        evidence=boundary_support([2,0],[2,3],[{'id':'a','axis':0,'position':0,'start':0,'end':3}])
        self.assertEqual(evidence['kind'],'coverage_boundary')
    def test_short_furniture_face_is_not_structural_wall(self):
        z,y=np.meshgrid(np.arange(0,3,.04),np.arange(.25,1.1,.04));p=np.c_[np.zeros(z.size),y.ravel(),z.ravel()]
        n=np.tile([1.,0.,0.],(len(p),1))
        self.assertEqual(surface_lines(p,n,np.zeros(len(p)),0,None),[])

    def test_empty_structure_is_explicitly_unresolved(self):
        r=extract_structure(np.empty((0,3)),[],np.empty((0,3)),'empty')
        self.assertEqual(r['status'],'unresolved');self.assertEqual(r['rooms'],[])
    def test_small_shelf_does_not_establish_ceiling(self):
        x,z=np.meshgrid(np.arange(0,.25,.01),np.arange(0,.25,.01));p=np.c_[x.ravel(),np.full(x.size,2.1),z.ravel()]
        self.assertIsNone(local_ceiling_plane(p,0,12))
    def test_broad_upper_plane_establishes_height_candidate(self):
        x,z=np.meshgrid(np.arange(0,4,.05),np.arange(0,3,.05));p=np.c_[x.ravel(),np.full(x.size,2.5),z.ravel()]
        plane=local_ceiling_plane(p,0,12)
        self.assertAlmostEqual(plane['coefficients'][2],2.5,places=4)
        self.assertFalse(plane['surface_class_confirmed'])
    def test_complete_two_room_layout_preserves_real_door(self):
        x,z=np.meshgrid(np.arange(-3,3.01,.05),np.arange(0,4.01,.05));floor=np.c_[x.ravel(),np.zeros(x.size),z.ravel()]
        ceiling=floor.copy();ceiling[:,1]=2.5;parts=[floor,ceiling]
        z,y=np.meshgrid(np.arange(0,4.01,.05),np.arange(.05,2.51,.05))
        for xx in [-3,3]:parts.append(np.c_[np.full(z.size,xx),y.ravel(),z.ravel()])
        x,y=np.meshgrid(np.arange(-3,3.01,.05),np.arange(.05,2.51,.05))
        for zz in [0,4]:parts.append(np.c_[x.ravel(),y.ravel(),np.full(x.size,zz)])
        z,y=np.meshgrid(np.arange(0,4.01,.025),np.arange(.05,2.51,.05));keep=(z<1.5)|(z>2.5)|(y>2.1)
        parts.append(np.c_[np.zeros(keep.sum()),y[keep],z[keep]])
        p=np.concatenate(parts);cameras=np.c_[np.linspace(-1,1,5),np.full(5,1.2),np.full(5,2)]
        r=extract_structure(p,[p]*5,cameras,'synthetic')
        self.assertEqual(len(r['rooms']),2);self.assertEqual(len(r['openings']),1);self.assertEqual(len(r['adjacency']),1)
        self.assertAlmostEqual(r['openings'][0]['width']['value'],1.,delta=.1)
        for room in r['rooms']:self.assertAlmostEqual(room['ceiling_height']['value'],2.5,delta=.02)
        self.assertGreater(r['diagnostics']['wall_clipped_rays'],0)

    def test_enclosed_exclusion_is_preserved_in_polygon(self):
        mask=np.ones((40,40),np.uint8);mask[10:30,10:30]=0
        outer,holes=region_rings(mask,[0,0],.05)
        self.assertEqual(len(holes),1)
        iou=polygon_iou(outer,outer,a_holes=holes)
        self.assertLess(iou,.8)
    def test_adjacency_requires_existing_rooms(self):
        r={'rooms':[{'id':'a'}],'adjacency':[{'room_a':'a','room_b':'missing'}]}
        with self.assertRaisesRegex(ValueError,'unknown room'):validate_topology(r)
    def test_strict_adjacency_requires_opening_evidence(self):
        r={'rooms':[{'id':'a'},{'id':'b'}],'adjacency':[{'room_a':'a','room_b':'b'}],
           'diagnostics':[{'geometry_revision':2}]}
        with self.assertRaisesRegex(ValueError,'lacks opening evidence'):validate_topology(r)
    def test_self_adjacency_is_rejected(self):
        r={'rooms':[{'id':'a'}],'adjacency':[{'room_a':'a','room_b':'a'}]}
        with self.assertRaisesRegex(ValueError,'Self-adjacency'):validate_topology(r)
    def test_opening_and_adjacency_sides_must_agree(self):
        r={'rooms':[{'id':i} for i in ['a','b','c']],
           'opening_candidates':[{'id':'door','room_a':'a','room_b':'b'}],
           'adjacency':[{'room_a':'a','room_b':'c','opening_id':'door'}],
           'diagnostics':[{'geometry_revision':2}]}
        with self.assertRaisesRegex(ValueError,'contradicts'):validate_topology(r)

if __name__=='__main__':unittest.main()
