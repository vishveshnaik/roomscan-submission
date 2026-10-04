import argparse,json,time
from pathlib import Path
import numpy as np
from roomscan.structure import extract_structure
p=argparse.ArgumentParser();p.add_argument('cache');p.add_argument('--out',required=True);a=p.parse_args()
cache=Path(a.cache);out=Path(a.out);data=np.load(cache/'clouds.npz');points=data['points'];offsets=data['offsets'];clouds=[points[start:end] for start,end in zip(offsets[:-1],offsets[1:])];meta=json.loads((cache/'metadata.json').read_text())
start=time.perf_counter();r=extract_structure(points,clouds,data['cameras'],meta['input']['source'],out);r['timing_seconds']=time.perf_counter()-start
(out/'structure.json').write_text(json.dumps(r,indent=2)+'\n');print(r['diagnostics']);print([(room['name'],room['floor_area']['value'],room['ceiling_height']['value']) for room in r['rooms']])
