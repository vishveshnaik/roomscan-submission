"""Use captured poses only to prepare room-folder labels, not for photo inference."""
import argparse,json
from pathlib import Path
import cv2,numpy as np
from scipy import ndimage
p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('cache');p.add_argument('structure');p.add_argument('--out',required=True);a=p.parse_args()
root=Path(a.root);cache=np.load(Path(a.cache)/'clouds.npz');sm=np.load(Path(a.structure)/'structure-map.npz');out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
regions=sm['regions'];rotation=sm['rotation'];origin=sm['origin'];grid=float(sm['grid'])
local=cache['cameras']@rotation.T;pix=np.rint((local[:,[0,2]]-origin)/grid).astype(int);labels=[]
distance,nearest=ndimage.distance_transform_edt(regions==0,return_indices=True)
for x,y in pix:
 label=0
 if 0<=x<regions.shape[1] and 0<=y<regions.shape[0]:
  label=int(regions[y,x])
  if not label and distance[y,x]<8:label=int(regions[nearest[0,y,x],nearest[1,y,x]])
 labels.append(label)
selected={};metadata=[]
for label in sorted(set(labels)-{0}):
 indices=np.flatnonzero(np.asarray(labels)==label)
 # Farthest-point sampling across camera positions discourages pure-rotation duplicates.
 chosen=[int(indices[0])]
 while len(chosen)<min(8,len(indices)):
  distances=np.min(np.linalg.norm(local[indices,None,:]-local[np.array(chosen)][None,:,:],axis=2),axis=1)
  idx=int(indices[np.argmax(distances)])
  if distances.max()<.15:break
  chosen.append(idx)
 if len(chosen)<2 and len(indices)>1:chosen=[int(indices[0]),int(indices[-1])]
 for idx in chosen:selected[int(cache['frames'][idx])]=label
cap=cv2.VideoCapture(str(root/'rgb.mp4'))
for index in range(int(cap.get(cv2.CAP_PROP_FRAME_COUNT))):
 if not cap.grab():break
 if index not in selected:continue
 ok,image=cap.retrieve()
 if not ok:continue
 label=selected[index];folder=out/f'room-{label}';folder.mkdir(exist_ok=True)
 # Stray Scanner raw raster is sideways in these supplied recordings.
 image=cv2.rotate(image,cv2.ROTATE_90_CLOCKWISE);image=cv2.resize(image,(720,960))
 file=folder/f'{index:06d}.jpg';cv2.imwrite(str(file),image);metadata.append({'image':str(file.relative_to(out)),'source_frame':index,'folder_label':label})
cap.release();(out/'preparation.json').write_text(json.dumps({'status':'derived_smoke_inputs_not_independent_benchmark','used_lidar_poses_for_folder_labels_only':True,'photo_inference_uses_no_depth_or_poses':True,'images':metadata},indent=2)+'\n');print(len(metadata),'photos',len(set(selected.values())),'folders')
