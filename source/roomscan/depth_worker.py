"""Isolated learned-depth inference process: never import pycolmap here."""
import sys,json
from pathlib import Path
from .metric_depth import MetricDepth

def main():
    request=json.loads(Path(sys.argv[1]).read_text());model=MetricDepth(request['weights'])
    for i,req in enumerate(request['requests']):
        _,meta=model.infer(req['file'],req['output'],req.get('focal_px'))
        print(f"Depth {i+1}/{len(request['requests'])}: {Path(req['file']).name}, {meta['seconds']} s",flush=True)

if __name__=='__main__':main()
