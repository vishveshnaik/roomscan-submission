"""Software smoke inputs, explicitly not independent benchmark captures."""
import argparse
from pathlib import Path
from roomscan.ingest import extract_zip, scan_roots
from roomscan.vision import extract_video
import tempfile

p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--out',required=True);args=p.parse_args()
source=Path(args.input).resolve();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as td:
    raw=extract_zip(source,td) if source.suffix=='.zip' else source
    roots=scan_roots(raw)
    if not roots:raise ValueError('No Stray Scanner scan found')
    for root in roots:extract_video(root/'rgb.mp4',out/root.name,count=8)
print('Created derived photos for smoke tests. These do not satisfy independent benchmark captures.')
