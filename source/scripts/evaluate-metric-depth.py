"""Paired RGB/LiDAR reference comparison; sensor depth is never a model input."""
import argparse,json
from pathlib import Path
import cv2,numpy as np
from PIL import Image
from roomscan.ingest import read_poses
from roomscan.metric_depth import MetricDepthClient
p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('--out',required=True);p.add_argument('--count',type=int,default=8);a=p.parse_args()
root=Path(a.source);out=Path(a.out);out.mkdir(parents=True,exist_ok=True);rows=read_poses(root)
indices=np.linspace(5,len(rows)-6,a.count).astype(int);wanted=set(indices);cap=cv2.VideoCapture(str(root/'rgb.mp4'));requests=[]
for index in range(len(rows)):
 if not cap.grab():break
 if index not in wanted:continue
 ok,image=cap.retrieve()
 if not ok:continue
 image=cv2.resize(cv2.rotate(image,cv2.ROTATE_90_CLOCKWISE),(720,960));file=out/f'{index:06d}.jpg';cv2.imwrite(str(file),image)
 requests.append({'file':str(file.resolve()),'output':str((out/f'{index:06d}.npy').resolve()),'focal_px':None})
cap.release();MetricDepthClient().ensure_batch(requests,out);scores=[]
for req in requests:
 index=int(Path(req['file']).stem);frame=int(rows[index]['frame']);name=f'{frame:06d}.png'
 ref=np.asarray(Image.open(root/'depth'/name)).astype(float)/1000;conf=np.asarray(Image.open(root/'confidence'/name))
 ref=cv2.rotate(ref,cv2.ROTATE_90_CLOCKWISE);conf=cv2.rotate(conf,cv2.ROTATE_90_CLOCKWISE)
 pred=cv2.resize(np.load(req['output']),ref.shape[::-1]);keep=(conf==2)&(ref>.3)&(ref<6)&np.isfinite(pred)
 residual=np.abs(pred[keep]-ref[keep]);relative=residual/ref[keep]
 scores.append({'frame':frame,'valid_pixels':int(keep.sum()),'median_abs_error_m':float(np.median(residual)),'median_abs_relative_error':float(np.median(relative)),'p90_abs_error_m':float(np.quantile(residual,.9)),'within_8_percent':float((relative<=.08).mean()),'within_3_percent':float((relative<=.03).mean())})
r={'reference':'paired LiDAR sensor estimates, not tape/laser truth','independent_capture':False,'lidar_input_to_model':False,'model':'Apple Depth Pro','orientation':'90 degrees clockwise','frames':scores,'median_frame_abs_relative_error':float(np.median([s['median_abs_relative_error'] for s in scores])),'accuracy_gate_status':'not_a_wall_or_footprint_benchmark'}
(out/'evaluation.json').write_text(json.dumps(r,indent=2)+'\n');print(r['median_frame_abs_relative_error'])
