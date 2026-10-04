"""Run image-only experiments on derived inputs; these are not independent tiers."""
from pathlib import Path
import argparse,json
from roomscan.vision import extract_video
from roomscan.pipeline import run
p=argparse.ArgumentParser();p.add_argument('--count',type=int,default=320);a=p.parse_args()
for name,root in [('floor-only','data/floor-only/1a8384c3f6'),('with-ceiling','data/with-ceiling/c7d28f72c6')]:
 out=Path('output')/('metric-video-'+name)
 r=run(Path(root)/'rgb.mp4',out,tier='video',metric=True,rotate_cw=True,keyframes=a.count,depth_views=6)
 print(name,r['status'],len(r['rooms']),flush=True)
