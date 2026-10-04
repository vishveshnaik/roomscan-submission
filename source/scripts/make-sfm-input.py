"""Extract overlapping RGB images only; evaluation IDs are kept separately."""
import argparse,json
from pathlib import Path
import cv2,numpy as np
p=argparse.ArgumentParser();p.add_argument('video');p.add_argument('--out',required=True);p.add_argument('--count',type=int,default=80);a=p.parse_args()
out=Path(a.out);out.mkdir(parents=True,exist_ok=True);cap=cv2.VideoCapture(a.video);frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));wanted=set(np.linspace(0,frames-1,a.count).astype(int));meta=[]
# Sequential decoding avoids approximate seek/frame synchronization errors.
for i in range(frames):
 ok=cap.grab()
 if not ok:break
 if i in wanted:
  ok,image=cap.retrieve()
  if ok:
   path=out/f'{i:06d}.jpg';cv2.imwrite(str(path),cv2.resize(image,(960,720)));meta.append({'image':path.name,'source_frame':i})
cap.release();(out/'frame-index.json').write_text(json.dumps(meta,indent=2)+'\n');print('frames',len(meta))
