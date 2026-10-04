"""Controlled software evidence gates; these are not a physical benchmark."""
import argparse,json
from pathlib import Path
import numpy as np
import roomscan.structure as structure
from roomscan.openings import wall_gap_candidates
p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();results=[]
lines=[{'id':'left','axis':0,'position':0.,'start':0.,'end':1.}, {'id':'right','axis':0,'position':0.,'start':2.,'end':3.}]
regions=np.ones((100,60),int);regions[:,20:]=2
for name,head,filled,cameras in [('unsupported_gap',False,False,[]),('pose_jump',False,False,[[-2,1,1.5],[2,1,1.5]]),('painted_gap',True,True,[])]:
 z,y=np.meshgrid(np.arange(0,3.01,.025),np.arange(.25,1.61,.05));keep=(z<=1)|(z>=2)|filled;cloud=np.c_[np.zeros(keep.sum()),y[keep],z[keep]]
 if head:
  z,y=np.meshgrid(np.arange(1,2.01,.025),np.arange(2.05,2.51,.05));cloud=np.r_[cloud,np.c_[np.zeros(z.size),y.ravel(),z.ravel()]]
 gaps=wall_gap_candidates(lines,cloud,np.asarray(cameras).reshape(-1,3),0,np.eye(3),regions,[-1,-1],.05,{1:'a',2:'b'},'fixture')
 results.append({'case':name,'expected_accepted_candidates':0,'actual_accepted_candidates':len(gaps),'pass':len(gaps)==0})
z,y=np.meshgrid(np.arange(0,3,.04),np.arange(.25,1.1,.04));cloud=np.c_[np.zeros(z.size),y.ravel(),z.ravel()];normals=np.tile([1.,0.,0.],(len(cloud),1))
walls=structure.surface_lines(cloud,normals,np.zeros(len(cloud)),0,None);results.append({'case':'short_furniture_face','expected_wall_candidates':0,'actual_wall_candidates':len(walls),'pass':len(walls)==0})
x,z=np.meshgrid(np.arange(-3,3.01,.05),np.arange(0,4.01,.05));floor=np.c_[x.ravel(),np.zeros(x.size),z.ravel()];ceiling=floor.copy();ceiling[:,1]=2.5;parts=[floor,ceiling]
z,y=np.meshgrid(np.arange(0,4.01,.05),np.arange(.05,2.51,.05))
for xx in [-3,3]:parts.append(np.c_[np.full(z.size,xx),y.ravel(),z.ravel()])
x,y=np.meshgrid(np.arange(-3,3.01,.05),np.arange(.05,2.51,.05))
for zz in [0,4]:parts.append(np.c_[x.ravel(),y.ravel(),np.full(x.size,zz)])
z,y=np.meshgrid(np.arange(0,4.01,.025),np.arange(.05,2.51,.05));keep=(z<1.5)|(z>2.5)|(y>2.1);parts.append(np.c_[np.zeros(keep.sum()),y[keep],z[keep]])
cloud=np.concatenate(parts);cameras=np.c_[np.linspace(-1,1,5),np.full(5,1.2),np.full(5,2)];r=structure.extract_structure(cloud,[cloud]*5,cameras,'fixture')
results.append({'case':'two_rooms_one_door','expected_rooms':2,'actual_rooms':len(r['rooms']),'expected_openings':1,'actual_openings':len(r['openings']),'pass':len(r['rooms'])==2 and len(r['openings'])==1})
report={'kind':'controlled_software_regression','physical_gate_status':'not_evaluated','implementation':str(Path(structure.__file__).resolve()),'cases':results,'passed':sum(c['pass'] for c in results),'total':len(results)}
Path(a.out).parent.mkdir(parents=True,exist_ok=True);Path(a.out).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
