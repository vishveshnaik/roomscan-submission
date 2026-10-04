import argparse,json
from pathlib import Path
import numpy as np
from roomscan.ingest import load_scan
from roomscan.drift import correct_clouds
p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('--out',required=True);p.add_argument('--every',type=int,default=20);a=p.parse_args()
out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
clouds,rows,meta=load_scan(a.source,every=a.every);fixed,log=correct_clouds(clouds)
cameras=[]
for original,registered,row in zip(clouds,fixed,rows):
 camera=np.array([float(row[k]) for k in ['x','y','z']])
 ac,bc=original.mean(0),registered.mean(0);u,_,vt=np.linalg.svd((original-ac).T@(registered-bc));r=vt.T@u.T
 camera=camera@r.T+(bc-ac@r.T);cameras.append(camera)
np.savez_compressed(out/'clouds.npz',points=np.concatenate(fixed),offsets=np.cumsum([0]+[len(c) for c in fixed]),cameras=cameras,frames=[int(r['frame']) for r in rows])
(out/'metadata.json').write_text(json.dumps({'input':meta,'drift':log},indent=2)+'\n')
print(out)
